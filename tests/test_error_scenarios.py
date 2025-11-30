"""Comprehensive error scenario tests for edge cases and error paths.

Tests various error conditions including:
- Invalid inputs
- Non-existent resources
- Double submissions
- Missing dependencies
- Race conditions
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.db.database import Base, get_db
from app.db.models import User, Letter, QuizAttempt, QuizQuestion
from datetime import datetime

# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """Override database dependency for testing."""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture
def client():
    """Create test client with fresh database."""
    Base.metadata.create_all(bind=engine)
    yield TestClient(app)
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db():
    """Create database session for test setup."""
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def seed_letters(db):
    """Seed database with Greek letters."""
    letters = [
        Letter(name="Alpha", uppercase="Α", lowercase="α", position=1),
        Letter(name="Beta", uppercase="Β", lowercase="β", position=2),
        Letter(name="Gamma", uppercase="Γ", lowercase="γ", position=3),
        Letter(name="Delta", uppercase="Δ", lowercase="δ", position=4),
        Letter(name="Epsilon", uppercase="Ε", lowercase="ε", position=5),
    ]
    for letter in letters:
        db.add(letter)
    db.commit()
    return letters


class TestQuizErrorScenarios:
    """Test error handling in quiz operations."""

    def test_submit_answer_to_nonexistent_question(self, client, seed_letters):
        """Test submitting answer to a question that doesn't exist."""
        # Create user and get session
        response = client.post("/api/user/initialize")
        assert response.status_code == 200
        cookies = response.cookies

        # Try to submit answer to non-existent question
        response = client.post(
            "/api/quiz/999/answer",
            json={"question_id": 99999, "selected_option": "Alpha"},
            cookies=cookies
        )
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_submit_answer_with_invalid_question_id(self, client, seed_letters):
        """Test submitting answer with invalid question ID format."""
        response = client.post("/api/user/initialize")
        cookies = response.cookies

        # Invalid question_id (negative)
        response = client.post(
            "/api/quiz/1/answer",
            json={"question_id": -1, "selected_option": "Alpha"},
            cookies=cookies
        )
        assert response.status_code == 422  # Validation error

    def test_submit_answer_with_empty_option(self, client, seed_letters):
        """Test submitting answer with empty selected_option."""
        response = client.post("/api/user/initialize")
        cookies = response.cookies

        response = client.post(
            "/api/quiz/1/answer",
            json={"question_id": 1, "selected_option": ""},
            cookies=cookies
        )
        assert response.status_code == 422  # Validation error

    def test_submit_answer_with_whitespace_only_option(self, client, seed_letters):
        """Test submitting answer with whitespace-only selected_option."""
        response = client.post("/api/user/initialize")
        cookies = response.cookies

        response = client.post(
            "/api/quiz/1/answer",
            json={"question_id": 1, "selected_option": "   "},
            cookies=cookies
        )
        assert response.status_code == 422  # Validation error

    def test_double_submission_of_same_answer(self, client, db, seed_letters):
        """Test submitting the same answer twice (idempotency)."""
        # Initialize user
        response = client.post("/api/user/initialize")
        user_data = response.json()
        cookies = response.cookies

        # Start quiz
        response = client.post(
            "/api/quiz/start",
            json={"include_audio": False},
            cookies=cookies
        )
        quiz_data = response.json()
        quiz_id = quiz_data["quiz_id"]
        first_question = quiz_data["questions"][0]

        # Submit answer first time
        response1 = client.post(
            f"/api/quiz/{quiz_id}/answer",
            json={
                "question_id": first_question["question_id"],
                "selected_option": first_question["options"][0]
            },
            cookies=cookies
        )
        assert response1.status_code == 200
        result1 = response1.json()

        # Submit same answer again (should return cached result)
        response2 = client.post(
            f"/api/quiz/{quiz_id}/answer",
            json={
                "question_id": first_question["question_id"],
                "selected_option": first_question["options"][0]
            },
            cookies=cookies
        )
        assert response2.status_code == 200
        result2 = response2.json()

        # Should return same result with already_answered flag
        assert result2.get("already_answered") is True
        assert result2["is_correct"] == result1["is_correct"]

    def test_quiz_with_invalid_user_id(self, client, seed_letters):
        """Test creating quiz with non-existent user_id."""
        # Try to start quiz without initializing user
        response = client.post(
            "/api/quiz/start",
            json={"include_audio": False}
        )
        assert response.status_code == 401
        assert "No user session" in response.json()["detail"]

    def test_access_quiz_from_different_user(self, client, db, seed_letters):
        """Test accessing a quiz created by a different user."""
        # Create first user and quiz
        response1 = client.post("/api/user/initialize")
        cookies1 = response1.cookies

        response = client.post(
            "/api/quiz/start",
            json={"include_audio": False},
            cookies=cookies1
        )
        quiz_id = response.json()["quiz_id"]

        # Create second user
        response2 = client.post("/api/user/initialize")
        cookies2 = response2.cookies

        # Try to access first user's quiz with second user's cookies
        response = client.get(f"/api/quiz/{quiz_id}/state", cookies=cookies2)
        assert response.status_code == 404
        assert "Quiz not found" in response.json()["detail"]

    def test_submit_answer_to_completed_quiz(self, client, db, seed_letters):
        """Test submitting answer to an already completed quiz."""
        # Initialize user
        response = client.post("/api/user/initialize")
        cookies = response.cookies

        # Start quiz
        response = client.post(
            "/api/quiz/start",
            json={"include_audio": False},
            cookies=cookies
        )
        quiz_data = response.json()
        quiz_id = quiz_data["quiz_id"]

        # Manually mark quiz as completed
        quiz = db.query(QuizAttempt).filter(QuizAttempt.id == quiz_id).first()
        quiz.completed_at = datetime.utcnow()
        db.commit()

        # Try to submit answer
        first_question = quiz_data["questions"][0]
        response = client.post(
            f"/api/quiz/{quiz_id}/answer",
            json={
                "question_id": first_question["question_id"],
                "selected_option": first_question["options"][0]
            },
            cookies=cookies
        )
        assert response.status_code == 400
        assert "already completed" in response.json()["detail"].lower()

    def test_resume_completed_quiz(self, client, db, seed_letters):
        """Test trying to resume a completed quiz."""
        # Initialize user and start quiz
        response = client.post("/api/user/initialize")
        cookies = response.cookies

        response = client.post(
            "/api/quiz/start",
            json={"include_audio": False},
            cookies=cookies
        )
        quiz_id = response.json()["quiz_id"]

        # Manually mark as completed
        quiz = db.query(QuizAttempt).filter(QuizAttempt.id == quiz_id).first()
        quiz.completed_at = datetime.utcnow()
        db.commit()

        # Try to get quiz state
        response = client.get(f"/api/quiz/{quiz_id}/state", cookies=cookies)
        assert response.status_code == 400
        assert "already completed" in response.json()["detail"].lower()

    def test_get_stats_for_new_user(self, client, seed_letters):
        """Test getting statistics for user with no quiz history."""
        response = client.post("/api/user/initialize")
        cookies = response.cookies

        response = client.get("/api/user/stats", cookies=cookies)
        assert response.status_code == 200
        data = response.json()
        assert data["total_quizzes"] == 0
        assert data["total_questions"] == 0
        assert data["overall_accuracy"] is None

    def test_create_quiz_with_insufficient_letters(self, client, db):
        """Test creating quiz when there aren't enough letters in database."""
        # Don't seed letters, database is empty
        response = client.post("/api/user/initialize")
        cookies = response.cookies

        # Try to start quiz (should fail gracefully)
        response = client.post(
            "/api/quiz/start",
            json={"include_audio": False},
            cookies=cookies
        )
        # Should return 500 or handle gracefully
        assert response.status_code >= 400


class TestUserErrorScenarios:
    """Test error handling in user operations."""

    def test_get_stats_without_session(self, client, seed_letters):
        """Test accessing stats without initializing user session."""
        response = client.get("/api/user/stats")
        assert response.status_code == 401

    def test_initialize_user_multiple_times(self, client, seed_letters):
        """Test that initializing user multiple times returns same user."""
        # First initialization
        response1 = client.post("/api/user/initialize")
        assert response1.status_code == 200
        user_id_1 = response1.json()["user_id"]
        cookies = response1.cookies

        # Second initialization with same cookies
        response2 = client.post("/api/user/initialize", cookies=cookies)
        assert response2.status_code == 200
        user_id_2 = response2.json()["user_id"]

        # Should return same user
        assert user_id_1 == user_id_2


class TestHealthCheckScenarios:
    """Test health check endpoint error scenarios."""

    def test_health_check_with_database_connection(self, client, seed_letters):
        """Test health check returns healthy when database is accessible."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["database"] == "connected"

    def test_readiness_check(self, client, seed_letters):
        """Test readiness check endpoint."""
        response = client.get("/readiness")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
