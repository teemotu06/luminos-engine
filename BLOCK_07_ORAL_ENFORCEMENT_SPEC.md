# Block 07 Oral Enforcement Spec

## Purpose

This spec defines a production-ready oral participation and marking subsystem for Block 07 (`Decodable Reader / Fluency`) in Luminos Engine.

The goal is to shift the teacher role from primary instructor to runtime enforcer:

- Luminos controls who reads, in what order, under what task demand, and when the class may proceed.
- The teacher validates performance, manages behavior, and handles exceptions.

This is not a generic UI enhancement. It is an instructional control system with explicit participation guarantees, saved accountability data, and deterministic completion rules.

---

## Product Goals

1. Every student in a roster-connected class must receive an explicit participation outcome during Block 07.
2. Block completion must depend on oral participation resolution, not slide navigation alone.
3. Short readers must remain rigorous without artificial text padding.
4. Teacher interaction must remain low-friction and fast enough for live classroom use.
5. Saved data must be defensible to parents, school leaders, and future analytics.

---

## Non-Goals

1. Real-time automatic speech recognition.
2. Student self-marking.
3. Replacing teacher judgment on accuracy or fluency.
4. Generalizing the full subsystem across all blocks in v1.

---

## Existing Repo Anchors

- Block registry: `app/services/block_registry.py`
- Lesson runtime page: `app/templates/lesson/view.html`
- Teacher overlay: `app/templates/lesson/partials/teacher_overlay.html`
- Runtime controller: `app/static/lesson.js`
- Slide payload models: `app/schemas/slide_payloads.py`
- Marking schemas: `app/schemas/marking.py`
- Lesson models: `app/models/lesson.py`
- Lesson routes: `app/routers/lesson.py`

This feature is scoped to Block 07 first, with all behavior attached to Block 07 `read_respond` slides.

---

## Core Concept

Block 07 becomes a controlled oral-check runtime with explicit phases:

1. `model`
2. `rehearsal`
3. `individual_check`
4. `correction`
5. `reteach_queue`
6. `completion_gate`

The platform, not the teacher, controls the queue and resolution state.

---

## Participation Modes

### 1. `full_roster`

Default mode for normal-length readers.

- Every present student must complete one required oral performance.
- Weak students may be queued for a correction reread.
- Block cannot complete until all students are resolved.

### 2. `short_reader_full_roster`

Default mode when the reader text is too short to distribute fairly across students.

- Every present student must still participate.
- Students are assigned micro-performances instead of unique chunks.
- Each student produces at least two evidence events by default.

### 3. `audit_roster`

Optional time-compressed mode.

- Only a selected subset of students is individually checked.
- Selection is platform-controlled and stored.
- Mode must be visibly differentiated from `full_roster`.

### Mode Selection Rule

V1 mode selection rule:

- If `oral_enforcement.participation_mode` is explicitly set, use that.
- Else:
  - use `short_reader_full_roster` when `text_length_mode == "short"`
  - otherwise use `full_roster`

---

## Performance Types

Supported performance types in v1:

- `read_accuracy`
- `reread_fluency`
- `track_and_read`
- `meaning_check`
- `correction_reread`

### Usage Rules

For normal readers:

- default initial performance type: `read_accuracy`
- weak students may receive `correction_reread`

For short readers:

- each student must receive `read_accuracy`
- each student must receive one additional evidence event by default
- second event selection order:
  1. `reread_fluency`
  2. `meaning_check`
  3. `track_and_read`

If a student is weak on the first event:

- second event becomes `correction_reread` instead of enrichment

---

## Status Model

### Assignment Statuses

Assignment-level statuses:

- `pending`
- `active`
- `secure`
- `shaky`
- `missed`
- `deferred`
- `absent`

### Final Resolution Statuses

Student resolution for the block:

- `secure`
- `shaky`
- `missed`
- `deferred`
- `absent`

### Notes

- `skipped` should not be used for Block 07 oral accountability.
- `deferred` means the teacher intentionally could not assess the student during the live block.
- `absent` means not present and counts as resolved for gating.

---

## Completion Rules

### `full_roster`

A Block 07 oral-check slide is complete only if:

1. every roster student has a final resolution status, and
2. no student remains `pending` or `active`, and
3. any student marked `missed` has either:
   - completed an immediate correction attempt, or
   - been explicitly finalized as `missed`, and
4. unresolved count is zero

### `short_reader_full_roster`

Complete only if:

1. every roster student has a final resolution status, and
2. every present student has completed the required evidence count, unless:
   - the teacher explicitly finalizes as `missed`, `deferred`, or `absent`

### `audit_roster`

Complete only if:

1. all selected students are resolved, and
2. required sample size is met, and
3. mode is stored as `audit_roster`

### Lesson Completion Rule

The lesson cannot be finalized if any Block 07 oral-enforcement slide is unresolved.

---

## Teacher Workflow

### Normal Reader

1. Teacher enters Block 07 slide.
2. Luminos displays `model` instructions.
3. Luminos starts a bounded `rehearsal` timer.
4. Luminos enters `individual_check`.
5. Current student and task are shown on screen.
6. Teacher taps one status.
7. Luminos advances automatically.
8. Weak students are added to `reteach_queue`.
9. Teacher resolves reteach queue.
10. Luminos unlocks advancement once roster is resolved.

### Short Reader

1. Whole-class model.
2. Rehearsal timer.
3. Student performs `read_accuracy`.
4. Teacher marks outcome.
5. Luminos assigns second evidence event or correction reread.
6. Teacher marks final outcome.
7. Student is resolved.

---

## UI Requirements

## Board Surface

The main board-facing view must display:

- current text
- current phase
- current student name
- current performance type prompt
- rehearsal timer
- correction cue when relevant
- completion progress

The board should never require the teacher to choose the next student.

## Teacher Control Surface

Add a Block 07-specific oral control section to the lesson runtime.

Required elements:

- current phase indicator
- current student card
- current performance type
- one-tap status actions:
  - `secure`
  - `shaky`
  - `missed`
  - `deferred`
  - `absent`
- queue preview
- reteach queue preview
- block completion progress
- explicit override controls

The existing generic roster float panel is insufficient for v1 oral enforcement and should not be the primary control surface for this flow.

---

## Frontend Runtime State

Add a dedicated oral enforcement state object inside `lessonShell` in `app/static/lesson.js`.

### Proposed Shape

```js
oralCheck: {
  enabled: false,
  slideId: "",
  blockId: "07",
  participationMode: "full_roster",
  textLengthMode: "normal",
  phase: "idle", // idle | model | rehearsal | individual_check | correction | reteach_queue | complete
  roster: [],
  assignments: [],
  activeAssignmentId: "",
  activeStudentName: "",
  activePerformanceType: "",
  rehearsalSecondsRemaining: 0,
  requiredEvidenceCount: 1,
  completedStudentCount: 0,
  unresolvedStudentCount: 0,
  reteachQueueIds: [],
  teacherOverrideRequired: false,
  sessionStatus: "idle", // idle | in_progress | complete
}
```

### Assignment Shape

```js
{
  assignmentId: "",
  studentName: "",
  performanceType: "read_accuracy",
  attemptNumber: 1,
  queueOrder: 0,
  status: "pending",
  requiresReteach: false,
  resolvedInBlock: false,
  overrideReason: "",
}
```

---

## Payload Changes

Extend `ReadRespondPayload` in `app/schemas/slide_payloads.py`.

### New Models

```python
from typing_extensions import Literal

class OralEnforcementConfig(BaseModel):
    enabled: bool = False
    participation_mode: Literal[
        "full_roster",
        "short_reader_full_roster",
        "audit_roster",
    ] = "full_roster"
    text_length_mode: Literal["normal", "short"] = "normal"
    rehearsal_seconds: int = 30
    required_evidence_count: int = 1
    allow_teacher_override: bool = True
    require_resolution_for_all: bool = True
    fluency_retry_on_shaky: bool = True
    auto_queue_missed_for_reteach: bool = True
    audit_sample_size: int = 0
    performance_types: List[str] = Field(default_factory=list)
```

Then add to `ReadRespondPayload`:

```python
oral_enforcement: Optional[OralEnforcementConfig] = None
```

### Constraints

- Only valid on Block 07 `read_respond` slides in v1.
- `required_evidence_count` must be at least `2` when `text_length_mode == "short"` unless explicitly overridden.
- `audit_sample_size` must be greater than `0` only when `participation_mode == "audit_roster"`.

---

## Backend Data Model

Add two new records to `app/models/lesson.py`.

### `OralCheckSessionRecord`

Purpose: one runtime oral-check session per attempt + slide.

Fields:

- `id`
- `attempt_id`
- `lesson_id`
- `slide_id`
- `block_id`
- `participation_mode`
- `text_length_mode`
- `required_evidence_count`
- `roster_size`
- `required_student_count`
- `resolved_student_count`
- `unresolved_student_count`
- `session_status`
- `created_at`
- `updated_at`

Constraints:

- unique on `(attempt_id, slide_id)`

### `OralCheckAssignmentRecord`

Purpose: each assigned oral event for a student.

Fields:

- `id`
- `session_id`
- `attempt_id`
- `lesson_id`
- `slide_id`
- `block_id`
- `student_name`
- `performance_type`
- `attempt_number`
- `queue_order`
- `status`
- `requires_reteach`
- `resolved_in_block`
- `teacher_note`
- `override_reason`
- `created_at`
- `updated_at`

Indexes:

- `(session_id, queue_order)`
- `(attempt_id, slide_id, student_name)`

### Relationship to Existing `StudentMarkRecord`

Keep `StudentMarkRecord` for the final per-student result, but use the new oral tables as the source of runtime truth.

V1 persistence rule:

- every oral assignment is saved in `OralCheckAssignmentRecord`
- when a student reaches final resolution, upsert a `StudentMarkRecord`

This preserves compatibility with current review logic while giving Block 07 enough structure.

---

## API Design

Add dedicated oral-check routes in `app/routers/lesson.py`.

### 1. Start Session

`POST /lesson/{lesson_id}/oral-check/session/start`

Request:

```json
{
  "attempt_id": "uuid",
  "lesson_id": "G1-L1",
  "slide_id": "07-1",
  "block_id": "07",
  "roster": ["지원", "Minho", "Yuna"]
}
```

Response:

```json
{
  "session_id": "uuid",
  "participation_mode": "full_roster",
  "text_length_mode": "normal",
  "phase": "model",
  "required_student_count": 3,
  "required_evidence_count": 1,
  "assignments": [
    {
      "assignment_id": "uuid",
      "student_name": "지원",
      "performance_type": "read_accuracy",
      "attempt_number": 1,
      "queue_order": 0,
      "status": "pending"
    }
  ]
}
```

### 2. Mark Assignment

`POST /lesson/{lesson_id}/oral-check/assignment/mark`

Request:

```json
{
  "session_id": "uuid",
  "assignment_id": "uuid",
  "status": "shaky",
  "teacher_note": "",
  "override_reason": ""
}
```

Response:

```json
{
  "assignment_id": "uuid",
  "student_name": "지원",
  "status": "shaky",
  "requires_reteach": true,
  "student_resolved": false,
  "next_assignment_id": "uuid",
  "session_status": "in_progress",
  "resolved_student_count": 1,
  "unresolved_student_count": 2
}
```

### 3. Resolve Student Exception

`POST /lesson/{lesson_id}/oral-check/student/resolve`

Use for:

- `deferred`
- `absent`
- explicit teacher override finalization

Request:

```json
{
  "session_id": "uuid",
  "student_name": "지원",
  "final_status": "deferred",
  "override_reason": "Behavior disruption"
}
```

### 4. Get Session State

`GET /lesson/{lesson_id}/oral-check/session/{attempt_id}/{slide_id}`

Returns full runtime session state for recovery and refresh.

### 5. Complete Session

`POST /lesson/{lesson_id}/oral-check/session/complete`

Server validates completion rules. If unresolved students remain, return `400`.

---

## API Schema Additions

Add Pydantic request/response models in `app/schemas/marking.py` or a new `app/schemas/oral_check.py`.

Recommended new schema file:

- `app/schemas/oral_check.py`

Models:

- `OralCheckSessionStartRequest`
- `OralCheckAssignmentSummary`
- `OralCheckSessionResponse`
- `OralCheckAssignmentMarkRequest`
- `OralCheckAssignmentMarkResponse`
- `OralCheckStudentResolveRequest`
- `OralCheckCompleteRequest`
- `OralCheckSessionStateResponse`

Recommendation: use a new schema file. Do not overload `marking.py` further.

---

## Service Layer

Add a new service:

- `app/services/oral_check_service.py`

Functions:

- `start_oral_check_session(...)`
- `build_initial_assignments(...)`
- `select_audit_sample(...)`
- `mark_assignment(...)`
- `resolve_student_exception(...)`
- `queue_reteach_assignment(...)`
- `determine_next_assignment(...)`
- `refresh_session_counts(...)`
- `validate_session_completion(...)`
- `complete_session(...)`

### Key Invariants

1. only one active oral session per attempt + slide
2. assignment mark writes are idempotent
3. final student resolution is derived from assignment outcomes plus explicit exception resolution
4. session counts are recomputed server-side, not trusted from frontend

---

## Queue Logic

### `full_roster`

Initial queue:

- one `read_accuracy` assignment per roster student
- queue order follows roster order in v1

Weakness handling:

- `missed` always queues `correction_reread`
- `shaky` queues `correction_reread` only if `fluency_retry_on_shaky == true`

### `short_reader_full_roster`

Initial queue:

- one `read_accuracy` assignment per roster student

Second-pass queue:

- after first-pass resolution, generate second evidence event for all present students not finalized as `missed`, `deferred`, or `absent`
- second pass defaults to `reread_fluency` unless configured otherwise

Weakness handling:

- if first pass is `shaky` or `missed`, second event becomes `correction_reread`

### `audit_roster`

Initial queue:

- select sample deterministically
- v1 deterministic rule:
  - previously weak students first, if such data is available
  - otherwise first `audit_sample_size` students by roster order

---

## Phase Logic

### `model`

Frontend-only phase before oral checking begins.

### `rehearsal`

Bounded timer phase.

Rules:

- default duration from payload config
- teacher may manually skip

### `individual_check`

Active queue consumption phase.

Rules:

- exactly one active assignment at a time
- teacher marks current assignment
- frontend requests next assignment from server response

### `correction`

Transient phase shown when a weak student is being corrected.

Can be represented in v1 as a UI state driven by next assignment type `correction_reread`.

### `reteach_queue`

Shown when primary queue is consumed and weak students remain queued.

### `complete`

Reached only after server confirms zero unresolved students.

---

## Frontend Changes

### `app/static/lesson.js`

Add:

- oral-check state bootstrapping
- session start call when entering Block 07 slide with `oral_enforcement.enabled`
- local state hydration from session response
- mark action handlers
- next-assignment activation
- completion polling / fetch
- advancement lock

Add methods:

- `isOralCheckSlide(slideIndex)`
- `startOralCheck(slideIndex, slideId, blockId)`
- `loadOralCheckState(slideIndex, slideId)`
- `markOralAssignment(status)`
- `resolveOralStudent(studentName, finalStatus, overrideReason)`
- `advanceOralPhase()`
- `canAdvanceFromActiveSlide()`

### Navigation Gate

Modify next-slide navigation:

- if active slide is oral-check enabled and unresolved, prevent `goToNextSlide()`
- surface a user-visible reason, for example:
  - `Cannot advance: 4 students unresolved`

### `app/templates/lesson/partials/teacher_overlay.html`

Add Block 07 conditional rendering for oral enforcement.

Sections:

- phase
- current student
- current task
- progress
- status buttons
- reteach queue
- defer / absent controls

### `app/templates/lesson/view.html`

Pass sufficient serialized slide metadata for Block 07 oral config, either:

- through existing slide payload rendering, or
- through data attributes on slide frames

Recommendation:

- add `data-oral-enforcement-enabled`
- add `data-oral-participation-mode`
- add `data-oral-text-length-mode`

---

## Review Page Impact

The review page should eventually show:

- participation mode
- per-student final status
- performance types completed
- reteach occurrences
- deferred / absent counts

V1 minimum:

- ensure final `StudentMarkRecord` remains populated so existing review remains functional

V2:

- enrich `app/services/review_service.py` to read oral session detail

---

## Validation Rules

### Content Validation

Add Block 07 validation in slide payload validation layer.

Rules:

1. `oral_enforcement.enabled` may only appear on Block 07 `read_respond` slides in v1.
2. `required_evidence_count >= 2` when `text_length_mode == "short"` unless an explicit override flag is later added.
3. `performance_types` must be a subset of supported performance types.
4. `audit_sample_size > 0` only when `participation_mode == "audit_roster"`.

### Runtime Validation

1. roster must be non-empty for `full_roster` and `short_reader_full_roster`
2. session start must fail if no roster is attached and oral enforcement is required
3. session complete must fail when unresolved students remain
4. assignment mark must fail if assignment is not part of the active session

---

## Failure Behavior

### No Roster Attached

If oral enforcement is enabled and no class roster exists:

- do not silently downgrade
- block session start
- show clear teacher-facing message:
  - `Roster required for Block 07 oral enforcement`

### Page Refresh Mid-Session

Use `GET session state` endpoint to rehydrate runtime.

### Network Failure During Mark

- do not advance local queue optimistically without server confirmation
- show an error state and allow retry

### Teacher Override

Overrides must always require:

- explicit final status
- explicit `override_reason`

---

## Migration Plan

### Database Migration

Add new tables:

- `oral_check_session`
- `oral_check_assignment`

No destructive migration to existing tables is required.

### Content Migration

No immediate bulk lesson rewrite required.

V1 content authoring can start by adding `oral_enforcement` only to targeted Block 07 slides.

---

## Rollout Plan

### Phase 1

Backend foundation:

- new schemas
- new models
- new service
- new routes

### Phase 2

Frontend runtime:

- session start
- queue handling
- marking controls
- advancement gating

### Phase 3

Short reader mode:

- second evidence pass
- correction reread routing

### Phase 4

Review/reporting enrichment

### Phase 5

Audit mode

Recommendation: do not implement `audit_roster` until `full_roster` and `short_reader_full_roster` are stable.

---

## Acceptance Criteria

The implementation is correct only if all of the following are true:

1. A roster-connected Block 07 oral-enforcement slide cannot be completed with unresolved students.
2. Every student in `full_roster` receives a saved final status.
3. Every present student in `short_reader_full_roster` receives the configured evidence count unless explicitly finalized as `missed`, `deferred`, or `absent`.
4. Weak students are queued for correction according to config.
5. The teacher never chooses the next student manually in the default flow.
6. A refresh mid-session can recover current oral-check state.
7. Existing review behavior still works through final `StudentMarkRecord` persistence.
8. No oral-enforcement slide may run without an attached roster.

---

## Open Implementation Decisions

These should be decided before coding begins:

1. Whether queue order in v1 is strictly roster order or may interleave by prior weakness.
2. Whether `shaky` should always trigger a retry in normal readers or only when configured.
3. Whether the board should display student names publicly in all classroom contexts.
4. Whether second evidence for short readers defaults to `reread_fluency` only or rotates among configured types.

Recommended v1 answers:

1. roster order
2. configurable, default `true`
3. yes
4. default to `reread_fluency`

---

## Recommended First Implementation Slice

Implement the narrowest valuable version first:

1. Block 07 `full_roster`
2. one `read_accuracy` assignment per student
3. one correction reread assignment for `missed`
4. final status persistence
5. next-slide gating

Then expand to:

6. `short_reader_full_roster`
7. second evidence event
8. richer review reporting

This keeps the system shippable while preserving the architecture needed for the full design.
