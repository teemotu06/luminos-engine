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
- Persistence: SQLAlchemy
- Default local database: SQLite via `sqlite:///./luminos_engine.db`
- Content layer: lesson JSON files in `app/content/lessons/`
- Static assets: `app/static/`

## 4. App entry and startup behavior

- App entrypoint: `app/main.py`
- Static files are mounted at `/static`
- Lesson router is mounted from `app/routers/lesson.py`
- On startup:
  - SQLAlchemy tables are created
  - lesson metadata is synced from JSON files into the database

Current startup behavior:
- The app creates the local DB schema on launch if needed
- The current lesson content is synced into the `lesson` table

## 5. Current route surface

Implemented lesson routes:
- `GET /`
  - simple health payload
- `GET /lesson/`
  - returns lesson index JSON
- `GET /lesson/{lesson_id}`
  - renders the full lesson shell
  - creates a new lesson attempt
- `GET /lesson/{lesson_id}/block/{block_id}`
  - renders the same full shell, but starts on the first slide for that block
  - creates a new lesson attempt
- `POST /lesson/{lesson_id}/mark`
  - receives a slide mark payload
  - writes slide results
  - updates the lesson attempt summary

## 6. Current data model and persistence

Implemented database tables:
- `lesson`
  - lesson metadata synced from JSON
- `lesson_attempt`
  - one attempt record per lesson run
- `slide_result`
  - one stored result per slide per attempt

Current persistence behavior:
- Opening a lesson creates a new `lesson_attempt`
- Marking writes or updates a `slide_result`
- Attempt summary is recalculated after each mark
- Completion is only set when a mark payload is submitted with `completed: true`

Current recommendation logic:
- `secure` -> `move_on`
- `shaky` -> `move_on`
- `missed` -> `repeat`
- If a learner key exists and repeated phoneme trouble is found across consecutive lessons, recommendation can escalate to `support`

## 7. Current lesson content contract

Current lesson files:
- one JSON file per lesson
- current sample lesson: `app/content/lessons/G1-L1.json`

Current implemented lesson schema shape:
- lesson-level fields:
  - `lesson_id`
  - `unit_id`
  - `target_pattern`
  - `title`
  - `korean_interference_active`
  - `content_pack_status`
  - `json_path` is populated at load time
- blocks are keyed by block id strings:
  - `"01"` through `"10"`
- each block contains:
  - `block_id`
  - `label`
  - `slides`
- each slide currently includes:
  - `slide_id`
  - `block_id`
  - `slide_title`
  - `view_type`
  - `content_payload`
  - `teacher_cue`
  - `expected_response`
  - `correction_move`
  - `observation_note`
  - `korean_interference_flag`
  - `markable`
  - `marking_options`
  - `next_action`

## 8. Block registry and allowed view types

The lesson engine enforces:
- fixed 10-block order
- fixed block labels
- allowed view types per block

Current allowed view types by block:
- `01` Flashcard Phoneme Review
  - `flashcard`, `audio_prompt`, `quick_check`
- `02` Listening & Write Review
  - `audio_prompt`, `writing_encoding`, `quick_check`
- `03` New Sound Introduction
  - `flashcard`, `audio_prompt`, `minimal_pair`, `read_respond`
- `04` Vocabulary Warm-Up
  - `flashcard`, `audio_prompt`, `minimal_pair`, `read_respond`
- `05` Word Building
  - `drag_letter`, `flashcard`, `read_respond`, `writing_encoding`
- `06` Sentence Bridge
  - `read_respond`, `drag_word`, `audio_prompt`
- `07` Decodable Reader / Fluency
  - `read_respond`, `audio_prompt`, `quick_check`
- `08` Encoding & Writing
  - `writing_encoding`, `audio_prompt`, `quick_check`
- `09` Morpheme Moment
  - `flashcard`, `drag_word`, `read_respond`
- `10` Meaning-Making Close
  - `read_respond`, `quick_check`

## 9. Current rendering model

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

## 10. Current frontend shell behavior

Primary shell state lives in `app/static/lesson.js`.

Current shell capabilities:
- in-page slide navigation
- block jump navigation
- shared reveal state
- presentation mode toggle
- audio playback via Howler
- drag build interactions
- teacher-side mark state
- quick-check item state
- POSTing marks to backend

Current keyboard controls:
- `P`
  - toggle presentation mode
- `R`
  - toggle reveal
- `ArrowLeft`
  - previous slide
- `ArrowRight`
  - next slide
- `Space`
  - reveal / next-step behavior depending on slide mode

## 11. Current teacher overlay behavior

The teacher overlay is visible when presentation mode is off.

Current overlay structure:
- compact block/slide meta header
- teacher cue as the primary instruction
- grouped guidance area
  - expected response
  - correction move
  - observation note
- Korean interference banner when present
- marking controls for markable slides

Current block-specific behavior:
- most markable slides show status buttons, error tags, Korean Transfer checkbox, note field, and confirm button in the overlay
- Block 10 currently uses a compact overlay mode
  - cue remains visible
  - guidance is reduced to a lighter watch-for area
  - overlay marking is not shown for Block 10 because Block 10 is no longer `markable`

## 12. Current top block tab row behavior

The block row:
- shows all 10 blocks
- uses the current active slide’s block to determine active state
- allows direct jump to the first slide in each block

Current UX characteristics:
- larger tab width than earlier versions
- better spacing for longer block names
- active state remains visually strong

## 13. Current implemented view library

Implemented view types:
- `flashcard`
- `audio_prompt`
- `minimal_pair`
- `drag_letter`
- `drag_word`
- `read_respond`
- `writing_encoding`
- `quick_check`

Current notable behavior by view:

### `flashcard`
- supports text front/back
- supports image-first front side
- supports audio replay
- reveal toggles within the card
- used for phoneme review and vocabulary warm-up

### `audio_prompt`
- supports audio play / replay
- supports optional reveal text
- supports optional image

### `minimal_pair`
- supports pair audio playback
- supports Korean interference display
- answer key is hidden in presentation mode

### `drag_letter`
- uses unit-based slot arrays
- slot count is driven by `slots` first, then falls back to `target_letters`
- supports chunk builds such as `r | a | ck`
- includes check / reset / reveal
- visual feedback:
  - green success state
  - red incorrect state

### `drag_word`
- sentence-level drag build
- supports check / reset / reveal

### `read_respond`
- supports sentence mode
- supports reader mode
- supports spot-part mode
- supports blend-reveal-next flow for word blending
- supports optional illustration/image in reader mode
- supports optional comprehension prompt
- supports font-size controls

### `writing_encoding`
- supports sentence dictation presentation
- supports word-level dictation slides
- for word dictation:
  - prompt text can be omitted
  - answer is not shown initially
  - reveal displays answer inside boxes
  - box count is dynamic and tied to answer or configured box count

### `quick_check`
- has two branches:
  - generic quick-check rubric branch
  - `lesson_close` branch
- generic quick-check:
  - item-level statuses
  - error tags
  - Korean Transfer toggle
  - confirm mark button
- lesson-close:
  - one oral prompt at a time
  - back / next / restart
  - final close rating appears only at the end
  - complete lesson button submits the final result

## 14. Current sample lesson (`G1-L1`) block-by-block behavior

### Block 01: Flashcard Phoneme Review

Current state:
- one flashcard slide
- reviews known sound `s`
- front shows grapheme
- reveal shows `/s/`
- audio available
- not markable

### Block 02: Listening & Write Review

Current state:
- five separate word dictation slides
- words:
  - `sat`
  - `tap`
  - `map`
  - `bat`
  - `hit`
- each slide:
  - one word only
  - audio play / replay
  - students write on paper or whiteboard
  - answer reveals inside the same writing boxes
- markable

### Block 03: New Sound Introduction

Current state:
- one flashcard slide introducing `/a/`
- markable
- Korean interference flag active for `vowel_quality`

### Block 04: Vocabulary Warm-Up

Current state:
- five image-led flashcard slides
- words:
  - `pie`
  - `pizza`
  - `puzzle`
  - `price`
  - `pirate`
- front side is image-first
- audio models the word
- reveal shows print
- not markable

### Block 05: Word Building

Current state:
- four drag-letter slides
- words:
  - `pat`
  - `pizza`
  - `rack`
  - `pineapple`
- uses unit/chunk slot logic
- examples:
  - `pat` -> `p | a | t`
  - `rack` -> `r | a | ck`
  - `pizza` -> `p | i | zz | a`
  - `pineapple` -> `p | i | n | e | a | pp | le`
- generic visible title
- cleaner UI with no answer leakage
- markable

### Block 06: Sentence Bridge

Current state:
- one sentence-level read/respond slide
- reads `Pat sat.`
- font controls enabled
- markable

### Block 07: Decodable Reader / Fluency

Current state:
- one reader-mode read/respond slide
- text:
  - `Pat sat. Pat sat at a mat.`
- text remains the primary focus
- supporting illustration appears to the side
- comprehension prompt:
  - `Who sat at the mat?`
- font controls enabled
- markable

### Block 08: Encoding & Writing

Current state:
- one sentence-level writing/encoding slide
- dictated sentence:
  - `Pat sat.`
- reveal shows answer on a sentence board
- markable

### Block 09: Morpheme Moment

Current state:
- three read/respond `spot_part` slides
- whole-word horizontal comparison cards
- repeated chunk highlighted inside full words
- current comparisons:
  - `pat / sat` with `at`
  - `map / tap` with `ap`
  - `rack / back` with `ack`
- no check button
- passive guided pattern-noticing format
- not markable

### Block 10: Meaning-Making Close

Current state:
- one `quick_check` slide using `display_mode: "lesson_close"`
- prompt sequence:
  - one oral prompt at a time
  - back / next / restart controls
- final close mark is hidden until the end of the prompt flow
- final statuses:
  - `secure`
  - `shaky`
  - `missed`
- `Complete Lesson` button submits final mark with `completed: true`
- overlay is compact for this block
- not markable in the overlay

## 15. Current marking model

Two implemented marking paths exist:

### Overlay slide mark path
Used for ordinary markable slides.

Behavior:
- teacher selects one slide-level status
- optional error tags and Korean Transfer can be added
- optional teacher note can be entered
- confirm sends one slide result

### Quick-check item path
Used by generic `quick_check` slides.

Behavior:
- teacher marks each item
- aggregate slide status is derived from the worst item status
- item-level data is submitted as `item_results`

### Block 10 close path
Used only for `lesson_close`.

Behavior:
- teacher progresses through oral prompts
- final mark is shown only on the last prompt
- `Complete Lesson` sends one slide-level result with `completed: true`

## 16. Current completion behavior

Lesson completion currently happens when:
- the teacher submits Block 10 through the `lesson_close` complete action
- that POST includes `completed: true`

This means:
- ordinary slide marks do not complete the lesson
- Block 10 is the implemented end-of-lesson completion point

## 17. Current assets

Current local image assets include:
- vocabulary images in `app/static/images/vocab/`
- decodable reader illustration in `app/static/images/readers/`

Current audio references exist in lesson content, but this repo currently documents the paths rather than bundling a complete verified audio library for every referenced file.

## 18. Current implementation boundaries

This repo currently behaves as:
- a standalone lesson engine
- a lesson delivery and teacher-marking system
- a single-lesson sample implementation (`G1-L1`) with full 10-block coverage

This repo does not currently implement:
- student-device mode
- parent views
- analytics dashboards
- authoring CMS
- speech recognition
- adaptive branching beyond the current recommendation logic

## 19. Current known realities and constraints

- `PROJECT_CONTEXT.md` is descriptive only
- the repo is materially more advanced than earlier continuity summaries
- current navigation is in-page, not query-string slide navigation
- the current sample lesson is `G1-L1`, not the earlier lower-case sample file
- Block 10 now completes the lesson through the close flow
- some content references local static audio paths that may still require real media files to exist for full live playback

## 20. Current practical summary

The system is currently operating as:
- one FastAPI-rendered lesson shell
- one fully rendered lesson in the DOM
- Alpine-managed in-page classroom navigation
- teacher-guided instruction with presentation mode
- DB-backed attempt creation and slide-level marking
- one implemented sample lesson covering Blocks 01 through 10

The current product state is no longer just a shell.
It is now a functional classroom lesson runner with:
- content validation
- fixed block architecture
- implemented view library
- persistent attempt/mark storage
- end-of-lesson close/completion flow
