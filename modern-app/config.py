"""Environment-driven configuration -- no secrets hardcoded.

Two ways secrets can be supplied, both env-driven, no plaintext value
ever in code or committed config:

- Secrets Manager (`DB_PASSWORD_SECRET_ARN`, `SECRET_KEY_SECRET_ARN`) --
  what both the CDK stack (infrastructure/cdk/, auto-generated) and the
  hand-built Phase 1 build (created by hand, see Part 5 of either
  simulation guide) use.
- SSM Parameter Store (`DB_PASSWORD_SSM_PARAM`, `SECRET_KEY_SSM_PARAM`)
  -- an earlier variant of the manual build used this before switching
  to Secrets Manager to match the CDK path. Kept here as a fallback,
  not used by anything currently in this repo.

Falls back to a plain `DB_PASSWORD`/`SECRET_KEY` env var for local/dev
if neither is set.
"""
import json
import os

import boto3

AWS_REGION = os.environ.get("AWS_REGION", "ap-southeast-1")

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = os.environ.get("DB_PORT", "3306")
DB_NAME = os.environ.get("DB_NAME", "smb_migration_demo")
DB_USER = os.environ.get("DB_USER", "app_user")

SESSION_TABLE = os.environ.get("SESSION_DYNAMODB_TABLE", "smb-migration-demo-sessions")
UPLOAD_BUCKET = os.environ.get("S3_UPLOAD_BUCKET", "smb-migration-demo-uploads")


def _secretsmanager_value(secret_arn):
    client = boto3.client("secretsmanager", region_name=AWS_REGION)
    return client.get_secret_value(SecretId=secret_arn)["SecretString"]


def _resolve_secret_key():
    secret_arn = os.environ.get("SECRET_KEY_SECRET_ARN")
    if secret_arn:
        return _secretsmanager_value(secret_arn)

    ssm_param = os.environ.get("SECRET_KEY_SSM_PARAM")
    if ssm_param:
        ssm = boto3.client("ssm", region_name=AWS_REGION)
        return ssm.get_parameter(Name=ssm_param, WithDecryption=True)["Parameter"]["Value"]

    return os.environ.get("SECRET_KEY", "dev-secret-do-not-use-in-prod")


def _resolve_db_password():
    secret_arn = os.environ.get("DB_PASSWORD_SECRET_ARN")
    if secret_arn:
        # RDS-generated secrets store a JSON blob, not a bare password.
        return json.loads(_secretsmanager_value(secret_arn))["password"]

    ssm_param = os.environ.get("DB_PASSWORD_SSM_PARAM")
    if ssm_param:
        ssm = boto3.client("ssm", region_name=AWS_REGION)
        return ssm.get_parameter(Name=ssm_param, WithDecryption=True)["Parameter"]["Value"]

    return os.environ.get("DB_PASSWORD", "")


SECRET_KEY = _resolve_secret_key()


def sqlalchemy_database_uri():
    password = _resolve_db_password()
    return f"mysql+pymysql://{DB_USER}:{password}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
