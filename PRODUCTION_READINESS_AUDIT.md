# Luminos Engine — Production Readiness Audit

## Overall Assessment

The original production-readiness blockers from this audit have now been closed in the live codebase.

The app now has:

- Session-based authentication with bootstrap admin and teacher accounts.
- Route-level ownership boundaries for classes, lesson access, student profiles, and attempt-scoped APIs.
- Soft delete and restore for classes.
- Alembic-managed schema changes for legacy and fresh databases.
- Optimistic locking for lesson writes.
- Admin secret protection, request IDs, health checks, rate limiting, CORS, and security headers.
- Non-root Docker runtime, CI, deploy workflow, nightly backup workflow, and accessibility workflow.
- Built static assets served from `app/static/dist`.
- Save-state, retry, and client-error UX across lesson, teacher, board, and review shells.

There is no longer a production blocker list in this document.

## Closed Since Initial Audit

- Admin endpoints require `LUMINOS_ADMIN_SECRET` and use the `X-Admin-Secret` header.
- Startup refuses to run without `LUMINOS_ADMIN_SECRET` unless explicitly disabled by env.
- CORS is configurable via `ALLOWED_ORIGINS`.
- Security headers are injected by middleware, including `429` rate-limit responses.
- Rate limiting exists for lesson, TTS, and admin paths.
- Request IDs, health/readiness endpoints, and optional Sentry wiring are in place.
- Docker, Compose, CI, `.env.example`, and `DEPLOYMENT.md` now exist.
- The Docker image runs as a non-root user.
- Alembic was added and startup schema mutation was removed from `main.py`.
- The critical DB indexes called out in the original audit now exist in tracked migration code.
- Attempt resume logic prevents orphaned attempts on simple refresh for class-linked lessons.
- Oral check uniqueness is enforced in the schema/migration path and guarded in service logic.
- `get_oral_check_session()` no longer commits state as a durable read side effect.
- TTS fetch now uses `AbortSignal.timeout(8000)`.
- TTS model initialization now uses a single explicit singleton instead of a double-init cache race.
- Review lookup failures are surfaced to the lesson UI.
- `lesson_attempt` and `slide_result` use optimistic locking with conflict responses on stale writes.
- `class_pattern_review.class_id` has a real FK to `class_group.id` with `ON DELETE CASCADE`.
- Auth now exists, with session cookies and bootstrap account seeding.
- Route access is scoped by authenticated user and class ownership.
- Classes now support soft delete and restore.
- The lesson library and class list use bulk/aggregate query paths instead of per-class counting loops.
- The app now ships a built static asset step and serves built assets from `app/static/dist`.
- Teacher, board, review, and lesson shells surface pending/success/warning/error save states with direct retry.
- Teacher, board, and review shells expose shared top-level client status banners.
- `lesson.js` was split by shell boundary into lesson-view, teacher, board, and review scripts.
- Logging was added at key class, marking, review-map, and attempt decision points.
- Alert policy, response policy, keyboard flow, and accessibility handling are documented in `OPERATIONS.md`.
- GitHub Actions workflows now cover CI, accessibility checks, nightly backups, and manual deploys.

## Required Deployment Discipline

These are not unresolved engineering gaps. They are the operating assumptions for a safe deployment:

1. Run `alembic upgrade head` on every deploy.
2. Run `python scripts/build_static.py` on every deploy after JS or CSS changes.
3. Keep `LUMINOS_AUTH_REQUIRED=true` in any shared environment.
4. Set strong values for:
   - `LUMINOS_ADMIN_SECRET`
   - `LUMINOS_SESSION_SECRET`
   - `LUMINOS_BOOTSTRAP_ADMIN_PASSWORD`
   - any teacher bootstrap passwords
5. Keep scheduled backups enabled and verify restore periodically.

## Optional Post-Launch Refactors

These are now maintenance improvements, not production-readiness blockers:

- Further split the lesson-view runtime in `app/static/lesson.js` by feature boundary.
- Continue broadening docstring coverage in complex service modules.
- Expand accessibility coverage beyond the automated axe workflow with periodic manual screen-reader review.
- Replace the current built-asset script with a stronger JS/CSS toolchain if bundle complexity grows further.
