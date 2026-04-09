import json
import os
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:////tmp/luminos_engine_test_authoring.db"
os.environ["LUMINOS_AUTH_REQUIRED"] = "false"
os.environ["LUMINOS_ADMIN_SECRET"] = "test-admin-secret"

from app.routers.authoring import router as authoring_router


def _groups_seed() -> str:
    return Path("app/content/groups.json").read_text(encoding="utf-8")


def test_group_crud_routes_return_correct_responses(tmp_path):
    groups_file = tmp_path / "groups.json"
    groups_file.write_text(_groups_seed(), encoding="utf-8")
    app = FastAPI()
    app.include_router(authoring_router)
    client = TestClient(app)
    with patch("app.services.group_service.GROUPS_FILE", groups_file):
        response = client.get("/authoring/groups")
        assert response.status_code == 200
        created = client.post("/authoring/groups", data={"unit_id": "G11", "title": "New Group", "description": "", "target_phonemes": "oa, ow"}, follow_redirects=False)
        assert created.status_code == 303
        edited = client.post("/authoring/groups/G1", data={"title": "Updated G1", "description": "Desc", "target_phonemes": "a, i"}, follow_redirects=False)
        assert edited.status_code == 303
    client.close()


def test_lesson_creation_duplicate_and_delete_routes(tmp_path):
    groups_file = tmp_path / "groups.json"
    groups_file.write_text(_groups_seed(), encoding="utf-8")
    lessons_dir = tmp_path / "lessons"
    backups_dir = tmp_path / "lesson_backups"
    lessons_dir.mkdir()
    backups_dir.mkdir()
    app = FastAPI()
    app.include_router(authoring_router)
    client = TestClient(app)
    with patch("app.services.group_service.GROUPS_FILE", groups_file), \
         patch("app.services.lesson_authoring_service.LESSONS_DIR", lessons_dir), \
         patch("app.services.lesson_authoring_service.LESSON_BACKUPS_DIR", backups_dir), \
         patch("app.services.lesson_service.LESSONS_DIR", lessons_dir):
        created = client.post(
            "/authoring/lessons",
            data={
                "unit_id": "G1",
                "lesson_number": "99",
                "title": "Test Lesson",
                "target_pattern": "oa",
                "new_units": "oa",
                "new_sight_words": "the",
            },
            follow_redirects=False,
        )
        assert created.status_code == 303
        assert (lessons_dir / "G1-L99.json").exists()

        duplicated = client.post("/authoring/lessons/G1-L99/duplicate", follow_redirects=False)
        assert duplicated.status_code == 303
        assert any(path.name != "G1-L99.json" for path in lessons_dir.glob("G1-L*.json"))

        deleted = client.post("/authoring/lessons/G1-L99/delete", follow_redirects=False)
        assert deleted.status_code == 303
        assert not (lessons_dir / "G1-L99.json").exists()
        assert list(backups_dir.glob("G1-L99.*.json"))
    client.close()
