# Rehost vs. replatform

Two ways to move an app to AWS:

- **Rehost** ("lift and shift"): move the app as-is onto AWS compute.
  Same code, same architecture, just a different data center.
- **Replatform**: change specific pieces to use managed cloud
  services, without a full rewrite.

This project deliberately tested rehost first. The single EC2
instance in `legacy-app/` running on `smb-migration-demo-legacy` *is*
what a rehost of this app looks like, and it got rejected. Here's why.

## What rehost alone doesn't fix

Straight lift-and-shift means: same SQLite file, same local session
files, same local uploads folder, just on an EC2 instance instead of
whatever the SMB was using before.

- **Still a single point of failure.** One instance, one AZ. Losing
  that instance loses the app, exactly like before.
- **Still can't scale horizontally.** Put a second instance behind a
  load balancer and:
  - A user's login only works on the instance that created their
    session; the other instance has never heard of them
  - A file uploaded to one instance doesn't exist on the other
  - Two instances can't safely share one SQLite file
- **Still no managed backups.** The database is a file on a disk.
  RDS's automated backups don't come free with rehosting; they need
  RDS specifically.

None of this is a knock on rehosting in general. It's a fast, low-risk
way to get *off* physical/on-prem infrastructure. It just doesn't
address *any* of this app's actual reliability problems, because those
problems are all about where state lives, not about which data center
the server sits in.

## What replatforming actually buys

Every fix targets one of the specific constraints above, see
`docs/app-rebuild.md` for the how:

- Sessions → **DynamoDB**: any instance can read any user's session,
  so a load balancer can freely route to either one
- Uploads → **S3**: any instance can serve a file any other instance
  received
- Database → **RDS**: managed backups, and a database built to be
  accessed over the network by multiple app servers at once
- None of this required a rewrite: same models, same routes, same
  templates (`docs/app-rebuild.md` covers exactly what changed)

## Why replatform, not rebuild from scratch

The other extreme, throwing out the app and rebuilding it cloud-native
from day one, wasn't necessary either:

- The business logic (customers, invoices, attachments) has nothing to
  do with where sessions or files are stored
- Swapping storage backends is a contained, well-understood change,
  not a rewrite
- A full rebuild would cost far more engineering time for the same
  end result

## Why not AWS MGN or DMS

AWS has dedicated services for exactly this kind of move: Application
Migration Service (MGN) for rehost, Database Migration Service (DMS)
for the database. Neither fits here, for different reasons.

**MGN** replicates a source server's disks block by block and cuts
over to an EC2 instance that's a copy of the source. That's a rehost
tool by design, and rehost is the strategy already ruled out above.
It has no mechanism for splitting session/upload/database state out of
an instance during replication, so it can't produce the target's
stateless, multi-instance shape no matter how it's configured. Running
MGN here would mean getting an EC2 copy of the on-prem VM and then
still doing all the same application-level replatforming work
afterward, adding a tool without removing any of the actual
engineering.

**DMS** is built for continuous database replication and minimal-
downtime cutover of actively-written production databases, plus (via
the Schema Conversion Tool) engine translation for cases where that's
needed. Two things rule it out here. First, DMS's supported source
engines don't include SQLite at all, so it isn't a usable option
regardless of preference. Second, even if it were, this client's
database doesn't have the kind of scale or write volume that
continuous replication exists to solve, see below.

## How the data actually moves

The client's database is small (a handful of customers and invoices,
see `seed.py`), and this is a non-critical, pilot workload that can
tolerate a short maintenance window for cutover. Given that, a one-time
database dump and restore is the appropriate approach, not a managed
replication service: export the data from the on-premise SQLite file,
transform it to match the RDS MySQL schema, load it into RDS.

Cost is part of that call too. DMS runs a replication instance billed
hourly for the duration of the migration, a cost that makes sense
against a large, continuously-changing production database where
downtime isn't acceptable. Standing one up for a sub-megabyte SQLite
file spends real money solving a problem this migration doesn't have.

`scripts/export_sqlite_to_rds.py` does exactly this: reads the SQLite
file and writes the same rows into RDS via SQLAlchemy. See Part 11 of
either simulation guide for the actual steps and what gets validated
afterward (row counts, spot-checked records).

## The actual decision, in one sentence

This app's reliability problems are entirely about **state tied to a
single instance**. Rehosting doesn't touch that at all, and a full
rewrite doesn't need to either. Replatforming the three stateful
pieces (sessions, uploads, database) is the smallest change that
actually fixes the real problem.
