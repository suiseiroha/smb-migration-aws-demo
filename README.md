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

Requires [Docker Desktop](https://www.docker.com/products/docker-desktop/) —
nothing else to install.

```bash
cd legacy-app
docker compose up
```

Open **http://localhost:5000** and log in with `admin` / `changeme123`.
First run builds the image and seeds sample data automatically; press
`Ctrl+C` to stop it, run the same command again any time to bring it
back up with everything you added still there.

(No Docker? [`legacy-app/README.md`](legacy-app/README.md) has the plain
Python setup instead.)

## What to look at

- Create a customer, create an invoice, attach a file to it. Everything
  you just created lives in `legacy-app/instance/app.db`,
  `legacy-app/uploads/`, and `legacy-app/flask_session/` — plain files
  on disk, nothing shared or backed up.
- [`legacy-app/README.md`](legacy-app/README.md) explains what that
  means in practice.
- [`docs/legacy-assessment.md`](docs/legacy-assessment.md) covers the
  app's structure and the case for migrating it.
