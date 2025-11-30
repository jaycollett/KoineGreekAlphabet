"""Unit tests for quiz generation service."""
import pytest
from app.db.models import Letter
from app.services.quiz_generator import (
    generate_question_types,
    generate_distractors,
    format_question,
    QuestionType,
    create_quiz
)


class TestQuestionTypeGeneration:
    """Tests for question type generation."""

    def test_generates_correct_count(self):
        """Should generate exactly the requested number of types."""
        types = generate_question_types(count=14)
        assert len(types) == 14

    def test_mixes_all_types_without_audio(self):
        """Should include all three non-audio question types."""
        types = generate_question_types(count=14, include_audio=False)
        unique_types = set(types)

        assert QuestionType.LETTER_TO_NAME in unique_types
        assert QuestionType.NAME_TO_UPPER in unique_types
        assert QuestionType.NAME_TO_LOWER in unique_types
        assert QuestionType.AUDIO_TO_UPPER not in unique_types
        assert QuestionType.AUDIO_TO_LOWER not in unique_types

    def test_includes_audio_types_when_enabled(self):
        """Should include audio question types when include_audio=True."""
        types = generate_question_types(count=14, include_audio=True)
        unique_types = set(types)

        # Should include at least some audio types
        assert QuestionType.AUDIO_TO_UPPER in unique_types or QuestionType.AUDIO_TO_LOWER in unique_types

    def test_roughly_even_distribution(self):
        """Question types should be roughly evenly distributed."""
        types = generate_question_types(count=15)

        letter_to_name = types.count(QuestionType.LETTER_TO_NAME)
        name_to_upper = types.count(QuestionType.NAME_TO_UPPER)
        name_to_lower = types.count(QuestionType.NAME_TO_LOWER)

        # Each should appear 4-6 times (5 ± 1) for 15 questions
        assert 4 <= letter_to_name <= 6
        assert 4 <= name_to_upper <= 6
        assert 4 <= name_to_lower <= 6


class TestDistractorGeneration:
    """Tests for distractor generation."""

    def test_generates_correct_count(self, test_db):
        """Should generate exactly the requested number of distractors."""
        correct_letter = test_db.query(Letter).first()
        distractors = generate_distractors(test_db, correct_letter, count=3)

        assert len(distractors) == 3

    def test_distractors_are_different_letters(self, test_db):
        """Distractors should not include the correct letter."""
        correct_letter = test_db.query(Letter).first()
        distractors = generate_distractors(test_db, correct_letter, count=3)

        distractor_ids = [d.id for d in distractors]
        assert correct_letter.id not in distractor_ids

    def test_distractors_are_unique(self, test_db):
        """All distractors should be unique."""
        correct_letter = test_db.query(Letter).first()
        distractors = generate_distractors(test_db, correct_letter, count=3)

        distractor_ids = [d.id for d in distractors]
        assert len(distractor_ids) == len(set(distractor_ids))

    def test_raises_error_if_not_enough_letters(self, test_db):
        """Should raise error if not enough letters available."""
        # Create a new DB with only 2 letters
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from app.db.database import Base

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        SessionLocal = sessionmaker(bind=engine)
        db = SessionLocal()

        letter1 = Letter(id=1, name="Alpha", uppercase="Α", lowercase="α", position=1)
        letter2 = Letter(id=2, name="Beta", uppercase="Β", lowercase="β", position=2)
        db.add(letter1)
        db.add(letter2)
        db.commit()

        with pytest.raises(ValueError):
            generate_distractors(db, letter1, count=3)

        db.close()


class TestQuestionFormatting:
    """Tests for question formatting."""

    def test_letter_to_name_format(self, test_db):
        """LETTER_TO_NAME question should show letter and ask for name."""
        letter = test_db.query(Letter).first()
        distractors = generate_distractors(test_db, letter, count=3)

        question = format_question(letter, QuestionType.LETTER_TO_NAME, distractors)

        assert "Which letter is this?" in question["prompt"]
        assert question["display_letter"] is not None
        assert question["correct_answer"] == letter.name
        assert len(question["options"]) == 4
        assert letter.name in question["options"]

    def test_name_to_upper_format(self, test_db):
        """NAME_TO_UPPER question should show name and ask for uppercase."""
        letter = test_db.query(Letter).first()
        distractors = generate_distractors(test_db, letter, count=3)

        question = format_question(letter, QuestionType.NAME_TO_UPPER, distractors)

        assert letter.name in question["prompt"]
        assert "uppercase" in question["prompt"]
        assert question["display_letter"] is None
        assert question["correct_answer"] == letter.uppercase
        assert len(question["options"]) == 4

    def test_name_to_lower_format(self, test_db):
        """NAME_TO_LOWER question should show name and ask for lowercase."""
        letter = test_db.query(Letter).first()
        distractors = generate_distractors(test_db, letter, count=3)

        question = format_question(letter, QuestionType.NAME_TO_LOWER, distractors)

        assert letter.name in question["prompt"]
        assert "lowercase" in question["prompt"]
        assert question["correct_answer"] == letter.lowercase

    def test_options_are_shuffled(self, test_db):
        """Options should be in random order (not always correct first)."""
        letter = test_db.query(Letter).first()
        distractors = generate_distractors(test_db, letter, count=3)

        # Generate multiple questions and check if correct answer position varies
        positions = []
        for _ in range(10):
            question = format_question(letter, QuestionType.LETTER_TO_NAME, distractors)
            correct_position = question["options"].index(question["correct_answer"])
            positions.append(correct_position)

        # Should have some variation in position
        assert len(set(positions)) > 1


class TestQuizCreation:
    """Tests for complete quiz creation."""

    def test_creates_quiz_with_14_questions(self, test_db, test_user):
        """Should create a quiz with exactly 14 questions."""
        # Initialize user stats
        all_letters = test_db.query(Letter).all()
        from app.db.models import UserLetterStat
        for letter in all_letters:
            stat = UserLetterStat(user_id=test_user.id, letter_id=letter.id)
            test_db.add(stat)
        test_db.commit()

        quiz, questions = create_quiz(test_db, test_user.id)

        assert quiz.question_count == 14
        assert len(questions) == 14
        assert quiz.correct_count == 0

    def test_quiz_questions_have_all_fields(self, test_db, test_user):
        """Quiz questions should have all required fields."""
        all_letters = test_db.query(Letter).all()
        from app.db.models import UserLetterStat
        for letter in all_letters:
            stat = UserLetterStat(user_id=test_user.id, letter_id=letter.id)
            test_db.add(stat)
        test_db.commit()

        quiz, questions = create_quiz(test_db, test_user.id)

        for question in questions:
            assert "question_id" in question
            assert "question_number" in question
            assert "prompt" in question
            assert "options" in question
            assert "correct_answer" in question
            assert len(question["options"]) == 4


class TestAudioQuestions:
    """Tests for audio question generation and formatting."""

    def test_audio_to_upper_format(self, test_db):
        """AUDIO_TO_UPPER question should have correct format and audio file path."""
        letter = test_db.query(Letter).first()
        distractors = generate_distractors(test_db, letter, count=3)

        question = format_question(letter, QuestionType.AUDIO_TO_UPPER, distractors)

        assert "Listen" in question["prompt"]
        assert "uppercase" in question["prompt"]
        assert question["display_letter"] is None
        assert question["correct_answer"] == letter.uppercase
        assert question["audio_file"] is not None
        assert question["is_audio_question"] is True
        assert letter.name.lower() in question["audio_file"]
        assert ".mp3" in question["audio_file"]

    def test_audio_to_lower_format(self, test_db):
        """AUDIO_TO_LOWER question should have correct format and audio file path."""
        letter = test_db.query(Letter).first()
        distractors = generate_distractors(test_db, letter, count=3)

        question = format_question(letter, QuestionType.AUDIO_TO_LOWER, distractors)

        assert "Listen" in question["prompt"]
        assert "lowercase" in question["prompt"]
        assert question["display_letter"] is None
        assert question["correct_answer"] == letter.lowercase
        assert question["audio_file"] is not None
        assert question["is_audio_question"] is True
        assert letter.name.lower() in question["audio_file"]

    def test_audio_file_path_generation(self, test_db):
        """Audio file paths should follow correct naming convention."""
        from app.constants import AUDIO_PATH_TEMPLATE

        # Test with different letters
        letters = test_db.query(Letter).limit(3).all()

        for letter in letters:
            distractors = generate_distractors(test_db, letter, count=3)
            question = format_question(letter, QuestionType.AUDIO_TO_UPPER, distractors)

            expected_path = AUDIO_PATH_TEMPLATE.format(letter_name=letter.name.lower())
            assert question["audio_file"] == expected_path

    def test_is_audio_question_flag_correctness(self, test_db):
        """is_audio_question flag should be True only for audio types."""
        letter = test_db.query(Letter).first()
        distractors = generate_distractors(test_db, letter, count=3)

        # Non-audio questions
        for qtype in [QuestionType.LETTER_TO_NAME, QuestionType.NAME_TO_UPPER, QuestionType.NAME_TO_LOWER]:
            question = format_question(letter, qtype, distractors)
            assert question["is_audio_question"] is False
            assert question["audio_file"] is None

        # Audio questions
        for qtype in [QuestionType.AUDIO_TO_UPPER, QuestionType.AUDIO_TO_LOWER]:
            question = format_question(letter, qtype, distractors)
            assert question["is_audio_question"] is True
            assert question["audio_file"] is not None

    def test_quiz_with_audio_questions(self, test_db, test_user):
        """Quiz created with include_audio=True should contain audio questions."""
        all_letters = test_db.query(Letter).all()
        from app.db.models import UserLetterStat
        for letter in all_letters:
            stat = UserLetterStat(user_id=test_user.id, letter_id=letter.id)
            test_db.add(stat)
        test_db.commit()

        quiz, questions = create_quiz(test_db, test_user.id, include_audio=True)

        # Should have at least some audio questions
        audio_questions = [q for q in questions if q.get("is_audio_question")]
        assert len(audio_questions) > 0

        # All audio questions should have audio_file
        for q in audio_questions:
            assert q["audio_file"] is not None
            assert ".mp3" in q["audio_file"]

    def test_quiz_without_audio_questions(self, test_db, test_user):
        """Quiz created with include_audio=False should not contain audio questions."""
        all_letters = test_db.query(Letter).all()
        from app.db.models import UserLetterStat
        for letter in all_letters:
            stat = UserLetterStat(user_id=test_user.id, letter_id=letter.id)
            test_db.add(stat)
        test_db.commit()

        quiz, questions = create_quiz(test_db, test_user.id, include_audio=False)

        # Should have no audio questions
        audio_questions = [q for q in questions if q.get("is_audio_question")]
        assert len(audio_questions) == 0

    def test_audio_question_options_are_symbols(self, test_db):
        """Audio questions should show letter symbols (uppercase/lowercase) as options."""
        letter = test_db.query(Letter).first()
        distractors = generate_distractors(test_db, letter, count=3)

        # AUDIO_TO_UPPER
        question_upper = format_question(letter, QuestionType.AUDIO_TO_UPPER, distractors)
        assert all(len(opt) <= 2 for opt in question_upper["options"])  # Greek symbols are 1-2 chars
        assert letter.uppercase in question_upper["options"]

        # AUDIO_TO_LOWER
        question_lower = format_question(letter, QuestionType.AUDIO_TO_LOWER, distractors)
        assert all(len(opt) <= 2 for opt in question_lower["options"])
        assert letter.lowercase in question_lower["options"]
