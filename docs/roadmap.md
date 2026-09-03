# Migration roadmap

Nine milestones, in order. Each one produces something concrete you can
look at, and each one exists to prove a specific point about the
migration — not just to move the project forward.

## 1. Build and assess the legacy system

Build the invoice/customer tracker exactly the way a small business
would actually run it: one server, local database, local file storage.
Then document precisely why that setup is a liability, not just a
performance problem. This sets the baseline everything else gets
measured against — without a real "before," the "after" has nothing to
prove itself against.

## 2. Deploy it to a single server

Put the app on one EC2 instance, configured by hand, the way it would
be in a typical SMB environment. This isn't a step toward the AWS
architecture — it's a deliberate dead end, kept as-is to anchor the
before/after comparison. Skipping it would make the "risk" in the
assessment abstract instead of demonstrated.

## 3. Refactor the app to be stateless

Move sessions to DynamoDB, uploads to S3, and the database to RDS. This
is the actual engineering work of the migration — everything before
this is context, everything after this is infrastructure. Get this
step wrong and no amount of load balancing or auto-scaling fixes it,
because the app itself would still be tied to whichever server answers
the request.

## 4. Build the target architecture

Stand up the VPC, subnets, security groups, load balancer, auto-scaling
group, RDS instance, DynamoDB table, and S3 bucket — by hand in the
console first, so every piece is understood rather than templated.
This is where "highly available three-tier architecture" stops being a
diagram and becomes something running.

## 5. Migrate the data

Move the existing SQLite data into RDS, and any existing files into S3,
without losing or corrupting anything. Every real migration lives or
dies on this step — the infrastructure can be perfect and the project
still fails if data doesn't survive the move intact.

## 6. Prove it's actually stateless and available

Hit the load balancer repeatedly, confirm a session or upload survives
regardless of which instance answers, then take an instance down mid-
demo and show the system keeps running. This is the payoff of
milestone 3 — the point where "stateless" and "highly available" stop
being claims and become something you can watch happen.

## 7. Tear down with cost discipline

Snapshot the database, then delete or stop everything that bills by
the hour. On a personal AWS account this isn't optional cleanup — it's
proof of understanding what actually costs money in this architecture
and why (ALB and NAT Gateway bill whether or not anyone's using them;
RDS and EC2 don't once stopped).

## 8. Rebuild it as infrastructure as code

Reimplement the same architecture as an AWS CDK app in Python, split
into network, data, compute, and monitoring stacks. The console build
proves the architecture works; this step proves it's repeatable —
`cdk deploy` gets you the same environment from nothing, without
relying on memory of what was clicked where.

## 9. Finalize documentation

Before/after diagrams, the migration runbook, and the rehost-vs-
replatform reasoning, all written to stand on their own for someone
who wasn't in the room for any of the above. A migration that isn't
documented isn't really finished — the next person who touches this
environment shouldn't have to reverse-engineer it.
