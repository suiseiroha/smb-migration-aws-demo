import os
import uuid
from datetime import date

from flask import (
    Flask,
    abort,
    flash,
    redirect,
    render_template,
    url_for,
)
from flask_login import (
    LoginManager,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from werkzeug.utils import secure_filename

import config
import storage_s3
from forms import CustomerForm, InvoiceForm, LoginForm
from models import Attachment, Customer, Invoice, User, db
from session_dynamodb import DynamoDBSessionInterface

app = Flask(__name__)

app.config["SECRET_KEY"] = config.SECRET_KEY

# Stateless: sessions in DynamoDB, uploads in S3, database in RDS (MySQL).
# Nothing about this app's own state is tied to the instance it runs on --
# the point of the whole rebuild. Compare to legacy-app/, which keeps
# every one of these on local disk.
app.config["SQLALCHEMY_DATABASE_URI"] = config.sqlalchemy_database_uri()
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024  # 5 MB

db.init_app(app)
app.session_interface = DynamoDBSessionInterface(
    table_name=config.SESSION_TABLE, region_name=config.AWS_REGION
)

login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            return redirect(url_for("dashboard"))
        flash("Invalid username or password", "error")
    return render_template("login.html", form=form)


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def dashboard():
    customer_count = Customer.query.count()
    invoice_count = Invoice.query.count()
    unpaid_total = db.session.query(db.func.coalesce(db.func.sum(Invoice.amount), 0)).filter(
        Invoice.status != "paid"
    ).scalar()
    recent_invoices = Invoice.query.order_by(Invoice.created_at.desc()).limit(5).all()
    return render_template(
        "dashboard.html",
        customer_count=customer_count,
        invoice_count=invoice_count,
        unpaid_total=unpaid_total,
        recent_invoices=recent_invoices,
    )


# --- Customers -------------------------------------------------------------

@app.route("/customers")
@login_required
def customer_list():
    customers = Customer.query.order_by(Customer.name).all()
    return render_template("customers/list.html", customers=customers)


@app.route("/customers/new", methods=["GET", "POST"])
@login_required
def customer_new():
    form = CustomerForm()
    if form.validate_on_submit():
        customer = Customer(
            name=form.name.data,
            email=form.email.data,
            phone=form.phone.data,
            address=form.address.data,
        )
        db.session.add(customer)
        db.session.commit()
        flash("Customer created", "success")
        return redirect(url_for("customer_list"))
    return render_template("customers/form.html", form=form, title="New customer")


@app.route("/customers/<int:customer_id>/edit", methods=["GET", "POST"])
@login_required
def customer_edit(customer_id):
    customer = db.session.get(Customer, customer_id) or abort(404)
    form = CustomerForm(obj=customer)
    if form.validate_on_submit():
        form.populate_obj(customer)
        db.session.commit()
        flash("Customer updated", "success")
        return redirect(url_for("customer_list"))
    return render_template("customers/form.html", form=form, title="Edit customer")


@app.route("/customers/<int:customer_id>/delete", methods=["POST"])
@login_required
def customer_delete(customer_id):
    customer = db.session.get(Customer, customer_id) or abort(404)
    db.session.delete(customer)
    db.session.commit()
    flash("Customer deleted", "success")
    return redirect(url_for("customer_list"))


# --- Invoices ----------------------------------------------------------------

@app.route("/invoices")
@login_required
def invoice_list():
    invoices = Invoice.query.order_by(Invoice.created_at.desc()).all()
    return render_template("invoices/list.html", invoices=invoices)


@app.route("/invoices/new", methods=["GET", "POST"])
@login_required
def invoice_new():
    form = InvoiceForm()
    form.customer_id.choices = [(c.id, c.name) for c in Customer.query.order_by(Customer.name)]
    if form.validate_on_submit():
        invoice = Invoice(
            invoice_number=form.invoice_number.data,
            customer_id=form.customer_id.data,
            amount=form.amount.data,
            status=form.status.data,
            issue_date=form.issue_date.data or date.today(),
            due_date=form.due_date.data,
            notes=form.notes.data,
        )
        db.session.add(invoice)
        db.session.commit()
        _save_attachment(form, invoice)
        flash("Invoice created", "success")
        return redirect(url_for("invoice_detail", invoice_id=invoice.id))
    return render_template("invoices/form.html", form=form, title="New invoice")


@app.route("/invoices/<int:invoice_id>")
@login_required
def invoice_detail(invoice_id):
    invoice = db.session.get(Invoice, invoice_id) or abort(404)
    return render_template("invoices/detail.html", invoice=invoice)


@app.route("/invoices/<int:invoice_id>/edit", methods=["GET", "POST"])
@login_required
def invoice_edit(invoice_id):
    invoice = db.session.get(Invoice, invoice_id) or abort(404)
    form = InvoiceForm(obj=invoice)
    form.customer_id.choices = [(c.id, c.name) for c in Customer.query.order_by(Customer.name)]
    if form.validate_on_submit():
        form.populate_obj(invoice)
        db.session.commit()
        _save_attachment(form, invoice)
        flash("Invoice updated", "success")
        return redirect(url_for("invoice_detail", invoice_id=invoice.id))
    return render_template("invoices/form.html", form=form, title="Edit invoice")


@app.route("/invoices/<int:invoice_id>/delete", methods=["POST"])
@login_required
def invoice_delete(invoice_id):
    invoice = db.session.get(Invoice, invoice_id) or abort(404)
    db.session.delete(invoice)
    db.session.commit()
    flash("Invoice deleted", "success")
    return redirect(url_for("invoice_list"))


def _save_attachment(form, invoice):
    file = form.attachment.data
    if not file or not file.filename:
        return
    original_filename = secure_filename(file.filename)
    stored_filename = f"{uuid.uuid4().hex}_{original_filename}"
    storage_s3.upload_attachment(file, stored_filename)
    db.session.add(
        Attachment(
            invoice_id=invoice.id,
            stored_filename=stored_filename,
            original_filename=original_filename,
        )
    )
    db.session.commit()


@app.route("/uploads/<path:stored_filename>")
@login_required
def uploaded_file(stored_filename):
    attachment = Attachment.query.filter_by(stored_filename=stored_filename).first() or abort(404)
    url = storage_s3.presigned_download_url(stored_filename, attachment.original_filename)
    return redirect(url)


if __name__ == "__main__":
    debug = os.environ.get("FLASK_DEBUG", "1") == "1"
    app.run(host="0.0.0.0", port=5000, debug=debug)
