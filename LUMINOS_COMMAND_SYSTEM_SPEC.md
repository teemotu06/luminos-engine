# Luminos Command System Spec

## Goal

Replace the teacher as the primary source of instructional direction.

Luminos should:
- direct the class
- call on students
- sequence instructional moves
- trigger correction and follow-up
- manage pacing and transitions

The teacher should:
- enforce compliance
- verify what actually happened
- mark outcomes
- handle exceptions

This is not a UI tweak. It is a classroom operating model.

---

## Core Principle

The current `Luminos says` panel is a good control surface, but it is not yet a full teacher replacement layer.

The stronger system is:

1. `Board Command Layer`
Class-facing. This is what the students see and obey.

2. `Teacher Control Layer`
Teacher-facing. This is where the teacher marks, overrides, and inspects.

3. `Instruction State Engine`
The runtime brain that decides what Luminos is doing right now.

---

## Product Model

### 1. Board Command Layer

This is the authority surface.

It should not look like an app widget. It should feel like a classroom command system.

Default behavior:
- compact, low-noise command chip
- anchored on the board without disrupting the slide
- always shows what the class should do now

Expanded behavior:
- appears when a new action begins
- appears when an individual student is called
- appears when correction is required
- appears when the class is transitioning modes

The board layer should show:
- current class command
- current student when individual turn is active
- short action phrase
- optional supporting cue

Examples:
- `Everybody read together.`
- `James, your turn. Read.`
- `Stop. Try that again.`
- `Point to the word sat.`
- `Answer this: What did Pat do?`

The board layer should never expose teacher controls.

---

### 2. Teacher Control Layer

This is the operations surface.

It should be visually quieter than the board layer.

The teacher layer should contain:
- play / pause / replay
- mark buttons
- progress
- next-up queue
- reteach queue
- compact roster inspector
- override controls

The teacher should not need to:
- decide who goes next
- remember who has gone
- remember who needs reteach
- remember what the next instruction is

Luminos owns all of that.

---

### 3. Instruction State Engine

This is the real system upgrade.

Luminos should move through explicit classroom states rather than showing one generic prompt card.

Required states:
- `idle`
- `transition`
- `model`
- `choral`
- `partner_practice`
- `individual_turn`
- `correction`
- `fluency_reread`
- `comprehension_turn`
- `reteach_queue`
- `complete`

Each state should define:
- board message
- spoken script
- whether autoplay runs
- whether marking is required
- whether the teacher controls are active
- whether the class can advance

---

## State Definitions

### `idle`

Used before instruction starts or after a block resolves.

Board:
- small command chip only

Teacher:
- no mark buttons

Advance:
- allowed

### `transition`

Used when moving into a new instructional move.

Examples:
- `Get ready to read.`
- `Now answer the question.`

Board:
- brief visible transition cue

Teacher:
- no mark buttons

Advance:
- blocked until next state loads

### `model`

Luminos directs whole-class attention to a modeled example.

Examples:
- `Listen carefully.`
- `Watch and track.`

Teacher:
- no mark buttons

### `choral`

Whole-group response.

Examples:
- `Everybody read together.`
- `Class, say the sound.`

Teacher:
- no individual marks

### `partner_practice`

Short rehearsal period before accountability.

Examples:
- `Turn and practice.`
- `Practice with your partner.`

Teacher:
- timer only

### `individual_turn`

Core cold-call or required student response state.

Examples:
- `James, your turn. Read.`
- `Mina, answer this.`

Teacher:
- marks enabled
- next-up visible

Advance:
- blocked until mark

### `correction`

Immediate fix after error.

Examples:
- `Stop. Fix that sound.`
- `Try again from the beginning.`

Teacher:
- marks enabled after retry

### `fluency_reread`

Second pass for smoothness and automaticity.

Examples:
- `Read it again smoothly.`
- `Read with your eyes up and your voice clear.`

### `comprehension_turn`

Individual response to a question.

Examples:
- `What did Pat do?`
- `Point to the word sat.`

Teacher:
- marks enabled

### `reteach_queue`

Students who need follow-up are re-queued.

Board:
- clear correction framing

Teacher:
- queue visible

### `complete`

Block is done.

Board:
- short completion status

Teacher:
- advance enabled

---

## Interaction Design

### A. Command Chip

Default state.

Properties:
- compact
- persistent
- class-facing
- does not dominate the slide

Should contain:
- `Luminos`
- active instruction line
- optional progress dot or badge

### B. Command Sheet

Expanded state.

Opens when:
- a new instructional state begins
- a student is called
- a correction is required
- teacher manually expands

Contains:
- instruction line
- support line
- audio controls
- teacher controls
- optional roster section

Behavior:
- opens automatically for action-heavy states
- can collapse back into chip

### C. Teacher Control Strip

For some future blocks, this may become a tighter secondary strip instead of living inside the command sheet.

That would let the board layer stay purely instructional while the teacher gets a smaller operational rail.

---

## Language System

The voice must stop sounding like a generic assistant.

Use a disciplined classroom script system:

### Good
- `Everybody read together.`
- `James, your turn. Read.`
- `Stop. Try that again.`
- `Now answer this.`
- `Point to sat.`
- `Class, track with your finger.`

### Weak
- `James, please read the story.`
- `Please answer the question clearly.`
- `Please point and explain your answer.`

Rules:
- shorter lines
- more authoritative rhythm
- fewer polite filler words
- more classroom verbs
- instruction first, explanation second

---

## Block Strategy

### Block 01 to Block 03

Use Luminos as direct instructor:
- `What sound?`
- `Say it together.`
- `Write sat.`
- `Build the word.`

Usually no full roster enforcement, but individual turns can still exist.

### Block 04 to Block 06

Mix whole-group and individual checks:
- decode
- blend
- sentence reading
- rapid verification

### Block 07

Most advanced use case.

Luminos should run:
1. transition
2. choral read
3. individual reading turns
4. correction / fluency reread
5. comprehension turns
6. reteach queue if needed
7. complete

### Other blocks

Default to generic instruction mode first.

Only some blocks need:
- roster enforcement
- student-level marks
- queue logic

This means the system should separate:
- generic instruction layer
- accountability layer

Not every slide needs the full enforcement engine.

---

## Runtime Architecture

### Slide-level instruction config

Every slide can author:
- `luminos_says.prompt_text`
- `luminos_says.support_text`
- `luminos_says.auto_speak`

This already exists as the base direction.

### New state config

Add a higher-level runtime instruction shape:

```json
{
  "luminos_runtime": {
    "enabled": true,
    "default_state": "transition",
    "states": [
      { "key": "choral", "prompt": "Everybody read together." },
      { "key": "individual_turn", "prompt": "{name}, your turn. Read." },
      { "key": "comprehension_turn", "prompt": "{name}, {question}" }
    ]
  }
}
```

This should not replace existing payloads immediately.
It should layer on top of them.

---

## Commercial-Grade UX Direction

To feel teacher-like, the system needs:
- stronger board authority
- cleaner state transitions
- shorter scripts
- less panel feel
- less generic assistant language

The best commercial-grade version is:
- command chip by default
- expanded sheet when action is required
- board-facing instruction always visible
- teacher controls only when needed
- explicit classroom states

---

## Recommended Build Order

### Phase 1

Refactor current `Luminos says` into:
- `collapsed chip`
- `expanded command sheet`
- better teacher-like scripts

### Phase 2

Introduce state engine:
- `transition`
- `choral`
- `individual_turn`
- `correction`
- `comprehension_turn`

Use Block 07 first.

### Phase 3

Move board-facing command presentation out of the current generic panel framing.

Create:
- class-facing command chip/sheet
- teacher-facing control layer

### Phase 4

Generalize state-based Luminos direction to all blocks.

---

## Immediate Recommendation

The next strongest move is:

1. Convert `Luminos says` from a static panel into a `chip -> sheet` model.
2. Rewrite prompts into classroom command language.
3. Add explicit state labels internally.
4. Start with Block 07, then propagate the generic instruction layer across all blocks.

This is the path from:
- `assistant panel`

to:
- `machine teacher`

