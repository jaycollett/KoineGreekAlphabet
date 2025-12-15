"""
Unit tests for level progression logic.

Tests cover:
1. check_and_update_level() function
   - Perfect quiz increments streak
   - Non-perfect quiz resets streak
   - Level-up at 10 perfect quizzes
   - No level-up beyond Level 3
   - Historical record created on level-up
   - Streak resets after level-up
2. get_level_progress() function
   - Correct progress percentage calculation
   - Correct requirements text
   - Max level edge case
3. get_level_description() function
   - Correct mechanics for each level
"""

import pytest
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base, User, LevelProgression, QuizAttempt, Letter
from app.db.init_db import GREEK_ALPHABET
from app.services.level_progression import (
    check_and_update_level,
    get_level_progress,
    get_level_description
)
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


class TestCheckAndUpdateLevel:
    """Test check_and_update_level function."""

    def test_perfect_quiz_increments_streak_no_levelup(self, test_db):
        """Perfect quiz should increment streak but not level up if streak < 10."""
        user = User(id="test-user-1", current_level=1, consecutive_perfect_streak=3)
        test_db.add(user)

        quiz = QuizAttempt(
            user_id=user.id,
            question_count=QUESTIONS_PER_QUIZ,
            correct_count=QUESTIONS_PER_QUIZ  # Perfect score
        )
        test_db.add(quiz)
        test_db.commit()

        result = check_and_update_level(test_db, user, quiz)

        assert result is None  # No level-up
        assert user.consecutive_perfect_streak == 4
        assert user.current_level == 1
        assert user.level_up_count == 0

    def test_non_perfect_quiz_resets_streak(self, test_db):
        """Non-perfect quiz should reset streak to 0."""
        user = User(id="test-user-2", current_level=1, consecutive_perfect_streak=7)
        test_db.add(user)

        quiz = QuizAttempt(
            user_id=user.id,
            question_count=QUESTIONS_PER_QUIZ,
            correct_count=12  # Not perfect
        )
        test_db.add(quiz)
        test_db.commit()

        result = check_and_update_level(test_db, user, quiz)

        assert result is None
        assert user.consecutive_perfect_streak == 0
        assert user.current_level == 1

    def test_level_up_from_1_to_2_at_10_streak(self, test_db):
        """User should level up from 1 to 2 after 5 perfect quizzes."""
        user = User(id="test-user-3", current_level=1, consecutive_perfect_streak=4)
        test_db.add(user)

        quiz = QuizAttempt(
            user_id=user.id,
            question_count=QUESTIONS_PER_QUIZ,
            correct_count=QUESTIONS_PER_QUIZ
        )
        test_db.add(quiz)
        test_db.commit()

        result = check_and_update_level(test_db, user, quiz)

        # Verify return value
        assert result is not None
        assert result["leveled_up"] is True
        assert result["from_level"] == 1
        assert result["to_level"] == 2
        assert result["streak_count"] == PERFECT_STREAK_FOR_LEVEL_UP

        # Verify user state
        assert user.current_level == 2
        assert user.consecutive_perfect_streak == 0  # Reset after level-up
        assert user.level_up_count == 1

        # Verify progression record created
        progression = test_db.query(LevelProgression).filter(
            LevelProgression.user_id == user.id
        ).first()
        assert progression is not None
        assert progression.from_level == 1
        assert progression.to_level == 2
        assert progression.perfect_streak_count == PERFECT_STREAK_FOR_LEVEL_UP

    def test_level_up_from_2_to_3(self, test_db):
        """User should level up from 2 to 3 after 5 perfect quizzes."""
        user = User(
            id="test-user-4",
            current_level=2,
            consecutive_perfect_streak=4,
            level_up_count=1
        )
        test_db.add(user)

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
        assert result["from_level"] == 2
        assert result["to_level"] == 3

        assert user.current_level == 3
        assert user.consecutive_perfect_streak == 0
        assert user.level_up_count == 2

    def test_no_level_up_beyond_level_3(self, test_db):
        """User at level 3 should not level up even with 10 perfect quizzes."""
        user = User(
            id="test-user-5",
            current_level=3,
            consecutive_perfect_streak=9,
            level_up_count=2
        )
        test_db.add(user)

        quiz = QuizAttempt(
            user_id=user.id,
            question_count=QUESTIONS_PER_QUIZ,
            correct_count=QUESTIONS_PER_QUIZ
        )
        test_db.add(quiz)
        test_db.commit()

        result = check_and_update_level(test_db, user, quiz)

        # No level-up but streak should still increment
        assert result is None
        assert user.current_level == 3
        assert user.consecutive_perfect_streak == 10
        assert user.level_up_count == 2

        # No new progression record
        progressions = test_db.query(LevelProgression).filter(
            LevelProgression.user_id == user.id
        ).all()
        assert len(progressions) == 0

    def test_streak_exactly_at_threshold(self, test_db):
        """Test level-up when streak is exactly at threshold after increment."""
        user = User(id="test-user-6", current_level=1, consecutive_perfect_streak=9)
        test_db.add(user)

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

    def test_streak_above_threshold_still_levels_up(self, test_db):
        """Test level-up when streak is above threshold (edge case check)."""
        # This should not happen in production, but test defensive coding
        user = User(id="test-user-7", current_level=1, consecutive_perfect_streak=12)
        test_db.add(user)

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

    def test_quiz_with_13_correct_not_perfect(self, test_db):
        """Quiz with 13/14 correct is not perfect and should reset streak."""
        user = User(id="test-user-8", current_level=1, consecutive_perfect_streak=5)
        test_db.add(user)

        quiz = QuizAttempt(
            user_id=user.id,
            question_count=QUESTIONS_PER_QUIZ,
            correct_count=13  # One wrong
        )
        test_db.add(quiz)
        test_db.commit()

        result = check_and_update_level(test_db, user, quiz)

        assert result is None
        assert user.consecutive_perfect_streak == 0

    def test_multiple_level_ups_tracked(self, test_db):
        """Test that multiple level-ups create multiple progression records."""
        user = User(id="test-user-9", current_level=1, consecutive_perfect_streak=9)
        test_db.add(user)
        test_db.commit()

        # First level-up (1 -> 2)
        quiz1 = QuizAttempt(
            user_id=user.id,
            question_count=QUESTIONS_PER_QUIZ,
            correct_count=QUESTIONS_PER_QUIZ
        )
        test_db.add(quiz1)
        test_db.commit()

        check_and_update_level(test_db, user, quiz1)
        assert user.current_level == 2

        # Build streak again
        user.consecutive_perfect_streak = 9
        test_db.commit()

        # Second level-up (2 -> 3)
        quiz2 = QuizAttempt(
            user_id=user.id,
            question_count=QUESTIONS_PER_QUIZ,
            correct_count=QUESTIONS_PER_QUIZ
        )
        test_db.add(quiz2)
        test_db.commit()

        check_and_update_level(test_db, user, quiz2)
        assert user.current_level == 3

        # Verify both progressions tracked
        progressions = test_db.query(LevelProgression).filter(
            LevelProgression.user_id == user.id
        ).order_by(LevelProgression.achieved_at).all()

        assert len(progressions) == 2
        assert progressions[0].from_level == 1
        assert progressions[0].to_level == 2
        assert progressions[1].from_level == 2
        assert progressions[1].to_level == 3


class TestGetLevelProgress:
    """Test get_level_progress function."""

    def test_progress_at_level_1_with_0_streak(self, test_db):
        """User at level 1 with 0 streak should have 0% progress."""
        user = User(id="test-progress-1", current_level=1, consecutive_perfect_streak=0)
        test_db.add(user)
        test_db.commit()

        progress = get_level_progress(user)

        assert progress["current_level"] == 1
        assert progress["max_level"] == 3
        assert progress["can_level_up"] is True
        assert progress["perfect_streak"] == 0
        assert progress["required_streak"] == PERFECT_STREAK_FOR_LEVEL_UP
        assert progress["progress_percentage"] == 0.0

    def test_progress_at_level_1_with_5_streak(self, test_db):
        """User at level 1 with 2 streak should have 40% progress."""
        user = User(id="test-progress-2", current_level=1, consecutive_perfect_streak=2)
        test_db.add(user)
        test_db.commit()

        progress = get_level_progress(user)

        assert progress["current_level"] == 1
        assert progress["perfect_streak"] == 2
        assert progress["progress_percentage"] == 40.0

    def test_progress_at_level_2_with_8_streak(self, test_db):
        """User at level 2 with 4 streak should have 80% progress."""
        user = User(id="test-progress-3", current_level=2, consecutive_perfect_streak=4)
        test_db.add(user)
        test_db.commit()

        progress = get_level_progress(user)

        assert progress["current_level"] == 2
        assert progress["perfect_streak"] == 4
        assert progress["progress_percentage"] == 80.0

    def test_progress_at_level_3_cannot_level_up(self, test_db):
        """User at level 3 cannot level up."""
        user = User(id="test-progress-4", current_level=3, consecutive_perfect_streak=5)
        test_db.add(user)
        test_db.commit()

        progress = get_level_progress(user)

        assert progress["current_level"] == 3
        assert progress["max_level"] == 3
        assert progress["can_level_up"] is False
        assert progress["perfect_streak"] == 5
        assert progress["progress_percentage"] == 0.0  # No progress when at max level

    def test_progress_at_level_3_with_high_streak(self, test_db):
        """User at level 3 with high streak shows 0% progress."""
        user = User(id="test-progress-5", current_level=3, consecutive_perfect_streak=25)
        test_db.add(user)
        test_db.commit()

        progress = get_level_progress(user)

        assert progress["can_level_up"] is False
        assert progress["perfect_streak"] == 25
        assert progress["progress_percentage"] == 0.0

    def test_progress_percentage_rounding(self, test_db):
        """Progress percentage should be rounded to 1 decimal place."""
        user = User(id="test-progress-6", current_level=1, consecutive_perfect_streak=1)
        test_db.add(user)
        test_db.commit()

        progress = get_level_progress(user)

        # 1/5 = 0.2 = 20.0%
        assert progress["progress_percentage"] == 20.0
        assert isinstance(progress["progress_percentage"], float)


class TestGetLevelDescription:
    """Test get_level_description function."""

    def test_level_1_description(self):
        """Level 1 should have correct mechanics."""
        desc = get_level_description(1)

        assert desc["level"] == 1
        assert desc["name"] == "Beginner"
        assert desc["audio_ratio"] == 40
        assert desc["distractor_count"] == 3
        assert desc["distractor_type"] == "random"
        assert "description" in desc

    def test_level_2_description(self):
        """Level 2 should have correct mechanics."""
        desc = get_level_description(2)

        assert desc["level"] == 2
        assert desc["name"] == "Intermediate"
        assert desc["audio_ratio"] == 65
        assert desc["distractor_count"] == 3
        assert desc["distractor_type"] == "similar"
        assert "description" in desc

    def test_level_3_description(self):
        """Level 3 should have correct mechanics."""
        desc = get_level_description(3)

        assert desc["level"] == 3
        assert desc["name"] == "Advanced"
        assert desc["audio_ratio"] == 90
        assert desc["distractor_count"] == 3
        assert desc["distractor_type"] == "extremely_similar"
        assert "description" in desc

    def test_invalid_level_returns_level_1(self):
        """Invalid level should default to level 1."""
        desc = get_level_description(99)

        assert desc["level"] == 1
        assert desc["name"] == "Beginner"

    def test_zero_level_returns_level_1(self):
        """Zero level should default to level 1."""
        desc = get_level_description(0)

        assert desc["level"] == 1
