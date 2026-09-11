# Try it yourself, start to finish

Everything in this repo, run in the order it's meant to be experienced:
the legacy app first, then why it has to move, then the modernized
architecture standing up for real on AWS.

Don't have Docker installed yet? See
[`../legacy-app/README.md`](../legacy-app/README.md) for install
commands. Don't have git or the AWS CLI installed yet?
[`simulation-guide-windows.md`](simulation-guide-windows.md)'s Part 1
and Part 3, or
[`simulation-guide-rocky-linux-10.md`](simulation-guide-rocky-linux-10.md)'s
Part 1 and Part 3, have install commands for those. Node.js is the one
thing unique to this path, needed for `npm install -g aws-cdk` below,
neither guide covers it since neither uses CDK.

## 1. Get the code

Clone this repository and open a terminal at its root.

## 2. Run the legacy app (the "before" state)

Requires [Docker Desktop](https://www.docker.com/products/docker-desktop/),
nothing else.

```bash
cd legacy-app
docker compose up
```

Open **http://localhost:5000**, log in with `admin` / `changeme123`.
Create a customer, create an invoice, attach a file to it.

Everything you just created lives in `legacy-app/instance/app.db`,
`legacy-app/uploads/`, and `legacy-app/flask_session/`: plain files on
disk, tied to this one process. That's deliberate. See
[`legacy-app/README.md`](../legacy-app/README.md) for what makes this
setup unmanaged, and [`legacy-assessment.md`](legacy-assessment.md) for
the module-by-module breakdown of why it can't scale as-is.

Press `Ctrl+C` when you're done looking around. No need to leave it
running for the next steps.

## 3. Understand why a straight lift-and-shift wouldn't fix it

[`rehost-vs-replatform.md`](rehost-vs-replatform.md) walks through why
rehosting (moving the same box to EC2 unchanged) still leaves you with
a single point of failure and no real horizontal scaling, and why
replatforming the state out of the app is what actually solves it.

## 4. See how the app itself changed

[`app-rebuild.md`](app-rebuild.md) covers the refactor in detail, with
diagrams. Short version: same business logic, three things moved off
the instance: sessions to DynamoDB, uploads to S3, database to RDS.
See [`../modern-app/README.md`](../modern-app/README.md) for the code.

Want to see it run without touching AWS at all? `modern-app/test_smoke.py`
exercises the same code against a mocked DynamoDB/S3 and a throwaway
local MySQL container.

## 5. Stand up the modernized architecture on AWS

Everything here is CLI and CDK, no AWS Console step:

```bash
# prerequisites: AWS CLI v2 configured, Node.js, Python 3.10+
npm install -g aws-cdk
cd infrastructure/cdk
python -m venv .venv
# Windows: .venv\Scripts\pip install -r requirements.txt
# macOS/Linux: .venv/bin/pip install -r requirements.txt

cdk bootstrap aws://$(aws sts get-caller-identity --query Account --output text)/ap-southeast-1  # one-time per account/region
cdk deploy --all --require-approval never
```

One command builds all four stacks (network, data, compute,
monitoring), 10-15 minutes, mostly RDS. Don't hit the ALB URL right
away, though: the instance still needs a couple more minutes to
finish installing dependencies and start the app after `cdk deploy`
returns, and doing so too early returns a Bad Gateway. Look up the ALB
URL and wait for the target to actually go healthy first, since none
of it is hardcoded:

```bash
TG_ARN=$(aws elbv2 describe-target-groups --names smb-migration-demo-tg \
  --region ap-southeast-1 --query "TargetGroups[0].TargetGroupArn" --output text)
aws elbv2 wait target-in-service --target-group-arn "$TG_ARN" --region ap-southeast-1

ALB_DNS=$(aws elbv2 describe-load-balancers --names smb-migration-demo-alb \
  --region ap-southeast-1 --query "LoadBalancers[0].DNSName" --output text)
echo "http://$ALB_DNS"
```

The database seeds itself at boot (schema and admin user), no separate
step needed.

## 6. Prove it's actually stateless and highly available

```bash
python scripts/smoke_test_statelessness.py
```

Finds the load balancer and instances by name, then proves a session
and an uploaded file created through one instance are visible
regardless of which instance answers the next request.

## 7. Tear down

```bash
cd infrastructure/cdk
cdk destroy --all --force
```

RDS takes an automatic final snapshot before deleting. That snapshot
is the one thing this doesn't clean up on its own, delete it once
you're sure you don't need it:

```bash
aws rds describe-db-snapshots --snapshot-type manual --region ap-southeast-1 \
  --query "DBSnapshots[].DBSnapshotIdentifier"
aws rds delete-db-snapshot --db-snapshot-identifier <name> --region ap-southeast-1
```

This bills hourly while running, see either simulation guide's "Cost
While Running" section for the breakdown, the same AWS resources
either way this gets built.
