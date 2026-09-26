"""One-time migration: legacy SQLite data -> RDS MySQL (+ S3 for uploads).

Reads directly from a local copy of legacy-app's SQLite file and
uploads directory, writes through modern-app's own models -- so the
target schema always matches what modern-app actually expects, and
row IDs are preserved (via SQLAlchemy `merge`) so foreign keys stay
correct.

Must run somewhere that can reach the RDS instance -- in practice,
inside the VPC (the app instance), since RDS isn't publicly
accessible. modern-app's env vars (DB_HOST, DB_USER,
DB_PASSWORD_SSM_PARAM, etc.) must already be set.

Usage:
    python export_sqlite_to_rds.py <sqlite_db_path> <uploads_dir>
"""
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "modern-app"))

import boto3  # noqa: E402
import config  # noqa: E402
from app import app  # noqa: E402
from models import Attachment, Customer, Invoice, User, db  # noqa: E402


def migrate(sqlite_path, uploads_dir):
    uploads_dir = Path(uploads_dir)
    src = sqlite3.connect(sqlite_path, detect_types=sqlite3.PARSE_DECLTYPES)
    src.row_factory = sqlite3.Row
    s3 = boto3.client("s3", region_name=config.AWS_REGION)

    with app.app_context():
        db.create_all()
        print("Schema created/confirmed in RDS.")

        customers = src.execute("SELECT * FROM customer").fetchall()
        for c in customers:
            db.session.merge(Customer(
                id=c["id"], name=c["name"], email=c["email"],
                phone=c["phone"], address=c["address"], created_at=c["created_at"],
            ))
        db.session.commit()
        print(f"Migrated {len(customers)} customers.")

        invoices = src.execute("SELECT * FROM invoice").fetchall()
        for i in invoices:
            db.session.merge(Invoice(
                id=i["id"], invoice_number=i["invoice_number"],
                customer_id=i["customer_id"], amount=i["amount"],
                status=i["status"], issue_date=i["issue_date"],
                due_date=i["due_date"], notes=i["notes"],
                created_at=i["created_at"],
            ))
        db.session.commit()
        print(f"Migrated {len(invoices)} invoices.")

        users = src.execute("SELECT * FROM user").fetchall()
        for u in users:
            db.session.merge(User(
                id=u["id"], username=u["username"], password_hash=u["password_hash"],
            ))
        db.session.commit()
        print(f"Migrated {len(users)} users.")

        attachments = src.execute("SELECT * FROM attachment").fetchall()
        migrated_files = 0
        for a in attachments:
            local_file = uploads_dir / a["stored_filename"]
            if local_file.exists():
                with open(local_file, "rb") as f:
                    s3.upload_fileobj(f, config.UPLOAD_BUCKET, a["stored_filename"])
                migrated_files += 1
            db.session.merge(Attachment(
                id=a["id"], invoice_id=a["invoice_id"],
                stored_filename=a["stored_filename"],
                original_filename=a["original_filename"],
                uploaded_at=a["uploaded_at"],
            ))
        db.session.commit()
        print(f"Migrated {len(attachments)} attachment records, {migrated_files} files uploaded to S3.")

        print("\nValidation (RDS row counts):")
        print(" customers:", Customer.query.count())
        print(" invoices:", Invoice.query.count())
        print(" users:", User.query.count())
        print(" attachments:", Attachment.query.count())


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python export_sqlite_to_rds.py <sqlite_db_path> <uploads_dir>")
        sys.exit(1)
    migrate(sys.argv[1], sys.argv[2])
