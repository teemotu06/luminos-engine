from app.schemas.lesson import Lesson
from app.schemas.slide_payloads import VIEW_PAYLOAD_MAP
from app.services.block_registry import BLOCK_REGISTRY

ALLOWED_RUNTIME_CONTROLS = {
    "mark_secure",
    "mark_shaky",
    "mark_missed",
    "mark_deferred",
    "mark_absent",
    "mark_class",
    "skip",
    "force_advance",
    "replay",
    "pause",
    "resume",
}


def validate_slide_payloads(lesson: Lesson) -> None:
    for definition in BLOCK_REGISTRY:
        block = lesson.blocks[definition.block_id]
        for slide in block.slides:

            view_type = slide.view_type

            if view_type not in VIEW_PAYLOAD_MAP:
                raise ValueError(
                    f"Unknown view_type '{view_type}' in slide {slide.slide_id}"
                )

            payload_model = VIEW_PAYLOAD_MAP[view_type]

            try:
                payload_model(**slide.content_payload.model_dump())
            except Exception as e:
                raise ValueError(
                    f"Invalid payload in lesson '{lesson.lesson_id}', "
                    f"block {block.block_id}, slide '{slide.slide_id}', "
                    f"view_type '{view_type}': {e}"
                )

            oral_enforcement = getattr(slide.content_payload, "oral_enforcement", None)
            comprehension_questions = getattr(slide.content_payload, "comprehension_questions", None) or []
            if any(not str(item).strip() for item in comprehension_questions):
                raise ValueError(
                    f"comprehension_questions cannot contain empty items in {lesson.lesson_id} / {slide.slide_id}"
                )
            if oral_enforcement and oral_enforcement.enabled:
                if not (slide.block_id == "07" and slide.view_type == "read_respond"):
                    raise ValueError(
                        f"oral_enforcement is only supported on Block 07 read_respond slides in {lesson.lesson_id} / {slide.slide_id}"
                    )
                if oral_enforcement.text_length_mode == "short" and oral_enforcement.required_evidence_count < 2:
                    raise ValueError(
                        f"short reader oral_enforcement requires required_evidence_count >= 2 in {lesson.lesson_id} / {slide.slide_id}"
                    )
                if oral_enforcement.participation_mode == "audit_roster" and oral_enforcement.audit_sample_size <= 0:
                    raise ValueError(
                        f"audit_roster requires audit_sample_size > 0 in {lesson.lesson_id} / {slide.slide_id}"
                    )
                if oral_enforcement.participation_mode != "audit_roster" and oral_enforcement.audit_sample_size > 0:
                    raise ValueError(
                        f"audit_sample_size is only valid for audit_roster in {lesson.lesson_id} / {slide.slide_id}"
                    )

            runtime = getattr(slide, "luminos_runtime", None)
            if runtime and runtime.enabled:
                state_sequence = runtime.state_sequence or []
                if not state_sequence:
                    raise ValueError(
                        f"luminos_runtime requires at least one state in {lesson.lesson_id} / {slide.slide_id}"
                    )
                seen_keys = set()
                for state in state_sequence:
                    if not state.key.strip():
                        raise ValueError(
                            f"luminos_runtime state keys cannot be empty in {lesson.lesson_id} / {slide.slide_id}"
                        )
                    if state.key in seen_keys:
                        raise ValueError(
                            f"luminos_runtime state keys must be unique in {lesson.lesson_id} / {slide.slide_id}: {state.key}"
                        )
                    seen_keys.add(state.key)
                    if state.timeout_ms is not None and state.timeout_ms <= 0:
                        raise ValueError(
                            f"luminos_runtime timeout_ms must be > 0 in {lesson.lesson_id} / {slide.slide_id} / {state.key}"
                        )
                    if not any([
                        (state.prompt or "").strip(),
                        (state.board_prompt or "").strip(),
                        (state.teacher_prompt or "").strip(),
                        (state.tts_prompt or "").strip(),
                    ]):
                        raise ValueError(
                            f"luminos_runtime state must define at least one prompt field in {lesson.lesson_id} / {slide.slide_id} / {state.key}"
                        )
                    invalid_controls = [control for control in (state.teacher_controls or []) if control not in ALLOWED_RUNTIME_CONTROLS]
                    if invalid_controls:
                        raise ValueError(
                            f"luminos_runtime has invalid teacher_controls in {lesson.lesson_id} / {slide.slide_id} / {state.key}: {', '.join(invalid_controls)}"
                        )
