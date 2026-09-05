"""Environment-driven configuration -- no secrets hardcoded.

DB_PASSWORD can come directly from the environment (local/dev) or from
SSM Parameter Store (set DB_PASSWORD_SSM_PARAM instead) -- the EC2
instance role only needs ssm:GetParameter for the latter, matching the
least-privilege IAM policy in infrastructure/iam/.
"""
import os

import boto3

AWS_REGION = os.environ.get("AWS_REGION", "ap-southeast-1")

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-do-not-use-in-prod")

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = os.environ.get("DB_PORT", "3306")
DB_NAME = os.environ.get("DB_NAME", "smb_migration_demo")
DB_USER = os.environ.get("DB_USER", "app_user")

SESSION_TABLE = os.environ.get("SESSION_DYNAMODB_TABLE", "smb-migration-demo-sessions")
UPLOAD_BUCKET = os.environ.get("S3_UPLOAD_BUCKET", "smb-migration-demo-uploads")


def _resolve_db_password():
    ssm_param = os.environ.get("DB_PASSWORD_SSM_PARAM")
    if ssm_param:
        ssm = boto3.client("ssm", region_name=AWS_REGION)
        return ssm.get_parameter(Name=ssm_param, WithDecryption=True)["Parameter"]["Value"]
    return os.environ.get("DB_PASSWORD", "")


def sqlalchemy_database_uri():
    password = _resolve_db_password()
    return f"mysql+pymysql://{DB_USER}:{password}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
