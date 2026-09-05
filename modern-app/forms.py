from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField
from wtforms import DateField, DecimalField, SelectField, StringField, TextAreaField
from wtforms.validators import DataRequired, Email, Length, Optional


class LoginForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired()])
    password = StringField("Password", validators=[DataRequired()])


class CustomerForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired(), Length(max=120)])
    email = StringField("Email", validators=[DataRequired(), Email()])
    phone = StringField("Phone", validators=[Optional(), Length(max=40)])
    address = StringField("Address", validators=[Optional(), Length(max=255)])


class InvoiceForm(FlaskForm):
    invoice_number = StringField("Invoice #", validators=[DataRequired(), Length(max=40)])
    customer_id = SelectField("Customer", coerce=int, validators=[DataRequired()])
    amount = DecimalField("Amount", places=2, validators=[DataRequired()])
    status = SelectField(
        "Status",
        choices=[("unpaid", "Unpaid"), ("paid", "Paid"), ("overdue", "Overdue")],
        validators=[DataRequired()],
    )
    issue_date = DateField("Issue date", validators=[Optional()])
    due_date = DateField("Due date", validators=[Optional()])
    notes = TextAreaField("Notes", validators=[Optional()])
    attachment = FileField(
        "Attach receipt/file",
        validators=[
            Optional(),
            FileAllowed(["pdf", "png", "jpg", "jpeg"], "PDF or image files only"),
        ],
    )
