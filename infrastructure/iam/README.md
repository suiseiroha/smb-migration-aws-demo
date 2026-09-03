# IAM setup for this project

Scoped custom policy instead of `AdministratorAccess`, per the decision in
`CLAUDE.md`. Covers everything Phase 1 (Console build) and Phase 2 (CDK)
need: EC2/VPC, ALB/ASG, RDS, DynamoDB, S3 (scoped to `smb-migration-demo-*`
and the CDK bootstrap bucket), IAM role/instance-profile management (scoped
to `smb-migration-demo-*` and `cdk-hnb659fds-*` resource names), CloudWatch,
SSM, and CloudFormation (for `cdk deploy`).

This is deliberately not perfectly least-privilege (e.g. `ec2:*`,
`rds:*`, `dynamodb:*` are action-scoped but not resource-scoped, since most
EC2/networking/RDS/DynamoDB actions don't support resource-level ARN
conditions cleanly). It's still meaningfully tighter than
`AdministratorAccess` and every service is one you actually need for this
project.

**Expect to hit `AccessDenied` errors occasionally** — that's fine, it's the
trade-off of scoping instead of using admin access. When it happens, share
the exact error/action name and we'll add it to the policy.

## Steps (do this yourself — do not share the resulting access key/secret in chat)

1. Sign in to the AWS Console with your **root or an existing admin
   account** (you need admin rights to create this new IAM user).
2. Go to **IAM → Policies → Create policy**.
   - Switch to the JSON tab, paste the contents of
     [`smb-migration-demo-policy.json`](smb-migration-demo-policy.json).
   - Name it `smb-migration-demo-policy`.
3. Go to **IAM → Users → Create user**.
   - Name: `smb-migration-demo-cli`
   - Do **not** enable console access (this is a CLI/programmatic-only user).
   - Attach the `smb-migration-demo-policy` you just created directly (skip
     groups for a single-user project like this).
4. After the user is created, open it → **Security credentials** tab →
   **Create access key**.
   - Use case: "Command Line Interface (CLI)".
   - Save the Access Key ID and Secret Access Key somewhere safe (password
     manager, not this repo).
5. In your own terminal (not through Claude), run:

   ```bash
   aws configure
   ```

   and enter:
   - AWS Access Key ID: *(paste yours)*
   - AWS Secret Access Key: *(paste yours)*
   - Default region name: `ap-southeast-1`
   - Default output format: `json`

6. Tell me when that's done and I'll verify with `aws sts get-caller-identity`
   (that command only echoes back your account ID/ARN, no secrets).

## Why not enter this in chat / have Claude run `aws configure`

Access keys are credentials. Entering them through an assistant (even to
paste into a prompt it runs on your behalf) means they pass through this
conversation, which isn't necessary here — `aws configure` writes directly to
`~/.aws/credentials` on your machine when you run it yourself.
