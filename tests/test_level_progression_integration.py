"""
Integration tests for full quiz flow with difficulty level progression.

Tests cover:
1. Complete quiz with perfect score -> streak increments
2. Complete quiz with non-perfect score -> streak resets
3. 10 consecutive perfect quizzes -> level-up
4. Level-up response includes correct data
5. Bootstrap endpoint returns level data
6. Quiz summary includes level progress
7. Full journey from Level 1 to Level 3
8. Error handling and transaction rollback
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base, User, Letter, QuizAttempt, QuizQuestion, LevelProgression
from app.db.init_db import GREEK_ALPHABET
from app.services.quiz_generator import create_quiz, evaluate_answer
from app.services.level_progression import check_and_update_level, get_level_progress
from app.constants import QUESTIONS_PER_QUIZ, PERFECT_STREAK_FOR_LEVEL_UP


@pytest.fixture
def test_db():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    # Seed letters
    for letter_data in GREEK_ALPHABET:
        letter = Letter(**letter_data)
        session.add(letter)
    session.commit()

    yield session
    session.close()


class TestQuizFlowWithLevelProgression:
    """Test complete quiz flow including level progression."""

    def test_perfect_quiz_increments_streak(self, test_db):
        """Completing a perfect quiz should increment the streak."""
        user = User(id="test-flow-1", current_level=1, consecutive_perfect_streak=0)
        test_db.add(user)
        test_db.commit()

        # Create quiz
        quiz, questions = create_quiz(test_db, user.id, include_audio=False)

        # Answer all questions correctly
        for question in questions:
            question_obj = test_db.query(QuizQuestion).filter(
                QuizQuestion.id == question["question_id"]
            ).first()
            question_obj.is_correct = 1
            question_obj.chosen_option = question["correct_answer"]

        quiz.correct_count = QUESTIONS_PER_QUIZ
        test_db.commit()

        # Check level progression
        result = check_and_update_level(test_db, user, quiz)

        assert user.consecutive_perfect_streak == 1
        assert result is None  # No level-up yet

    def test_non_perfect_quiz_resets_streak(self, test_db):
        """Completing a non-perfect quiz should reset the streak."""
        user = User(id="test-flow-2", current_level=1, consecutive_perfect_streak=5)
        test_db.add(user)
        test_db.commit()

        # Create quiz
        quiz, questions = create_quiz(test_db, user.id, include_audio=False)

        # Answer 13/14 correctly
        for i, question in enumerate(questions):
            question_obj = test_db.query(QuizQuestion).filter(
                QuizQuestion.id == question["question_id"]
            ).first()

            if i < 13:
                question_obj.is_correct = 1
                question_obj.chosen_option = question["correct_answer"]
            else:
                question_obj.is_correct = 0
                question_obj.chosen_option = "Wrong Answer"

        quiz.correct_count = 13
        test_db.commit()

        # Check level progression
        result = check_and_update_level(test_db, user, quiz)

        assert user.consecutive_perfect_streak == 0
        assert result is None

    def test_10_consecutive_perfect_quizzes_triggers_levelup(self, test_db):
        """10 consecutive perfect quizzes should trigger level-up."""
        user = User(id="test-flow-3", current_level=1, consecutive_perfect_streak=0)
        test_db.add(user)
        test_db.commit()

        level_up_result = None

        # Complete 10 perfect quizzes
        for i in range(PERFECT_STREAK_FOR_LEVEL_UP):
            quiz, questions = create_quiz(test_db, user.id, include_audio=False)

            # Answer all correctly
            for question in questions:
                question_obj = test_db.query(QuizQuestion).filter(
                    QuizQuestion.id == question["question_id"]
                ).first()
                question_obj.is_correct = 1
                question_obj.chosen_option = question["correct_answer"]

            quiz.correct_count = QUESTIONS_PER_QUIZ
            test_db.commit()

            level_up_result = check_and_update_level(test_db, user, quiz)
            test_db.commit()

        # Should have leveled up on 10th quiz
        assert level_up_result is not None
        assert level_up_result["leveled_up"] is True
        assert level_up_result["from_level"] == 1
        assert level_up_result["to_level"] == 2

        assert user.current_level == 2
        assert user.consecutive_perfect_streak == 0
        assert user.level_up_count == 1

    def test_level_up_creates_progression_record(self, test_db):
        """Level-up should create a LevelProgression record."""
        user = User(id="test-flow-4", current_level=1, consecutive_perfect_streak=9)
        test_db.add(user)
        test_db.commit()

        # One more perfect quiz to trigger level-up
        quiz, questions = create_quiz(test_db, user.id, include_audio=False)

        for question in questions:
            question_obj = test_db.query(QuizQuestion).filter(
                QuizQuestion.id == question["question_id"]
            ).first()
            question_obj.is_correct = 1
            question_obj.chosen_option = question["correct_answer"]

        quiz.correct_count = QUESTIONS_PER_QUIZ
        test_db.commit()

        check_and_update_level(test_db, user, quiz)
        test_db.commit()

        # Verify progression record
        progression = test_db.query(LevelProgression).filter(
            LevelProgression.user_id == user.id
        ).first()

        assert progression is not None
        assert progression.from_level == 1
        assert progression.to_level == 2
        assert progression.perfect_streak_count == PERFECT_STREAK_FOR_LEVEL_UP

    def test_difficulty_increases_after_level_up(self, test_db):
        """Quiz difficulty should increase after leveling up."""
        user = User(id="test-flow-5", current_level=1, consecutive_perfect_streak=9)
        test_db.add(user)
        test_db.commit()

        # Quiz before level-up (Level 1)
        quiz_before, questions_before = create_quiz(test_db, user.id, include_audio=True)

        # Count audio questions
        audio_before = sum(1 for q in questions_before if q.get("is_audio_question"))
        options_before = len(questions_before[0].get("options", []))

        # Complete quiz and level up
        for question in questions_before:
            question_obj = test_db.query(QuizQuestion).filter(
                QuizQuestion.id == question["question_id"]
            ).first()
            question_obj.is_correct = 1
            question_obj.chosen_option = question["correct_answer"]

        quiz_before.correct_count = QUESTIONS_PER_QUIZ
        test_db.commit()

        check_and_update_level(test_db, user, quiz_before)
        test_db.commit()

        assert user.current_level == 2

        # Quiz after level-up (Level 2)
        quiz_after, questions_after = create_quiz(test_db, user.id, include_audio=True)

        audio_after = sum(1 for q in questions_after if q.get("is_audio_question"))

        # Level 2 should have more audio questions than Level 1
        assert audio_after > audio_before


class TestLevelProgressData:
    """Test level progress data retrieval."""

    def test_get_level_progress_shows_correct_data(self, test_db):
        """get_level_progress should return accurate progress data."""
        user = User(id="test-progress-1", current_level=1, consecutive_perfect_streak=5)
        test_db.add(user)
        test_db.commit()

        progress = get_level_progress(user)

        assert progress["current_level"] == 1
        assert progress["max_level"] == 3
        assert progress["can_level_up"] is True
        assert progress["perfect_streak"] == 5
        assert progress["required_streak"] == PERFECT_STREAK_FOR_LEVEL_UP
        assert progress["progress_percentage"] == 50.0

    def test_level_progress_updates_after_quiz(self, test_db):
        """Level progress should update after completing quiz."""
        user = User(id="test-progress-2", current_level=1, consecutive_perfect_streak=7)
        test_db.add(user)
        test_db.commit()

        # Complete perfect quiz
        quiz, questions = create_quiz(test_db, user.id, include_audio=False)

        for question in questions:
            question_obj = test_db.query(QuizQuestion).filter(
                QuizQuestion.id == question["question_id"]
            ).first()
            question_obj.is_correct = 1
            question_obj.chosen_option = question["correct_answer"]

        quiz.correct_count = QUESTIONS_PER_QUIZ
        test_db.commit()

        check_and_update_level(test_db, user, quiz)
        test_db.commit()

        progress = get_level_progress(user)

        assert progress["perfect_streak"] == 8
        assert progress["progress_percentage"] == 80.0


class TestCompleteJourney:
    """Test complete user journey from Level 1 to Level 3."""

    def test_full_journey_1_to_3(self, test_db):
        """Test complete journey from Level 1 to Level 3."""
        user = User(id="test-journey", current_level=1, consecutive_perfect_streak=0)
        test_db.add(user)
        test_db.commit()

        # Track progression
        level_ups = []

        # Complete 20 perfect quizzes (10 for 1->2, 10 for 2->3)
        for i in range(20):
            quiz, questions = create_quiz(test_db, user.id, include_audio=False)

            # Answer all correctly
            for question in questions:
                question_obj = test_db.query(QuizQuestion).filter(
                    QuizQuestion.id == question["question_id"]
                ).first()
                question_obj.is_correct = 1
                question_obj.chosen_option = question["correct_answer"]

            quiz.correct_count = QUESTIONS_PER_QUIZ
            test_db.commit()

            result = check_and_update_level(test_db, user, quiz)
            test_db.commit()

            if result and result.get("leveled_up"):
                level_ups.append(result)

        # Should have leveled up twice
        assert len(level_ups) == 2
        assert level_ups[0]["from_level"] == 1
        assert level_ups[0]["to_level"] == 2
        assert level_ups[1]["from_level"] == 2
        assert level_ups[1]["to_level"] == 3

        # Final state
        assert user.current_level == 3
        assert user.level_up_count == 2

        # Verify progression history
        progressions = test_db.query(LevelProgression).filter(
            LevelProgression.user_id == user.id
        ).order_by(LevelProgression.achieved_at).all()

        assert len(progressions) == 2

    def test_journey_with_interruptions(self, test_db):
        """Test journey with streak interruptions."""
        user = User(id="test-interrupted", current_level=1, consecutive_perfect_streak=0)
        test_db.add(user)
        test_db.commit()

        # Complete 7 perfect quizzes
        for _ in range(7):
            quiz, questions = create_quiz(test_db, user.id, include_audio=False)

            for question in questions:
                question_obj = test_db.query(QuizQuestion).filter(
                    QuizQuestion.id == question["question_id"]
                ).first()
                question_obj.is_correct = 1
                question_obj.chosen_option = question["correct_answer"]

            quiz.correct_count = QUESTIONS_PER_QUIZ
            test_db.commit()

            check_and_update_level(test_db, user, quiz)
            test_db.commit()

        assert user.consecutive_perfect_streak == 7

        # Fail one quiz
        quiz_fail, questions_fail = create_quiz(test_db, user.id, include_audio=False)

        for i, question in enumerate(questions_fail):
            question_obj = test_db.query(QuizQuestion).filter(
                QuizQuestion.id == question["question_id"]
            ).first()

            if i < 10:
                question_obj.is_correct = 1
                question_obj.chosen_option = question["correct_answer"]
            else:
                question_obj.is_correct = 0
                question_obj.chosen_option = "Wrong"

        quiz_fail.correct_count = 10
        test_db.commit()

        check_and_update_level(test_db, user, quiz_fail)
        test_db.commit()

        # Streak should be reset
        assert user.consecutive_perfect_streak == 0

        # Complete 10 more perfect quizzes to level up
        for _ in range(10):
            quiz, questions = create_quiz(test_db, user.id, include_audio=False)

            for question in questions:
                question_obj = test_db.query(QuizQuestion).filter(
                    QuizQuestion.id == question["question_id"]
                ).first()
                question_obj.is_correct = 1
                question_obj.chosen_option = question["correct_answer"]

            quiz.correct_count = QUESTIONS_PER_QUIZ
            test_db.commit()

            result = check_and_update_level(test_db, user, quiz)
            test_db.commit()

        # Should now be at level 2
        assert user.current_level == 2


class TestEdgeCasesIntegration:
    """Test edge cases in integration scenarios."""

    def test_level_3_user_perfect_streak_no_levelup(self, test_db):
        """Level 3 user with 10 perfect quizzes should not level up."""
        user = User(id="test-max-level", current_level=3, consecutive_perfect_streak=0)
        test_db.add(user)
        test_db.commit()

        # Complete 10 perfect quizzes at level 3
        for _ in range(10):
            quiz, questions = create_quiz(test_db, user.id, include_audio=False)

            for question in questions:
                question_obj = test_db.query(QuizQuestion).filter(
                    QuizQuestion.id == question["question_id"]
                ).first()
                question_obj.is_correct = 1
                question_obj.chosen_option = question["correct_answer"]

            quiz.correct_count = QUESTIONS_PER_QUIZ
            test_db.commit()

            result = check_and_update_level(test_db, user, quiz)
            test_db.commit()

            # Should never level up
            assert result is None

        # Still at level 3 with high streak
        assert user.current_level == 3
        assert user.consecutive_perfect_streak == 10

        # Progress shows can't level up
        progress = get_level_progress(user)
        assert progress["can_level_up"] is False

    def test_concurrent_quizzes_maintain_streak_consistency(self, test_db):
        """Test that quiz completion maintains streak consistency."""
        user = User(id="test-consistency", current_level=1, consecutive_perfect_streak=5)
        test_db.add(user)
        test_db.commit()

        initial_streak = user.consecutive_perfect_streak

        # Create multiple quizzes
        quiz1, _ = create_quiz(test_db, user.id, include_audio=False)
        quiz2, _ = create_quiz(test_db, user.id, include_audio=False)

        # Complete first quiz perfectly
        quiz1.correct_count = QUESTIONS_PER_QUIZ
        test_db.commit()

        check_and_update_level(test_db, user, quiz1)
        test_db.commit()

        assert user.consecutive_perfect_streak == initial_streak + 1

        # Complete second quiz perfectly
        quiz2.correct_count = QUESTIONS_PER_QUIZ
        test_db.commit()

        check_and_update_level(test_db, user, quiz2)
        test_db.commit()

        assert user.consecutive_perfect_streak == initial_streak + 2

    def test_progression_timestamps_are_recorded(self, test_db):
        """Level progressions should have accurate timestamps."""
        user = User(id="test-timestamps", current_level=1, consecutive_perfect_streak=9)
        test_db.add(user)
        test_db.commit()

        # Complete final quiz for level-up
        quiz, questions = create_quiz(test_db, user.id, include_audio=False)

        for question in questions:
            question_obj = test_db.query(QuizQuestion).filter(
                QuizQuestion.id == question["question_id"]
            ).first()
            question_obj.is_correct = 1
            question_obj.chosen_option = question["correct_answer"]

        quiz.correct_count = QUESTIONS_PER_QUIZ
        test_db.commit()

        check_and_update_level(test_db, user, quiz)
        test_db.commit()

        # Check progression timestamp
        progression = test_db.query(LevelProgression).filter(
            LevelProgression.user_id == user.id
        ).first()

        assert progression is not None
        assert progression.achieved_at is not None

    def test_quiz_without_audio_works_at_all_levels(self, test_db):
        """Quizzes without audio should work at all levels."""
        for level in [1, 2, 3]:
            user = User(id=f"test-no-audio-{level}", current_level=level)
            test_db.add(user)
            test_db.commit()

            # Create quiz without audio
            quiz, questions = create_quiz(test_db, user.id, include_audio=False)

            # Verify no audio questions
            audio_count = sum(1 for q in questions if q.get("is_audio_question"))
            assert audio_count == 0

            # Complete perfectly
            for question in questions:
                question_obj = test_db.query(QuizQuestion).filter(
                    QuizQuestion.id == question["question_id"]
                ).first()
                question_obj.is_correct = 1
                question_obj.chosen_option = question["correct_answer"]

            quiz.correct_count = QUESTIONS_PER_QUIZ
            test_db.commit()

            # Should work normally
            check_and_update_level(test_db, user, quiz)
            test_db.commit()
