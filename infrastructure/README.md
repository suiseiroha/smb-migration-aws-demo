# infrastructure/

- `iam/`: least-privilege IAM policies (CLI user and the app's EC2
  instance role)
- `launch-template-app.json`: launch template data for
  `smb-migration-demo-lt` (the manual Phase 1 build's compute layer,
  superseded by `cdk/` below). No `KeyName` field on purpose, no SSH
  keypair, SSM Session Manager only.
  `MetadataOptions.HttpTokens: required` enforces IMDSv2. `UserData`
  (base64, from `modern-app/deploy/ec2-user-data.sh`) fully deploys the
  app at boot: downloads the code from S3, installs dependencies,
  starts it as a systemd service, so a fresh ASG instance becomes
  healthy on its own with no manual step. That wasn't true until
  milestone 6: the original version only installed Docker, which
  turned out to be unused dead weight (the real deployment is a plain
  Python venv, not a container), leaving every replacement instance
  failing its ALB health check until someone deployed to it by hand.
  If `modern-app`'s code changes, re-package and re-upload
  `modern-app.tar.gz` to S3 before the next instance launch picks it
  up (see Part 7 of either simulation guide). Existing running
  instances aren't affected retroactively; redeploy one by hand with
  `scripts/deploy_modern_app_to_instance.sh <instance-id>` instead of
  waiting for the ASG to cycle it.
  `ImageId` is a snapshot of the latest Amazon Linux 2023 AMI as of
  2026-09-05; to refresh it:

  ```bash
  aws ec2 describe-images --owners amazon --region ap-southeast-1 \
    --filters "Name=name,Values=al2023-ami-2023.*-kernel-6.1-x86_64" "Name=state,Values=available" \
    --query "reverse(sort_by(Images, &CreationDate))[0].ImageId" --output text
  ```

  (The usual `/aws/service/ami-amazon-linux-latest/...` SSM public
  parameter path returned `ParameterNotFound` when tried here. Worth
  rechecking in case that's fixed later, but `describe-images` is a
  reliable fallback either way.)
- `cdk/`: Phase 2 CDK rebuild. The primary path now, see
  `docs/quickstart.md` for the `cdk deploy --all`/`cdk destroy --all`
  commands.
