# Luminos Engine Operations

## Alert Policy

- `critical`: app will not start, migrations fail, database unavailable, or login is broken.
- `high`: lesson marking, oral check, review, or TTS fails for live classroom use.
- `medium`: background jobs, nightly backups, or deploy workflow failures.
- `low`: transient client banner errors that self-recover after retry.

## Response Policy

- `critical`: stop deploys, restore the last known good release, and verify `alembic current`, `/health`, and `/ready`.
- `high`: keep the service up, collect the failing request ID, and triage from Sentry/logs before the next lesson block.
- `medium`: resolve within one business day.
- `low`: batch into the next maintenance pass unless the same issue repeats.

## Runbook

1. Check `/health` and `/ready`.
2. Check `alembic current` on the host.
3. Review application logs by request ID.
4. If TTS is failing, hit `/admin/tts-health` with `X-Admin-Secret`.
5. If a deploy introduced the issue, roll back the release and rerun migrations only if the target revision changed.

## Keyboard Flow

- `Space`: reveal the current slide, then advance once revealed.
- `Left Arrow`: previous slide.
- `Right Arrow`: next slide.
- `R`: toggle the roster detail panel in the lesson view.

## Accessibility Checks

- Run the GitHub accessibility workflow on every pull request.
- Treat any new axe violations as release blockers.
- Keep status banners on `aria-live="polite"` unless the message blocks the task, in which case use `assertive`.
