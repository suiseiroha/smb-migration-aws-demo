#!/bin/bash
# Deploys modern-app to a given EC2 instance via SSM Run Command (no SSH).
# Assumes modern-app.tar.gz is already current in
# s3://smb-migration-demo-uploads/deploy/ (re-run the package+upload
# step in Part 7 of either simulation guide first if the code changed).
#
# This is a stand-in for real deployment automation (baked AMI, or a
# proper user-data/CI pipeline) -- the ASG doesn't know how to deploy
# the app to a fresh instance on its own yet. See PLAN.md milestone
# 5/6 for why. (The CDK path in infrastructure/cdk/ doesn't have this
# gap -- its launch template's user data does this same deployment
# automatically.)
#
# Usage: ./deploy_modern_app_to_instance.sh <instance-id>
set -e

INSTANCE_ID="$1"
REGION="ap-southeast-1"

if [ -z "$INSTANCE_ID" ]; then
  echo "Usage: $0 <instance-id>"
  exit 1
fi

DB_HOST=$(aws rds describe-db-instances --db-instance-identifier smb-migration-demo-db \
  --region "$REGION" --query "DBInstances[0].Endpoint.Address" --output text)
DB_SECRET_ARN=$(aws secretsmanager describe-secret --secret-id smb-migration-demo/db-password \
  --region "$REGION" --query ARN --output text)
FLASK_SECRET_ARN=$(aws secretsmanager describe-secret --secret-id smb-migration-demo/flask-secret-key \
  --region "$REGION" --query ARN --output text)

run() {
  local cmd_id
  cmd_id=$(aws ssm send-command \
    --instance-ids "$INSTANCE_ID" \
    --document-name "AWS-RunShellScript" \
    --parameters "commands=$1" \
    --region "$REGION" \
    --query "Command.CommandId" --output text)
  sleep "$2"
  aws ssm get-command-invocation --command-id "$cmd_id" --instance-id "$INSTANCE_ID" --region "$REGION" \
    --query "{Status:Status,Output:StandardOutputContent}" --output json
}

echo "=== Deploying code + installing dependencies ==="
run '[
  "mkdir -p /home/ec2-user/app-deploy/modern-app",
  "aws s3 cp s3://smb-migration-demo-uploads/deploy/modern-app.tar.gz /tmp/modern-app.tar.gz --region ap-southeast-1",
  "tar -xzf /tmp/modern-app.tar.gz -C /home/ec2-user/app-deploy/modern-app",
  "cd /home/ec2-user/app-deploy/modern-app",
  "python3 -m venv .venv",
  "./.venv/bin/pip install -q --upgrade pip",
  "./.venv/bin/pip install -q -r requirements.txt",
  "echo DEPS_OK"
]' 25

echo "=== Writing systemd unit and starting the service ==="
run '[
  "rm -f /etc/systemd/system/modern-app.service",
  "echo \"[Unit]\" >> /etc/systemd/system/modern-app.service",
  "echo \"Description=SMB modern invoice tracker (stateless)\" >> /etc/systemd/system/modern-app.service",
  "echo \"After=network.target\" >> /etc/systemd/system/modern-app.service",
  "echo \"\" >> /etc/systemd/system/modern-app.service",
  "echo \"[Service]\" >> /etc/systemd/system/modern-app.service",
  "echo \"Type=simple\" >> /etc/systemd/system/modern-app.service",
  "echo \"WorkingDirectory=/home/ec2-user/app-deploy/modern-app\" >> /etc/systemd/system/modern-app.service",
  "echo \"Environment=AWS_REGION=ap-southeast-1\" >> /etc/systemd/system/modern-app.service",
  "echo \"Environment=DB_HOST='"$DB_HOST"'\" >> /etc/systemd/system/modern-app.service",
  "echo \"Environment=DB_PORT=3306\" >> /etc/systemd/system/modern-app.service",
  "echo \"Environment=DB_NAME=smb_migration_demo\" >> /etc/systemd/system/modern-app.service",
  "echo \"Environment=DB_USER=app_user\" >> /etc/systemd/system/modern-app.service",
  "echo \"Environment=DB_PASSWORD_SECRET_ARN='"$DB_SECRET_ARN"'\" >> /etc/systemd/system/modern-app.service",
  "echo \"Environment=SESSION_DYNAMODB_TABLE=smb-migration-demo-sessions\" >> /etc/systemd/system/modern-app.service",
  "echo \"Environment=S3_UPLOAD_BUCKET=smb-migration-demo-uploads\" >> /etc/systemd/system/modern-app.service",
  "echo \"Environment=SECRET_KEY_SECRET_ARN='"$FLASK_SECRET_ARN"'\" >> /etc/systemd/system/modern-app.service",
  "echo \"Environment=FLASK_DEBUG=0\" >> /etc/systemd/system/modern-app.service",
  "echo \"ExecStart=/home/ec2-user/app-deploy/modern-app/.venv/bin/python /home/ec2-user/app-deploy/modern-app/app.py\" >> /etc/systemd/system/modern-app.service",
  "echo \"Restart=on-failure\" >> /etc/systemd/system/modern-app.service",
  "echo \"\" >> /etc/systemd/system/modern-app.service",
  "echo \"[Install]\" >> /etc/systemd/system/modern-app.service",
  "echo \"WantedBy=multi-user.target\" >> /etc/systemd/system/modern-app.service",
  "systemctl daemon-reload",
  "systemctl enable modern-app > /dev/null 2>&1",
  "systemctl start modern-app",
  "sleep 3",
  "systemctl is-active modern-app",
  "curl -s -o /dev/null -w LOCALCURL:%{http_code} http://localhost:5000/login"
]' 10

echo "=== Done. Check target group health separately (takes a couple minutes to flip). ==="
