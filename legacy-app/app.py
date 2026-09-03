import os
import uuid
from datetime import date

from flask import (
    Flask,
    abort,
    flash,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)
from flask_login import (
    LoginManager,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from flask_session import Session
from werkzeug.utils import secure_filename

from forms import CustomerForm, InvoiceForm, LoginForm
from models import Attachment, Customer, Invoice, User, db

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

app = Flask(
    __name__,
    instance_relative_config=True,
    instance_path=os.path.join(BASE_DIR, "instance"),
)
os.makedirs(app.instance_path, exist_ok=True)

app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-do-not-use-in-prod")

# Deliberately stateful/local: SQLite on the local filesystem, filesystem
# sessions, and uploads saved directly to disk. This is the "legacy SMB box"
# side of the demo -- the modern-app/ rebuild replaces every one of these.
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(
    app.instance_path, "app.db"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_FILE_DIR"] = os.path.join(BASE_DIR, "flask_session")
app.config["SESSION_PERMANENT"] = False

app.config["UPLOAD_FOLDER"] = os.path.join(BASE_DIR, "uploads")
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024  # 5 MB
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
os.makedirs(app.config["SESSION_FILE_DIR"], exist_ok=True)

db.init_app(app)
Session(app)

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
    file.save(os.path.join(app.config["UPLOAD_FOLDER"], stored_filename))
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
    return send_from_directory(app.config["UPLOAD_FOLDER"], stored_filename)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
