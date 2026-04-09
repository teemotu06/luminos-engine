from __future__ import annotations

from typing import Any

from app.slide_types.base import SlideTypeDefinition


class SlideTypeRegistry:
    def __init__(self) -> None:
        self._definitions: dict[str, SlideTypeDefinition] = {}

    def register(self, definition: SlideTypeDefinition) -> None:
        if definition.type_key in self._definitions:
            raise ValueError(f"Duplicate slide type registration: {definition.type_key}")
        self._definitions[definition.type_key] = definition

    def get(self, type_key: str) -> SlideTypeDefinition:
        try:
            return self._definitions[type_key]
        except KeyError as exc:
            raise KeyError(f"Unknown slide type: {type_key}") from exc

    def exists(self, type_key: str) -> bool:
        return type_key in self._definitions

    def all_type_keys(self) -> list[str]:
        return list(self._definitions.keys())

    def label_for(self, type_key: str) -> str:
        return self.get(type_key).label

    def payload_model_for(self, type_key: str):
        return self.get(type_key).payload_model

    def summary_for(self, type_key: str, payload: dict) -> str:
        summary = self.get(type_key).summary_extractor(payload)
        return str(summary)

    def teacher_template_for(self, type_key: str) -> str:
        return f"lesson/partials/views/{self.get(type_key).teacher_template}"

    def board_template_for(self, type_key: str) -> str:
        return f"lesson/partials/views/{self.get(type_key).board_template}"

    def command_state_defaults_for(self, type_key: str):
        return self.get(type_key).command_state_defaults

    def all_labels(self) -> dict[str, str]:
        return {type_key: definition.label for type_key, definition in self._definitions.items()}

    def control_actions_for(self, type_key: str) -> list[str]:
        return list(self.get(type_key).control_actions or [])


registry = SlideTypeRegistry()
