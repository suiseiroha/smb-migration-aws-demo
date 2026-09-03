# Migration roadmap

Nine milestones, in order. Each one produces something concrete you can
look at, and each one exists to prove a specific point about the
migration — not just to move the project forward. Several of them draw
directly on years of on-premises systems engineering: the instincts
that come from actually racking, patching, and troubleshooting physical
and virtual infrastructure carry over to AWS more than people expect.

## 1. Build and assess the legacy system

Build the invoice/customer tracker exactly the way a small business
would actually run it: one server, local database, local file storage.
Then document precisely why that setup is a liability, not just a
performance problem. This sets the baseline everything else gets
measured against — without a real "before," the "after" has nothing to
prove itself against. Spotting that risk quickly is the same skill as
walking into an unfamiliar server room and knowing within an hour which
box nobody's allowed to touch.

## 2. Deploy it to a single server

Put the app on one EC2 instance, configured by hand, the way it would
be in a typical SMB environment. This isn't a step toward the AWS
architecture — it's a deliberate dead end, kept as-is to anchor the
before/after comparison. Skipping it would make the "risk" in the
assessment abstract instead of demonstrated. Provisioning a box by
hand — OS, dependencies, no config management — is exactly how most
on-prem servers actually get built, whatever the official process
says.

## 3. Refactor the app to be stateless

Move sessions to DynamoDB, uploads to S3, and the database to RDS. This
is the actual engineering work of the migration — everything before
this is context, everything after this is infrastructure. Get this
step wrong and no amount of load balancing or auto-scaling fixes it,
because the app itself would still be tied to whichever server answers
the request. It's the same underlying fix as moving a server's data
off local disk onto a SAN or a dedicated DB box — the reasoning is
identical, only the vocabulary changes.

## 4. Build the target architecture

Stand up the VPC, subnets, security groups, load balancer, auto-scaling
group, RDS instance, DynamoDB table, and S3 bucket — by hand in the
console first, so every piece is understood rather than templated.
This is where "highly available three-tier architecture" stops being a
diagram and becomes something running. Subnet tiers and scoped
security groups are VLAN segmentation and firewall rules under a new
name — the network design instincts transfer directly, even though the
console looks nothing like a switch's CLI.

## 5. Migrate the data

Move the existing SQLite data into RDS, and any existing files into S3,
without losing or corrupting anything. Every real migration lives or
dies on this step — the infrastructure can be perfect and the project
still fails if data doesn't survive the move intact. Planning a cutover,
validating row counts, having a rollback path if something looks wrong
— that discipline is identical to any on-prem storage or database
migration, cloud or not.

## 6. Prove it's actually stateless and available

Hit the load balancer repeatedly, confirm a session or upload survives
regardless of which instance answers, then take an instance down mid-
demo and show the system keeps running. This is the payoff of
milestone 3 — the point where "stateless" and "highly available" stop
being claims and become something you can watch happen. It's the same
test as pulling a node from an on-prem HA cluster to confirm failover
actually works instead of just trusting the config — the only thing
that's changed is which vendor's dashboard you're watching.

## 7. Tear down with cost discipline

Snapshot the database, then delete or stop everything that bills by
the hour. On a personal AWS account this isn't optional cleanup — it's
proof of understanding what actually costs money in this architecture
and why (ALB and NAT Gateway bill whether or not anyone's using them;
RDS and EC2 don't once stopped). It's the cloud version of knowing
which servers you can power down over a holiday shutdown and which
ones you can't — the awareness comes from having managed a real
capacity and power budget before, not from a pricing page.

## 8. Rebuild it as infrastructure as code

Reimplement the same architecture as an AWS CDK app in Python, split
into network, data, compute, and monitoring stacks. The console build
proves the architecture works; this step proves it's repeatable —
`cdk deploy` gets you the same environment from nothing, without
relying on memory of what was clicked where. This is the one milestone
that's a deliberate break from typical on-prem practice, not an
extension of it — most on-prem environments run on servers nobody
fully documented, built up by hand over years. Writing the environment
down as code is the fix for that exact problem.

## 9. Finalize documentation

Before/after diagrams, the migration runbook, and the rehost-vs-
replatform reasoning, all written to stand on their own for someone
who wasn't in the room for any of the above. A migration that isn't
documented isn't really finished — the next person who touches this
environment shouldn't have to reverse-engineer it. That's a habit worth
carrying over from anywhere infrastructure changes hands between
shifts or teams: if it's not written down, it didn't happen.
