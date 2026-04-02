import unittest

from sqlalchemy import select

from tests.support import SqliteTestSession, seed_attempt, seed_lesson
from app.models.lesson import OralCheckAssignmentRecord, StudentMarkRecord
from app.schemas.oral_check import (
    OralCheckAssignmentMarkRequest,
    OralCheckCompleteRequest,
    OralCheckSessionStartRequest,
)
from app.services.oral_check_service import (
    complete_oral_check_session,
    get_oral_check_session,
    mark_oral_check_assignment,
    start_oral_check_session,
)


class OralCheckServiceTests(unittest.TestCase):
    def setUp(self):
        self.session = SqliteTestSession()
        self.db = self.session.db
        seed_lesson(self.db, "G1-L1")
        self.attempt = seed_attempt(self.db, "G1-L1", class_id="class-1")

    def tearDown(self):
        self.session.close()

    def test_full_roster_missed_queues_correction_and_blocks_until_resolved(self):
        started = start_oral_check_session(
            self.db,
            OralCheckSessionStartRequest(
                attempt_id=str(self.attempt.attempt_id),
                lesson_id="G1-L1",
                slide_id="07-01",
                block_id="07",
                roster=["Tom", "James"],
                participation_mode="full_roster",
                text_length_mode="normal",
                required_evidence_count=1,
            ),
        )

        self.assertEqual(started.required_student_count, 2)
        self.assertEqual(started.active_student_name, "Tom")

        first_mark = mark_oral_check_assignment(
            self.db,
            OralCheckAssignmentMarkRequest(
                session_id=started.session_id,
                assignment_id=started.active_assignment_id,
                status="missed",
            ),
        )
        self.assertTrue(first_mark.requires_reteach)
        self.assertFalse(first_mark.student_resolved)
        self.assertEqual(first_mark.unresolved_student_count, 2)

        james_assignment = first_mark.next_assignment_id
        second_mark = mark_oral_check_assignment(
            self.db,
            OralCheckAssignmentMarkRequest(
                session_id=started.session_id,
                assignment_id=james_assignment,
                status="secure",
            ),
        )
        self.assertTrue(second_mark.student_resolved)
        self.assertEqual(second_mark.unresolved_student_count, 1)

        session = get_oral_check_session(self.db, str(self.attempt.attempt_id), "07-01")
        self.assertEqual(session.active_student_name, "Tom")
        self.assertEqual(session.active_performance_type, "correction_reread")

        final_mark = mark_oral_check_assignment(
            self.db,
            OralCheckAssignmentMarkRequest(
                session_id=session.session_id,
                assignment_id=session.active_assignment_id,
                status="secure",
            ),
        )
        self.assertTrue(final_mark.student_resolved)
        self.assertEqual(final_mark.unresolved_student_count, 0)
        self.assertEqual(final_mark.session_status, "complete")

        completed = complete_oral_check_session(
            self.db,
            OralCheckCompleteRequest(session_id=session.session_id),
        )
        self.assertEqual(completed.session_status, "complete")

        tom_mark = (
            self.db.execute(
                select(StudentMarkRecord).where(
                    StudentMarkRecord.attempt_id == self.attempt.attempt_id,
                    StudentMarkRecord.slide_id == "07-01",
                    StudentMarkRecord.student_name == "Tom",
                )
            )
            .scalars()
            .one()
        )
        self.assertEqual(tom_mark.status, "secure")

    def test_short_reader_secure_requires_second_evidence_before_resolution(self):
        started = start_oral_check_session(
            self.db,
            OralCheckSessionStartRequest(
                attempt_id=str(self.attempt.attempt_id),
                lesson_id="G1-L1",
                slide_id="07-02",
                block_id="07",
                roster=["Hyun"],
                participation_mode="short_reader_full_roster",
                text_length_mode="short",
                required_evidence_count=2,
            ),
        )

        first_mark = mark_oral_check_assignment(
            self.db,
            OralCheckAssignmentMarkRequest(
                session_id=started.session_id,
                assignment_id=started.active_assignment_id,
                status="secure",
            ),
        )

        self.assertFalse(first_mark.student_resolved)
        self.assertEqual(first_mark.unresolved_student_count, 1)

        session = get_oral_check_session(self.db, str(self.attempt.attempt_id), "07-02")
        self.assertEqual(session.active_student_name, "Hyun")
        self.assertEqual(session.active_performance_type, "reread_fluency")

        follow_up = mark_oral_check_assignment(
            self.db,
            OralCheckAssignmentMarkRequest(
                session_id=session.session_id,
                assignment_id=session.active_assignment_id,
                status="secure",
            ),
        )

        self.assertTrue(follow_up.student_resolved)
        self.assertEqual(follow_up.unresolved_student_count, 0)

        assignments = (
            self.db.execute(
                select(OralCheckAssignmentRecord).where(
                    OralCheckAssignmentRecord.session_id == session.session_id
                )
            )
            .scalars()
            .all()
        )
        self.assertEqual([a.performance_type for a in assignments], ["read_accuracy", "reread_fluency"])
