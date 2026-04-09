import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

from alembic import command
from alembic.config import Config


REPO_ROOT = Path(__file__).resolve().parents[1]


def _alembic_config(database_url: str) -> Config:
    config = Config(str(REPO_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(REPO_ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


class AlembicMigrationTests(unittest.TestCase):
    def test_upgrade_head_creates_fresh_schema(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "fresh.db"
            database_url = f"sqlite:///{db_path}"
            os.environ["DATABASE_URL"] = database_url

            command.upgrade(_alembic_config(database_url), "head")

            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='lesson_runtime_state'")
            self.assertEqual(cur.fetchone()[0], "lesson_runtime_state")
            cur.execute("PRAGMA table_info(oral_check_session)")
            oral_columns = {row[1] for row in cur.fetchall()}
            self.assertIn("audit_selection_strategy", oral_columns)
            cur.execute("PRAGMA table_info(lesson_attempt)")
            lesson_attempt_columns = {row[1] for row in cur.fetchall()}
            self.assertIn("version", lesson_attempt_columns)
            cur.execute("PRAGMA table_info(slide_result)")
            slide_result_columns = {row[1] for row in cur.fetchall()}
            self.assertIn("version", slide_result_columns)
            cur.execute("PRAGMA foreign_key_list(class_pattern_review)")
            class_review_fks = {(row[2], row[3], row[4], row[6]) for row in cur.fetchall()}
            self.assertIn(("class_group", "class_id", "id", "CASCADE"), class_review_fks)
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='app_user'")
            self.assertEqual(cur.fetchone()[0], "app_user")
            cur.execute("PRAGMA table_info(class_group)")
            class_group_columns = {row[1] for row in cur.fetchall()}
            self.assertIn("owner_user_id", class_group_columns)
            self.assertIn("deleted_at", class_group_columns)
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='class_session'")
            self.assertEqual(cur.fetchone()[0], "class_session")
            cur.execute("SELECT version_num FROM alembic_version")
            self.assertEqual(cur.fetchone()[0], "20260409_0001")
            cur.execute("PRAGMA table_info(lesson_attempt)")
            lesson_attempt_info = {row[1]: row[2] for row in cur.fetchall()}
            self.assertEqual(lesson_attempt_info["current_slide_id"], "VARCHAR(64)")
            cur.execute("PRAGMA table_info(class_session)")
            class_session_info = {row[1]: row[2] for row in cur.fetchall()}
            self.assertEqual(class_session_info["current_slide_id"], "VARCHAR(64)")
            conn.close()

    def test_upgrade_head_patches_legacy_sqlite_schema(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "legacy.db"
            database_url = f"sqlite:///{db_path}"
            os.environ["DATABASE_URL"] = database_url

            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            cur.execute("CREATE TABLE lesson (lesson_id VARCHAR(20) PRIMARY KEY, unit_id VARCHAR(10) NOT NULL, target_pattern VARCHAR(50) NOT NULL, content_pack_status VARCHAR(20) NOT NULL, json_path VARCHAR(200) NOT NULL)")
            cur.execute("CREATE TABLE lesson_attempt (attempt_id VARCHAR(36) PRIMARY KEY, lesson_id VARCHAR(20) NOT NULL, learner_key VARCHAR(64), teacher_key VARCHAR(64), attempt_date DATETIME NOT NULL, completed BOOLEAN NOT NULL, mastery_status VARCHAR(20) NOT NULL, phoneme_error_log JSON NOT NULL, notes TEXT, next_recommendation VARCHAR(20) NOT NULL)")
            cur.execute("CREATE TABLE oral_check_session (id VARCHAR(36) PRIMARY KEY, attempt_id VARCHAR(36) NOT NULL, lesson_id VARCHAR(20) NOT NULL, slide_id VARCHAR(20) NOT NULL, block_id VARCHAR(2) NOT NULL, participation_mode VARCHAR(40) NOT NULL, text_length_mode VARCHAR(20) NOT NULL, required_evidence_count INTEGER NOT NULL, roster_size INTEGER NOT NULL, required_student_count INTEGER NOT NULL, resolved_student_count INTEGER NOT NULL, unresolved_student_count INTEGER NOT NULL, session_status VARCHAR(20) NOT NULL, created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL)")
            cur.execute("CREATE TABLE student_mark (id VARCHAR(36) PRIMARY KEY, attempt_id VARCHAR(36) NOT NULL, lesson_id VARCHAR(20) NOT NULL, slide_id VARCHAR(20) NOT NULL, block_id VARCHAR(2) NOT NULL, student_name VARCHAR(100) NOT NULL, status VARCHAR(20) NOT NULL, error_tags JSON, support_level VARCHAR(20), teacher_note TEXT, timestamp DATETIME NOT NULL)")
            cur.execute("CREATE TABLE slide_result (result_id VARCHAR(36) PRIMARY KEY, attempt_id VARCHAR(36) NOT NULL, slide_id VARCHAR(20) NOT NULL, block_id VARCHAR(2) NOT NULL, status VARCHAR(20) NOT NULL, error_tags JSON NOT NULL, korean_transfer BOOLEAN NOT NULL, teacher_note TEXT, item_results JSON NOT NULL)")
            cur.execute("CREATE TABLE class_group (id VARCHAR(36) PRIMARY KEY, class_name VARCHAR(100) NOT NULL, description TEXT, created_at DATETIME NOT NULL)")
            cur.execute("CREATE TABLE class_pattern_review (id VARCHAR(36) PRIMARY KEY, class_id VARCHAR(36) NOT NULL, pattern_key VARCHAR(100) NOT NULL, source_lesson_id VARCHAR(20) NOT NULL, first_taught_lesson_id VARCHAR(20) NOT NULL, last_seen_lesson_id VARCHAR(20) NOT NULL, last_reviewed_lesson_id VARCHAR(20), mastery_state VARCHAR(20) NOT NULL, times_secure INTEGER NOT NULL, times_shaky INTEGER NOT NULL, times_missed INTEGER NOT NULL, consecutive_weak_lessons INTEGER NOT NULL, korean_transfer_count INTEGER NOT NULL, weak_learner_count INTEGER NOT NULL, marked_learner_count INTEGER NOT NULL, next_due_lesson_number INTEGER NOT NULL, priority_score INTEGER NOT NULL, notes TEXT, updated_at DATETIME NOT NULL)")
            conn.commit()
            conn.close()

            command.upgrade(_alembic_config(database_url), "head")

            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            cur.execute("PRAGMA table_info(lesson_attempt)")
            lesson_attempt_rows = cur.fetchall()
            lesson_attempt_columns = {row[1] for row in lesson_attempt_rows}
            self.assertIn("class_id", lesson_attempt_columns)
            self.assertIn("current_slide_id", lesson_attempt_columns)
            self.assertIn("version", lesson_attempt_columns)
            lesson_attempt_info = {row[1]: row[2] for row in lesson_attempt_rows}
            self.assertEqual(lesson_attempt_info["current_slide_id"], "VARCHAR(64)")
            cur.execute("PRAGMA table_info(slide_result)")
            slide_result_columns = {row[1] for row in cur.fetchall()}
            self.assertIn("version", slide_result_columns)
            cur.execute("PRAGMA foreign_key_list(class_pattern_review)")
            class_review_fks = {(row[2], row[3], row[4], row[6]) for row in cur.fetchall()}
            self.assertIn(("class_group", "class_id", "id", "CASCADE"), class_review_fks)
            cur.execute("PRAGMA table_info(class_group)")
            class_group_columns = {row[1] for row in cur.fetchall()}
            self.assertIn("owner_user_id", class_group_columns)
            self.assertIn("deleted_at", class_group_columns)
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='app_user'")
            self.assertEqual(cur.fetchone()[0], "app_user")
            cur.execute("PRAGMA table_info(oral_check_session)")
            oral_columns = {row[1] for row in cur.fetchall()}
            self.assertIn("audit_selection_strategy", oral_columns)
            cur.execute("PRAGMA index_list(oral_check_session)")
            oral_indexes = {row[1] for row in cur.fetchall()}
            self.assertIn("sqlite_autoindex_oral_check_session_2", oral_indexes)
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='lesson_runtime_state'")
            self.assertEqual(cur.fetchone()[0], "lesson_runtime_state")
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='class_session'")
            self.assertEqual(cur.fetchone()[0], "class_session")
            cur.execute("PRAGMA table_info(class_session)")
            class_session_info = {row[1]: row[2] for row in cur.fetchall()}
            self.assertEqual(class_session_info["current_slide_id"], "VARCHAR(64)")
            conn.close()

    def test_upgrade_head_drops_orphaned_class_pattern_review_rows_before_fk(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "orphaned.db"
            database_url = f"sqlite:///{db_path}"
            os.environ["DATABASE_URL"] = database_url

            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            cur.execute("CREATE TABLE class_group (id VARCHAR(36) PRIMARY KEY, class_name VARCHAR(100) NOT NULL, description TEXT, created_at DATETIME NOT NULL)")
            cur.execute("CREATE TABLE class_pattern_review (id VARCHAR(36) PRIMARY KEY, class_id VARCHAR(36) NOT NULL, pattern_key VARCHAR(100) NOT NULL, source_lesson_id VARCHAR(20) NOT NULL, first_taught_lesson_id VARCHAR(20) NOT NULL, last_seen_lesson_id VARCHAR(20) NOT NULL, last_reviewed_lesson_id VARCHAR(20), mastery_state VARCHAR(20) NOT NULL, times_secure INTEGER NOT NULL, times_shaky INTEGER NOT NULL, times_missed INTEGER NOT NULL, consecutive_weak_lessons INTEGER NOT NULL, korean_transfer_count INTEGER NOT NULL, weak_learner_count INTEGER NOT NULL, marked_learner_count INTEGER NOT NULL, next_due_lesson_number INTEGER NOT NULL, priority_score INTEGER NOT NULL, notes TEXT, updated_at DATETIME NOT NULL)")
            cur.execute("INSERT INTO class_pattern_review (id, class_id, pattern_key, source_lesson_id, first_taught_lesson_id, last_seen_lesson_id, mastery_state, times_secure, times_shaky, times_missed, consecutive_weak_lessons, korean_transfer_count, weak_learner_count, marked_learner_count, next_due_lesson_number, priority_score, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (
                "review-1", "missing-class", "sat", "G1-L1", "G1-L1", "G1-L1", "shaky", 0, 1, 0, 1, 0, 0, 0, 1, 0, "2026-04-02 00:00:00"
            ))
            conn.commit()
            conn.close()

            command.upgrade(_alembic_config(database_url), "head")

            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM class_pattern_review")
            self.assertEqual(cur.fetchone()[0], 0)
            conn.close()
