"""Quiz generation service with question type mixing and distractor generation."""
import random
from enum import Enum
from typing import List, Dict, Tuple
from sqlalchemy.orm import Session
from app.db.models import Letter, QuizAttempt, QuizQuestion
from app.services.adaptive import select_letters_for_quiz


class QuestionType(str, Enum):
    """Types of questions in the quiz."""
    LETTER_TO_NAME = "LETTER_TO_NAME"  # Show letter, ask for name
    NAME_TO_UPPER = "NAME_TO_UPPER"     # Show name, ask for uppercase
    NAME_TO_LOWER = "NAME_TO_LOWER"     # Show name, ask for lowercase
    AUDIO_TO_UPPER = "AUDIO_TO_UPPER"   # Play audio, ask for uppercase
    AUDIO_TO_LOWER = "AUDIO_TO_LOWER"   # Play audio, ask for lowercase


def generate_question_types(count: int = 14, include_audio: bool = True) -> List[QuestionType]:
    """
    Generate a mixed list of question types.

    Strategy: Aim for roughly even distribution among all types.

    Args:
        count: Number of questions (default 14)
        include_audio: Whether to include audio question types (default True)

    Returns:
        List of QuestionType values, shuffled
    """
    types = [
        QuestionType.LETTER_TO_NAME,
        QuestionType.NAME_TO_UPPER,
        QuestionType.NAME_TO_LOWER
    ]

    if include_audio:
        types.extend([
            QuestionType.AUDIO_TO_UPPER,
            QuestionType.AUDIO_TO_LOWER
        ])

    # Create roughly equal distribution
    per_type = count // len(types)
    remainder = count % len(types)

    question_types = []
    for i, qtype in enumerate(types):
        # Add remainder to first few types
        type_count = per_type + (1 if i < remainder else 0)
        question_types.extend([qtype] * type_count)

    # Shuffle to avoid clustering
    random.shuffle(question_types)
    return question_types


def generate_distractors(
    db: Session,
    correct_letter: Letter,
    count: int = 3
) -> List[Letter]:
    """
    Generate distractor letters for multiple choice.

    Args:
        db: Database session
        correct_letter: The correct answer letter
        count: Number of distractors needed (default 3)

    Returns:
        List of Letter objects (distractors only, not including correct)
    """
    all_letters = db.query(Letter).filter(Letter.id != correct_letter.id).all()

    if len(all_letters) < count:
        raise ValueError(f"Not enough letters for {count} distractors")

    return random.sample(all_letters, count)


def format_question(
    letter: Letter,
    question_type: QuestionType,
    distractors: List[Letter]
) -> Dict:
    """
    Format a question with prompt, options, and correct answer.

    Args:
        letter: The target letter
        question_type: Type of question
        distractors: List of distractor letters

    Returns:
        Dictionary with question data for frontend
    """
    if question_type == QuestionType.LETTER_TO_NAME:
        # Show letter, ask for name
        prompt_text = f"Which letter is this?"
        display_letter = random.choice([letter.uppercase, letter.lowercase])
        correct_answer = letter.name
        options = [letter.name] + [d.name for d in distractors]
        audio_file = None
        is_audio_question = False

    elif question_type == QuestionType.NAME_TO_UPPER:
        # Show name, ask for uppercase
        prompt_text = f"Select the uppercase form of {letter.name}"
        display_letter = None
        correct_answer = letter.uppercase
        options = [letter.uppercase] + [d.uppercase for d in distractors]
        audio_file = None
        is_audio_question = False

    elif question_type == QuestionType.NAME_TO_LOWER:
        # Show name, ask for lowercase
        prompt_text = f"Select the lowercase form of {letter.name}"
        display_letter = None
        correct_answer = letter.lowercase
        options = [letter.lowercase] + [d.lowercase for d in distractors]
        audio_file = None
        is_audio_question = False

    elif question_type == QuestionType.AUDIO_TO_UPPER:
        # Play audio, ask for uppercase
        prompt_text = "Listen and select the uppercase form of this letter"
        display_letter = None
        correct_answer = letter.uppercase
        options = [letter.uppercase] + [d.uppercase for d in distractors]
        audio_file = f"/static/audio/{letter.name.lower()}.mp3"
        is_audio_question = True

    else:  # AUDIO_TO_LOWER
        # Play audio, ask for lowercase
        prompt_text = "Listen and select the lowercase form of this letter"
        display_letter = None
        correct_answer = letter.lowercase
        options = [letter.lowercase] + [d.lowercase for d in distractors]
        audio_file = f"/static/audio/{letter.name.lower()}.mp3"
        is_audio_question = True

    # Shuffle options
    random.shuffle(options)

    return {
        "prompt": prompt_text,
        "display_letter": display_letter,
        "options": options,
        "correct_answer": correct_answer,
        "letter_name": letter.name,
        "audio_file": audio_file,
        "is_audio_question": is_audio_question
    }


def create_quiz(
    db: Session,
    user_id: str,
    include_audio: bool = True
) -> Tuple[QuizAttempt, List[Dict]]:
    """
    Create a new quiz with 14 questions.

    Process:
    1. Select 14 letters using adaptive algorithm
    2. Generate question types (mixed)
    3. Create QuizAttempt and QuizQuestion records
    4. Format questions for frontend

    Args:
        db: Database session
        user_id: User UUID
        include_audio: Whether to include audio question types (default True)

    Returns:
        Tuple of (QuizAttempt object, list of formatted question dicts)
    """
    # Create quiz attempt
    quiz = QuizAttempt(
        user_id=user_id,
        question_count=14,
        correct_count=0
    )
    db.add(quiz)
    db.flush()  # Get quiz.id without committing

    # Select letters and question types
    selected_letters = select_letters_for_quiz(db, user_id, count=14)
    question_types = generate_question_types(count=14, include_audio=include_audio)

    # Shuffle selected_letters to ensure random pairing with question types
    # (both lists are independently randomized, but zip creates deterministic pairing)
    random.shuffle(selected_letters)

    formatted_questions = []

    for i, (letter, qtype) in enumerate(zip(selected_letters, question_types)):
        # Generate distractors
        distractors = generate_distractors(db, letter, count=3)

        # Format question for frontend
        formatted = format_question(letter, qtype, distractors)

        # Create database record
        question = QuizQuestion(
            quiz_id=quiz.id,
            letter_id=letter.id,
            question_type=qtype.value,
            correct_option=formatted["correct_answer"]
        )
        db.add(question)
        db.flush()

        # Add question ID and number to formatted output
        formatted_questions.append({
            "question_id": question.id,
            "question_number": i + 1,
            **formatted
        })

    db.commit()

    return quiz, formatted_questions


def evaluate_answer(
    db: Session,
    question_id: int,
    selected_option: str
) -> Dict:
    """
    Evaluate an answer and return result.

    Args:
        db: Database session
        question_id: QuizQuestion ID
        selected_option: User's selected answer

    Returns:
        Dictionary with evaluation result
    """
    question = db.query(QuizQuestion).filter(QuizQuestion.id == question_id).first()

    if not question:
        raise ValueError(f"Question {question_id} not found")

    is_correct = selected_option == question.correct_option

    # Update question record
    question.is_correct = 1 if is_correct else 0
    question.chosen_option = selected_option

    return {
        "question_id": question_id,
        "is_correct": is_correct,
        "correct_answer": question.correct_option,
        "selected_answer": selected_option,
        "letter_id": question.letter_id
    }
