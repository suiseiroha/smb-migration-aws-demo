# Legacy system assessment

The pattern below is a familiar one to anyone who's done systems
engineering on-premises: a line-of-business app that works fine day to
day while quietly accumulating risk nobody has priced in. The
invoice/customer tracker here is a deliberate example of that pattern —
built to be assessed and migrated, not just described.

## What it is

A Flask app for tracking customers and invoices, with file attachments
(receipts, scanned documents) per invoice.

| Module | Responsibility |
|---|---|
| `app.py` | Routes, auth, request handling |
| `models.py` | Data models: `User`, `Customer`, `Invoice`, `Attachment` |
| `forms.py` | Form validation |
| `seed.py` | Schema creation and sample data |

All state — database, sessions, uploaded files — lives on the same
local disk as the app itself.

## How it's run

One server, set up by hand: install Python, copy the code, start the
process. No config management, no infrastructure-as-code, no rebuild
procedure. It works, so nobody touches it — until something forces the
issue.

## Why it has to move

The trigger isn't performance. It's exposure.

**No backups.** The database is a single file on local disk. A disk
failure erases every invoice and customer record, with nothing to
restore from.

**One person holds the knowledge.** Whoever built the server is the
only one who knows how it's configured. No runbook exists. If that
person is unreachable when something breaks, so is the fix.

**No redundancy.** One instance means one outage takes the whole
system down — no failover, and no way to patch or reboot without
downtime.

**State is glued to the instance.** Sessions and uploads live on
local disk alongside the database. Adding a second server doesn't
help by itself: a login only works on the instance that created it,
and a file only exists on the instance it was uploaded to.

That last point is the real blocker. It's why
[`rehost-vs-replatform.md`](rehost-vs-replatform.md) rules out a
straight lift-and-shift — copying this app onto a bigger EC2 instance
would fix none of the four risks above.
