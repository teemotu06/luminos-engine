# LUMINOS Lesson Engine — Project Context

## Purpose
This project is the standalone MVP for the **LUMINOS teaching presentation tool / lesson engine**.

It is being built separately from the placement system for now, with the intention to connect later.

Current goal:
- build the lesson engine cleanly
- keep architecture modular
- enforce the fixed LUMINOS lesson structure
- avoid mixed-purpose files

---

## Core Build Rules

### Structure rule
Keep every file single-purpose and small. One file should do one job only. If a file starts handling multiple concerns, split it immediately into a new router, service, schema, template partial, or utility module. Never mix routing, business logic, data models, and rendering logic in the same file.

### Design rule
Maintain one consistent design system across the whole app. Reuse the same layout structure, spacing, typography, colors, buttons, cards, and interaction patterns everywhere. Do not create one-off styles or page-specific UI patterns unless they are added back into the shared design system first.

### Build rule
Structure first, content second. Do not hardcode lesson content into templates. Lessons must be driven by JSON content files and validated by schema.

### Workflow rule
Give one instruction at a time. Do not overload steps. Keep implementation incremental and safe.

---

## Current Tech Stack
- FastAPI
- Jinja2 templates
- Pydantic
- local `.venv`
- local Uvicorn dev server
- Git + GitHub

Docker is **not** being used yet in this project.

---

## Current Project Folder Structure

```text
luminos-engine/
├── .gitignore
├── PROJECT_CONTEXT.md
├── requirements.txt
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── content/
│   │   └── lessons/
│   │       ├── G1-L1.json
│   │       ├── g1_l1_u1_lesson_1.json
│   │       └── g1_l1_u1_lesson_1_blocks.json
│   ├── routers/
│   │   ├── __init__.py
│   │   └── lesson.py
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── block_definition.py
│   │   ├── block_id.py
│   │   ├── lesson.py
│   │   ├── lesson_block.py
│   │   ├── slide.py
│   │   └── view_type.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── block_registry.py
│   │   ├── block_validator.py
│   │   ├── lesson_navigation.py
│   │   └── lesson_service.py
│   ├── static/
│   │   ├── lesson.css
│   │   ├── lesson.js
│   │   └── styles.css
│   └── templates/
│       ├── base.html
│       └── lesson/
│           ├── view.html
│           └── partials/
│               ├── block_card.html
│               ├── block_header.html
│               ├── block_body_router.html
│               ├── block_progress.html
│               ├── lesson_header.html
│               ├── slide_nav.html
│               ├── slide_stage.html
│               ├── teacher_overlay.html
│               ├── shared/
│               │   ├── block_notes.html
│               │   └── list_rows.html
│               └── views/
│                   ├── view_audio_prompt.html
│                   ├── view_drag_letter.html
│                   ├── view_drag_word.html
│                   ├── view_flashcard.html
│                   ├── view_minimal_pair.html
│                   ├── view_quick_check.html
│                   ├── view_read_respond.html
│                   └── view_writing_encoding.html