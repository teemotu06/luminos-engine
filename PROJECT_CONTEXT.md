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
├── requirements.txt
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── content/
│   │   └── lessons/
│   │       ├── g1_l1_u1_lesson_1.json
│   │       └── g1_l1_u1_lesson_1_blocks.json
│   ├── routers/
│   │   ├── __init__.py
│   │   └── lesson.py
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── block.py
│   │   ├── lesson.py
│   │   ├── lesson_block.py
│   │   └── slide.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── block_registry.py
│   │   ├── block_validator.py
│   │   ├── lesson_service.py
│   │   └── view_resolver.py
│   ├── static/
│   │   └── styles.css
│   └── templates/
│       ├── base.html
│       └── lesson/
│           ├── view.html
│           ├── partials/
│           │   └── slide_card.html
│           └── views/
│               ├── default.html
│               ├── launch.html
│               ├── teach.html
│               ├── model.html
│               ├── guided.html
│               ├── independent.html
│               ├── check.html
│               ├── quiz.html
│               └── wrap.html