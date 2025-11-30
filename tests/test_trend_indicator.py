"""Unit tests for performance trend indicator feature."""
import pytest
from datetime import datetime, timedelta
from app.routers.quiz import calculate_trend
from app.db.models import QuizAttempt, User


class TestTrendCalculation:
    """Tests for the calculate_trend function."""

    def test_no_trend_with_fewer_than_3_quizzes(self, test_db):
        """Should return None when there are fewer than 3 previous quizzes."""
        # Create user
        user = User(id="test_user_trend_1")
        test_db.add(user)
        test_db.commit()

        # Create 2 previous quizzes
        for i in range(2):
            quiz = QuizAttempt(
                user_id=user.id,
                question_count=14,
                correct_count=10,
                accuracy=10/14,
                started_at=datetime.utcnow() - timedelta(days=i+1),
                completed_at=datetime.utcnow() - timedelta(days=i+1)
            )
            test_db.add(quiz)
        test_db.commit()

        # Current quiz
        current_quiz = QuizAttempt(
            user_id=user.id,
            question_count=14,
            correct_count=10,
            accuracy=10/14,
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow()
        )
        test_db.add(current_quiz)
        test_db.commit()

        # Should return None with only 2 previous quizzes
        trend = calculate_trend(test_db, user.id, current_quiz.id, current_quiz.accuracy)
        assert trend is None

    def test_trend_shown_with_3_previous_quizzes(self, test_db):
        """Should return trend data when there are 3 or more previous quizzes."""
        # Create user
        user = User(id="test_user_trend_2")
        test_db.add(user)
        test_db.commit()

        # Create 3 previous quizzes with 70% accuracy
        for i in range(3):
            quiz = QuizAttempt(
                user_id=user.id,
                question_count=14,
                correct_count=10,
                accuracy=10/14,
                started_at=datetime.utcnow() - timedelta(days=i+1),
                completed_at=datetime.utcnow() - timedelta(days=i+1)
            )
            test_db.add(quiz)
        test_db.commit()

        # Current quiz with 70% accuracy
        current_quiz = QuizAttempt(
            user_id=user.id,
            question_count=14,
            correct_count=10,
            accuracy=10/14,
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow()
        )
        test_db.add(current_quiz)
        test_db.commit()

        # Should return trend data
        trend = calculate_trend(test_db, user.id, current_quiz.id, current_quiz.accuracy)
        assert trend is not None
        assert "trend" in trend
        assert "change_percent" in trend
        assert "recent_average" in trend

    def test_improving_trend(self, test_db):
        """Should return 'up' trend when performance improves by 5% or more."""
        # Create user
        user = User(id="test_user_trend_3")
        test_db.add(user)
        test_db.commit()

        # Create 3 previous quizzes with 60% accuracy
        for i in range(3):
            quiz = QuizAttempt(
                user_id=user.id,
                question_count=14,
                correct_count=8,
                accuracy=8/14,  # ~57%
                started_at=datetime.utcnow() - timedelta(days=i+1),
                completed_at=datetime.utcnow() - timedelta(days=i+1)
            )
            test_db.add(quiz)
        test_db.commit()

        # Current quiz with 85% accuracy (12 correct) - significant improvement
        current_quiz = QuizAttempt(
            user_id=user.id,
            question_count=14,
            correct_count=12,
            accuracy=12/14,  # ~85.7%
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow()
        )
        test_db.add(current_quiz)
        test_db.commit()

        trend = calculate_trend(test_db, user.id, current_quiz.id, current_quiz.accuracy)
        assert trend is not None
        assert trend["trend"] == "up"
        assert trend["change_percent"] > 5.0

    def test_declining_trend(self, test_db):
        """Should return 'down' trend when performance declines by 5% or more."""
        # Create user
        user = User(id="test_user_trend_4")
        test_db.add(user)
        test_db.commit()

        # Create 3 previous quizzes with 85% accuracy
        for i in range(3):
            quiz = QuizAttempt(
                user_id=user.id,
                question_count=14,
                correct_count=12,
                accuracy=12/14,  # ~85.7%
                started_at=datetime.utcnow() - timedelta(days=i+1),
                completed_at=datetime.utcnow() - timedelta(days=i+1)
            )
            test_db.add(quiz)
        test_db.commit()

        # Current quiz with 50% accuracy - significant decline
        current_quiz = QuizAttempt(
            user_id=user.id,
            question_count=14,
            correct_count=7,
            accuracy=7/14,  # 50%
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow()
        )
        test_db.add(current_quiz)
        test_db.commit()

        trend = calculate_trend(test_db, user.id, current_quiz.id, current_quiz.accuracy)
        assert trend is not None
        assert trend["trend"] == "down"
        assert trend["change_percent"] < -5.0

    def test_stable_trend(self, test_db):
        """Should return 'stable' trend when performance is within ±5%."""
        # Create user
        user = User(id="test_user_trend_5")
        test_db.add(user)
        test_db.commit()

        # Create 3 previous quizzes with 71% accuracy
        for i in range(3):
            quiz = QuizAttempt(
                user_id=user.id,
                question_count=14,
                correct_count=10,
                accuracy=10/14,  # ~71.4%
                started_at=datetime.utcnow() - timedelta(days=i+1),
                completed_at=datetime.utcnow() - timedelta(days=i+1)
            )
            test_db.add(quiz)
        test_db.commit()

        # Current quiz with same 71% accuracy
        current_quiz = QuizAttempt(
            user_id=user.id,
            question_count=14,
            correct_count=10,
            accuracy=10/14,
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow()
        )
        test_db.add(current_quiz)
        test_db.commit()

        trend = calculate_trend(test_db, user.id, current_quiz.id, current_quiz.accuracy)
        assert trend is not None
        assert trend["trend"] == "stable"
        assert -5.0 <= trend["change_percent"] <= 5.0

    def test_trend_uses_last_3_quizzes_only(self, test_db):
        """Should only compare against the most recent 3 quizzes, not all quizzes."""
        # Create user
        user = User(id="test_user_trend_6")
        test_db.add(user)
        test_db.commit()

        # Create 5 old poor quizzes (50% accuracy)
        for i in range(8, 3, -1):
            quiz = QuizAttempt(
                user_id=user.id,
                question_count=14,
                correct_count=7,
                accuracy=7/14,  # 50%
                started_at=datetime.utcnow() - timedelta(days=i),
                completed_at=datetime.utcnow() - timedelta(days=i)
            )
            test_db.add(quiz)

        # Create 3 recent good quizzes (85% accuracy)
        for i in range(3, 0, -1):
            quiz = QuizAttempt(
                user_id=user.id,
                question_count=14,
                correct_count=12,
                accuracy=12/14,  # ~85.7%
                started_at=datetime.utcnow() - timedelta(days=i),
                completed_at=datetime.utcnow() - timedelta(days=i)
            )
            test_db.add(quiz)
        test_db.commit()

        # Current quiz with 85% accuracy - should compare to last 3, not all 8
        current_quiz = QuizAttempt(
            user_id=user.id,
            question_count=14,
            correct_count=12,
            accuracy=12/14,
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow()
        )
        test_db.add(current_quiz)
        test_db.commit()

        trend = calculate_trend(test_db, user.id, current_quiz.id, current_quiz.accuracy)
        assert trend is not None
        # Should be stable since last 3 quizzes were also ~85%
        assert trend["trend"] == "stable"
        # Recent average should be around 85%, not 60% (which would be if all 8 counted)
        assert trend["recent_average"] > 80.0

    def test_trend_excludes_current_quiz(self, test_db):
        """Should not include current quiz in the calculation."""
        # Create user
        user = User(id="test_user_trend_7")
        test_db.add(user)
        test_db.commit()

        # Create exactly 3 quizzes with 50% accuracy
        for i in range(3):
            quiz = QuizAttempt(
                user_id=user.id,
                question_count=14,
                correct_count=7,
                accuracy=7/14,  # 50%
                started_at=datetime.utcnow() - timedelta(days=i+1),
                completed_at=datetime.utcnow() - timedelta(days=i+1)
            )
            test_db.add(quiz)
        test_db.commit()

        # Current quiz with 100% accuracy
        current_quiz = QuizAttempt(
            user_id=user.id,
            question_count=14,
            correct_count=14,
            accuracy=1.0,  # 100%
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow()
        )
        test_db.add(current_quiz)
        test_db.commit()

        trend = calculate_trend(test_db, user.id, current_quiz.id, current_quiz.accuracy)
        assert trend is not None
        # Recent average should be 50%, not inflated by current 100%
        assert 49.0 <= trend["recent_average"] <= 51.0
        # Trend should be "up" since 100% is much higher than 50%
        assert trend["trend"] == "up"
        assert trend["change_percent"] > 40.0

    def test_trend_recent_average_accuracy(self, test_db):
        """Verify recent_average is calculated correctly."""
        # Create user
        user = User(id="test_user_trend_8")
        test_db.add(user)
        test_db.commit()

        # Create 3 quizzes with known accuracies: 50%, 60%, 70% = 60% average
        accuracies = [7/14, 8/14, 10/14]  # ~50%, ~57%, ~71%
        for i, acc in enumerate(accuracies):
            quiz = QuizAttempt(
                user_id=user.id,
                question_count=14,
                correct_count=int(acc * 14),
                accuracy=acc,
                started_at=datetime.utcnow() - timedelta(days=len(accuracies)-i),
                completed_at=datetime.utcnow() - timedelta(days=len(accuracies)-i)
            )
            test_db.add(quiz)
        test_db.commit()

        # Current quiz
        current_quiz = QuizAttempt(
            user_id=user.id,
            question_count=14,
            correct_count=10,
            accuracy=10/14,
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow()
        )
        test_db.add(current_quiz)
        test_db.commit()

        trend = calculate_trend(test_db, user.id, current_quiz.id, current_quiz.accuracy)
        assert trend is not None

        # Calculate expected average: (50 + 57 + 71) / 3 = 59.5%
        expected_avg = sum(acc * 100 for acc in accuracies) / len(accuracies)
        # Allow small rounding difference
        assert abs(trend["recent_average"] - expected_avg) < 2.0
