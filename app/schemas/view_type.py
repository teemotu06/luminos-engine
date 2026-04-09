ViewType = str


def validate_view_type(v: str) -> str:
    from app.slide_types import registry

    value = str(v)
    if not registry.exists(value):
        raise ValueError(f"Unknown view_type '{value}'")
    return value
