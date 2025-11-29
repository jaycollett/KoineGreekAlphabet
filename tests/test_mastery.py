"""Unit tests for mastery calculation service."""
import pytest
from app.services.mastery import (
    calculate_mastery_score,
    get_mastery_state,
    MasteryState,
    update_letter_stats
)
from app.db.models import UserLetterStat


class TestMasteryScoreCalculation:
    """Tests for mastery score calculation."""

    def test_unseen_letter_has_zero_score(self):
        """Unseen letters should have mastery score of 0."""
        score = calculate_mastery_score(seen_count=0, correct_count=0, current_streak=0)
        assert score == 0.0

    def test_few_attempts_capped_low(self):
        """Letters with < 3 attempts should have capped scores."""
        # 2 attempts, all correct
        score = calculate_mastery_score(seen_count=2, correct_count=2, current_streak=2)
        assert score <= 0.4  # Capped at 0.4
        assert score > 0

    def test_high_accuracy_with_streak(self):
        """High accuracy with good streak should give high mastery score."""
        # 10 attempts, 9 correct, streak of 5
        score = calculate_mastery_score(seen_count=10, correct_count=9, current_streak=5)
        assert score > 0.8  # Should be high

    def test_perfect_performance(self):
        """Perfect performance should give maximum score."""
        # 10 attempts, all correct, streak of 10
        score = calculate_mastery_score(seen_count=10, correct_count=10, current_streak=10)
        assert score == 1.0  # Capped at 1.0

    def test_poor_performance(self):
        """Poor performance should give low mastery score."""
        # 10 attempts, 3 correct, no streak
        score = calculate_mastery_score(seen_count=10, correct_count=3, current_streak=0)
        assert score < 0.5

    def test_score_bounded_0_to_1(self):
        """Mastery score should always be between 0 and 1."""
        test_cases = [
            (5, 5, 10),   # High streak
            (10, 0, 0),   # All wrong
            (100, 100, 50),  # Very high values
        ]

        for seen, correct, streak in test_cases:
            score = calculate_mastery_score(seen, correct, streak)
            assert 0.0 <= score <= 1.0


class TestMasteryState:
    """Tests for mastery state determination."""

    def test_unseen_state(self):
        """Never seen letters should be UNSEEN."""
        state = get_mastery_state(seen_count=0, correct_count=0, current_streak=0)
        assert state == MasteryState.UNSEEN

    def test_learning_state(self):
        """Letters that don't meet mastery criteria should be LEARNING."""
        # Not enough attempts
        state = get_mastery_state(seen_count=5, correct_count=4, current_streak=3)
        assert state == MasteryState.LEARNING

        # Not enough accuracy
        state = get_mastery_state(seen_count=10, correct_count=7, current_streak=3)
        assert state == MasteryState.LEARNING

        # Not enough streak
        state = get_mastery_state(seen_count=10, correct_count=9, current_streak=2)
        assert state == MasteryState.LEARNING

    def test_mastered_state(self):
        """Letters meeting all criteria should be MASTERED."""
        # Exactly meeting criteria: 8 attempts, 90% accuracy, streak 3
        state = get_mastery_state(seen_count=8, correct_count=8, current_streak=3)
        assert state == MasteryState.MASTERED

        # Exceeding criteria
        state = get_mastery_state(seen_count=10, correct_count=10, current_streak=5)
        assert state == MasteryState.MASTERED

    def test_mastery_boundary_cases(self):
        """Test edge cases for mastery criteria."""
        # Just below mastery (7 attempts)
        state = get_mastery_state(seen_count=7, correct_count=7, current_streak=5)
        assert state == MasteryState.LEARNING

        # Just below 90% accuracy with 8 attempts
        state = get_mastery_state(seen_count=10, correct_count=8, current_streak=5)
        assert state == MasteryState.LEARNING  # 80% < 90%

        # Exactly 90% accuracy
        state = get_mastery_state(seen_count=10, correct_count=9, current_streak=3)
        assert state == MasteryState.MASTERED


class TestUpdateLetterStats:
    """Tests for updating letter statistics."""

    def test_correct_answer_updates(self):
        """Correct answer should increment counts and streak."""
        stat = UserLetterStat(
            user_id="test",
            letter_id=1,
            seen_count=5,
            correct_count=3,
            incorrect_count=2,
            current_streak=1,
            longest_streak=2
        )

        result = update_letter_stats(stat, is_correct=True)

        assert stat.seen_count == 6
        assert stat.correct_count == 4
        assert stat.incorrect_count == 2
        assert stat.current_streak == 2
        assert stat.longest_streak == 2
        assert stat.last_result == "correct"
        assert result["mastery_score"] > 0

    def test_incorrect_answer_resets_streak(self):
        """Incorrect answer should reset streak."""
        stat = UserLetterStat(
            user_id="test",
            letter_id=1,
            seen_count=5,
            correct_count=4,
            incorrect_count=1,
            current_streak=4,
            longest_streak=4
        )

        result = update_letter_stats(stat, is_correct=False)

        assert stat.seen_count == 6
        assert stat.correct_count == 4
        assert stat.incorrect_count == 2
        assert stat.current_streak == 0  # Reset
        assert stat.longest_streak == 4  # Preserved
        assert stat.last_result == "incorrect"

    def test_longest_streak_updated(self):
        """Longest streak should update when current exceeds it."""
        stat = UserLetterStat(
            user_id="test",
            letter_id=1,
            seen_count=2,
            correct_count=2,
            incorrect_count=0,
            current_streak=2,
            longest_streak=2
        )

        update_letter_stats(stat, is_correct=True)

        assert stat.current_streak == 3
        assert stat.longest_streak == 3  # Updated
