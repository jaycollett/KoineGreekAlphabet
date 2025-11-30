"""Integration tests for API endpoints."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.db.database import Base, get_db
from app.db.models import Letter, User, UserLetterStat, QuizAttempt, QuizQuestion
from app.db.init_db import GREEK_ALPHABET


@pytest.fixture(scope="function")
def test_client():
    """Create a test client with in-memory database."""
    # Create test database with thread-safety disabled for testing
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=None
    )
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    # Override dependency
    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    # Seed Greek alphabet
    db = TestingSessionLocal()
    for letter_data in GREEK_ALPHABET:
        letter = Letter(**letter_data)
        db.add(letter)
    db.commit()
    db.close()

    # Create test client
    client = TestClient(app)

    yield client

    # Cleanup
    app.dependency_overrides.clear()


class TestBootstrapEndpoint:
    """Tests for /api/bootstrap endpoint."""

    def test_bootstrap_creates_new_user(self, test_client):
        """Bootstrap should create a new user if none exists."""
        response = test_client.get("/api/bootstrap")

        assert response.status_code == 200
        data = response.json()

        assert "user_id" in data
        assert data["user_id"].startswith("gam_")
        assert data["total_quizzes"] == 0
        assert "gam_uid" in response.cookies

    def test_bootstrap_returns_existing_user(self, test_client):
        """Bootstrap should recognize existing user by cookie."""
        # First request
        response1 = test_client.get("/api/bootstrap")
        user_id_1 = response1.json()["user_id"]

        # Second request with same cookie
        cookies = {"gam_uid": user_id_1}
        response2 = test_client.get("/api/bootstrap", cookies=cookies)
        user_id_2 = response2.json()["user_id"]

        assert user_id_1 == user_id_2

    def test_bootstrap_returns_quiz_history(self, test_client):
        """Bootstrap should return quiz history if quizzes completed."""
        response = test_client.get("/api/bootstrap")
        assert response.status_code == 200

        data = response.json()
        assert "quiz_history" in data
        assert isinstance(data["quiz_history"], list)


class TestQuizFlow:
    """Integration tests for complete quiz flow."""

    def test_start_quiz_creates_quiz(self, test_client):
        """Starting a quiz should create quiz with 14 questions."""
        # Bootstrap first to get user
        test_client.get("/api/bootstrap")

        # Start quiz
        response = test_client.post("/api/quiz/start")

        assert response.status_code == 200
        data = response.json()

        assert "quiz_id" in data
        assert data["question_count"] == 14
        assert len(data["questions"]) == 14

    def test_quiz_questions_have_required_fields(self, test_client):
        """Quiz questions should have all required fields."""
        test_client.get("/api/bootstrap")
        response = test_client.post("/api/quiz/start")
        data = response.json()

        for question in data["questions"]:
            assert "question_id" in question
            assert "question_number" in question
            assert "prompt" in question
            assert "options" in question
            assert "correct_answer" in question
            assert len(question["options"]) == 4

    def test_submit_correct_answer(self, test_client):
        """Submitting correct answer should return success."""
        test_client.get("/api/bootstrap")

        # Start quiz
        quiz_response = test_client.post("/api/quiz/start")
        quiz_data = quiz_response.json()
        quiz_id = quiz_data["quiz_id"]
        first_question = quiz_data["questions"][0]

        # Submit correct answer
        answer_response = test_client.post(
            f"/api/quiz/{quiz_id}/answer",
            json={
                "question_id": first_question["question_id"],
                "selected_option": first_question["correct_answer"]
            }
        )

        assert answer_response.status_code == 200
        result = answer_response.json()

        assert result["is_correct"] is True
        assert result["is_last_question"] is False

    def test_submit_incorrect_answer(self, test_client):
        """Submitting incorrect answer should return failure."""
        test_client.get("/api/bootstrap")

        # Start quiz
        quiz_response = test_client.post("/api/quiz/start")
        quiz_data = quiz_response.json()
        quiz_id = quiz_data["quiz_id"]
        first_question = quiz_data["questions"][0]

        # Find wrong answer
        wrong_option = None
        for option in first_question["options"]:
            if option != first_question["correct_answer"]:
                wrong_option = option
                break

        # Submit wrong answer
        answer_response = test_client.post(
            f"/api/quiz/{quiz_id}/answer",
            json={
                "question_id": first_question["question_id"],
                "selected_option": wrong_option
            }
        )

        assert answer_response.status_code == 200
        result = answer_response.json()

        assert result["is_correct"] is False
        assert result["correct_answer"] == first_question["correct_answer"]

    def test_complete_full_quiz(self, test_client):
        """Completing all 14 questions should generate summary."""
        test_client.get("/api/bootstrap")

        # Start quiz
        quiz_response = test_client.post("/api/quiz/start")
        quiz_data = quiz_response.json()
        quiz_id = quiz_data["quiz_id"]

        # Answer all questions
        for i, question in enumerate(quiz_data["questions"]):
            is_last = (i == 13)

            response = test_client.post(
                f"/api/quiz/{quiz_id}/answer",
                json={
                    "question_id": question["question_id"],
                    "selected_option": question["correct_answer"]  # All correct
                }
            )

            assert response.status_code == 200
            result = response.json()

            if is_last:
                assert result["is_last_question"] is True
                assert "summary" in result
                summary = result["summary"]

                assert summary["correct_count"] == 14
                assert summary["question_count"] == 14
                assert summary["accuracy"] == 1.0
                assert summary["accuracy_percentage"] == 100.0
            else:
                assert result["is_last_question"] is False

    def test_quiz_updates_user_stats(self, test_client):
        """Completing quiz should update user letter statistics."""
        # Bootstrap
        bootstrap_response = test_client.get("/api/bootstrap")
        initial_data = bootstrap_response.json()

        # Complete a quiz with all correct answers
        quiz_response = test_client.post("/api/quiz/start")
        quiz_data = quiz_response.json()
        quiz_id = quiz_data["quiz_id"]

        for question in quiz_data["questions"]:
            test_client.post(
                f"/api/quiz/{quiz_id}/answer",
                json={
                    "question_id": question["question_id"],
                    "selected_option": question["correct_answer"]
                }
            )

        # Check bootstrap again
        final_bootstrap = test_client.get("/api/bootstrap")
        final_data = final_bootstrap.json()

        # Should now have 1 completed quiz
        assert final_data["total_quizzes"] == 1
        assert len(final_data["quiz_history"]) == 1
        assert final_data["quiz_history"][0]["accuracy"] == 1.0


class TestTrendIndicator:
    """Tests for performance trend indicator feature."""

    def _complete_quiz(self, test_client, correct_count=14):
        """Helper to complete a quiz with specified number of correct answers."""
        # Ensure test_client has JSON body support
        quiz_response = test_client.post("/api/quiz/start", json={"include_audio": True})
        quiz_data = quiz_response.json()
        quiz_id = quiz_data["quiz_id"]
        questions = quiz_data["questions"]

        # Answer questions (correct for first N, incorrect for rest)
        for i, question in enumerate(questions):
            if i < correct_count:
                selected = question["correct_answer"]
            else:
                # Pick first wrong answer
                selected = next(opt for opt in question["options"] if opt != question["correct_answer"])

            response = test_client.post(
                f"/api/quiz/{quiz_id}/answer",
                json={
                    "question_id": question["question_id"],
                    "selected_option": selected
                }
            )

            if i == len(questions) - 1:
                return response.json()

    def test_no_trend_with_less_than_3_previous_quizzes(self, test_client):
        """Trend should not be shown when user has fewer than 3 previous quizzes."""
        test_client.get("/api/bootstrap")

        # Complete first quiz
        result = self._complete_quiz(test_client, correct_count=10)

        # First quiz should have no trend (0 previous)
        assert "summary" in result
        assert result["summary"]["trend"] is None

        # Complete second quiz
        result = self._complete_quiz(test_client, correct_count=10)

        # Second quiz should have no trend (1 previous)
        assert result["summary"]["trend"] is None

        # Complete third quiz
        result = self._complete_quiz(test_client, correct_count=10)

        # Third quiz should have no trend (2 previous)
        assert result["summary"]["trend"] is None

    def test_trend_shown_after_3_previous_quizzes(self, test_client):
        """Trend should be shown starting from the 4th quiz."""
        test_client.get("/api/bootstrap")

        # Complete 3 quizzes
        for _ in range(3):
            self._complete_quiz(test_client, correct_count=10)

        # Fourth quiz should have trend
        result = self._complete_quiz(test_client, correct_count=10)

        assert "summary" in result
        assert result["summary"]["trend"] is not None
        assert "trend" in result["summary"]["trend"]
        assert "change_percent" in result["summary"]["trend"]
        assert "recent_average" in result["summary"]["trend"]

    def test_improving_trend(self, test_client):
        """Trend should show 'up' when performance improves by 5% or more."""
        test_client.get("/api/bootstrap")

        # Complete 3 quizzes with 60% accuracy (8-9 correct)
        for _ in range(3):
            self._complete_quiz(test_client, correct_count=8)

        # Fourth quiz with 85% accuracy (12 correct) - significant improvement
        result = self._complete_quiz(test_client, correct_count=12)

        summary = result["summary"]
        assert summary["trend"] is not None
        assert summary["trend"]["trend"] == "up"
        assert summary["trend"]["change_percent"] > 5.0

    def test_declining_trend(self, test_client):
        """Trend should show 'down' when performance declines by 5% or more."""
        test_client.get("/api/bootstrap")

        # Complete 3 quizzes with 85% accuracy (12 correct)
        for _ in range(3):
            self._complete_quiz(test_client, correct_count=12)

        # Fourth quiz with 50% accuracy (7 correct) - significant decline
        result = self._complete_quiz(test_client, correct_count=7)

        summary = result["summary"]
        assert summary["trend"] is not None
        assert summary["trend"]["trend"] == "down"
        assert summary["trend"]["change_percent"] < -5.0

    def test_stable_trend(self, test_client):
        """Trend should show 'stable' when performance is within ±5%."""
        test_client.get("/api/bootstrap")

        # Complete 3 quizzes with 71% accuracy (10 correct)
        for _ in range(3):
            self._complete_quiz(test_client, correct_count=10)

        # Fourth quiz with 71% accuracy (10 correct) - same performance
        result = self._complete_quiz(test_client, correct_count=10)

        summary = result["summary"]
        assert summary["trend"] is not None
        assert summary["trend"]["trend"] == "stable"
        assert -5.0 <= summary["trend"]["change_percent"] <= 5.0

    def test_trend_uses_last_3_quizzes_only(self, test_client):
        """Trend should only compare against the most recent 3 quizzes."""
        test_client.get("/api/bootstrap")

        # Complete 5 poor quizzes (50% accuracy)
        for _ in range(5):
            self._complete_quiz(test_client, correct_count=7)

        # Complete 3 good quizzes (85% accuracy)
        for _ in range(3):
            self._complete_quiz(test_client, correct_count=12)

        # Next quiz should compare against last 3 (85% avg), not all 8
        result = self._complete_quiz(test_client, correct_count=12)

        summary = result["summary"]
        assert summary["trend"] is not None
        # Should be stable since last 3 quizzes were also ~85%
        assert summary["trend"]["trend"] == "stable"

    def test_trend_boundary_at_5_percent(self, test_client):
        """Test exact boundary conditions at ±5%."""
        test_client.get("/api/bootstrap")

        # Complete 3 quizzes with 71.4% accuracy (10 correct out of 14)
        for _ in range(3):
            self._complete_quiz(test_client, correct_count=10)

        # Test just at boundary: 71.4% + 5% = 76.4%
        # 11 correct = 78.6%, should be "up"
        result = self._complete_quiz(test_client, correct_count=11)
        assert result["summary"]["trend"]["trend"] == "up"

        # Complete 3 more at 71.4%
        for _ in range(3):
            self._complete_quiz(test_client, correct_count=10)

        # Test just below boundary: ~71% should be "stable"
        result = self._complete_quiz(test_client, correct_count=10)
        assert result["summary"]["trend"]["trend"] == "stable"

    def test_trend_recent_average_calculation(self, test_client):
        """Verify recent_average is calculated correctly."""
        test_client.get("/api/bootstrap")

        # Complete 3 quizzes: 50%, 60%, 70% = 60% average
        self._complete_quiz(test_client, correct_count=7)   # 50%
        self._complete_quiz(test_client, correct_count=8)   # ~57%
        self._complete_quiz(test_client, correct_count=10)  # ~71%

        # Fourth quiz
        result = self._complete_quiz(test_client, correct_count=10)

        summary = result["summary"]
        assert summary["trend"] is not None
        # Recent average should be around 59-60%
        assert 55.0 <= summary["trend"]["recent_average"] <= 65.0


class TestErrorHandling:
    """Tests for error handling in API."""

    def test_submit_answer_without_user(self, test_client):
        """Submitting answer without user cookie should fail."""
        response = test_client.post(
            "/api/quiz/1/answer",
            json={
                "question_id": 1,
                "selected_option": "Alpha"
            }
        )

        assert response.status_code == 401

    def test_start_quiz_without_user(self, test_client):
        """Starting quiz without user cookie should fail."""
        response = test_client.post("/api/quiz/start")
        assert response.status_code == 401

    def test_submit_answer_to_nonexistent_quiz(self, test_client):
        """Submitting answer to non-existent quiz should fail."""
        test_client.get("/api/bootstrap")

        response = test_client.post(
            "/api/quiz/99999/answer",
            json={
                "question_id": 1,
                "selected_option": "Alpha"
            }
        )

        assert response.status_code == 404
