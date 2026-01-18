"""Quiz generation service with question type mixing and distractor generation."""
import random
from enum import Enum
from typing import List, Dict, Tuple
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.db.models import Letter, QuizAttempt, QuizQuestion, User
from app.services.adaptive import select_letters_for_quiz
from app.services.similar_letters import get_similar_letters
from app.constants import (
    QUESTIONS_PER_QUIZ,
    DISTRACTOR_COUNT,
    AUDIO_PATH_TEMPLATE,
    LEVEL_1_AUDIO_RATIO,
    LEVEL_2_AUDIO_RATIO,
    LEVEL_3_AUDIO_RATIO,
    LEVEL_3_DISTRACTOR_COUNT
)


class QuestionType(str, Enum):
    """Types of questions in the quiz."""
    LETTER_TO_NAME = "LETTER_TO_NAME"  # Show letter, ask for name
    NAME_TO_UPPER = "NAME_TO_UPPER"     # Show name, ask for uppercase
    NAME_TO_LOWER = "NAME_TO_LOWER"     # Show name, ask for lowercase
    AUDIO_TO_UPPER = "AUDIO_TO_UPPER"   # Play audio, ask for uppercase
    AUDIO_TO_LOWER = "AUDIO_TO_LOWER"   # Play audio, ask for lowercase


def generate_question_types(
    count: int = 14,
    include_audio: bool = True,
    audio_ratio: float = 0.4
) -> List[QuestionType]:
    """
    Generate a mixed list of question types based on difficulty level.

    Strategy: Control audio ratio based on difficulty level.
    - Level 1: 40% audio
    - Level 2: 65% audio
    - Level 3: 80% audio

    Args:
        count: Number of questions (default 14)
        include_audio: Whether to include audio question types (default True)
        audio_ratio: Proportion of audio questions (0.0-1.0)

    Returns:
        List of QuestionType values, shuffled
    """
    if not include_audio or audio_ratio == 0:
        # No audio - use only visual types
        visual_types = [
            QuestionType.LETTER_TO_NAME,
            QuestionType.NAME_TO_UPPER,
            QuestionType.NAME_TO_LOWER
        ]
        # Distribute evenly
        per_type = count // len(visual_types)
        remainder = count % len(visual_types)
        question_types = []
        for i, qtype in enumerate(visual_types):
            type_count = per_type + (1 if i < remainder else 0)
            question_types.extend([qtype] * type_count)
        random.shuffle(question_types)
        return question_types

    # Calculate audio vs visual question counts
    audio_count = int(count * audio_ratio)
    visual_count = count - audio_count

    question_types = []

    # Add visual questions
    visual_types = [
        QuestionType.LETTER_TO_NAME,
        QuestionType.NAME_TO_UPPER,
        QuestionType.NAME_TO_LOWER
    ]
    if visual_count > 0:
        per_visual = visual_count // len(visual_types)
        remainder_visual = visual_count % len(visual_types)
        for i, qtype in enumerate(visual_types):
            type_count = per_visual + (1 if i < remainder_visual else 0)
            question_types.extend([qtype] * type_count)

    # Add audio questions
    audio_types = [
        QuestionType.AUDIO_TO_UPPER,
        QuestionType.AUDIO_TO_LOWER
    ]
    if audio_count > 0:
        per_audio = audio_count // len(audio_types)
        remainder_audio = audio_count % len(audio_types)
        for i, qtype in enumerate(audio_types):
            type_count = per_audio + (1 if i < remainder_audio else 0)
            question_types.extend([qtype] * type_count)

    # Shuffle to avoid clustering
    random.shuffle(question_types)
    return question_types


def generate_distractors(
    db: Session,
    correct_letter: Letter,
    count: int = 3,
    use_similar: bool = False,
    strict_similar: bool = False
) -> List[Letter]:
    """
    Generate distractor letters for multiple choice.

    Args:
        db: Database session
        correct_letter: The correct answer letter
        count: Number of distractors needed (default 3)
        use_similar: If True, prefer visually/phonetically similar letters (Level 2/3)
        strict_similar: If True, ONLY use extremely similar letters (Level 3)

    Returns:
        List of Letter objects (distractors only, not including correct)
    """
    if use_similar:
        # Level 2/3: Use similar letter selection
        all_letters = db.query(Letter).all()
        distractors = get_similar_letters(correct_letter, all_letters, count, strict_mode=strict_similar)
    else:
        # Level 1: Random distractor selection
        distractors = db.query(Letter).filter(
            Letter.id != correct_letter.id
        ).order_by(func.random()).limit(count).all()

    if len(distractors) < count:
        raise ValueError(f"Not enough letters for {count} distractors")

    return distractors


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
        audio_file = AUDIO_PATH_TEMPLATE.format(letter_name=letter.name.lower())
        is_audio_question = True

    else:  # AUDIO_TO_LOWER
        # Play audio, ask for lowercase
        prompt_text = "Listen and select the lowercase form of this letter"
        display_letter = None
        correct_answer = letter.lowercase
        options = [letter.lowercase] + [d.lowercase for d in distractors]
        audio_file = AUDIO_PATH_TEMPLATE.format(letter_name=letter.name.lower())
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
    Create a new quiz with QUESTIONS_PER_QUIZ questions.

    Process:
    1. Get user's difficulty level
    2. Select letters using adaptive algorithm
    3. Generate question types based on difficulty level
    4. Create QuizAttempt and QuizQuestion records
    5. Format questions for frontend

    Difficulty mechanics:
    - Level 1: 40% audio, 3 random distractors (4 total options)
    - Level 2: 65% audio, 3 similar distractors (4 total options)
    - Level 3: 90% audio, 3 EXTREMELY similar distractors (4 total options, all confusing)

    Args:
        db: Database session
        user_id: User UUID
        include_audio: Whether to include audio question types (default True)

    Returns:
        Tuple of (QuizAttempt object, list of formatted question dicts)
    """
    # Get user to determine difficulty level
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise ValueError(f"User {user_id} not found")

    # Determine difficulty parameters based on level
    if user.current_level == 1:
        audio_ratio = LEVEL_1_AUDIO_RATIO
        distractor_count = DISTRACTOR_COUNT
        use_similar_distractors = False
        strict_similar_distractors = False
    elif user.current_level == 2:
        audio_ratio = LEVEL_2_AUDIO_RATIO
        distractor_count = DISTRACTOR_COUNT
        use_similar_distractors = True
        strict_similar_distractors = False
    else:  # Level 3
        audio_ratio = LEVEL_3_AUDIO_RATIO
        distractor_count = LEVEL_3_DISTRACTOR_COUNT
        use_similar_distractors = True
        strict_similar_distractors = True

    # Create quiz attempt
    quiz = QuizAttempt(
        user_id=user_id,
        question_count=QUESTIONS_PER_QUIZ,
        correct_count=0
    )
    db.add(quiz)
    db.flush()  # Get quiz.id without committing

    # Select letters and question types
    selected_letters = select_letters_for_quiz(db, user_id, count=QUESTIONS_PER_QUIZ)
    question_types = generate_question_types(
        count=QUESTIONS_PER_QUIZ,
        include_audio=include_audio,
        audio_ratio=audio_ratio
    )

    # Shuffle selected_letters to ensure random pairing with question types
    # (both lists are independently randomized, but zip creates deterministic pairing)
    random.shuffle(selected_letters)

    formatted_questions = []

    for i, (letter, qtype) in enumerate(zip(selected_letters, question_types)):
        # Generate distractors based on difficulty level
        distractors = generate_distractors(
            db,
            letter,
            count=distractor_count,
            use_similar=use_similar_distractors,
            strict_similar=strict_similar_distractors
        )

        # Format question for frontend
        formatted = format_question(letter, qtype, distractors)

        # Create database record with stored options to prevent regeneration issues
        question = QuizQuestion(
            quiz_id=quiz.id,
            letter_id=letter.id,
            question_type=qtype.value,
            correct_option=formatted["correct_answer"],
            option_1=formatted["options"][0] if len(formatted["options"]) > 0 else None,
            option_2=formatted["options"][1] if len(formatted["options"]) > 1 else None,
            option_3=formatted["options"][2] if len(formatted["options"]) > 2 else None,
            option_4=formatted["options"][3] if len(formatted["options"]) > 3 else None
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
    selected_option: str,
    response_time_ms: int = None
) -> Dict:
    """
    Evaluate an answer and return result.

    Args:
        db: Database session
        question_id: QuizQuestion ID
        selected_option: User's selected answer
        response_time_ms: Optional response time in milliseconds

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
    if response_time_ms is not None:
        question.response_time_ms = response_time_ms

    return {
        "question_id": question_id,
        "is_correct": is_correct,
        "correct_answer": question.correct_option,
        "selected_answer": selected_option,
        "letter_id": question.letter_id,
        "response_time_ms": response_time_ms
    }
