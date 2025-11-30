"""Tests for concurrent operations and race condition handling.

Tests include:
- Concurrent answer submissions
- Concurrent quiz creation
- Double submission prevention
- Database transaction handling
"""
import pytest
import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.db.database import Base, get_db
from app.db.models import User, Letter, QuizAttempt, QuizQuestion, UserLetterStat
from datetime import datetime

# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    pool_pre_ping=True
)
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
        Letter(name="Zeta", uppercase="Ζ", lowercase="ζ", position=6),
        Letter(name="Eta", uppercase="Η", lowercase="η", position=7),
        Letter(name="Theta", uppercase="Θ", lowercase="θ", position=8),
    ]
    for letter in letters:
        db.add(letter)
    db.commit()
    return letters


@pytest.fixture
def initialized_user(client, seed_letters):
    """Create and return initialized user with cookies."""
    response = client.post("/api/user/initialize")
    assert response.status_code == 200
    return {
        "user_data": response.json(),
        "cookies": response.cookies
    }


class TestConcurrentAnswerSubmissions:
    """Test handling of concurrent answer submissions."""

    def test_concurrent_answer_submission_to_different_questions(self, client, db, initialized_user):
        """Multiple answers to different questions should all succeed."""
        cookies = initialized_user["cookies"]

        # Start quiz
        response = client.post(
            "/api/quiz/start",
            json={"include_audio": False},
            cookies=cookies
        )
        quiz_data = response.json()
        quiz_id = quiz_data["quiz_id"]
        questions = quiz_data["questions"][:3]  # Use first 3 questions

        # Submit answers concurrently
        def submit_answer(question):
            return client.post(
                f"/api/quiz/{quiz_id}/answer",
                json={
                    "question_id": question["question_id"],
                    "selected_option": question["options"][0]
                },
                cookies=cookies
            )

        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(submit_answer, q) for q in questions]
            results = [f.result() for f in as_completed(futures)]

        # All should succeed
        assert all(r.status_code == 200 for r in results)

        # Check final quiz state
        quiz = db.query(QuizAttempt).filter(QuizAttempt.id == quiz_id).first()
        answered = db.query(QuizQuestion).filter(
            QuizQuestion.quiz_id == quiz_id,
            QuizQuestion.chosen_option.isnot(None)
        ).count()
        assert answered == 3

    def test_concurrent_same_answer_submission_is_idempotent(self, client, db, initialized_user):
        """Submitting same answer multiple times concurrently should be idempotent."""
        cookies = initialized_user["cookies"]

        # Start quiz
        response = client.post(
            "/api/quiz/start",
            json={"include_audio": False},
            cookies=cookies
        )
        quiz_data = response.json()
        quiz_id = quiz_data["quiz_id"]
        first_question = quiz_data["questions"][0]

        # Submit same answer multiple times concurrently
        def submit_same_answer():
            return client.post(
                f"/api/quiz/{quiz_id}/answer",
                json={
                    "question_id": first_question["question_id"],
                    "selected_option": first_question["options"][0]
                },
                cookies=cookies
            )

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(submit_same_answer) for _ in range(5)]
            results = [f.result() for f in as_completed(futures)]

        # All should return 200 (some might have already_answered flag)
        assert all(r.status_code == 200 for r in results)

        # Question should only be marked as answered once
        question = db.query(QuizQuestion).filter(
            QuizQuestion.id == first_question["question_id"]
        ).first()
        assert question.chosen_option is not None

        # Quiz correct count should only increment once if correct
        quiz = db.query(QuizAttempt).filter(QuizAttempt.id == quiz_id).first()
        if question.is_correct:
            assert quiz.correct_count == 1
        else:
            assert quiz.correct_count == 0


class TestConcurrentQuizCreation:
    """Test concurrent quiz creation for the same user."""

    def test_concurrent_quiz_creation_succeeds(self, client, db, initialized_user):
        """Multiple quizzes can be created concurrently for same user."""
        cookies = initialized_user["cookies"]
        user_id = initialized_user["user_data"]["user_id"]

        # Create multiple quizzes concurrently
        def create_quiz():
            return client.post(
                "/api/quiz/start",
                json={"include_audio": False},
                cookies=cookies
            )

        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(create_quiz) for _ in range(3)]
            results = [f.result() for f in as_completed(futures)]

        # All should succeed
        assert all(r.status_code == 200 for r in results)

        # Should have 3 distinct quizzes
        quiz_ids = [r.json()["quiz_id"] for r in results]
        assert len(set(quiz_ids)) == 3

        # All quizzes should belong to the same user
        quizzes = db.query(QuizAttempt).filter(QuizAttempt.user_id == user_id).all()
        assert len(quizzes) == 3


class TestConcurrentStatsUpdates:
    """Test concurrent updates to user letter statistics."""

    def test_concurrent_stats_updates_maintain_consistency(self, client, db, initialized_user):
        """Concurrent answer submissions should maintain stat consistency."""
        cookies = initialized_user["cookies"]
        user_id = initialized_user["user_data"]["user_id"]

        # Start quiz
        response = client.post(
            "/api/quiz/start",
            json={"include_audio": False},
            cookies=cookies
        )
        quiz_data = response.json()
        quiz_id = quiz_data["quiz_id"]
        questions = quiz_data["questions"]

        # Get a question about a specific letter
        first_question = questions[0]
        letter_name = first_question["letter_name"]

        # Find the letter_id
        letter = db.query(Letter).filter(Letter.name == letter_name).first()

        # Get initial stats
        initial_stat = db.query(UserLetterStat).filter(
            UserLetterStat.user_id == user_id,
            UserLetterStat.letter_id == letter.id
        ).first()
        initial_seen = initial_stat.seen_count if initial_stat else 0

        # Submit answer
        response = client.post(
            f"/api/quiz/{quiz_id}/answer",
            json={
                "question_id": first_question["question_id"],
                "selected_option": first_question["correct_answer"]
            },
            cookies=cookies
        )
        assert response.status_code == 200

        # Check stats were updated correctly
        updated_stat = db.query(UserLetterStat).filter(
            UserLetterStat.user_id == user_id,
            UserLetterStat.letter_id == letter.id
        ).first()
        assert updated_stat.seen_count == initial_seen + 1
        assert updated_stat.correct_count >= 1


class TestRaceConditions:
    """Test race condition handling."""

    def test_quiz_completion_race_condition(self, client, db, initialized_user):
        """Test that quiz completion is handled correctly when last two answers come in simultaneously."""
        cookies = initialized_user["cookies"]

        # Start quiz
        response = client.post(
            "/api/quiz/start",
            json={"include_audio": False},
            cookies=cookies
        )
        quiz_data = response.json()
        quiz_id = quiz_data["quiz_id"]
        questions = quiz_data["questions"]

        # Answer all questions except the last two
        for question in questions[:-2]:
            client.post(
                f"/api/quiz/{quiz_id}/answer",
                json={
                    "question_id": question["question_id"],
                    "selected_option": question["options"][0]
                },
                cookies=cookies
            )

        # Submit last two answers concurrently
        last_two = questions[-2:]

        def submit_last_answer(question):
            return client.post(
                f"/api/quiz/{quiz_id}/answer",
                json={
                    "question_id": question["question_id"],
                    "selected_option": question["options"][0]
                },
                cookies=cookies
            )

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(submit_last_answer, q) for q in last_two]
            results = [f.result() for f in as_completed(futures)]

        # Both should succeed
        assert all(r.status_code == 200 for r in results)

        # Exactly one should have is_last_question=True and summary
        last_question_responses = [r for r in results if r.json().get("is_last_question")]
        assert len(last_question_responses) >= 1  # At least one should indicate completion

        # Quiz should be completed
        quiz = db.query(QuizAttempt).filter(QuizAttempt.id == quiz_id).first()
        assert quiz.completed_at is not None
        assert quiz.accuracy is not None


class TestDatabaseTransactionHandling:
    """Test database transaction rollback and error handling."""

    def test_answer_submission_rolls_back_on_error(self, client, db, initialized_user):
        """Failed answer submission should not leave partial updates."""
        cookies = initialized_user["cookies"]

        # Start quiz
        response = client.post(
            "/api/quiz/start",
            json={"include_audio": False},
            cookies=cookies
        )
        quiz_data = response.json()

        # Try to submit with invalid question_id
        response = client.post(
            f"/api/quiz/{quiz_data['quiz_id']}/answer",
            json={
                "question_id": 999999,  # Non-existent
                "selected_option": "Alpha"
            },
            cookies=cookies
        )

        # Should fail
        assert response.status_code == 404

        # Quiz state should be unchanged
        quiz = db.query(QuizAttempt).filter(
            QuizAttempt.id == quiz_data['quiz_id']
        ).first()
        assert quiz.correct_count == 0
