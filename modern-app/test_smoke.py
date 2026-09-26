"""One-off smoke test for modern-app.

Exercises the DynamoDB session interface, S3 uploads, and MySQL
persistence without touching real AWS or costing anything: DynamoDB
and S3 are mocked in-memory (moto), MySQL is a throwaway local Docker
container. Full test against real RDS/DynamoDB/S3 happens once
milestone 4's infrastructure exists (see milestone 5).

Requires Docker running, and requirements-dev.txt installed. Run:
    python test_smoke.py
"""
import io
import os
import subprocess
import time

import pymysql
from moto import mock_aws

MYSQL_CONTAINER = "modern-app-mysql-smoketest"
MYSQL_PORT = 3307
MYSQL_ROOT_PASSWORD = "smoketest-pw"
DB_NAME = "smb_migration_demo"


def start_mysql():
    subprocess.run(["docker", "rm", "-f", MYSQL_CONTAINER], capture_output=True)
    subprocess.run(
        [
            "docker", "run", "-d", "--name", MYSQL_CONTAINER,
            "-e", f"MYSQL_ROOT_PASSWORD={MYSQL_ROOT_PASSWORD}",
            "-e", f"MYSQL_DATABASE={DB_NAME}",
            "-p", f"{MYSQL_PORT}:3306",
            "mysql:8",
        ],
        check=True,
    )
    print("Waiting for MySQL to accept connections...")
    for _ in range(60):
        try:
            conn = pymysql.connect(
                host="127.0.0.1", port=MYSQL_PORT, user="root",
                password=MYSQL_ROOT_PASSWORD, database=DB_NAME,
            )
            conn.close()
            print("MySQL ready.")
            return
        except pymysql.err.OperationalError:
            time.sleep(2)
    raise RuntimeError("MySQL never became ready")


def stop_mysql():
    subprocess.run(["docker", "rm", "-f", MYSQL_CONTAINER], capture_output=True)


def main():
    os.environ["AWS_REGION"] = "us-east-1"
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["SECRET_KEY"] = "smoke-test-secret"
    os.environ["DB_HOST"] = "127.0.0.1"
    os.environ["DB_PORT"] = str(MYSQL_PORT)
    os.environ["DB_NAME"] = DB_NAME
    os.environ["DB_USER"] = "root"
    os.environ["DB_PASSWORD"] = MYSQL_ROOT_PASSWORD
    os.environ["SESSION_DYNAMODB_TABLE"] = "smb-migration-demo-sessions-test"
    os.environ["S3_UPLOAD_BUCKET"] = "smb-migration-demo-uploads-test"

    start_mysql()

    mock = mock_aws()
    mock.start()
    try:
        import boto3

        boto3.client("dynamodb", region_name="us-east-1").create_table(
            TableName=os.environ["SESSION_DYNAMODB_TABLE"],
            KeySchema=[{"AttributeName": "session_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "session_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        boto3.client("s3", region_name="us-east-1").create_bucket(
            Bucket=os.environ["S3_UPLOAD_BUCKET"]
        )

        import seed
        from app import app
        from models import Customer, Invoice

        seed.seed()

        app.config["WTF_CSRF_ENABLED"] = False  # smoke test only, not testing CSRF here
        client = app.test_client()

        r = client.get("/login")
        assert r.status_code == 200
        r = client.post(
            "/login", data={"username": "admin", "password": "changeme123"},
            follow_redirects=True,
        )
        assert b"Dashboard" in r.data, "login failed"
        print("PASS: login")

        r = client.get("/customers")
        assert r.status_code == 200
        print("PASS: session persists across requests (DynamoDB-backed)")

        r = client.post(
            "/customers/new",
            data={"name": "Smoke Test Co", "email": "smoke@test.example", "phone": "", "address": ""},
            follow_redirects=True,
        )
        assert b"Customer created" in r.data
        print("PASS: create customer")

        with app.app_context():
            customer = Customer.query.filter_by(name="Smoke Test Co").first()
            assert customer is not None
            customer_id = customer.id

        data = {
            "invoice_number": "INV-SMOKE-001",
            "customer_id": str(customer_id),
            "amount": "42.00",
            "status": "unpaid",
            "attachment": (io.BytesIO(b"fake receipt bytes"), "receipt.png"),
        }
        r = client.post(
            "/invoices/new", data=data, content_type="multipart/form-data",
            follow_redirects=True,
        )
        assert b"Invoice created" in r.data
        print("PASS: create invoice with S3 attachment")

        with app.app_context():
            invoice = Invoice.query.filter_by(invoice_number="INV-SMOKE-001").first()
            assert invoice is not None
            assert len(invoice.attachments) == 1
            stored_filename = invoice.attachments[0].stored_filename

        s3 = boto3.client("s3", region_name="us-east-1")
        head = s3.head_object(Bucket=os.environ["S3_UPLOAD_BUCKET"], Key=stored_filename)
        assert head["ContentLength"] == len(b"fake receipt bytes")
        print("PASS: attachment bytes present in S3")

        r = client.get(f"/uploads/{stored_filename}")
        assert r.status_code == 302
        assert os.environ["S3_UPLOAD_BUCKET"] in r.headers["Location"]
        print("PASS: download route issues a presigned S3 redirect")

        client.get("/logout")
        r = client.get("/customers", follow_redirects=False)
        assert r.status_code == 302 and "/login" in r.headers["Location"]
        print("PASS: logout revokes access")

        print("\nAll smoke tests passed.")
    finally:
        mock.stop()
        stop_mysql()


if __name__ == "__main__":
    main()
