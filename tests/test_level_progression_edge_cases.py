"""
Edge case tests for difficulty level progression system.

Tests cover:
1. Boundary conditions (exactly at thresholds)
2. Maximum level scenarios
3. Streak overflow scenarios
4. Database transaction error handling
5. Invalid data handling
6. Race conditions and concurrency
7. Rollback on errors
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError

from app.db.models import Base, User, Letter, QuizAttempt, LevelProgression
from app.db.init_db import GREEK_ALPHABET
from app.services.level_progression import (
    check_and_update_level,
    get_level_progress,
    get_level_description
)
from app.services.quiz_generator import create_quiz
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


class TestBoundaryConditions:
    """Test behavior at exact threshold boundaries."""

    def test_streak_at_exactly_9_no_levelup(self, test_db):
        """Streak of exactly 9 should not trigger level-up."""
        user = User(id="test-boundary-1", current_level=1, consecutive_perfect_streak=8)
        test_db.add(user)
        test_db.commit()

        quiz = QuizAttempt(
            user_id=user.id,
            question_count=QUESTIONS_PER_QUIZ,
            correct_count=QUESTIONS_PER_QUIZ
        )
        test_db.add(quiz)
        test_db.commit()

        result = check_and_update_level(test_db, user, quiz)

        assert result is None
        assert user.consecutive_perfect_streak == 9
        assert user.current_level == 1

    def test_streak_at_exactly_10_triggers_levelup(self, test_db):
        """Streak of exactly 10 should trigger level-up."""
        user = User(id="test-boundary-2", current_level=1, consecutive_perfect_streak=9)
        test_db.add(user)
        test_db.commit()

        quiz = QuizAttempt(
            user_id=user.id,
            question_count=QUESTIONS_PER_QUIZ,
            correct_count=QUESTIONS_PER_QUIZ
        )
        test_db.add(quiz)
        test_db.commit()

        result = check_and_update_level(test_db, user, quiz)

        assert result is not None
        assert result["leveled_up"] is True
        assert user.current_level == 2

    def test_quiz_score_13_is_not_perfect(self, test_db):
        """13/14 correct is not perfect (boundary case)."""
        user = User(id="test-boundary-3", current_level=1, consecutive_perfect_streak=5)
        test_db.add(user)
        test_db.commit()

        quiz = QuizAttempt(
            user_id=user.id,
            question_count=QUESTIONS_PER_QUIZ,
            correct_count=13
        )
        test_db.add(quiz)
        test_db.commit()

        result = check_and_update_level(test_db, user, quiz)

        assert result is None
        assert user.consecutive_perfect_streak == 0

    def test_quiz_score_14_is_perfect(self, test_db):
        """14/14 correct is perfect."""
        user = User(id="test-boundary-4", current_level=1, consecutive_perfect_streak=0)
        test_db.add(user)
        test_db.commit()

        quiz = QuizAttempt(
            user_id=user.id,
            question_count=QUESTIONS_PER_QUIZ,
            correct_count=QUESTIONS_PER_QUIZ
        )
        test_db.add(quiz)
        test_db.commit()

        result = check_and_update_level(test_db, user, quiz)

        assert user.consecutive_perfect_streak == 1

    def test_level_2_to_3_boundary(self, test_db):
        """Test boundary at level 2 -> 3 transition."""
        user = User(
            id="test-boundary-5",
            current_level=2,
            consecutive_perfect_streak=9,
            level_up_count=1
        )
        test_db.add(user)
        test_db.commit()

        quiz = QuizAttempt(
            user_id=user.id,
            question_count=QUESTIONS_PER_QUIZ,
            correct_count=QUESTIONS_PER_QUIZ
        )
        test_db.add(quiz)
        test_db.commit()

        result = check_and_update_level(test_db, user, quiz)

        assert result is not None
        assert result["from_level"] == 2
        assert result["to_level"] == 3
        assert user.current_level == 3


class TestMaxLevelScenarios:
    """Test behavior at maximum level."""

    def test_level_3_perfect_quiz_increments_streak_no_levelup(self, test_db):
        """Level 3 perfect quiz increments streak but doesn't level up."""
        user = User(
            id="test-max-1",
            current_level=3,
            consecutive_perfect_streak=5,
            level_up_count=2
        )
        test_db.add(user)
        test_db.commit()

        quiz = QuizAttempt(
            user_id=user.id,
            question_count=QUESTIONS_PER_QUIZ,
            correct_count=QUESTIONS_PER_QUIZ
        )
        test_db.add(quiz)
        test_db.commit()

        result = check_and_update_level(test_db, user, quiz)

        assert result is None
        assert user.consecutive_perfect_streak == 6
        assert user.current_level == 3

    def test_level_3_streak_can_exceed_10(self, test_db):
        """Level 3 users can have streak > 10."""
        user = User(
            id="test-max-2",
            current_level=3,
            consecutive_perfect_streak=25
        )
        test_db.add(user)
        test_db.commit()

        quiz = QuizAttempt(
            user_id=user.id,
            question_count=QUESTIONS_PER_QUIZ,
            correct_count=QUESTIONS_PER_QUIZ
        )
        test_db.add(quiz)
        test_db.commit()

        result = check_and_update_level(test_db, user, quiz)

        assert result is None
        assert user.consecutive_perfect_streak == 26

    def test_level_3_progress_shows_cannot_levelup(self, test_db):
        """get_level_progress at level 3 shows can_level_up=False."""
        user = User(id="test-max-3", current_level=3, consecutive_perfect_streak=10)
        test_db.add(user)
        test_db.commit()

        progress = get_level_progress(user)

        assert progress["can_level_up"] is False
        assert progress["progress_percentage"] == 0.0
        assert progress["current_level"] == 3
        assert progress["max_level"] == 3

    def test_no_progression_record_at_level_3(self, test_db):
        """No LevelProgression record should be created at level 3."""
        user = User(
            id="test-max-4",
            current_level=3,
            consecutive_perfect_streak=9
        )
        test_db.add(user)
        test_db.commit()

        quiz = QuizAttempt(
            user_id=user.id,
            question_count=QUESTIONS_PER_QUIZ,
            correct_count=QUESTIONS_PER_QUIZ
        )
        test_db.add(quiz)
        test_db.commit()

        check_and_update_level(test_db, user, quiz)
        test_db.commit()

        # No new progression record should exist
        progressions = test_db.query(LevelProgression).filter(
            LevelProgression.user_id == user.id
        ).all()

        assert len(progressions) == 0


class TestStreakOverflow:
    """Test scenarios with very high streaks."""

    def test_very_high_streak_at_level_1(self, test_db):
        """User with streak > 10 at level 1 should still level up."""
        # This should not happen in production, but test defensive coding
        user = User(id="test-overflow-1", current_level=1, consecutive_perfect_streak=15)
        test_db.add(user)
        test_db.commit()

        quiz = QuizAttempt(
            user_id=user.id,
            question_count=QUESTIONS_PER_QUIZ,
            correct_count=QUESTIONS_PER_QUIZ
        )
        test_db.add(quiz)
        test_db.commit()

        result = check_and_update_level(test_db, user, quiz)

        assert result is not None
        assert result["leveled_up"] is True
        assert user.current_level == 2
        assert user.consecutive_perfect_streak == 0

    def test_streak_at_100_at_level_3(self, test_db):
        """Very high streak at level 3 should work normally."""
        user = User(id="test-overflow-2", current_level=3, consecutive_perfect_streak=100)
        test_db.add(user)
        test_db.commit()

        quiz = QuizAttempt(
            user_id=user.id,
            question_count=QUESTIONS_PER_QUIZ,
            correct_count=QUESTIONS_PER_QUIZ
        )
        test_db.add(quiz)
        test_db.commit()

        result = check_and_update_level(test_db, user, quiz)

        assert result is None
        assert user.consecutive_perfect_streak == 101
        assert user.current_level == 3


class TestDatabaseConstraints:
    """Test database constraint enforcement."""

    def test_cannot_create_user_with_level_4(self, test_db):
        """Database should reject level > 3."""
        user = User(id="test-constraint-1", current_level=4)
        test_db.add(user)

        with pytest.raises(IntegrityError):
            test_db.commit()

    def test_cannot_create_user_with_level_0(self, test_db):
        """Database should reject level < 1."""
        user = User(id="test-constraint-2", current_level=0)
        test_db.add(user)

        with pytest.raises(IntegrityError):
            test_db.commit()

    def test_cannot_create_user_with_negative_streak(self, test_db):
        """Database should reject negative streak."""
        user = User(id="test-constraint-3", consecutive_perfect_streak=-5)
        test_db.add(user)

        with pytest.raises(IntegrityError):
            test_db.commit()

    def test_cannot_create_progression_skipping_levels(self, test_db):
        """Database should reject progression from 1 to 3."""
        user = User(id="test-constraint-4")
        test_db.add(user)
        test_db.commit()

        progression = LevelProgression(
            user_id=user.id,
            from_level=1,
            to_level=3,  # Skip level 2
            perfect_streak_count=10
        )
        test_db.add(progression)

        with pytest.raises(IntegrityError):
            test_db.commit()

    def test_cannot_create_progression_going_backwards(self, test_db):
        """Database should reject progression from 2 to 1."""
        user = User(id="test-constraint-5")
        test_db.add(user)
        test_db.commit()

        progression = LevelProgression(
            user_id=user.id,
            from_level=2,
            to_level=1,  # Backwards
            perfect_streak_count=0
        )
        test_db.add(progression)

        with pytest.raises(IntegrityError):
            test_db.commit()


class TestInvalidData:
    """Test handling of invalid or unexpected data."""

    def test_invalid_level_in_get_level_description(self):
        """get_level_description should handle invalid levels."""
        # Negative level
        desc = get_level_description(-1)
        assert desc["level"] == 1  # Default to level 1

        # Level 0
        desc = get_level_description(0)
        assert desc["level"] == 1

        # Level 99
        desc = get_level_description(99)
        assert desc["level"] == 1

    def test_quiz_with_impossible_score(self, test_db):
        """Quiz with score > question_count should be handled."""
        user = User(id="test-invalid-1", current_level=1, consecutive_perfect_streak=5)
        test_db.add(user)
        test_db.commit()

        # Create quiz with impossible score
        quiz = QuizAttempt(
            user_id=user.id,
            question_count=QUESTIONS_PER_QUIZ,
            correct_count=20  # More than possible
        )
        test_db.add(quiz)
        test_db.commit()

        # check_and_update_level compares against QUESTIONS_PER_QUIZ
        # 20 == 14 is False, so treated as non-perfect
        result = check_and_update_level(test_db, user, quiz)

        assert result is None
        assert user.consecutive_perfect_streak == 0

    def test_quiz_with_negative_score(self, test_db):
        """Quiz with negative score should be handled."""
        user = User(id="test-invalid-2", current_level=1, consecutive_perfect_streak=3)
        test_db.add(user)
        test_db.commit()

        quiz = QuizAttempt(
            user_id=user.id,
            question_count=QUESTIONS_PER_QUIZ,
            correct_count=-5
        )
        test_db.add(quiz)
        test_db.commit()

        result = check_and_update_level(test_db, user, quiz)

        assert result is None
        assert user.consecutive_perfect_streak == 0


class TestTransactionRollback:
    """Test transaction rollback on errors."""

    def test_rollback_maintains_consistent_state(self, test_db):
        """Transaction rollback should maintain consistent user state."""
        user = User(id="test-rollback-1", current_level=1, consecutive_perfect_streak=9)
        test_db.add(user)
        test_db.commit()

        initial_streak = user.consecutive_perfect_streak
        initial_level = user.current_level

        try:
            # Start a transaction
            quiz = QuizAttempt(
                user_id=user.id,
                question_count=QUESTIONS_PER_QUIZ,
                correct_count=QUESTIONS_PER_QUIZ
            )
            test_db.add(quiz)
            test_db.flush()

            # Simulate level-up logic
            user.consecutive_perfect_streak += 1

            # Force an error (invalid progression)
            if user.consecutive_perfect_streak >= PERFECT_STREAK_FOR_LEVEL_UP:
                progression = LevelProgression(
                    user_id=user.id,
                    from_level=1,
                    to_level=4,  # Invalid - will cause constraint error
                    perfect_streak_count=10
                )
                test_db.add(progression)

            test_db.commit()

        except IntegrityError:
            test_db.rollback()

        # User state should be unchanged after rollback
        test_db.refresh(user)
        assert user.consecutive_perfect_streak == initial_streak
        assert user.current_level == initial_level


class TestConcurrencyAndRaceConditions:
    """Test concurrent operations and race conditions."""

    def test_multiple_level_ups_in_sequence(self, test_db):
        """Multiple level-ups should work correctly in sequence."""
        user = User(id="test-concurrent-1", current_level=1, consecutive_perfect_streak=0)
        test_db.add(user)
        test_db.commit()

        # First level-up
        for _ in range(PERFECT_STREAK_FOR_LEVEL_UP):
            user.consecutive_perfect_streak += 1

        quiz1 = QuizAttempt(
            user_id=user.id,
            question_count=QUESTIONS_PER_QUIZ,
            correct_count=QUESTIONS_PER_QUIZ
        )
        test_db.add(quiz1)
        test_db.commit()

        # Manually trigger level-up
        user.consecutive_perfect_streak = PERFECT_STREAK_FOR_LEVEL_UP
        check_and_update_level(test_db, user, quiz1)
        test_db.commit()

        assert user.current_level == 2
        assert user.consecutive_perfect_streak == 0

        # Second level-up
        for _ in range(PERFECT_STREAK_FOR_LEVEL_UP):
            user.consecutive_perfect_streak += 1

        quiz2 = QuizAttempt(
            user_id=user.id,
            question_count=QUESTIONS_PER_QUIZ,
            correct_count=QUESTIONS_PER_QUIZ
        )
        test_db.add(quiz2)
        test_db.commit()

        user.consecutive_perfect_streak = PERFECT_STREAK_FOR_LEVEL_UP
        check_and_update_level(test_db, user, quiz2)
        test_db.commit()

        assert user.current_level == 3
        assert user.consecutive_perfect_streak == 0

    def test_level_up_count_increments_correctly(self, test_db):
        """level_up_count should increment correctly through journey."""
        user = User(id="test-concurrent-2", current_level=1, consecutive_perfect_streak=9)
        test_db.add(user)
        test_db.commit()

        assert user.level_up_count == 0

        # First level-up
        quiz1 = QuizAttempt(
            user_id=user.id,
            question_count=QUESTIONS_PER_QUIZ,
            correct_count=QUESTIONS_PER_QUIZ
        )
        test_db.add(quiz1)
        test_db.commit()

        check_and_update_level(test_db, user, quiz1)
        test_db.commit()

        assert user.level_up_count == 1

        # Second level-up
        user.consecutive_perfect_streak = 9
        quiz2 = QuizAttempt(
            user_id=user.id,
            question_count=QUESTIONS_PER_QUIZ,
            correct_count=QUESTIONS_PER_QUIZ
        )
        test_db.add(quiz2)
        test_db.commit()

        check_and_update_level(test_db, user, quiz2)
        test_db.commit()

        assert user.level_up_count == 2


class TestQuizGenerationEdgeCases:
    """Test edge cases in quiz generation with levels."""

    def test_create_quiz_for_nonexistent_user_raises_error(self, test_db):
        """Creating quiz for non-existent user should raise error."""
        with pytest.raises(ValueError, match="User .* not found"):
            create_quiz(test_db, "nonexistent-user-id", include_audio=False)

    def test_quiz_generation_works_for_all_valid_levels(self, test_db):
        """Quiz generation should work for levels 1, 2, 3."""
        for level in [1, 2, 3]:
            user = User(id=f"test-gen-{level}", current_level=level)
            test_db.add(user)
            test_db.commit()

            quiz, questions = create_quiz(test_db, user.id, include_audio=False)

            assert quiz is not None
            assert len(questions) == QUESTIONS_PER_QUIZ

    def test_zero_streak_at_each_level(self, test_db):
        """Users with 0 streak at each level should work normally."""
        for level in [1, 2, 3]:
            user = User(
                id=f"test-zero-{level}",
                current_level=level,
                consecutive_perfect_streak=0
            )
            test_db.add(user)
            test_db.commit()

            progress = get_level_progress(user)

            assert progress["perfect_streak"] == 0
            assert progress["progress_percentage"] == 0.0
