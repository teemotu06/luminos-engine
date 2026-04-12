# Project Context

This document is a descriptive snapshot of the current implemented state of `luminos-engine`.
It is not the product spec. It is the operational map of what exists in the codebase now.

Use it to answer:
- what surfaces the app currently has
- how lesson delivery currently works
- how authoring is wired
- how teacher control and board synchronization currently behave
- what slide types now exist
- what persistence and migration assumptions the code relies on

If this file diverges from the code, the code wins.

## 1. Source-of-truth order

1. Repository code and tests
2. Active migration chain in `alembic/versions/`
3. This file
4. Older mockups/spec documents

## 2. Current product shape

`luminos-engine` is no longer just a lesson runner.
It is now a teacher-facing literacy lesson platform with four main surfaces:

- Lesson library / launcher
- Lesson authoring
- Teacher control
- Student board

The current implementation also includes:
- class and roster management
- per-slide and per-student marking
- class-session state for the detached board
- command-state for teacher lesson progression
- local media upload for authoring
- Kokoro-backed TTS prompt generation
- dynamic review injection and KI lesson insertion

## 3. Stack

- Backend: FastAPI
- Templates: Jinja2
- Frontend state: Alpine.js
- ORM: SQLAlchemy 2.x
- Validation: Pydantic 2
- Migrations: Alembic
- Primary DB: PostgreSQL
- Test DB: SQLite
- Audio playback: browser audio + Howler-backed flows where applicable
- Static asset build: `scripts/build_static.py`

Key runtime libraries declared in `requirements.txt` include:
- `fastapi`
- `jinja2`
- `sqlalchemy`
- `alembic`
- `pydantic`
- `psycopg2-binary`
- `python-multipart`
- `httpx`
- `uvicorn`
- `soundfile`
- `numpy`
- `sentry-sdk[fastapi]`

## 4. Entry points and app boot

App entrypoint:
- `app/main.py`

Current startup behavior:
- loads DB config from `DATABASE_URL`
- sets up template environment
- mounts `/static`
- mounts `/tts-cache`
- includes routers for auth, lessons, classes, students, admin, authoring, and media
- installs request/security/rate-limit middleware
- can bootstrap auth users when auth is enabled
- can initialize Sentry
- can prewarm or prune TTS cache depending on env

Current important mounted/served paths:
- `/static`
- `/tts-cache`

Current important routers:
- `app/routers/auth.py`
- `app/routers/lesson.py`
- `app/routers/classes.py`
- `app/routers/students.py`
- `app/routers/admin.py`
- `app/routers/authoring.py`
- `app/routers/authoring_media.py`
- `app/routers/teach.py`

## 5. Core architecture split

There are now two distinct runtime state systems:

### 5.1 Command state

Used for teacher lesson flow and generic reveal/progression behavior.

Primary files:
- `app/services/command_state_service.py`
- `app/schemas/command_state.py`
- `app/routers/lesson.py`

This drives:
- active slide selection
- advance/reveal state
- teacher control progression
- board projections for generic reveal-based slides

### 5.2 Class session state

Used for detached board synchronization and interactive slide states that need class-level persistence.

Primary files:
- `app/services/class_session_service.py`
- `app/routers/classes.py`
- `app/models/lesson.py`

This now drives:
- current board slide projection
- `drag_letter` manual selection state
- `spell_word` manual selection state
- `pattern_noticing` reveal count
- detached board render payloads

This split matters:
- if a slide only depends on generic reveal/hide, command state may be enough
- if a slide has interactive selection state that must survive polling and sync to the board, it now needs class-session persistence

## 6. Database and persistence

Primary model file:
- `app/models/lesson.py`

Current important persisted tables/entities:
- `app_user`
- `class_group`
- `student_record`
- `lesson`
- `lesson_attempt`
- `slide_result`
- `student_mark`
- `oral_check_session`
- `oral_check_assignment`
- `lesson_runtime_state`
- `class_pattern_review`
- `class_session`

Current important `class_session` persisted fields include:
- `class_id`
- `lesson_id`
- `attempt_id`
- `current_slide_id`
- `status`
- `paused`
- `display_message`
- `letter_reveal_count`
- `letter_reveal_slide_id`
- `pattern_noticing_reveal_count`
- `pattern_noticing_slide_id`
- `spell_word_selection`
- `spell_word_slide_id`
- `drag_letter_selection`
- `drag_letter_selection_slide_id`
- optimistic/version timestamps

Important persistence behavior:
- opening a lesson creates a `lesson_attempt`
- teacher progression state persists
- board session state persists per class
- roster marking persists independently of slide-level marking
- review scheduling state is persisted across attempts

## 7. Migration chain

Current migration chain includes:
- `20260402_0001_baseline_schema.py`
- `20260402_0002_optimistic_locking.py`
- `20260402_0003_class_pattern_review_fk.py`
- `20260402_0004_auth_and_soft_delete.py`
- `20260403_0001_runtime_student_outcomes.py`
- `20260408_0001_class_session_control_plane.py`
- `20260409_0001_widen_slide_id_columns.py`
- `20260409_0002_drag_letter_reveal.py`
- `20260409_0003_spell_word_selection.py`
- `20260409_0004_pattern_noticing_reveal.py`
- `20260409_0005_drag_letter_selection.py`

Operational rule:
- if the app code references new `class_session` columns and the DB is not at head, teacher/class routes will fail
- after pulling schema changes, run:

```bash
cd /Users/tanioramotu/luminos-engine
. .venv/bin/activate
alembic upgrade head
```

## 8. Content system

Lessons live under:
- `app/content/lessons/`

Groups live under:
- `app/content/groups.json`

Backups created by authoring currently land in:
- `app/content/lesson_backups/`

Current inventory on disk:
- G1 through G10 lesson JSON files
- KI intervention lessons

The lesson runtime still assumes canonical block structure from `BLOCK_REGISTRY`, but runtime behavior can now be filtered or specialized per lesson.

Implemented special-case runtime behavior:
- `G1-L1` starts from Block `03` at runtime
- Blocks `01` and `02` are structurally present but skipped for runtime navigation

## 9. Slide-type system

Slide types are now formalized through a registry.

Primary files:
- `app/slide_types/base.py`
- `app/slide_types/registry.py`
- `app/slide_types/__init__.py`
- `app/slide_types/definitions/*.py`

Current implemented slide types in the registry include:
- `audio_prompt`
- `connect_word_to_picture`
- `drag_letter`
- `drag_word`
- `fill_in_the_blank`
- `flashcard`
- `minimal_pair`
- `pattern_noticing`
- `phonemes`
- `quick_check`
- `read_respond`
- `sentence_builder`
- `spell_word`
- `word_sort`
- `writing_encoding`

Notes on newer/important types:

### Flashcard
- side-based model
- `front_text`, `front_image`, `back_text`, `back_image`
- one content mode per side is enforced
- generic legacy `image` handling was cleaned up

### Phonemes
- large single-card board presentation
- symbol on board
- audio-driven teacher control

### Drag Letter / Build the Word
- authoring supports simplified grapheme-unit input
- teacher manual placement now syncs to the board
- `Letter Answer` assisted reveal exists
- `Reset` clears board + teacher state
- board and teacher show green/red correctness feedback when full

### Spell the Word
- separate from `writing_encoding`
- central answer box with surrounding letters
- teacher manual placement syncs to the board
- green/red correctness feedback exists
- `Reset` clears both teacher and board

### Pattern Noticing
- new dedicated type for Morpheme Moment / shared-part spotting
- replaces prior `read_respond` + `display_mode: "spot_part"` usage
- authoring uses bracket notation such as `s[at]`
- teacher action reveals the pattern
- board now shows words immediately and reveals highlight styling progressively

### Read & Respond
- dedicated board rendering now exists
- if image exists, image is prominent and sentence sits below it
- if no image exists, sentence is centered and prominent
- comprehension is now driven through teacher prompts rather than a separate visible comprehension field in authoring

## 10. Authoring system

Authoring is now a first-class surface.

Primary files:
- `app/routers/authoring.py`
- `app/routers/authoring_media.py`
- `app/services/lesson_authoring_service.py`
- `app/services/slide_editor_service.py`
- `app/services/lesson_backup_service.py`
- `app/templates/authoring/base.html`
- `app/templates/authoring/lessons/*.html`
- `app/templates/authoring/media/*.html`
- `app/static/authoring.js`

Current authoring capabilities:
- lesson list
- create lesson
- open lesson editor
- add/reorder/delete slides
- block-based editing
- type-specific form rendering
- upload and attach media
- save slide
- save lesson with backup creation

Current authoring UX rules that were recently implemented:
- slide editing is grouped into distinct visual sections:
  - Board Section
  - Audio Attachment
  - Teacher Instructions Section
  - Teacher Prompts Section
  - Tracking
- helper copy is hidden behind clickable section headers instead of being always visible
- `Save Slide` and `Cancel` live in a sticky slide editor header
- `Teacher Preview` and `Board Preview` were removed from the visible slide form
- `Validate` was removed from the visible lesson-level controls

### Media attachment pattern

Main-editor media now follows a single-attached-asset model.

For slide audio:
- main editor shows only current attachment or empty state
- upload/replace opens file picker directly
- old library items are not shown inline

For top-level image fields:
- same attached-asset pattern
- current image card or empty state
- upload/replace rather than inline library browsing

### Teacher instructions simplification

Visible authoring fields were reduced.

Removed from visible authoring teacher-instruction UI:
- `Slide Title`
- `Students Should`
- `If They Struggle`
- `Notes`

Important implementation detail:
- some of these still post as hidden values to avoid wiping legacy data or breaking save contracts

## 11. Teacher control surface

Primary files:
- `app/templates/lesson/teacher.html`
- `app/static/lesson_teacher.js`
- `app/routers/lesson.py`

Current teacher shell behavior:
- opens against a lesson attempt and optional class
- supports board detachment/open
- shows slide actions based on slide type and runtime state
- has simplified `TEACHER` disclosure instead of always-open instruction clutter
- has redesigned navigation cards for slide/block

Important recent behavior:
- teacher prompts are clickable and can still trigger audio-backed behavior
- prompt buttons now use full width and wrap instead of truncating
- navigation now shows:
  - slide dots + count
  - block label + count

### Action mapping

Teacher control actions are not uniform across all slide types.

Examples:
- `flashcard` uses answer/hide reveal flow
- `phonemes` uses `Play Sound`
- `drag_letter` uses `Letter Answer`, manual tile placement, reset, and marking
- `spell_word` uses answer/hide, manual placement, reset, and marking
- `pattern_noticing` uses `Reveal Pattern`

Operational rule:
- new slide types should not modify shared action behavior for existing slide types
- regressions in teacher control usually mean shared action plumbing was touched when it should have been isolated

## 12. Student board surface

Primary files:
- `app/templates/classes/board.html`
- `app/services/class_session_service.py`
- `app/routers/classes.py`

Current board behavior:
- detached board polls class session state
- board rerenders only when relevant state changes
- board polling now includes cache-busting query params
- board flashing was reduced by relaxing poll cadence and preventing no-op rerenders

Current board-specific rendering rules of note:
- flashcards render only board-owned content, not teacher-only copy
- `Build the Word` and `Spell the Word` show interactive correctness state
- `Read & Respond` no longer ignores image attachments
- `Pattern Noticing` no longer shows the prompt on the board

### Theme support

Teacher and board now have explicit light/dark theme toggles.

Important styling fix already applied:
- `Spell the Word` letters needed explicit dark text fill in dark theme so the letters do not disappear

## 13. Class control surface

Primary files:
- `app/templates/classes/control.html`
- `app/routers/classes.py`
- `app/services/class_session_service.py`

Current role:
- launch teacher flow for a class
- create or reuse active class session
- manage board link and teacher entrypoint

This is now the normal starting point for class-aware lesson delivery.

## 14. Marking model

There are multiple distinct marking paths.

### Slide/class marking
Stored in:
- `slide_result`

Used for:
- class response marking
- quick-check aggregate status

### Per-student roster marking
Stored in:
- `student_mark`

Used for:
- teacher roster interactions during lesson
- review edits
- oral-check resolution

### Oral-check marking
Stored in:
- `oral_check_session`
- `oral_check_assignment`

### Mark Students visibility rule

This rule matters and was explicitly corrected:
- if authoring/slide config marks the slide as markable, teacher control shows `MARK STUDENTS`
- if not, teacher control must not invent it

## 15. Oral-check and review scheduling

Still implemented and still active.

Primary files:
- `app/services/oral_check_service.py`
- `app/services/review_scheduler_service.py`
- `app/services/review_service.py`
- `app/services/pattern_noticing_service.py`

Still true:
- oral-check can block lesson completion
- class pattern review persists across attempts
- review recommendations can affect runtime lesson presentation

## 16. Local TTS

Primary files:
- `app/services/kokoro_tts_service.py`
- `app/routers/lesson.py`

Current behavior:
- prompt text is normalized and hashed
- generated files are cached on disk
- TTS can be prewarmed or pruned
- teacher/oral prompt flows can fetch audio on demand

Related env vars include:
- `LUMINOS_TTS_CACHE_DIR`
- `LUMINOS_TTS_PREWARM_ENABLED`
- `LUMINOS_TTS_STRICT_STARTUP`
- `LUMINOS_TTS_CACHE_PRUNE_ON_STARTUP`
- `KOKORO_VOICE`
- `KOKORO_SPEED`
- `KOKORO_SAMPLE_RATE`

## 17. Assets and uploads

Static source:
- `app/static/`

Built assets:
- `app/static/dist/`

Uploads currently land under:
- `app/static/uploads/audio/`
- `app/static/uploads/images/`

Important operational rule:
- after changing `app/static/authoring.js`, `app/static/lesson_teacher.js`, `app/static/lesson.css`, or `app/static/styles.css`, rebuild static assets so the served bundle matches source

Typical command:

```bash
cd /Users/tanioramotu/luminos-engine
. .venv/bin/activate
python scripts/build_static.py
```

## 18. Tests

There is now substantial test coverage under `tests/`.

Important areas covered:
- Alembic migrations
- auth and class routes
- authoring routes and end-to-end flows
- media upload flows
- slide type registry
- teacher control behavior
- teacher/board session sync
- new slide types
- lesson authoring services

Files of note:
- `tests/test_alembic_migration.py`
- `tests/test_auth_and_class_routes.py`
- `tests/test_authoring_editor_routes.py`
- `tests/test_authoring_end_to_end.py`
- `tests/test_authoring_media_routes.py`
- `tests/test_flashcard_payload.py`
- `tests/test_new_slide_types.py`
- `tests/test_new_types_authoring_integration.py`
- `tests/test_teacher_control_marking.py`
- `tests/test_teacher_shell_session_sync.py`

## 19. Known operational pitfalls

These are current practical pitfalls, not abstract risks.

### 19.1 Migrations must be current

If routes start failing with missing column errors on `class_session`, the DB is behind the code.
Run:

```bash
alembic upgrade head
```

### 19.2 Static bundle staleness

If teacher or authoring behavior does not match source code:
- rebuild static assets
- hard refresh browser
- sometimes restart the dev server

This was a repeated source of confusion during recent teacher/control work.

### 19.3 Shared control-path regressions

Teacher control has generic action plumbing plus slide-specific branches.
If a new slide type changes shared action resolution instead of being isolated, existing blocks can regress.

Safe rule:
- additive behavior for new slide types
- do not rewrite shared teacher action behavior unless necessary

### 19.4 Board sync is split by mechanism

Not every board interaction is driven the same way.

Examples:
- generic reveal slides rely on command-state/runtime projection
- `drag_letter`, `spell_word`, and `pattern_noticing` now rely on class-session persisted state

When debugging board/teacher mismatches, identify which state path the slide uses first.

## 20. Current repo boundaries

Currently implemented:
- teacher-facing lesson delivery
- class-aware control and detached board
- authoring UI for lesson editing
- media upload/attachment for authoring
- slide-type registry with specialized slide renderers
- per-slide and per-student marking
- post-lesson review/editing
- review scheduling
- KI insertion metadata
- oral-check enforcement
- local TTS generation

Not implemented as first-class product surfaces:
- student device workflow
- parent-facing surfaces
- analytics dashboards
- speech recognition / ASR
- a public multi-user content CMS beyond the current authoring editor

## 21. Practical summary

As of the current branch state, `luminos-engine` should be understood as:

- a JSON-driven literacy lesson system
- with a formal authoring surface
- a teacher control plane
- a detached synchronized board
- a slide-type registry instead of ad hoc template branching
- PostgreSQL-backed runtime/session persistence
- Alembic-managed schema evolution
- media attachment and backup-aware lesson editing

Any future work should assume this broader architecture.
Do not plan against the older “simple lesson player” mental model.
