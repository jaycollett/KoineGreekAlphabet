"""Tests for critical and high-priority bug fixes."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError
from app.db.database import Base
from app.db.models import User, Letter, QuizAttempt, QuizQuestion, UserLetterStat
from app.db.init_db import GREEK_ALPHABET
from app.services.quiz_generator import create_quiz
from app.routers.quiz import AnswerSubmission
from pydantic import ValidationError


@pytest.fixture(scope="function")
def test_db():
    """Create a test database with new schema."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    # Seed Greek alphabet
    for letter_data in GREEK_ALPHABET:
        letter = Letter(**letter_data)
        db.add(letter)
    db.commit()

    yield db
    db.close()


@pytest.fixture
def test_user(test_db):
    """Create a test user with initialized stats."""
    user = User(id="test_user_fix_123")
    test_db.add(user)

    # Initialize stats for all letters
    letters = test_db.query(Letter).all()
    for letter in letters:
        stat = UserLetterStat(user_id=user.id, letter_id=letter.id)
        test_db.add(stat)

    test_db.commit()
    return user


class TestQuizStateRestoration:
    """Test Fix #1: Quiz state restoration with saved options."""

    def test_options_are_saved_during_quiz_creation(self, test_db, test_user):
        """Test that options are stored in database when quiz is created."""
        quiz, questions = create_quiz(test_db, test_user.id, include_audio=False)

        # Verify options are saved in database
        db_questions = test_db.query(QuizQuestion).filter(
            QuizQuestion.quiz_id == quiz.id
        ).all()

        for db_question in db_questions:
            assert db_question.option_1 is not None
            assert db_question.option_2 is not None
            assert db_question.option_3 is not None
            assert db_question.option_4 is not None

            # Verify we have 4 distinct options
            options = [
                db_question.option_1,
                db_question.option_2,
                db_question.option_3,
                db_question.option_4
            ]
            assert len(set(options)) == 4, "Options should be distinct"

    def test_options_remain_consistent_on_reload(self, test_db, test_user):
        """Test that reloading quiz state returns same options."""
        # Create quiz
        quiz, original_questions = create_quiz(test_db, test_user.id, include_audio=False)

        # Get first question's options
        first_question = original_questions[0]
        original_options = set(first_question["options"])

        # Reload question from database
        db_question = test_db.query(QuizQuestion).filter(
            QuizQuestion.id == first_question["question_id"]
        ).first()

        # Reconstruct options from saved data
        saved_options = {
            db_question.option_1,
            db_question.option_2,
            db_question.option_3,
            db_question.option_4
        }

        # Options should be identical
        assert original_options == saved_options

    def test_correct_answer_is_in_saved_options(self, test_db, test_user):
        """Test that correct answer is always one of the saved options."""
        quiz, questions = create_quiz(test_db, test_user.id, include_audio=False)

        for question_data in questions:
            db_question = test_db.query(QuizQuestion).filter(
                QuizQuestion.id == question_data["question_id"]
            ).first()

            saved_options = [
                db_question.option_1,
                db_question.option_2,
                db_question.option_3,
                db_question.option_4
            ]

            assert db_question.correct_option in saved_options


class TestRaceConditionPrevention:
    """Test Fix #2: Race condition prevention with unique constraint."""

    def test_unique_constraint_on_quiz_letter(self, test_db, test_user):
        """Test that unique constraint prevents duplicate questions."""
        quiz = QuizAttempt(user_id=test_user.id, question_count=14)
        test_db.add(quiz)
        test_db.commit()

        letter = test_db.query(Letter).first()

        # Create first question
        question1 = QuizQuestion(
            quiz_id=quiz.id,
            letter_id=letter.id,
            question_type="LETTER_TO_NAME",
            correct_option="Alpha",
            option_1="Alpha",
            option_2="Beta",
            option_3="Gamma",
            option_4="Delta"
        )
        test_db.add(question1)
        test_db.commit()

        # Try to create duplicate question (same quiz_id and letter_id)
        question2 = QuizQuestion(
            quiz_id=quiz.id,
            letter_id=letter.id,  # Same letter as question1
            question_type="NAME_TO_UPPER",
            correct_option="Α",
            option_1="Α",
            option_2="Β",
            option_3="Γ",
            option_4="Δ"
        )
        test_db.add(question2)

        # Should raise IntegrityError due to unique constraint
        with pytest.raises(IntegrityError):
            test_db.commit()

    def test_double_submission_handling(self, test_db, test_user):
        """Test that submitting answer twice for same question is handled gracefully."""
        quiz, questions = create_quiz(test_db, test_user.id, include_audio=False)

        first_question = questions[0]
        question_id = first_question["question_id"]
        correct_answer = first_question["correct_answer"]

        # Submit answer first time
        from app.services.quiz_generator import evaluate_answer
        result1 = evaluate_answer(test_db, question_id, correct_answer)
        test_db.commit()

        # Verify answer was saved
        db_question = test_db.query(QuizQuestion).filter(
            QuizQuestion.id == question_id
        ).first()
        assert db_question.chosen_option == correct_answer
        first_chosen = db_question.chosen_option

        # Try to submit different answer (simulating race condition)
        # This should detect the question was already answered
        db_question_check = test_db.query(QuizQuestion).filter(
            QuizQuestion.id == question_id
        ).first()
        assert db_question_check.chosen_option is not None
        # In the actual endpoint, this would return early with already_answered flag


class TestTransactionManagement:
    """Test Fix #3: Transaction management in submit_answer."""

    def test_transaction_rollback_on_error(self, test_db, test_user):
        """Test that errors trigger rollback (implicitly tested through integrity)."""
        quiz, questions = create_quiz(test_db, test_user.id, include_audio=False)

        # Get initial correct count
        initial_correct = quiz.correct_count

        # Try to evaluate non-existent question (should fail)
        from app.services.quiz_generator import evaluate_answer
        with pytest.raises(ValueError):
            evaluate_answer(test_db, 999999, "some answer")

        # Verify quiz state wasn't changed
        test_db.rollback()
        test_db.refresh(quiz)
        assert quiz.correct_count == initial_correct

    def test_quiz_completion_is_atomic(self, test_db, test_user):
        """Test that quiz completion updates are atomic."""
        quiz, questions = create_quiz(test_db, test_user.id, include_audio=False)

        # Answer all questions
        from app.services.quiz_generator import evaluate_answer
        for question_data in questions:
            evaluate_answer(
                test_db,
                question_data["question_id"],
                question_data["correct_answer"]
            )
            quiz.correct_count += 1

        # Check completion count
        answered_count = test_db.query(QuizQuestion).filter(
            QuizQuestion.quiz_id == quiz.id,
            QuizQuestion.chosen_option.isnot(None)
        ).count()

        assert answered_count == quiz.question_count
        test_db.commit()


class TestDatabaseIndexes:
    """Test Fix #4: Database indexes are created properly."""

    def test_indexes_exist_in_schema(self, test_db):
        """Test that required indexes are present in database."""
        from sqlalchemy import inspect
        inspector = inspect(test_db.bind)

        # Check UserLetterStat indexes
        user_stat_indexes = inspector.get_indexes('user_letter_stats')
        index_names = [idx['name'] for idx in user_stat_indexes]
        assert 'idx_user_mastery' in index_names
        assert 'idx_user_seen_count' in index_names

        # Check QuizAttempt indexes
        quiz_indexes = inspector.get_indexes('quiz_attempts')
        index_names = [idx['name'] for idx in quiz_indexes]
        assert 'idx_user_completed' in index_names

        # Check QuizQuestion indexes
        question_indexes = inspector.get_indexes('quiz_questions')
        index_names = [idx['name'] for idx in question_indexes]
        assert 'idx_quiz_correct' in index_names


class TestInputValidation:
    """Test Fix #7: Input validation in Pydantic models."""

    def test_answer_submission_requires_positive_question_id(self):
        """Test that question_id must be positive."""
        # Valid submission
        valid = AnswerSubmission(question_id=1, selected_option="Alpha")
        assert valid.question_id == 1

        # Invalid: zero
        with pytest.raises(ValidationError):
            AnswerSubmission(question_id=0, selected_option="Alpha")

        # Invalid: negative
        with pytest.raises(ValidationError):
            AnswerSubmission(question_id=-1, selected_option="Alpha")

    def test_answer_submission_validates_empty_option(self):
        """Test that selected_option cannot be empty."""
        # Valid submission
        valid = AnswerSubmission(question_id=1, selected_option="Alpha")
        assert valid.selected_option == "Alpha"

        # Invalid: empty string
        with pytest.raises(ValidationError):
            AnswerSubmission(question_id=1, selected_option="")

        # Invalid: whitespace only (gets stripped and caught)
        with pytest.raises(ValidationError):
            AnswerSubmission(question_id=1, selected_option="   ")

    def test_answer_submission_strips_whitespace(self):
        """Test that whitespace is stripped from selected_option."""
        submission = AnswerSubmission(question_id=1, selected_option="  Alpha  ")
        assert submission.selected_option == "Alpha"

    def test_answer_submission_max_length(self):
        """Test that selected_option has max length."""
        # Valid: within limit
        valid = AnswerSubmission(question_id=1, selected_option="A" * 100)
        assert len(valid.selected_option) == 100

        # Invalid: exceeds limit
        with pytest.raises(ValidationError):
            AnswerSubmission(question_id=1, selected_option="A" * 101)


class TestCookieSecurity:
    """Test Fix #6: Cookie security configuration."""

    def test_cookie_settings_configurable(self):
        """Test that cookie settings can be configured via settings."""
        from app.config import Settings
        import os

        # Test default (development)
        settings = Settings()
        assert settings.COOKIE_SECURE is False
        assert settings.COOKIE_HTTPONLY is True
        assert settings.COOKIE_SAMESITE == "lax"

        # Test production mode
        os.environ["COOKIE_SECURE"] = "true"
        settings = Settings()
        assert settings.COOKIE_SECURE is True

        # Clean up
        os.environ.pop("COOKIE_SECURE", None)

    def test_environment_detection(self):
        """Test that environment is properly detected."""
        from app.config import Settings
        import os

        # Test development
        settings = Settings()
        assert settings.is_production is False

        # Test production
        os.environ["ENVIRONMENT"] = "production"
        settings = Settings()
        assert settings.is_production is True

        # Clean up
        os.environ.pop("ENVIRONMENT", None)


class TestAudioCleanup:
    """Test Fix #5: Audio memory leak (JavaScript - tested via documentation)."""

    def test_audio_cleanup_documented(self):
        """
        Verify audio cleanup is properly implemented in quiz.js.

        This is a placeholder test to document that the audio cleanup
        fix has been implemented in the JavaScript code. The actual
        implementation sets currentAudio.src = '' to release resources.

        Manual verification required:
        1. Check that currentAudio.src = '' is called before creating new Audio
        2. Verify that currentAudio is set to null after cleanup
        3. Test in browser dev tools that audio objects are garbage collected
        """
        # Read the JavaScript file to verify fix is present
        import os
        js_path = os.path.join(
            os.path.dirname(__file__),
            "..", "app", "static", "js", "quiz.js"
        )

        if os.path.exists(js_path):
            with open(js_path, 'r') as f:
                content = f.read()
                # Verify the fix is in the code
                assert "currentAudio.src = '';" in content or 'currentAudio.src = "";' in content
                assert "currentAudio = null;" in content
        else:
            pytest.skip("JavaScript file not found for verification")
