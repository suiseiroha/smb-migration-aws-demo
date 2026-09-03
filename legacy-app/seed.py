"""Creates the SQLite schema and loads realistic-looking sample data.

Run with the legacy-app venv active: python seed.py
Safe to re-run -- it only creates the admin user/sample rows if the
database is empty.
"""
from datetime import date, timedelta

from app import app
from models import Customer, Invoice, User, db

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "changeme123"

SAMPLE_CUSTOMERS = [
    dict(name="Riverside Cafe", email="billing@riversidecafe.example", phone="555-0101", address="12 River Rd"),
    dict(name="Grandview Hardware", email="ap@grandviewhw.example", phone="555-0142", address="88 Main St"),
    dict(name="Blue Fox Studio", email="hello@bluefoxstudio.example", phone="555-0177", address="4 Studio Ln"),
]

SAMPLE_INVOICES = [
    dict(invoice_number="INV-1001", customer_idx=0, amount=420.00, status="paid", days_ago=30),
    dict(invoice_number="INV-1002", customer_idx=0, amount=185.50, status="unpaid", days_ago=5),
    dict(invoice_number="INV-1003", customer_idx=1, amount=1290.00, status="overdue", days_ago=45),
    dict(invoice_number="INV-1004", customer_idx=2, amount=650.00, status="unpaid", days_ago=2),
]


def seed():
    with app.app_context():
        db.create_all()

        if User.query.filter_by(username=ADMIN_USERNAME).first() is None:
            admin = User(username=ADMIN_USERNAME)
            admin.set_password(ADMIN_PASSWORD)
            db.session.add(admin)
            print(f"Created admin user '{ADMIN_USERNAME}' / '{ADMIN_PASSWORD}' (change this)")

        if Customer.query.count() == 0:
            customers = [Customer(**data) for data in SAMPLE_CUSTOMERS]
            db.session.add_all(customers)
            db.session.flush()  # assign ids

            for inv in SAMPLE_INVOICES:
                db.session.add(
                    Invoice(
                        invoice_number=inv["invoice_number"],
                        customer_id=customers[inv["customer_idx"]].id,
                        amount=inv["amount"],
                        status=inv["status"],
                        issue_date=date.today() - timedelta(days=inv["days_ago"]),
                        due_date=date.today() - timedelta(days=inv["days_ago"] - 14),
                    )
                )
            print(f"Seeded {len(customers)} customers and {len(SAMPLE_INVOICES)} invoices")

        db.session.commit()


if __name__ == "__main__":
    seed()
