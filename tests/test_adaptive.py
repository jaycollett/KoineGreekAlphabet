"""Unit tests for adaptive selection algorithm."""
import pytest
from datetime import datetime
from app.db.models import QuizAttempt, UserLetterStat, Letter
from app.services.adaptive import (
    should_use_adaptive_mode,
    select_letters_for_quiz,
    select_letter_balanced,
    select_letter_adaptive,
    get_user_letter_stats_map
)


class TestAdaptiveMode:
    """Tests for adaptive mode activation."""

    def test_adaptive_mode_not_active_initially(self, test_db, test_user):
        """Adaptive mode should not be active for new users."""
        assert should_use_adaptive_mode(test_db, test_user.id) is False

    def test_adaptive_mode_activates_after_10_quizzes(self, test_db, test_user):
        """Adaptive mode should activate after 10 completed quizzes."""
        # Create 9 completed quizzes
        for i in range(9):
            quiz = QuizAttempt(
                user_id=test_user.id,
                question_count=14,
                correct_count=10,
                accuracy=0.71,
                completed_at=datetime.utcnow()
            )
            test_db.add(quiz)
        test_db.commit()

        # Should not be active yet
        assert should_use_adaptive_mode(test_db, test_user.id) is False

        # Add 10th quiz
        quiz = QuizAttempt(
            user_id=test_user.id,
            question_count=14,
            correct_count=12,
            accuracy=0.86,
            completed_at=datetime.utcnow()
        )
        test_db.add(quiz)
        test_db.commit()

        # Now should be active
        assert should_use_adaptive_mode(test_db, test_user.id) is True


class TestLetterSelection:
    """Tests for letter selection algorithms."""

    def test_select_letters_returns_correct_count(self, test_db, test_user):
        """Should return exactly the requested number of letters."""
        letters = select_letters_for_quiz(test_db, test_user.id, count=14)
        assert len(letters) == 14

    def test_select_letters_returns_varied_letters(self, test_db, test_user):
        """Should return a variety of letters, not just one repeated."""
        letters = select_letters_for_quiz(test_db, test_user.id, count=14)
        unique_letters = set(letter.id for letter in letters)
        # Should have some variety (at least 5 different letters in 14 questions)
        assert len(unique_letters) >= 5

    def test_balanced_mode_for_new_users(self, test_db, test_user):
        """New users should use balanced selection."""
        # Initialize stats for all letters
        all_letters = test_db.query(Letter).all()
        for letter in all_letters:
            stat = UserLetterStat(user_id=test_user.id, letter_id=letter.id)
            test_db.add(stat)
        test_db.commit()

        letters = select_letters_for_quiz(test_db, test_user.id, count=14)

        # Should have good coverage of alphabet
        unique_letters = set(letter.id for letter in letters)
        assert len(unique_letters) >= 10  # Expect good variety


class TestBalancedSelection:
    """Tests for balanced selection mode."""

    def test_prefers_unseen_letters(self, test_db, test_user):
        """Balanced mode should prefer letters that haven't been seen."""
        all_letters = test_db.query(Letter).all()
        stats_map = {}

        # Create stats: some letters seen, some not
        for i, letter in enumerate(all_letters[:10]):
            stat = UserLetterStat(
                user_id=test_user.id,
                letter_id=letter.id,
                seen_count=5 if i < 5 else 0
            )
            test_db.add(stat)
            stats_map[letter.id] = stat
        test_db.commit()

        # Select many times and track selections
        selections = []
        for _ in range(50):
            letter = select_letter_balanced(test_db, all_letters[:10], stats_map, [])
            selections.append(letter.id)

        # Unseen letters (ids 6-10) should appear more often
        unseen_count = sum(1 for lid in selections if lid > 5)
        seen_count = sum(1 for lid in selections if lid <= 5)

        # Unseen should be selected more frequently
        assert unseen_count > seen_count


class TestAdaptiveSelection:
    """Tests for adaptive selection mode."""

    def test_focuses_on_weak_letters(self, test_db, test_user):
        """Adaptive mode should focus more on weaker letters."""
        all_letters = test_db.query(Letter).all()
        stats_map = {}

        # Create mixed stats: some mastered, some weak
        for i, letter in enumerate(all_letters):
            if i < 10:
                # Weak letters
                stat = UserLetterStat(
                    user_id=test_user.id,
                    letter_id=letter.id,
                    seen_count=5,
                    correct_count=2,
                    current_streak=0,
                    mastery_score=0.3
                )
            else:
                # Mastered letters
                stat = UserLetterStat(
                    user_id=test_user.id,
                    letter_id=letter.id,
                    seen_count=10,
                    correct_count=10,
                    current_streak=10,
                    mastery_score=1.0
                )
            test_db.add(stat)
            stats_map[letter.id] = stat
        test_db.commit()

        # Select weak letters multiple times
        weak_selections = []
        for _ in range(30):
            letter = select_letter_adaptive(
                test_db, all_letters, stats_map, [], force_weak=True
            )
            weak_selections.append(letter.id)

        # Should primarily select from weak letters (first 10)
        weak_count = sum(1 for lid in weak_selections if lid <= 10)
        assert weak_count >= 25  # At least 80% should be weak letters
