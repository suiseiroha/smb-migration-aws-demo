# modern-app — the "after" state

The same invoice/customer tracker as `legacy-app/`, refactored so no
part of its state is tied to the instance running it. This is what
"replatform" actually means for this app, concretely:

| Legacy (`legacy-app/`) | Modern (`modern-app/`) |
|---|---|
| SQLite file on local disk | RDS MySQL |
| Flask-Session, filesystem backend | DynamoDB (custom session interface, see `session_dynamodb.py`) |
| Uploads saved to local disk | S3, served via presigned URLs |
| Secrets hardcoded / local `.env` | Environment variables, with an SSM Parameter Store option for the DB password |

The business logic — models, routes, templates — is intentionally
almost identical to `legacy-app/`. The point of this project is what
changes when you modernize, not a rewrite.

## Why a custom DynamoDB session backend

Flask-Session ships backends for Redis, Memcached, MongoDB, SQLAlchemy,
and the filesystem — not DynamoDB. Rather than pull in an unofficial
third-party package, `session_dynamodb.py` implements Flask's
`SessionInterface` directly: a random session id goes in a signed
cookie, the session data itself lives in a DynamoDB item keyed by that
id. This is the same pattern Flask-Session's own backends use.

Expected table schema (created in milestone 4):
- Partition key: `session_id` (String)
- TTL attribute: `expires_at` (Number) — let DynamoDB expire old
  sessions automatically instead of writing cleanup logic

## Configuration

Everything environment-driven (see `config.py`), no defaults suitable
for anything but local testing:

| Variable | Purpose |
|---|---|
| `AWS_REGION` | Defaults to `ap-southeast-1` |
| `SECRET_KEY` | Flask session-signing key |
| `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER` | RDS connection details |
| `DB_PASSWORD` | Plain env var (local/dev only) |
| `DB_PASSWORD_SSM_PARAM` | SSM parameter name — if set, the password is fetched from Parameter Store instead of `DB_PASSWORD` (what the real deployment uses) |
| `SESSION_DYNAMODB_TABLE` | Defaults to `smb-migration-demo-sessions` |
| `S3_UPLOAD_BUCKET` | Defaults to `smb-migration-demo-uploads` |

## Running it

There's no local-only fallback mode by design — this app always talks
to DynamoDB/S3/RDS, because that's the thing it's meant to demonstrate.
Against the real AWS resources (once milestone 4 exists):

```bash
export DB_HOST=... DB_USER=... DB_PASSWORD_SSM_PARAM=...
python seed.py
python app.py
```

For local development without touching real AWS, see
`test_smoke.py` — it runs the same code against a mocked
DynamoDB/S3 (via `moto`) and a throwaway local MySQL container.
