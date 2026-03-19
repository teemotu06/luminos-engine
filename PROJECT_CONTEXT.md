# Project Context

## 1. Purpose of this file

This file is a working continuity summary of the current implemented state of the `luminos-engine` repository.
It is not the product authority. It exists so future work can start from the current runtime reality instead of outdated assumptions.

Use this file to understand:
- what architecture is actually implemented
- how the lesson engine currently runs
- how marking and completion currently work
- what each lesson block is currently doing in the sample lesson

Do not use this file to override the formal product spec.

## 2. Source-of-truth hierarchy

1. `LUMINOS Lesson Engine Spec v3.1`
2. Repository implementation in this repo
3. `PROJECT_CONTEXT.md`

Notes:
- `PROJECT_CONTEXT.md` should describe the implementation as it exists now.
- If the repo diverges from the spec, this file should state the implemented behavior clearly, not reinterpret the spec.

## 3. Current stack

- Backend: FastAPI
- Templates: Jinja2
- Frontend interaction: Alpine.js
- Audio playback: Howler.js
- Typography: Inter (UI), Cormorant Garamond (display/titles), IBM Plex Mono (grapheme/phoneme) — all via Google Fonts, loaded in `base.html`
- Persistence: SQLAlchemy + PostgreSQL (`psycopg2-binary`)
- Database: PostgreSQL — `luminos_engine` database on `localhost:5432`
- Content layer: lesson JSON files in `app/content/lessons/`
- Static assets: `app/static/`
  - `styles.css` — CSS design tokens, base styles, lesson header, chrome, launcher, class selector, student profile
  - `lesson.css` — all lesson component styles (2900+ lines)
  - `lesson.js` — Alpine.js `lessonShell()`, `reviewShell()`, `dragBuild()` components + `lessonRoster` Alpine store

## 4. App entry and startup behavior

- App entrypoint: `app/main.py`
- Static files are mounted at `/static`
- Routers mounted: `lesson_router`, `students_router`, `classes_router`
- On startup:
  - `python-dotenv` loads `.env` via `app/db.py`
  - `DATABASE_URL` is read from the environment — app raises `RuntimeError` if not set
  - SQLAlchemy creates all tables via `Base.metadata.create_all()`
  - Startup migration: adds `class_id` column to `lesson_attempt` if it doesn't exist (safe no-op if already present)
  - Lesson metadata is synced from JSON files into the `lesson` table

## 5. Database configuration

- **Engine**: PostgreSQL (`postgres:16`)
- **Container**: `platform-postgres` Docker container
- **Host**: `localhost:5432`
- **Database**: `luminos_engine` — isolated, not shared with other projects
- **User**: `luminos`
- **Tables created on startup**: `lesson`, `lesson_attempt`, `slide_result`, `student_mark`, `student`, `class`
- **`app/db.py`**: central DB setup — calls `load_dotenv()`, reads `DATABASE_URL` from env, raises clearly if missing
- **`.env`**: gitignored local file — must contain `DATABASE_URL=postgresql://luminos:luminos@localhost:5432/luminos_engine`
- **`.env.example`**: committed — documents the expected format
- **No Alembic yet** — schema is managed by `create_all()` + startup migration shim

## 6. Current route surface

### Lesson routes (`app/routers/lesson.py`)
- `GET /` — redirects to `/lesson/`
- `GET /lesson/` — teacher-facing lesson launcher page; class selector at top; grouped lesson list
- `GET /lesson/{lesson_id}` — renders full lesson shell; creates new attempt
- `GET /lesson/{lesson_id}/block/{block_id}` — same shell, starts at first slide of that block
- `POST /lesson/{lesson_id}/mark` — receives slide mark payload; writes slide result; updates attempt summary
- `POST /lesson/{lesson_id}/student-mark` — upserts a `StudentMarkRecord` for one student × slide
- `DELETE /lesson/{lesson_id}/student-mark` — deletes a `StudentMarkRecord` (used when cycling back to unmarked)
- `POST /lesson/{lesson_id}/complete` — sets `attempt.completed = True`; navigates to review on success
- `GET /lesson/{lesson_id}/review/{attempt_id}` — post-lesson review screen with mastery summary and editable student marks

### Student routes (`app/routers/students.py`)
- `GET /students/{student_name}` — student profile page showing all historical marks grouped by lesson

### Class routes (`app/routers/classes.py`)
- Class management routes (create, list, detail)

## 7. Current data model and persistence

Implemented database tables:

- `lesson` — lesson metadata synced from JSON
- `lesson_attempt` — one attempt record per lesson run; has `class_id` column for roster association
- `slide_result` — one stored result per slide per attempt
- `student_mark` (`StudentMarkRecord`) — one record per student × slide × attempt; stores `status`, `error_tags` (nullable JSON), `teacher_note`
- `student` (`StudentRecord`) — student registry
- `class` (`ClassRecord`) — class registry; holds roster JSON

Current persistence behavior:
- Opening a lesson creates a new `lesson_attempt`
- Slide marks write or update a `slide_result`
- Student marks write or update a `student_mark` via POST; DELETE removes the record
- `StudentMarkRecord.error_tags` is nullable (no error tags are collected in the current teacher overlay — field reserved for review editing)
- Attempt `completed` is set via the dedicated `/complete` endpoint (not via the mark payload)
- Attempt summary is recalculated after each slide mark

Current recommendation logic:
- `secure` → `move_on`
- `shaky` → `move_on`
- `missed` → `repeat`
- If a learner key exists and repeated phoneme trouble is found across consecutive lessons, recommendation can escalate to `support`

## 8. Current lesson content contract

Current lesson files:
- one JSON file per lesson
- two implemented lessons: `G1-L1.json`, `G1-L2.json`

Current implemented lesson schema shape:
- lesson-level fields: `lesson_id`, `unit_id`, `target_pattern`, `title`, `korean_interference_active`, `content_pack_status`, `json_path`
- blocks keyed by block id strings: `"01"` through `"10"`
- each block: `block_id`, `label`, `slides`
- each slide: `slide_id`, `block_id`, `slide_title`, `view_type`, `content_payload`, `teacher_cue`, `expected_response`, `correction_move`, `observation_note`, `korean_interference_flag`, `markable`, `marking_options`, `next_action`

## 9. Block registry and allowed view types

The lesson engine enforces:
- fixed 10-block order
- fixed block labels
- allowed view types per block

Current allowed view types by block:
- `01` Flashcard Phoneme Review — `flashcard`, `audio_prompt`, `quick_check`
- `02` Listening & Write Review — `audio_prompt`, `writing_encoding`, `quick_check`
- `03` New Sound Introduction — `flashcard`, `audio_prompt`, `minimal_pair`, `read_respond`
- `04` Vocabulary Warm-Up — `flashcard`, `audio_prompt`, `minimal_pair`, `read_respond`
- `05` Word Building — `drag_letter`, `flashcard`, `read_respond`, `writing_encoding`
- `06` Sentence Bridge — `read_respond`, `drag_word`, `audio_prompt`
- `07` Decodable Reader / Fluency — `read_respond`, `audio_prompt`, `quick_check`
- `08` Encoding & Writing — `writing_encoding`, `audio_prompt`, `quick_check`
- `09` Morpheme Moment — `flashcard`, `drag_word`, `read_respond`
- `10` Meaning-Making Close — `read_respond`, `quick_check`

## 10. Current rendering model

Current runtime lesson model:
- the full lesson is rendered once into the page
- all slides exist in the DOM
- Alpine controls which slide is currently shown
- navigation does not reload the page

Current lesson render flow:
1. Load lesson JSON
2. Validate schema, block order, and payloads
3. Flatten all slides in canonical block order
4. Create a lesson attempt
5. Render the lesson shell with all slides
6. Alpine controls in-page navigation, reveal states, audio, and marking

## 11. Current frontend shell behavior

Primary shell state lives in `app/static/lesson.js`.

### `lessonShell` component
All lesson interactivity. Key state:
- `activeSlideIndex` — currently displayed slide
- `presentationMode` — toggles teacher overlay and floating roster button visibility
- `slideMarks` — class-level slide marks (status per slide index)
- `studentMarks` — per-student marks keyed by `[slideIndex][studentName]`
- `quickCheckMarks` — quick-check item state
- `roster` — array of student names from the loaded class
- `classLabel` — display name of the loaded class (NOTE: config key is `className`, internal property is `classLabel` — `className` is a reserved DOM property and must not be used as an Alpine reactive key)

Key methods:
- `cycleStudentMark(studentName, slideId, blockId)` — cycles `""→secure→shaky→missed→skipped→""`, auto-DELETEs on cycle back to `""`
- `setAndSubmitSlideMark(slideIndex, option, slideId, blockId)` — sets class response status and immediately POSTs (no confirm button)
- `finishLesson()` — POSTs to `/lesson/{id}/complete` then navigates to review screen
- `togglePresentationMode()` — toggles mode, closes floating roster panel when switching back to teacher mode

### `lessonRoster` Alpine store
Registered in `alpine:init` in `lesson.js`. Bridges the floating roster panel (rendered at body level, outside the lesson card) to `lessonShell` state.

State:
- `shell` — reference set to `this` in `lessonShell.init()`
- `panelOpen` — controls floating panel visibility
- Getters: `roster`, `classLabel`, `presentationMode` — all proxied from `shell`
- `getStudentStatus(student)` — reads `shell.studentMarks[activeSlideIndex][student]`
- `cycleStudent(student)` — calls `shell.cycleStudentMark(...)` for the current slide

### `reviewShell` component
Post-lesson review screen interactivity.
- Initialised with server-rendered `marks` dict (keyed `"slide_id__student_name"`)
- `openEdit(slideId, studentName)` / `saveEdit(...)` / `closeEdit()` — inline edit panel
- Edit panel: status buttons + note textarea only (no error tags)
- POSTs to `/lesson/{id}/student-mark`

Current keyboard controls:
- `P` — toggle presentation mode
- `R` — toggle reveal
- `ArrowLeft` — previous slide
- `ArrowRight` — next slide
- `Space` — reveal / next-step behavior depending on slide mode

## 12. Current teacher overlay behavior

The teacher overlay is visible when presentation mode is off.
It renders as the left column of the 2-column grid on desktop (≥ 1100px), `304px` wide.
In presentation mode the overlay column is hidden; the content column expands to full width.

Current mode toggle labels:
- Teacher mode (overlay visible): button reads **"Presentation Mode"** (click to enter)
- Presentation mode (overlay hidden): button reads **"Teacher Mode"** (click to return)

Current overlay DOM structure:
- `teacher-overlay__header` — block ID + label (meta-primary), slide title (meta-secondary)
- `teacher-overlay__section--primary` — teacher cue (largest text in overlay)
- `teacher-overlay__section--guidance` — Expected response, Correction move, Watch for
- `teacher-overlay__section--flag` — Korean interference banner (amber tint, only when present)
- `teacher-overlay__section--roster` — student roster badges (on every slide, including non-markable)
- `teacher-overlay__section--marking` — Class Response buttons (on every slide except `lesson_close`):
  - "Got it" / "Mixed" / "Revisit" buttons (label mapping: `secure`/`shaky`/`missed`)
  - Tapping a button immediately saves (no confirm button)
  - Section label: "Class response"
  - No error tags, no Korean Transfer checkbox, no teacher note, no confirm button

No marking is shown on `lesson_close` slides (Block 10). The Finish & Review button in `slide_nav.html` is sufficient.

Block progress bar:
- drag-to-scroll via mousedown/mousemove/mouseup
- `hasDragged` guard prevents click events from firing after a drag

## 13. Current block progress / tab row behavior

- Shows all 10 blocks as pill buttons
- Uses active slide's `block_id` to determine active state
- Allows direct jump to first slide in each block
- Horizontally scrollable; drag-to-scroll enabled; scrollbar hidden
- Hidden in presentation mode

## 14. Current floating roster (presentation mode)

In presentation mode, a small fixed **"Roster"** button appears at `position: fixed; bottom: 24px; right: 24px; z-index: 1000`.

Tapping opens a compact panel at `position: fixed; bottom: 72px; right: 24px; z-index: 1000; width: 220px`.

Panel contents:
- Class name in the header
- Close (×) button
- Student list — each row shows student name + current status badge for the active slide
- Tapping a student cycles their mark (same `secure→shaky→missed→skipped→""` cycle as teacher mode)

The button and panel are rendered at body level via `{% block body_panels %}` in `base.html` — completely outside the lesson card div. They use `$store.lessonRoster` to communicate with `lessonShell`.

The projected screen (main content) is unaffected — only the Roster button is visible in the corner. Students do not see the panel unless the teacher opens it.

## 15. Current post-lesson review screen

Route: `GET /lesson/{lesson_id}/review/{attempt_id}`
Template: `app/templates/lesson/review.html`
Alpine component: `reviewShell`

Layout:
- "Session summary" section: mastery status chip + recommendation label
- Block-by-block student mark grid
- Each student badge shows status color + dashed border if unmarked + note dot indicator
- Tapping a badge opens an inline edit panel (status buttons + note textarea; no error tags)
- "Done" link returns to lesson library

## 16. Current visual design system

CSS variables are defined in `styles.css` and referenced throughout `lesson.css`.

### Palette

The current palette is warm earth tones. The `--c-blue` alias points to the primary accent colour (terracotta).

Current token values:
- `--bg: #efe8df` — warm parchment page background
- `--surface: #fbf7f0` — card surfaces
- `--surface-strong: #fffdf9` — elevated card surfaces
- `--surface-muted: #f3ebdf` — recessed/muted surfaces
- `--accent: #b66636` — primary terracotta accent
- `--accent-strong: #995022` — darker accent for hover/active states
- `--c-blue: #b66636` — semantic alias for primary accent
- `--c-blue-hover: #995022` — hover state
- `--c-blue-light: rgba(182, 102, 54, 0.08)` — tinted backgrounds
- `--c-blue-mid: rgba(182, 102, 54, 0.18)` — active border tints
- `--c-border: #ddd0bf` — warm border
- `--c-border-strong: #cfbda9` — stronger border
- `--c-text: #171411` — near-black warm text
- `--c-text-muted: #685d52` — secondary text
- `--c-text-tertiary: #a09284` — tertiary/label text
- `--max-width: 1320px` — page container cap
- `--radius: 18px` — base border radius
- Status: green (`#166534`), amber (`#92400e`), red (`#991b1b`) with matching `*-bg` and `*-border` variants

### Typography

Three-font system:
- `--font-sans: "Inter"` — UI chrome, overlays, labels, navigation
- `--font-serif: "Cormorant Garamond"` — display text, lesson titles
- `--font-mono: "IBM Plex Mono"` — grapheme and phoneme display

### Layout
- Page background: `radial-gradient` light bloom at top + `linear-gradient` warm fade
- Two-column on desktop (≥ 1100px): `304px` teacher overlay + `minmax(0, 1fr)` content
- Single-column in presentation mode (overlay hidden, content full width)
- All primary CTAs use `translateY(-1px)` on hover

## 17. Current implemented view library

Implemented view types: `flashcard`, `audio_prompt`, `minimal_pair`, `drag_letter`, `drag_word`, `read_respond`, `writing_encoding`, `quick_check`

### `flashcard`
- text front/back, optional image-first, optional audio, reveal toggle
- optional `blend_units` mode: `{grapheme, phoneme?, audio?}` array; Blend button steps through units with per-unit audio

### `audio_prompt`
- audio play/replay, optional reveal text, optional image

### `minimal_pair`
- pair audio playback, Korean interference display, answer key hidden in presentation mode

### `drag_letter`
- unit-based slot arrays, chunk builds, check/reset/reveal, green/red feedback

### `drag_word`
- sentence-level drag build, check/reset/reveal

### `read_respond`
- sentence mode, reader mode, spot-part mode, blend-reveal-next flow, optional illustration, optional comprehension prompt, font-size controls

### `writing_encoding`
- sentence and word-level dictation, reveal displays answer in boxes, box count tied to answer or configured count

### `quick_check`
Two branches:
- **Generic quick-check**: item-level statuses, error tags, Korean Transfer toggle, confirm mark
- **`lesson_close`**: one oral prompt at a time, back/next/restart navigation only — no marking controls (lesson is completed via the Finish & Review button in `slide_nav.html`)

## 18. Current marking model

### Overlay class response path
Used on every slide except `lesson_close`.

Behavior:
- Teacher taps one of three buttons: Got it (secure) / Mixed (shaky) / Revisit (missed)
- Mark saves immediately on tap — no confirm button
- Section label: "Class response"
- No error tags, no Korean Transfer, no teacher note at slide level

### Student roster path
Present on every slide (including non-markable ones).

Behavior:
- Roster shows all students in the loaded class
- Tapping a student badge cycles status: `""→secure→shaky→missed→skipped→""`
- Cycling back to `""` sends a DELETE to remove the record
- All other states POST to `/lesson/{lesson_id}/student-mark`

### Quick-check item path
Used by generic `quick_check` slides.

Behavior:
- Teacher marks each item
- Aggregate slide status derived from worst item status
- Item-level data submitted as `item_results`

## 19. Current completion behavior

Lesson completion:
- Teacher taps **"Finish & review"** in `slide_nav.html` (visible on the last slide)
- `finishLesson()` POSTs to `/lesson/{id}/complete` (sets `attempt.completed = True`)
- Browser navigates to the review screen at `/lesson/{id}/review/{attempt_id}`

The old `Complete Lesson` button in the `lesson_close` quick_check view has been removed. Block 10 only shows oral prompts; completion is entirely handled by the Finish & Review button.

## 20. Class selector on launcher

The launcher page (`GET /lesson/`) includes a class selector at the top.

Behavior:
- Styled card with label + "Manage" link + `<select>` dropdown
- Disabled placeholder option as the first `<option>`
- Selecting a class sets `class_id` on the attempt and loads the class roster into the lesson shell
- Roster flows through to the teacher overlay and the floating roster panel

## 21. Current assets

Current local image assets:
- vocabulary images in `app/static/images/vocab/`
- decodable reader illustrations in `app/static/images/readers/`

Audio references exist in lesson content. Not all referenced audio files may be present locally.

## 22. Current implementation boundaries

This repo currently behaves as:
- a standalone lesson engine
- a teacher-facing lesson delivery and marking system
- a student mark history tracker (student profile pages)
- two lesson implementations (`G1-L1`, `G1-L2`) with full 10-block coverage

This repo does not currently implement:
- student-device mode
- parent views
- analytics dashboards
- authoring CMS
- speech recognition
- adaptive branching beyond the current recommendation logic

## 23. Current lessons

Two lessons at `content_pack_status: draft`.

### G1-L1 — Group 1, Lesson 1: s, a, t

**Block 01** — Flashcard Phoneme Review (1 slide) — not markable
**Block 02** — Listening & Write Review (1 slide) — not markable
**Block 03** — New Sound Introduction (3 slides) — markable: `/s/`, `/æ/`, `/t/`
**Block 04** — Vocabulary Warm-Up (3 flashcard slides with `blend_units`): `sat`, `at`, `a` — not markable
**Block 05** — Word Building (3 drag-letter slides): `sat`, `at`, `as` — markable
**Block 06** — Sentence Bridge (1 slide): `I sat.` — markable
**Block 07** — Decodable Reader (1 slide): `I sat.` reader mode — markable
**Block 08** — Encoding & Writing (3 slides): `sat`, `at`, `a` — markable
**Block 09** — Morpheme Moment (1 slide): spot_part `sat`/`at` — not markable
**Block 10** — Meaning-Making Close (1 slide): lesson_close, 4 oral prompts

### G1-L2 — Group 1, Lesson 2: i

**Block 01** — Flashcard Phoneme Review (3 slides): reviews `s`, `a`, `t`
**Block 02** — Listening & Write Review (3 slides): encoding review
**Block 03** — New Sound Introduction (1 slide): `/ɪ/` — markable
**Block 04** — Vocabulary Warm-Up (4 flashcard slides with `blend_units`)
**Block 05** — Word Building (3 drag-letter slides) — markable
**Block 06** — Sentence Bridge (3 slides)
**Block 07** — Decodable Reader (1 slide)
**Block 08** — Encoding & Writing (3 slides) — markable
**Block 09** — Morpheme Moment (1 slide): spot_part
**Block 10** — Meaning-Making Close (1 slide): lesson_close

## 24. Known implementation notes and constraints

- `className` is a reserved DOM property — Alpine reactive data must use `classLabel` instead. Config object passed to `lessonShell()` still uses `className` as the key; it is immediately aliased to `classLabel` inside the component.
- `StudentMarkRecord.error_tags` is nullable; error tags are not currently collected in the lesson flow (field is reserved for future use).
- Block progress bar drag-to-scroll uses a `hasDragged` boolean guard to prevent clicks from firing after a drag gesture.
- The `lessonRoster` Alpine store is registered in `alpine:init` and wired to `lessonShell` in `init()`. The store is the only channel between the body-level floating roster panel and the lesson shell scope.
- Server runs on port 8001 (port 8000 is used by another project).
- No Alembic — `class_id` column migration is handled by a startup shim in `main.py`.

## 25. Current practical summary

The system is currently operating as:
- Teacher-facing lesson launcher at `/lesson/` with class selector
- Full lesson shell with 2-column teacher overlay (teacher mode) / full-width clean display (presentation mode)
- Floating Roster button in presentation mode for discreet per-student marking
- Auto-saving class response on every slide (no confirm button)
- Per-student one-tap cycling marks synced to DB in real time
- Post-lesson review screen with mastery summary and inline mark editing
- Student profile pages showing full mark history
- Two draft lessons: G1-L1 (s·a·t) and G1-L2 (i)
- Polished warm earth-tone visual design system (three-font stack, terracotta accent, consistent component language)
