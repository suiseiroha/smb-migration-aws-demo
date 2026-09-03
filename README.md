# SMB migration simulation

A working simulation of migrating a small business's line-of-business
web app to AWS: a stateful legacy app running as-is today, evaluated
and rebuilt into a stateless, highly-available architecture.

See [`docs/legacy-assessment.md`](docs/legacy-assessment.md) for what's
wrong with the current setup and why it has to move, and
[`docs/roadmap.md`](docs/roadmap.md) for the milestones this project
moves through and why each one matters.

## What's here right now

The legacy side of the simulation: an invoice/customer tracker built to
run exactly the way a lot of small businesses actually run things — one
server, local database, local file storage, local session storage. It's
a real, working app, not a mockup.

The AWS rebuild (VPC, load balancer, auto-scaling, managed database)
comes next and will be added to this repo as it's built.

## Running the legacy app yourself

Requires Python 3.10+.

```bash
cd legacy-app
python -m venv .venv
```

Activate the virtual environment:

```bash
# Windows (PowerShell)
.venv\Scripts\Activate.ps1

# macOS/Linux
source .venv/bin/activate
```

Install dependencies and set up the database:

```bash
pip install -r requirements.txt
python seed.py
```

Run it:

```bash
python app.py
```

Open **http://localhost:5000** and log in with `admin` / `changeme123`.

## What to look at

- Create a customer, create an invoice, attach a file to it. Everything
  you just created lives in `legacy-app/instance/app.db`,
  `legacy-app/uploads/`, and `legacy-app/flask_session/` — plain files
  on disk, nothing shared or backed up.
- [`legacy-app/README.md`](legacy-app/README.md) explains what that
  means in practice.
- [`docs/legacy-assessment.md`](docs/legacy-assessment.md) covers the
  app's structure and the case for migrating it.
