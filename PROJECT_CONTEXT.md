# Project Context

## 1. Project overview

Luminos is currently a FastAPI-based lesson engine for rendering structured literacy lessons from JSON content through server-rendered Jinja templates. This file is a continuity summary only, not the product definition or implementation authority.

The present focus is improving lesson flow inside the Luminos lesson engine while keeping implementation aligned to LUMINOS Lesson Engine Spec v3.1.

## 2. Source-of-truth hierarchy

1. LUMINOS Lesson Engine Spec v3.1: final source of truth for engine behavior and lesson flow.
2. LUMINOS_Blueprint_v6: instructional design reference only; it may clarify lesson intent but does not override the spec.
3. Repository implementation: current working code and runtime behavior to be understood and extended in alignment with the spec.
4. PROJECT_CONTEXT.md: working summary for continuity across chats only.

## 3. Current architecture

- FastAPI app entrypoint in `app/main.py`.
- Lesson routes in `app/routers/lesson.py`.
- Lesson content loaded from JSON in `app/content/lessons/`.
- Pydantic schemas define lesson, block, slide, and payload shapes in `app/schemas/`.
- Services handle lesson loading, block validation, payload validation, and slide flattening in `app/services/`.
- Rendering is server-side Jinja with a lesson shell in `app/templates/lesson/view.html`.
- View selection is template-driven through block and view partials under `app/templates/lesson/partials/`.
- Frontend interaction state lives in `app/static/lesson.js`.

## 4. Current working state

- Lesson shell is working.
- Arrow-key navigation is working.
- Space-to-reveal behavior is working.
- Presentation mode is working.
- Flashcard reveal is fixed to use shared `lessonShell` state.
- Lesson navigation is slide-index based using `/lesson/{lesson_id}?slide_index={n}`.
- The current repo includes one sample lesson JSON: `g1_l1_u1_lesson_1`.
- CEFR placement engine exists in the wider platform context.
- DECODE diagnostic exists in the wider platform context.

## 5. Active frontend patterns

- Alpine powers the lesson shell and slide interactions.
- Shared shell state currently includes `presentationMode`, `revealed`, and audio playback helpers.
- Keyboard controls are centralized in `lessonShell()`.
- Slide navigation is full-page navigation via previous/next links, not client-side routing.
- Interaction views are isolated by `view_type` partials such as flashcard, drag letter, drag word, quick check, audio prompt, minimal pair, read/respond, and writing/encoding.
- Audio playback is handled in the frontend through Howler usage inside `lesson.js`.

## 6. Current lesson engine status

- Core lesson rendering loop is in place: load lesson -> validate -> flatten slides -> render current slide.
- Block sequence is constrained by the block registry for the 10-block lesson model.
- Payload validation exists for supported slide types.
- The engine is in refinement mode rather than greenfield setup.
- Current goal is better lesson flow and tighter implementation alignment to Spec v3.1.

## 7. Known constraints

- Do not use this file as source of truth.
- Do not restate or reinterpret Spec v3.1 here; update the implementation against the spec directly.
- Do not treat LUMINOS_Blueprint_v6 as an implementation spec.
- Keep architecture descriptions limited to what is present in the repo.
- Current navigation is request-based, so shell state is page-local and resets on slide change.
- Current repo state appears to be a standalone lesson engine, not the placement or diagnostic system.

## 8. Immediate next priorities

- Improve lesson flow inside the existing shell without breaking current navigation, reveal, or presentation behavior.
- Keep all lesson-engine changes explicitly aligned to LUMINOS Lesson Engine Spec v3.1.
- Continue refining view templates and shell behavior within the current FastAPI + Jinja + Alpine architecture.
- Preserve modular boundaries between routes, services, schemas, content, templates, and frontend state.
