# IAM setup for this project

A scoped custom policy instead of `AdministratorAccess`. Covers
everything Phase 1 (Console build) and Phase 2 (CDK) need: EC2/VPC,
ALB/ASG, RDS, DynamoDB, S3 (scoped to `smb-migration-demo-*` and the
CDK bootstrap bucket), IAM role/instance-profile management (scoped to
`smb-migration-demo-*` and `cdk-hnb659fds-*` resource names),
CloudWatch, SSM, and CloudFormation (for `cdk deploy`).

This is deliberately not perfectly least-privilege (e.g. `ec2:*`,
`rds:*`, `dynamodb:*` are action-scoped but not resource-scoped, since
most EC2/networking/RDS/DynamoDB actions don't support resource-level
ARN conditions cleanly). It's still meaningfully tighter than
`AdministratorAccess`, and every service included is one this project
actually uses.

**Expect to hit `AccessDenied` errors occasionally** — that's the
trade-off of scoping instead of using admin access. When it happens,
add the specific action to the policy rather than widening broadly.

## Setup

1. Sign in to the AWS Console with a **root or existing admin
   account** (admin rights are needed to create this new IAM user).
2. Go to **IAM → Policies → Create policy**.
   - Switch to the JSON tab, paste the contents of
     [`smb-migration-demo-policy.json`](smb-migration-demo-policy.json).
   - Name it `smb-migration-demo-policy`.
3. Go to **IAM → Users → Create user**.
   - Name: `smb-migration-demo-cli`
   - Do **not** enable console access (this is a CLI/programmatic-only
     user).
   - Attach the `smb-migration-demo-policy` created above directly
     (skip groups for a single-user project like this).
4. Open the new user → **Security credentials** tab → **Create access
   key**.
   - Use case: "Command Line Interface (CLI)".
   - Save the Access Key ID and Secret Access Key in a password
     manager — never in this repo.
5. Run:

   ```bash
   aws configure
   ```

   and enter:
   - AWS Access Key ID: *(paste yours)*
   - AWS Secret Access Key: *(paste yours)*
   - Default region name: `ap-southeast-1`
   - Default output format: `json`

6. Verify with `aws sts get-caller-identity` (echoes back the account
   ID/ARN, no secrets involved).

## Why `aws configure`, not a pasted key

`aws configure` writes credentials directly to `~/.aws/credentials` on
your own machine. Access keys are credentials — they shouldn't be
typed into a chat window, a script, or anywhere else they'd need to be
copy-pasted through a third party first.
