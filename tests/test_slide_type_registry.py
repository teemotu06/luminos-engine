import os
import unittest
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite:////tmp/luminos_engine_test_bootstrap.db"
os.environ["LUMINOS_AUTH_REQUIRED"] = "false"

from app.slide_types import registry


class SlideTypeRegistryTests(unittest.TestCase):
    KNOWN_ACTIONS = {
        "reveal",
        "reveal_answer",
        "produce_phase",
        "play_model",
        "play_sound",
        "play_audio",
        "read_sentence",
        "mark_students",
    }

    def test_registry_contains_all_current_types(self):
        self.assertEqual(
            registry.all_type_keys(),
            [
                "flashcard",
                "phonemes",
                "spell_word",
                "listen_spell",
                "sound_match",
                "pattern_noticing",
                "audio_prompt",
                "minimal_pair",
                "drag_letter",
                "drag_word",
                "read_respond",
                "writing_encoding",
                "quick_check",
                "connect_word_to_picture",
                "fill_in_the_blank",
                "word_sort",
                "sentence_builder",
            ],
        )

    def test_every_registered_type_has_valid_payload_model_and_default_payload(self):
        for type_key in registry.all_type_keys():
            definition = registry.get(type_key)
            self.assertIsNotNone(definition.payload_model)
            definition.payload_model(**definition.default_payload)

    def test_registered_templates_exist(self):
        root = Path(__file__).resolve().parents[1] / "app" / "templates"
        for type_key in registry.all_type_keys():
            self.assertTrue((root / registry.teacher_template_for(type_key)).exists())
            self.assertTrue((root / registry.board_template_for(type_key)).exists())

    def test_labels_are_non_empty(self):
        for type_key in registry.all_type_keys():
            self.assertTrue(registry.label_for(type_key).strip())

    def test_summaries_return_strings_for_default_payloads(self):
        for type_key in registry.all_type_keys():
            summary = registry.summary_for(type_key, registry.get(type_key).default_payload)
            self.assertIsInstance(summary, str)

    def test_allowed_blocks_are_never_empty(self):
        for type_key in registry.all_type_keys():
            self.assertTrue(registry.get(type_key).allowed_blocks)

    def test_editor_config_control_actions_and_default_marking_exist(self):
        for type_key in registry.all_type_keys():
            definition = registry.get(type_key)
            editor_config = definition.resolved_editor_config()
            self.assertTrue(editor_config["content_fields"] or editor_config["list_fields"])
            resolved_actions = registry.control_actions_for(type_key)
            self.assertIsInstance(resolved_actions, list)
            self.assertTrue(resolved_actions)
            for action in resolved_actions:
                self.assertIn(action, self.KNOWN_ACTIONS)
            self.assertIsInstance(definition.default_marking.get("markable"), bool)
            self.assertIsInstance(definition.default_marking.get("marking_options"), list)
            for field in editor_config["content_fields"]:
                self.assertTrue(field.get("display_label"))
                self.assertTrue(field.get("type"))
                self.assertNotEqual(field.get("media_type"), "audio")

    def test_audio_capable_types_expose_audio_actions(self):
        audio_actions = {"play_sound", "play_audio", "read_sentence"}
        for type_key in registry.all_type_keys():
            definition = registry.get(type_key)
            if definition.capability_flags.get("supports_audio"):
                self.assertTrue(audio_actions.intersection(registry.control_actions_for(type_key)))

    def test_markable_types_include_secure_shaky_missed_defaults(self):
        expected = {"secure", "shaky", "missed"}
        for type_key in registry.all_type_keys():
            definition = registry.get(type_key)
            if definition.default_marking.get("markable"):
                self.assertTrue(
                    expected.issubset(set(definition.default_marking.get("marking_options", [])))
                )

    def test_registry_actions_include_prompts_or_mark_students(self):
        for type_key in registry.all_type_keys():
            actions = registry.control_actions_for(type_key)
            self.assertIn("mark_students", actions)

    def test_paired_audio_references_existing_fields(self):
        for type_key in registry.all_type_keys():
            definition = registry.get(type_key)
            editor_config = definition.resolved_editor_config()
            names = {
                field["name"]
                for section in ("content_fields", "task_fields", "advanced_fields", "list_fields")
                for field in editor_config.get(section, [])
            }
            for field in editor_config.get("task_fields", []):
                paired_audio = field.get("paired_audio")
                if paired_audio:
                    self.assertIn(paired_audio, names)


if __name__ == "__main__":
    unittest.main()
