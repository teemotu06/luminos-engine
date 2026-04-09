# Project Context

## 1. Purpose

This file is a working summary of the current implemented state of `luminos-engine`.
It is descriptive, not normative.

Use it to understand:
- what the app currently does
- what data and routes exist now
- how lesson delivery, marking, oral checks, review injection, and TTS currently behave
- what content exists on disk today

Do not use this file to override the formal specs in the repo root.

## 2. Source-of-truth hierarchy

1. Current repository implementation
2. Formal specs in the repo root
3. `PROJECT_CONTEXT.md`

If the code and the specs diverge, this file should describe the code as it exists now.

## 3. Current stack

- Backend: FastAPI
- Templating: Jinja2
- Frontend state: Alpine.js
- Audio playback: Howler.js
- Data validation: Pydantic 2
- ORM: SQLAlchemy 2.x
- Migrations: Alembic
- Primary DB target: PostgreSQL via `psycopg2-binary`
- Test DB path: SQLite is used in tests
- Content source: JSON lesson files under `app/content/lessons/`
- Local TTS: Kokoro-based runtime with on-disk WAV cache
- Auth/session model: signed cookie session auth with bootstrap admin/teacher users

Python dependencies currently declared in `requirements.txt` include:
- `alembic`
- `fastapi`
- `jinja2`
- `sqlalchemy`
- `python-dotenv`
- `psycopg2-binary`
- `httpx`
- `numpy`
- `pydantic`
- `python-multipart`
- `sentry-sdk[fastapi]`
- `soundfile`
- `uvicorn`

Kokoro runtime dependencies are documented separately in `KOKORO_TTS_SETUP.md`; they are not fully represented in `requirements.txt`.

## 4. App startup and mounting

App entrypoint: `app/main.py`

Current startup behavior:
- loads `DATABASE_URL` from env via `app/db.py`
- raises `RuntimeError` if `DATABASE_URL` is missing
- validates auth env when auth is enabled
- refuses to start if `LUMINOS_ENFORCE_ADMIN_SECRET` is true and `LUMINOS_ADMIN_SECRET` is unset
- bootstraps configured admin/teacher users when auth is enabled
- optionally initializes Sentry when `SENTRY_DSN` is set and the package is installed
- optionally prunes old TTS cache files on startup
- optionally prewarms the Kokoro TTS runtime on startup

Current middleware behavior:
- request IDs are generated or propagated via `X-Request-ID`
- baseline security headers are added to all responses
- simple in-memory per-path rate limiting is applied outside static/health paths
- CORS is enabled only when `ALLOWED_ORIGINS` is configured

Mounted paths:
- `/static` -> `app/static`
- `/tts-cache` -> local WAV cache directory

Included routers:
- `auth_router`
- `lesson_router`
- `students_router`
- `classes_router`
- `admin_router`

## 5. Database and persistence

`app/db.py` supports both PostgreSQL and SQLite based on `DATABASE_URL`.

Current ORM tables:
- `app_user`
- `lesson`
- `lesson_attempt`
- `slide_result`
- `student_mark`
- `class_group`
- `student_record`
- `oral_check_session`
- `oral_check_assignment`
- `lesson_runtime_state`
- `class_pattern_review`

Current persistence behavior:
- opening a lesson creates a new `lesson_attempt`
- command/teacher-mode progression persists per-slide runtime state in `lesson_runtime_state`
- slide-level class marks write `slide_result`
- student roster marks write `student_mark`
- oral-check completion also upserts final per-student `student_mark` records
- lesson completion sets `lesson_attempt.completed = True`
- lesson and slide writes use optimistic version fields on `lesson_attempt` and `slide_result`
- class-pattern review scheduling is updated at lesson completion, not on every mark
- classes are soft-deletable via `class_group.deleted_at`
- non-admin teachers only see their own classes via `owner_user_id`

Implementation note:
- there is now an Alembic migration chain under `alembic/versions/`
- tests explicitly cover fresh-schema upgrades and patching of legacy SQLite schemas
- runtime startup is no longer the source of truth for schema evolution

## 6. Current route surface

### Root
- `GET /` -> redirects to `/auth/login` when auth is enabled, otherwise `/lesson/`
- `GET /health` -> DB-backed liveness check
- `GET /ready` -> same readiness payload as `/health`

### Auth routes
- `GET /auth/login`
- `POST /auth/login`
- `POST /auth/logout`

### Lesson routes
- `GET /lesson/` -> lesson launcher/library
- `GET /lesson/mastery-gates?class_id=...` -> compact per-lesson mastery gate summaries
- `GET /lesson/progress?class_id=...` -> lesson progress for a class
- `GET /lesson/{lesson_id}` -> lesson shell, creates attempt
- `GET /lesson/{lesson_id}/block/{block_id}` -> lesson shell starting at a block
- `GET /lesson/{lesson_id}/teacher` -> teacher control surface
- `GET /lesson/{lesson_id}/board` -> board/student-display surface
- `GET /lesson/{lesson_id}/review/{attempt_id}` -> post-lesson review page
- `POST /lesson/{lesson_id}/mark` -> write/update class slide result
- `POST /lesson/{lesson_id}/student-mark` -> upsert one student mark
- `DELETE /lesson/{lesson_id}/student-mark` -> delete one student mark
- `POST /lesson/{lesson_id}/oral-check/session/start` -> create or resume oral-check session
- `GET /lesson/{lesson_id}/oral-check/session/{attempt_id}/{slide_id}` -> fetch oral-check session
- `POST /lesson/{lesson_id}/oral-check/assignment/mark` -> mark active oral assignment
- `POST /lesson/{lesson_id}/oral-check/session/complete` -> complete oral-check session
- `POST /lesson/tts/prompt` -> generate or fetch cached local TTS audio
- `GET /lesson/{lesson_id}/command-state/{attempt_id}` -> fetch current command/runtime state
- `POST /lesson/{lesson_id}/command-state/{attempt_id}/active-slide` -> move active slide
- `POST /lesson/{lesson_id}/command-state/{attempt_id}/advance` -> advance teacher/board runtime state
- `POST /lesson/{lesson_id}/complete` -> complete lesson attempt if oral checks are resolved

### Class routes
- `GET /classes/` -> class list
- `GET /classes/new` -> class creation form
- `POST /classes/new` -> create class
- `GET /classes/{class_id}` -> class detail page with roster
- `POST /classes/{class_id}/students` -> add student to class
- `POST /classes/{class_id}/archive` -> soft-delete class
- `POST /classes/{class_id}/restore` -> restore soft-deleted class

### Student routes
- `GET /students/{student_name}/profile`

### Admin routes
- `POST /admin/rebuild-review-records`
- `POST /admin/clear-lesson-cache`
- `GET /admin/tts-health`
- `POST /admin/tts-prune-cache`

Admin routes are guarded by `X-Admin-Secret` and are unavailable when `LUMINOS_ADMIN_SECRET` is unset. By default, startup also refuses to run without the admin secret.

## 7. Current lesson/content inventory

Lesson files currently on disk: 76 total, all marked `content_pack_status: draft`.

Current distribution:
- `G1`: 4 lessons (`G1-L1` to `G1-L4`)
- `G2`: 7 lessons (`G2-L5` to `G2-L11`)
- `G3`: 9 lessons (`G3-L12` to `G3-L20`)
- `G4`: 6 lessons (`G4-L21` to `G4-L26`)
- `G5`: 9 lessons (`G5-L27` to `G5-L35`)
- `G6`: 4 lessons (`G6-L36` to `G6-L39`)
- `G7`: 4 lessons (`G7-L40` to `G7-L43`)
- `G8`: 13 lessons (`G8-L44` to `G8-L56`)
- `G9`: 11 lessons (`G9-L57` to `G9-L67`)
- `G10`: 4 lessons (`G10-L68` to `G10-L71`)
- `KI`: 5 intervention lessons (`KI-L1` to `KI-L5`)

This is a major change from earlier repo states that only had the first few G1 lessons implemented.

## 8. Lesson schema and ordering

Current lesson loading path:
- file read in `app/services/lesson_service.py`
- parsed into `app.schemas.lesson.Lesson`
- validated by:
  - `validate_lesson_blocks`
  - `validate_slide_payloads`

Lesson ordering:
- standard lessons are sorted by `Gx-Ly`
- KI lessons are inserted using `KI_INSERTION_MAP`
- lesson IDs are cached in-process via `_lesson_ids_cached()`
- admin cache-clear and rebuild endpoints invalidate this cache

The lesson runtime still assumes a fixed 10-block architecture enforced by `BLOCK_REGISTRY`.

Implemented view types remain:
- `flashcard`
- `audio_prompt`
- `minimal_pair`
- `drag_letter`
- `drag_word`
- `read_respond`
- `writing_encoding`
- `quick_check`

## 9. Dynamic review and KI insertion

Two repo-level systems now materially affect lesson runtime:

### KI insertion metadata
`KI_INSERTION_MAP` defines where intervention lessons belong relative to the main sequence and provides assignment/skip guidance text.

### Dynamic class review injection
For graded lessons with a selected class:
- the launcher computes class review recommendations from `class_pattern_review`
- lesson load can inject dynamic review slides into the runtime lesson via `inject_dynamic_review_into_lesson(...)`
- `build_dynamic_review_slides(...)` exposes those recommendations to the template layer

The runtime lesson shown to the teacher can therefore differ from the raw JSON lesson on disk when class review recommendations are present.

## 10. Marking model

There are now three distinct marking paths:

### 1. Slide/class marking
Stored in `slide_result`.

Used for:
- teacher overlay class-response buttons
- quick-check aggregate submission

Stored fields include:
- `status`
- `error_tags`
- `korean_transfer`
- `teacher_note`
- `item_results`

### 2. Per-student roster marking
Stored in `student_mark`.

Used for:
- roster taps during the lesson
- review-page inline editing
- oral-check final per-student resolution

Current student status cycle in the lesson shell:
- `"" -> secure -> shaky -> missed -> skipped -> ""`

`student_mark.error_tags` is nullable and not collected in the main lesson flow today.

### 3. Oral-check assignment marking
Stored in `oral_check_assignment` and summarized by `oral_check_session`.

Terminal statuses currently accepted by the service:
- `secure`
- `shaky`
- `missed`
- `deferred`
- `absent`

## 11. Oral-check system

The repo now has a block-07 oral enforcement system, implemented in `app/services/oral_check_service.py` and wired through the lesson runtime plus the teacher/board command-state flow.

Current behavior:
- eligible slides start or resume an oral-check session automatically when the slide becomes active and a roster is present
- lesson completion is blocked while any oral-check session for the attempt has unresolved students
- the active prompt can be full-roster or audit-roster based
- short-reader mode can require multiple evidence passes
- missed reads can queue a correction/reread assignment
- once all required readers are resolved, the frontend auto-completes the session
- after oral check completes, the same slide can run a comprehension round across the roster if comprehension prompts are configured

Audit selection strategies currently supported:
- `roster_order`
- `least_recently_checked`

Frontend consequence:
- the old small presentation-mode roster button has been replaced by a larger floating oral/roster control panel that also handles prompt playback, assignment marking, audit controls, and roster inspection

## 12. Local TTS system

The repo now includes a Kokoro-backed local TTS path:
- service: `app/services/kokoro_tts_service.py`
- route: `POST /lesson/tts/prompt`
- cache mount: `/tts-cache`

Current TTS behavior:
- prompt text is normalized and hashed
- generated WAVs are cached on disk
- generation uses file locks to prevent duplicate concurrent synthesis
- cache can be prewarmed on startup
- cache can be pruned on startup or through admin endpoints
- frontend fetches TTS on demand for oral prompts and prefetches likely next prompts

Relevant env vars include:
- `LUMINOS_TTS_CACHE_DIR`
- `LUMINOS_TTS_PREWARM_ENABLED`
- `LUMINOS_TTS_STRICT_STARTUP`
- `LUMINOS_TTS_CACHE_PRUNE_ON_STARTUP`
- `KOKORO_VOICE`
- `KOKORO_SPEED`
- `KOKORO_SAMPLE_RATE`

## 13. Frontend runtime

Current frontend entrypoints are split by surface:
- `app/static/lesson.js` -> lesson/review shell
- `app/static/lesson_teacher.js` -> teacher control surface
- `app/static/lesson_board.js` -> board display
- `app/static/lesson_launcher.js` -> launcher/library behavior

Main Alpine components/stores now include:
- `lessonShell(...)`
- `reviewShell(...)`
- `teacherShell(...)`
- `boardShell(...)`
- `launcherShell(...)`
- `Alpine.store("lessonRoster", ...)`
- `dragBuild(...)`

Current frontend responsibilities across those surfaces:
- lesson launch with class-aware progress/review metadata
- teacher/board command-state synchronization
- slide navigation and reveal flow
- audio playback
- TTS prompt fetching/caching
- class slide marking
- per-student roster marking
- oral-check session orchestration
- comprehension follow-up orchestration
- dynamic-review skipping

The old `P` presentation-mode toggle described in earlier project-context versions is no longer a reliable description of the current frontend behavior and should not be assumed.

## 14. Current UI/template structure

Key templates:
- `app/templates/lesson/index.html`
- `app/templates/lesson/view.html`
- `app/templates/lesson/teacher.html`
- `app/templates/lesson/board.html`
- `app/templates/lesson/review.html`
- lesson partials under `app/templates/lesson/partials/`

Current launcher behavior:
- grouped lesson library
- class selector
- KI insertion context
- class review map data for lesson cards
- roster-connected vs no-roster messaging

Current lesson-view behavior:
- full lesson rendered into the page
- slide frames flattened in canonical order
- dynamic review slides can be rendered ahead of the main lesson sequence
- floating oral/roster panel is body-level UI, driven by the Alpine store

Current review-page behavior:
- session summary and mark grid
- inline save of student status and note edits
- oral-check review information is also rendered when present

## 15. Review scheduling model

`class_pattern_review` is now a first-class persistence concept.

Current intent:
- track pattern mastery at class level across attempts
- derive review urgency using weak-learner counts, Korean-transfer evidence, consecutive weak lessons, and due-gap logic
- support lesson-card review recommendations before the teacher opens the next lesson

Important implementation detail:
- startup rebuild is conservative and only runs when the table is empty
- a full wipe-and-replay exists behind `POST /admin/rebuild-review-records`

## 16. Tests that exist now

There is now a dedicated `tests/` directory.

Current test coverage includes:
- Alembic migration behavior
- auth/login behavior
- class ownership and soft-delete behavior
- lesson-route behavior
- admin-route behavior
- oral-check service behavior
- Kokoro TTS cache behavior

Notable tested cases:
- fresh-schema and legacy-schema Alembic upgrades
- bootstrap auth configuration and teacher ownership boundaries
- `/lesson/tts/prompt` success and failure handling
- oral checks blocking lesson completion until resolved
- dynamic-review lookup failing open instead of breaking lesson rendering
- TTS cache reuse and prune logic

## 17. Assets and supporting files

Current static assets include:
- lesson and base CSS
- `oral_prompt_helper.js`
- vocabulary images
- reader images
- some local phoneme audio assets

Current supporting/spec files in the repo root include:
- `BLOCK_07_ORAL_ENFORCEMENT_SPEC.md`
- `KOKORO_TTS_SETUP.md`
- `KI_INSERTION_MAP.md`
- `SPACED_REVIEW_ENGINE_SPEC.md`
- `STRICT_VALIDATOR_SPEC.md`
- `LUMINOS_COMMAND_SYSTEM_SPEC.md`

There is also a `scripts/` directory with validation and repair utilities, including strict lesson validation.

## 18. Current implementation boundaries

This repo currently implements:
- teacher-facing lesson delivery
- class roster management
- per-student and per-slide marking
- post-lesson review editing
- class-level review scheduling/recommendations
- KI intervention lesson inventory
- oral reading enforcement workflow
- local TTS-backed oral prompting

This repo still does not implement:
- student-device mode
- parent-facing views
- a full authoring CMS
- analytics dashboards
- speech recognition / ASR

## 19. Practical summary

Today `luminos-engine` is not just a simple lesson runner.
It is currently a teacher-facing literacy lesson system with:
- a JSON lesson library
- class-aware lesson launch
- dynamic review injection
- KI intervention sequencing metadata
- per-slide and per-student persistence
- enforced oral-check workflow for reading passages
- Kokoro-backed local TTS prompts
- post-lesson review and class-pattern scheduling state

Any future context or planning should start from that broader implemented surface, not from the earlier two-lesson / simple-overlay version of the project.
