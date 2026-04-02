# Luminos Engine Deployment Notes

## Environment

Set these before starting the app:

- `DATABASE_URL`: PostgreSQL connection string with a strong password.
- `LUMINOS_ADMIN_SECRET`: required. Send it only in the `X-Admin-Secret` header.
- `LUMINOS_SESSION_SECRET`: required when auth is enabled.
- `LUMINOS_BOOTSTRAP_ADMIN_USERNAME`, `LUMINOS_BOOTSTRAP_ADMIN_PASSWORD`: required when auth is enabled.
- `LUMINOS_BOOTSTRAP_TEACHER_USERNAME`, `LUMINOS_BOOTSTRAP_TEACHER_PASSWORD`: optional bootstrap teacher.
- `ALLOWED_ORIGINS`: explicit browser origin allowlist.
- `LOG_LEVEL`: usually `INFO` in production.
- `SENTRY_DSN`: optional error tracking.

Optional tuning:

- `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`
- `LUMINOS_RATE_LIMITS`
- `LUMINOS_TTS_*`

## Auth

The application now defaults to session-based auth. Leave `LUMINOS_AUTH_REQUIRED=true`
for any shared environment. Only disable it for local fixtures and CI.

## Local Docker

```bash
docker compose up --build
```

The app will be available at `http://localhost:8000`.

## Migrations

Apply schema changes before serving traffic:

```bash
alembic upgrade head
python scripts/build_static.py
```

Check the current revision with:

```bash
alembic current
```

The application no longer auto-creates or auto-upgrades schema on startup.
Built assets are served from `app/static/dist`, so rebuild them whenever JS or CSS changes.

## Health Checks

- `GET /health`
- `GET /ready`

Both return `503` if the database check fails.

## Admin Endpoints

All `/admin/*` routes require:

```http
X-Admin-Secret: <your-secret>
```

Do not pass secrets in query parameters.

## Backups

Daily backup example:

```bash
bash scripts/backup_postgres.sh
```

Restore example:

```bash
psql "$DATABASE_URL" < luminos_engine_2026-04-02.sql
```

Keep backups off the application host when possible.

## Deploy Flow

The repository now includes:

- `.github/workflows/deploy.yml` for manual GitHub Actions deploys over SSH
- `.github/workflows/backup.yml` for nightly backup artifacts
- `.github/workflows/accessibility.yml` for axe-based accessibility regression checks

Remote hosts can use `scripts/deploy_app.sh` to pull, install dependencies, rebuild static assets, run Alembic, and restart the service.

## Alerts And Runbooks

See `OPERATIONS.md` for severity policy, response expectations, keyboard flow, and accessibility handling.
