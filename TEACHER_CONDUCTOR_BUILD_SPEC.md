# Teacher As Conductor Build Spec

## Goal

Refactor the live lesson experience so the teacher phone behaves like a conductor console:

- one dominant action at a time
- almost no reading during live teaching
- board acts as a student-facing classroom surface
- system suggests moves, teacher confirms
- marking scales from 8 students to 25+

This spec is aligned to the current Luminos lesson runtime and templates rather than replacing them.

Current anchors in the codebase:

- teacher surface: `app/templates/lesson/teacher.html`
- board surface: `app/templates/lesson/board.html`
- teacher state client: `app/static/lesson_teacher.js`
- board state client: `app/static/lesson_board.js`
- runtime orchestration: `app/services/command_state_service.py`
- runtime schema: `app/schemas/command_state.py`

## Product Principle

The teacher should not manage a UI. The system should keep the lesson moving and ask for confirmation at the right moments.

The phone always answers one question:

- `What is the next thing I should do right now?`

The board always answers two questions:

- `What are students meant to do right now?`
- `Whose turn is it right now?`

## Runtime Model

### Current State

The current runtime already has useful primitives:

- `current_state`
- `prompt_text`
- `teacher_prompt_text`
- `current_student`
- `queue_position`
- `queue_total`
- `teacher_controls`
- `state_timeout_ms`
- `paused`
- `reteach_queue`

The gap is that the UI infers too much from these fields. The runtime should provide an explicit UI contract.

### Proposed UI Runtime Contract

Extend `CommandStateResponse` with these fields:

```py
ui_phase: Literal[
    "ready",
    "deliver",
    "observe",
    "mark_sequential",
    "mark_grid",
    "review",
    "complete",
]
primary_action: str
primary_action_label: str
primary_action_tone: Literal["brand", "success", "warning", "danger", "neutral"]
secondary_actions: list[str]
class_pulse: Literal["secure", "mixed", "at_risk", "neutral"]
marking_mode: Literal["none", "sequential", "grid"]
student_outcomes: dict[str, str]
pending_count: int
secure_count: int
mixed_count: int
revisit_count: int
focus_students: list[str]
board_banner_text: str
board_banner_tone: Literal["neutral", "focus", "celebrate", "warning"]
board_timer_visible: bool
board_progress_percent: int
recommendation: Optional[dict]
```

`recommendation` shape:

```json
{
  "type": "call_first|repeat_slide|pause_for_rehearsal|close_strong",
  "title": "Call on Alice and Sam first",
  "reason": "They were marked revisit on blends last session.",
  "accept_action": "apply_recommendation",
  "dismiss_action": "dismiss_recommendation"
}
```

### Phase Rules

Derive `ui_phase` from runtime, not from the template.

Rules:

1. `ready`
   - slide loaded, teaching not started
   - primary action: `begin_slide`

2. `deliver`
   - teacher needs to say or model something
   - primary action: `continue`

3. `observe`
   - timed student work or listening window
   - primary action: `pause` or `continue` when timer ends

4. `mark_sequential`
   - small-group cold call or oral check
   - primary action is implicit through the 3 outcome buttons

5. `mark_grid`
   - roster visible, tap-to-cycle outcomes
   - primary action: `next_slide` only when pending count is zero or teacher overrides

6. `review`
   - runtime generated suggestion
   - primary action: `repeat` or `next_slide`

7. `complete`
   - slide complete
   - primary action: `next_slide`

## Interaction Model

### Teacher Phone

Keep the three-zone structure permanently visible:

1. Context zone
   - slide position
   - slide title
   - active student or focus students
   - class pulse

2. Action zone
   - 60% of viewport
   - only one dominant visual task at a time

3. Override zone
   - previous
   - skip
   - pause
   - replay

### Action Zone by Phase

#### Ready

- show slide title
- show one short teacher framing line
- dominant button: `Begin slide`

#### Deliver

- large script text
- current student if relevant
- dominant button: `Continue`
- secondary actions move to override zone

#### Observe

- giant countdown
- one dim hint: `Eyes on the room`
- board mirrors a visible timer bar

#### Mark Sequential

- giant student name
- three oversized color outcomes:
  - green `Got it`
  - amber `Mixed`
  - red `Revisit`

#### Mark Grid

- all students visible at once
- one tap cycles:
  - `pending -> secure -> mixed -> revisit -> pending`
- completion bar at bottom
- dominant button locked until all marked, but teacher can still use `Skip unresolved`

#### Review

- one recommendation card only
- `Repeat this slide` or `Move on`

## Board Surface

The board should stop acting like a passive projector. It should become a classroom management surface.

### Persistent Board Regions

1. Header
   - lesson title
   - class name
   - slide progress

2. Main content stage
   - current slide content

3. Live progress rail
   - timer bar or progress bar

4. Student banner
   - `SAM - your turn`
   - recommendation-safe classroom cues only

### Board Behavior

- during `deliver`: show content and short directive
- during `observe`: show visible timer
- during `mark_*`: keep content visible, show current student banner or `Mark your class`
- when slide closes strong: show subtle class-level success state
- never reveal individual outcomes publicly

## Recommendations Engine

Start rules-based. Do not block launch on AI.

### Recommendation Inputs

- prior slide outcomes
- prior lesson outcomes by skill or pattern
- current slide target pattern
- revisit ratio on the current slide

### First-Round Rules

1. `call_first`
   - trigger when 1-3 students recently struggled with the same pattern

2. `repeat_slide`
   - trigger when `revisit + mixed >= 50%`

3. `pause_for_rehearsal`
   - trigger when many students are pending during grid marking after a threshold time

4. `close_strong`
   - trigger when `secure >= 80%`

### Teacher Contract

The system suggests. The teacher confirms.

Actions:

- `Yes`
- `Skip`

No autonomous lesson jumps in v1.

## Data Model Changes

### Extend `CommandStateResponse`

Add the fields listed in the runtime contract above.

### Add Teacher-Facing Grid Mark State

Persist per-slide, per-student outcomes so board/phone can recover after refresh.

Recommended persistence shape:

```py
student_outcomes: dict[str, Literal["pending", "secure", "mixed", "revisit", "absent", "deferred"]]
```

For roster-scale marking, do not rely only on `current_student`.

### Recommendation Persistence

Add lightweight runtime recommendation fields:

```py
active_recommendation_type: Optional[str]
active_recommendation_payload: Optional[dict]
active_recommendation_dismissed: bool
```

## API Changes

### Keep Existing Polling API

Current endpoints are good enough for v1:

- `GET /lesson/{lesson_id}/command-state/{attempt_id}`
- `POST /lesson/{lesson_id}/command-state/{attempt_id}`

### Extend Advance Actions

Current `CommandAction` is too narrow for the target UX. Add:

```py
CommandAction = Literal[
    "begin_slide",
    "continue",
    "mark",
    "mark_class",
    "mark_grid",
    "skip",
    "force_advance",
    "replay",
    "pause",
    "resume",
    "apply_recommendation",
    "dismiss_recommendation",
]
```

`mark_grid` request body:

```json
{
  "slide_id": "G1-L4-S3",
  "action": "mark_grid",
  "student": "Sam",
  "status": "mixed"
}
```

## Frontend Implementation Plan

### Phase 1: Runtime Contract

Files:

- `app/schemas/command_state.py`
- `app/services/command_state_service.py`

Work:

- add explicit `ui_phase`
- add `primary_action` and recommendation payloads
- add slide-level roster outcomes
- keep backward-compatible fields until templates are migrated

### Phase 2: Teacher Shell Refactor

Files:

- `app/templates/lesson/teacher.html`
- `app/static/lesson_teacher.js`
- `app/static/lesson.css`

Work:

- replace multi-button phase sections with one consistent three-zone shell
- move secondary actions into fixed override rail
- add grid marking mode
- keep sequential marking as fallback

### Phase 3: Board Upgrade

Files:

- `app/templates/lesson/board.html`
- `app/static/lesson_board.js`
- `app/static/lesson.css`

Work:

- add student callout banner
- add timer/progress rail
- add aggregate close-state feedback
- preserve existing slide stage rendering

### Phase 4: Recommendations

Files:

- `app/services/command_state_service.py`
- possibly new helper: `app/services/lesson_recommendation_service.py`

Work:

- compute rules-based recommendations
- expose only one recommendation at a time
- track accept/dismiss actions

### Phase 5: Post-Lesson Summary

Possible file:

- `app/templates/lesson/review.html`

Work:

- summarize secure/mixed/revisit by pattern
- surface at-risk students
- recommend repeat targets

## UI Details

### Visual Hierarchy

- dominant action must occupy the center of the phone viewport
- only one bright control at any time
- all passive status information moves to low-contrast rails
- use shape and placement before text density

### Color Contract

- secure: `#2f7a4b`
- mixed: `#c98522`
- revisit: `#b8473c`
- pending: neutral parchment
- brand action: existing Luminos warm ochre range

### Type Contract

- preserve high legibility tone from current teacher UI
- short, directive copy only
- no instructional paragraphs inside live states

## Acceptance Criteria

### Teacher Phone

- a teacher can run a slide using one thumb without scanning multiple panels
- each phase has one dominant action
- grid marking works for 25 students without opening subviews
- reconnecting or refreshing restores current phase and marks

### Board

- students can tell whose turn it is without the teacher repeating names
- students can see time remaining during observation phases
- slide progress is visible without showing marks publicly

### Runtime

- UI phase comes directly from the server payload
- no client-only inference for core lesson flow
- recommendation logic is deterministic and testable

## Risks

1. Polling frequency
   - current `250-500ms` polling may be noisy once grid updates increase
   - consider moving to SSE or websockets after the UX contract stabilizes

2. TTS request pressure
   - board prompt TTS can produce repeated `/lesson/tts/prompt` requests
   - cache by normalized text and only request on prompt change

3. Runtime ambiguity
   - if `ui_phase` is not explicit, teacher and board clients will drift again

## Recommended First Slice

Build this vertical slice first:

1. `ready`
2. `deliver`
3. `observe`
4. `mark_grid`
5. `review`
6. `next_slide`

This gets the real conductor interaction on one lesson path before broadening to all slide types.
