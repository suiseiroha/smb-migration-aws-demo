# SMB migration simulation

A working simulation of migrating a small business's line-of-business
web app to AWS: a stateful legacy app running as-is today, evaluated
and rebuilt into a stateless, highly-available, infrastructure-as-code
architecture.

**Business case, architecture, and a full step-by-step simulation in
one document**, start to teardown, via the Console:
[`docs/simulation-guide-rocky-linux-10.md`](docs/simulation-guide-rocky-linux-10.md)
(on-premises Rocky Linux 10 VM, [.docx version](docs/simulation-guide-rocky-linux-10.docx))
or [`docs/simulation-guide-windows.md`](docs/simulation-guide-windows.md)
(Windows, one machine plays both roles). Each is fully self-contained,
nothing installed, no code cloned, all the way to a live, verified,
torn-down deployment.

## Quick start

Already read one of the guides above and just want the fastest
possible local look, no on-premises machine or AWS account needed?
[`docs/quickstart.md`](docs/quickstart.md): Docker Compose for the
legacy app, `cdk deploy --all` for the modernized AWS side.

## The story, in order

1. [`docs/legacy-assessment.md`](docs/legacy-assessment.md): what's
   wrong with the current setup and why it has to move
2. [`docs/rehost-vs-replatform.md`](docs/rehost-vs-replatform.md): why
   a straight lift-and-shift wouldn't have fixed anything, and why
   AWS's own migration tooling (MGN, DMS) doesn't fit this move either
3. [`docs/app-rebuild.md`](docs/app-rebuild.md): how the app itself was
   refactored to be stateless, with diagrams
4. [`docs/architecture-diagrams.md`](docs/architecture-diagrams.md):
   before/after infrastructure diagrams
5. [`docs/simulation-guide-rocky-linux-10.md`](docs/simulation-guide-rocky-linux-10.md)
   or [`docs/simulation-guide-windows.md`](docs/simulation-guide-windows.md):
   the whole migration yourself, start to finish, including the actual
   data migration steps and what went wrong
6. [`docs/roadmap.md`](docs/roadmap.md): the milestones this project
   moved through and why each one mattered

## Reference

- [`docs/quickstart.md`](docs/quickstart.md): fast local-only
  walkthrough, no on-premises VM or AWS account needed
- [`infrastructure/iam/README.md`](infrastructure/iam/README.md):
  setting up the scoped IAM user this project uses instead of admin
  access

## What's here

- **`legacy-app/`**: the invoice/customer tracker as a small business
  would actually run it: one server, local database, local file
  storage, local session storage. A real, working app, not a mockup.
- **`modern-app/`**: the same app, refactored so none of that state is
  tied to the server running it: sessions in DynamoDB, uploads in S3,
  database in RDS.
- **`infrastructure/cdk/`**: the modernized architecture (VPC, ALB,
  Auto Scaling Group, RDS, DynamoDB, S3, IAM, CloudWatch) as an AWS CDK
  Python app.
- **`infrastructure/iam/`**: the least-privilege IAM policies used
  throughout, instead of admin access.
