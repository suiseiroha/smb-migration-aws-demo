# legacy-app: the "before" state

A small Flask invoice/customer tracker representing how a typical SMB
actually runs a line-of-business web app: hand-deployed on a single box,
built without any thought toward horizontal scaling. This app is **not
meant to be improved**. `modern-app/` is the refactored, stateless
version. This one stays as-is to document the starting point.

## What makes this deliberately stateful / unmanaged

- **Sessions on local disk.** `Flask-Session` is configured with the
  `filesystem` backend (`flask_session/`). Login state lives in files next
  to the app process. If you ran two copies of this app behind a load
  balancer, a user's session would only be valid on whichever instance
  created it. That's the classic reason lift-and-shift alone doesn't
  give you real horizontal scaling.
- **Uploads on local disk.** Invoice attachments are saved straight to
  `uploads/` via `werkzeug`'s file handling. Same problem: a file uploaded
  on one instance doesn't exist on any other instance or survive that
  instance being replaced.
- **SQLite on local disk.** The database is a single file
  (`instance/app.db`). It cannot be shared safely across multiple
  app instances, has no automated backup story, and there's no HA without
  a completely different database engine.
- **Single instance, no supervision beyond what you set up by hand.** No
  auto-restart, no auto-scaling, no health checks beyond "is someone
  checking the site."

None of this is a bug in the code. It's realistic of how a lot of small
businesses actually run things. See
[`../docs/legacy-assessment.md`](../docs/legacy-assessment.md) for the
module breakdown and why this setup forces a migration, and
[`../docs/rehost-vs-replatform.md`](../docs/rehost-vs-replatform.md) for
the rehost-vs-replatform reasoning.

## Running locally

**With Docker (recommended, no Python setup needed):**

Don't have Docker yet:

```bash
# Windows, using winget
winget install -e --id Docker.DockerDesktop --source winget --accept-package-agreements --accept-source-agreements

# Linux (Debian/Ubuntu, including WSL), official convenience script
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER   # log out and back in afterward
```

On Windows, Docker Desktop needs WSL2, which its installer offers to
enable if it isn't already (a reboot is required the first time).
Start Docker Desktop once after installing so its background service
is running.

```bash
docker compose up
```

First run builds the image, creates the database, and seeds sample data
automatically. Open http://localhost:5000.

**Without Docker:**

```bash
# from legacy-app/, with its .venv active
python seed.py     # creates instance/app.db, seeds an admin user + sample data
python app.py       # runs on http://localhost:5000
```

Default login after seeding: `admin` / `changeme123` (change
`ADMIN_PASSWORD` in `seed.py` before using this anywhere but a local demo).

Either way, `instance/`, `uploads/`, and `flask_session/` end up as real
folders on disk right here in `legacy-app/`. That's deliberate, see below.

## Deploying to the single EC2 instance

[`deploy/ec2-user-data.sh`](deploy/ec2-user-data.sh) bootstraps Docker
on a fresh `smb-migration-demo-legacy` instance at launch (paste it into
the launch wizard's user data field). Everything after that, copying
the code over and running `docker compose up`, is still done by hand,
matching the "unmanaged SMB box" framing in `docs/legacy-assessment.md`.

## Deploying to a real on-premises machine

Part 2 of [`docs/simulation-guide-rocky-linux-10.md`](../docs/simulation-guide-rocky-linux-10.md)
(system packages, venv, systemd unit, firewall) or
[`docs/simulation-guide-windows.md`](../docs/simulation-guide-windows.md)
(Python, venv, NSSM service, Windows Firewall) walks through installing
this app directly on a real machine. A more realistic stand-in for
"the SMB's actual on-prem box" than an EC2 instance.

## What's local and gitignored

`instance/`, `flask_session/`, `uploads/`, and `*.db` are all gitignored
at the repo root. This app's entire state lives outside version control,
which is itself part of the "unmanaged SMB infrastructure" story.
