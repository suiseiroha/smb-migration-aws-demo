#!/bin/bash
# EC2 launch template user data (Amazon Linux 2023). Runs once on first
# boot and fully deploys modern-app: pulls the code from S3 (uploaded
# by Part 7 of either simulation guide), installs dependencies into a
# venv, and starts it as a systemd service.
#
# This replaced an earlier version that only installed Docker -- that
# path was never actually used (the real deployment ended up being a
# plain Python venv + systemd, not a container) and left every fresh
# ASG instance failing its ALB health check until someone deployed to
# it by hand. See PLAN.md milestone 6.
set -e

dnf install -y python3-pip

mkdir -p /home/ec2-user/app-deploy/modern-app
aws s3 cp s3://smb-migration-demo-uploads/deploy/modern-app.tar.gz /tmp/modern-app.tar.gz --region ap-southeast-1
tar -xzf /tmp/modern-app.tar.gz -C /home/ec2-user/app-deploy/modern-app
chown -R ec2-user:ec2-user /home/ec2-user/app-deploy

cd /home/ec2-user/app-deploy/modern-app
python3 -m venv .venv
./.venv/bin/pip install -q --upgrade pip
./.venv/bin/pip install -q -r requirements.txt

# Looked up by name, not hardcoded, so the same script works no matter
# when the secrets were created (see Part 5 of either simulation guide).
DB_SECRET_ARN=$(aws secretsmanager describe-secret --secret-id smb-migration-demo/db-password \
  --region ap-southeast-1 --query ARN --output text)
FLASK_SECRET_ARN=$(aws secretsmanager describe-secret --secret-id smb-migration-demo/flask-secret-key \
  --region ap-southeast-1 --query ARN --output text)

# Seed the database (creates schema + admin user, safe to re-run since
# seed.py only inserts if empty) before starting the app, so the first
# request never hits a missing-table error. "|| true" so a transient
# RDS connection issue here doesn't abort the rest of this script,
# since set -e is active; the app itself will keep retrying via
# Restart=on-failure below regardless of whether seeding succeeded.
export AWS_REGION=ap-southeast-1
export DB_HOST=smb-migration-demo-db.cj0mkcukwgwk.ap-southeast-1.rds.amazonaws.com
export DB_PORT=3306
export DB_NAME=smb_migration_demo
export DB_USER=app_user
export DB_PASSWORD_SECRET_ARN=$DB_SECRET_ARN
export SESSION_DYNAMODB_TABLE=smb-migration-demo-sessions
export S3_UPLOAD_BUCKET=smb-migration-demo-uploads
export SECRET_KEY_SECRET_ARN=$FLASK_SECRET_ARN
./.venv/bin/python seed.py || true

cat > /etc/systemd/system/modern-app.service << UNIT
[Unit]
Description=SMB modern invoice tracker (stateless)
After=network.target

[Service]
Type=simple
WorkingDirectory=/home/ec2-user/app-deploy/modern-app
Environment=AWS_REGION=ap-southeast-1
Environment=DB_HOST=smb-migration-demo-db.cj0mkcukwgwk.ap-southeast-1.rds.amazonaws.com
Environment=DB_PORT=3306
Environment=DB_NAME=smb_migration_demo
Environment=DB_USER=app_user
Environment=DB_PASSWORD_SECRET_ARN=$DB_SECRET_ARN
Environment=SESSION_DYNAMODB_TABLE=smb-migration-demo-sessions
Environment=S3_UPLOAD_BUCKET=smb-migration-demo-uploads
Environment=SECRET_KEY_SECRET_ARN=$FLASK_SECRET_ARN
Environment=FLASK_DEBUG=0
ExecStart=/home/ec2-user/app-deploy/modern-app/.venv/bin/python /home/ec2-user/app-deploy/modern-app/app.py
Restart=on-failure

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable --now modern-app
