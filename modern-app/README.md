# modern-app: the "after" state

The same invoice/customer tracker as `legacy-app/`, refactored so no
part of its state is tied to the instance running it. This is what
"replatform" actually means for this app, concretely:

| Legacy (`legacy-app/`) | Modern (`modern-app/`) |
|---|---|
| SQLite file on local disk | RDS MySQL |
| Flask-Session, filesystem backend | DynamoDB (custom session interface, see `session_dynamodb.py`) |
| Uploads saved to local disk | S3, served via presigned URLs |
| Secrets hardcoded / local `.env` | Environment variables, backed by Secrets Manager or SSM |

The business logic (models, routes, templates) is intentionally
almost identical to `legacy-app/`. The point of this project is what
changes when you modernize, not a rewrite.

## Why a custom DynamoDB session backend

Flask-Session ships backends for Redis, Memcached, MongoDB, SQLAlchemy,
and the filesystem, not DynamoDB. Rather than pull in an unofficial
third-party package, `session_dynamodb.py` implements Flask's
`SessionInterface` directly: a random session id goes in a signed
cookie, the session data itself lives in a DynamoDB item keyed by that
id. This is the same pattern Flask-Session's own backends use.

Expected table schema (created by `infrastructure/cdk/`):
- Partition key: `session_id` (String)
- TTL attribute: `expires_at` (Number), lets DynamoDB expire old
  sessions automatically instead of writing cleanup logic

## Configuration

Everything environment-driven (see `config.py`), no defaults suitable
for anything but local testing. Secrets come from Secrets Manager,
either way this gets deployed: `infrastructure/cdk/` auto-generates
them, the manual Phase 1 build creates them by hand (see Part 5 of
either simulation guide). SSM Parameter Store is also supported in
`config.py` as a fallback, but nothing in this repo uses it anymore.

| Variable | Purpose |
|---|---|
| `AWS_REGION` | Defaults to `ap-southeast-1` |
| `SECRET_KEY` | Flask session-signing key, plain env var (local/dev only) |
| `SECRET_KEY_SECRET_ARN` | Secrets Manager ARN for the signing key |
| `SECRET_KEY_SSM_PARAM` | SSM parameter name for the signing key (unused fallback) |
| `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER` | RDS connection details |
| `DB_PASSWORD` | Plain env var (local/dev only) |
| `DB_PASSWORD_SECRET_ARN` | Secrets Manager ARN for the DB password |
| `DB_PASSWORD_SSM_PARAM` | SSM parameter name for the DB password (unused fallback) |
| `SESSION_DYNAMODB_TABLE` | Defaults to `smb-migration-demo-sessions` |
| `S3_UPLOAD_BUCKET` | Defaults to `smb-migration-demo-uploads` |

## Running it

There's no local-only fallback mode by design. This app always talks
to DynamoDB/S3/RDS, because that's the thing it's meant to demonstrate.
Against the real AWS resources (see `docs/simulation-guide-rocky-linux-10.md`
or `docs/simulation-guide-windows.md` to stand them up by hand in the
Console, or `docs/quickstart.md` for the one-command CDK path):

```bash
export DB_HOST=... DB_USER=... DB_PASSWORD_SECRET_ARN=...
python seed.py
python app.py
```

For local development without touching real AWS, see
`test_smoke.py`. It runs the same code against a mocked
DynamoDB/S3 (via `moto`) and a throwaway local MySQL container.
