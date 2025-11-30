"""Quiz operation endpoints."""
from datetime import datetime
from typing import Dict
from fastapi import APIRouter, Depends, Request, HTTPException
from pydantic import BaseModel, Field, validator
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc
from app.db.database import get_db
from app.db.models import QuizAttempt, QuizQuestion, UserLetterStat, Letter
from app.services.quiz_generator import create_quiz, evaluate_answer
from app.services.mastery import update_letter_stats, get_mastery_state
from app.constants import (
    COOKIE_NAME,
    MIN_LETTER_OCCURRENCES_IN_QUIZ,
    MIN_ATTEMPTS_FOR_WEAK_IDENTIFICATION,
    WEAK_LETTER_THRESHOLD,
    RECENT_QUIZ_HISTORY_LIMIT,
    WEAK_LETTERS_SUMMARY_COUNT
)

router = APIRouter(prefix="/api/quiz", tags=["quiz"])


class AnswerSubmission(BaseModel):
    """Request body for answer submission."""
    question_id: int = Field(..., gt=0, description="Question ID must be a positive integer")
    selected_option: str = Field(..., min_length=1, max_length=100, description="Selected option text")

    @validator('selected_option')
    def validate_option(cls, v):
        """Validate that selected_option is not empty or whitespace."""
        if not v or v.strip() == '':
            raise ValueError('selected_option cannot be empty')
        return v.strip()


class StartQuizRequest(BaseModel):
    """Request body for starting a quiz."""
    include_audio: bool = True


def get_user_id_from_cookie(request: Request) -> str:
    """Extract user ID from cookie."""
    user_id = request.cookies.get(COOKIE_NAME)
    if not user_id:
        raise HTTPException(status_code=401, detail="No user session found")
    return user_id


@router.get("/{quiz_id}/state")
async def get_quiz_state(
    quiz_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Get the current state of an in-progress quiz.

    Returns:
    - quiz data
    - questions with answered status
    - current progress
    """
    user_id = get_user_id_from_cookie(request)

    # Verify quiz belongs to user
    quiz = db.query(QuizAttempt).filter(QuizAttempt.id == quiz_id).first()
    if not quiz or quiz.user_id != user_id:
        raise HTTPException(status_code=404, detail="Quiz not found")

    # Don't allow resuming completed quizzes
    if quiz.completed_at is not None:
        raise HTTPException(status_code=400, detail="Quiz already completed")

    # Get all questions with their answers
    questions = db.query(QuizQuestion, Letter).join(
        Letter, QuizQuestion.letter_id == Letter.id
    ).filter(
        QuizQuestion.quiz_id == quiz_id
    ).all()

    # Format questions for frontend
    from app.services.quiz_generator import QuestionType
    formatted_questions = []

    for i, (question, letter) in enumerate(questions):
        # Determine question type and format accordingly
        qtype = QuestionType(question.question_type)

        # Use saved options from database to maintain consistency
        saved_options = [
            question.option_1,
            question.option_2,
            question.option_3,
            question.option_4
        ]
        # Filter out None values
        options = [opt for opt in saved_options if opt is not None]

        # Reconstruct prompt and display using format_question logic
        from app.services.quiz_generator import format_question, generate_distractors
        # We still need distractors for format_question, but we'll override options
        distractors = generate_distractors(db, letter, count=3)
        formatted = format_question(letter, qtype, distractors)

        formatted_questions.append({
            "question_id": question.id,
            "question_number": i + 1,
            "prompt": formatted["prompt"],
            "display_letter": formatted["display_letter"],
            "options": options,  # Use saved options instead of regenerated ones
            "correct_answer": formatted["correct_answer"],
            "letter_name": letter.name,
            "audio_file": formatted.get("audio_file"),
            "is_audio_question": formatted.get("is_audio_question", False),
            "is_answered": question.chosen_option is not None,
            "was_correct": question.is_correct == 1 if question.chosen_option else None
        })

    answered_count = sum(1 for q in formatted_questions if q["is_answered"])

    return {
        "quiz_id": quiz.id,
        "question_count": quiz.question_count,
        "questions": formatted_questions,
        "correct_count": quiz.correct_count,
        "answered_count": answered_count
    }


@router.post("/start")
async def start_quiz(
    quiz_request: StartQuizRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Start a new quiz.

    Args:
        quiz_request: Request body with quiz preferences (include_audio)

    Returns:
    - quiz_id
    - questions (list of 14 formatted questions)
    """
    user_id = get_user_id_from_cookie(request)

    # Create quiz with questions
    quiz, questions = create_quiz(db, user_id, include_audio=quiz_request.include_audio)

    return {
        "quiz_id": quiz.id,
        "question_count": quiz.question_count,
        "questions": questions
    }


@router.post("/{quiz_id}/answer")
async def submit_answer(
    quiz_id: int,
    answer: AnswerSubmission,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Submit an answer to a question.

    Updates:
    - QuizQuestion record (is_correct, chosen_option)
    - UserLetterStat (seen_count, correct/incorrect, streak, mastery_score)
    - QuizAttempt (correct_count, accuracy if last question)

    Returns:
    - Evaluation result
    - Quiz summary if last question
    """
    user_id = get_user_id_from_cookie(request)

    try:
        # Verify quiz belongs to user
        quiz = db.query(QuizAttempt).filter(QuizAttempt.id == quiz_id).first()
        if not quiz or quiz.user_id != user_id:
            raise HTTPException(status_code=404, detail="Quiz not found")

        # Verify quiz is not already completed
        if quiz.completed_at is not None:
            raise HTTPException(status_code=400, detail="Quiz already completed")

        # Check if question was already answered (prevents race condition)
        question = db.query(QuizQuestion).filter(QuizQuestion.id == answer.question_id).first()
        if not question:
            raise HTTPException(status_code=404, detail="Question not found")

        if question.chosen_option is not None:
            # Question already answered, return existing result
            return {
                "question_id": question.id,
                "is_correct": question.is_correct == 1,
                "correct_answer": question.correct_option,
                "selected_answer": question.chosen_option,
                "letter_id": question.letter_id,
                "is_last_question": False,
                "already_answered": True
            }

        # Evaluate answer
        result = evaluate_answer(db, answer.question_id, answer.selected_option)

        # Update quiz correct count
        if result["is_correct"]:
            quiz.correct_count += 1

        # Update user letter stats
        stat = db.query(UserLetterStat).filter(
            UserLetterStat.user_id == user_id,
            UserLetterStat.letter_id == result["letter_id"]
        ).first()

        if stat:
            stat.last_seen_at = datetime.utcnow()
            update_letter_stats(stat, result["is_correct"])

        # Flush changes so the current answer is counted
        db.flush()

        # Check if this was the last question
        answered_count = db.query(QuizQuestion).filter(
            QuizQuestion.quiz_id == quiz_id,
            QuizQuestion.chosen_option.isnot(None)
        ).count()

        is_last_question = answered_count >= quiz.question_count

        if is_last_question:
            # Finalize quiz
            quiz.completed_at = datetime.utcnow()
            quiz.accuracy = quiz.correct_count / quiz.question_count

            db.commit()

            # Generate summary
            summary = generate_quiz_summary(db, quiz, user_id)

            return {
                **result,
                "is_last_question": True,
                "summary": summary
            }

        db.commit()

        return {
            **result,
            "is_last_question": False
        }

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Rollback transaction on any error
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error submitting answer: {str(e)}")


def calculate_trend(db: Session, user_id: str, current_quiz_id: int, current_accuracy: float) -> Dict:
    """
    Calculate performance trend compared to recent quizzes.

    Args:
        db: Database session
        user_id: User UUID
        current_quiz_id: ID of the current quiz (to exclude it)
        current_accuracy: Accuracy of current quiz (0.0-1.0)

    Returns:
        Dictionary with trend data: {"trend": "up"|"stable"|"down", "change_percent": float}
        Returns None if insufficient data (< 3 previous quizzes)
    """
    # Get last 3 completed quizzes (excluding current)
    previous_quizzes = db.query(QuizAttempt).filter(
        QuizAttempt.user_id == user_id,
        QuizAttempt.completed_at.isnot(None),
        QuizAttempt.id != current_quiz_id
    ).order_by(desc(QuizAttempt.completed_at)).limit(3).all()

    if len(previous_quizzes) < 3:
        return None

    # Calculate average accuracy of previous 3 quizzes
    avg_accuracy = sum(q.accuracy for q in previous_quizzes) / len(previous_quizzes)

    # Calculate percentage difference
    change_percent = (current_accuracy - avg_accuracy) * 100

    # Determine trend (threshold of 5%)
    if change_percent >= 5.0:
        trend = "up"
    elif change_percent <= -5.0:
        trend = "down"
    else:
        trend = "stable"

    return {
        "trend": trend,
        "change_percent": round(change_percent, 1),
        "recent_average": round(avg_accuracy * 100, 1)
    }


def generate_quiz_summary(db: Session, quiz: QuizAttempt, user_id: str) -> Dict:
    """
    Generate summary for completed quiz.

    Args:
        db: Database session
        quiz: Completed QuizAttempt
        user_id: User UUID

    Returns:
        Dictionary with quiz summary data
    """
    # Get questions with letter info using eager loading to avoid N+1 queries
    questions = db.query(QuizQuestion).options(
        joinedload(QuizQuestion.letter)
    ).filter(
        QuizQuestion.quiz_id == quiz.id
    ).all()

    # Extract letter objects for easier access
    questions_with_letters = [(q, q.letter) for q in questions]

    # Analyze performance by letter
    letter_performance = {}
    for question, letter in questions_with_letters:
        if letter.name not in letter_performance:
            letter_performance[letter.name] = {
                "correct": 0,
                "total": 0
            }
        letter_performance[letter.name]["total"] += 1
        if question.is_correct:
            letter_performance[letter.name]["correct"] += 1

    # Identify strong and weak letters in this quiz
    strong_letters = []
    weak_letters = []

    for letter_name, perf in letter_performance.items():
        if perf["total"] >= MIN_LETTER_OCCURRENCES_IN_QUIZ:
            if perf["correct"] == perf["total"]:
                strong_letters.append(letter_name)
            elif perf["correct"] == 0:
                weak_letters.append(letter_name)

    # Get last N quiz scores
    recent_quizzes = db.query(QuizAttempt).filter(
        QuizAttempt.user_id == user_id,
        QuizAttempt.completed_at.isnot(None)
    ).order_by(desc(QuizAttempt.completed_at)).limit(RECENT_QUIZ_HISTORY_LIMIT).all()

    quiz_history = [
        {
            "quiz_id": q.id,
            "correct_count": q.correct_count,
            "accuracy": q.accuracy
        }
        for q in recent_quizzes
    ]

    # Overall weak letters (from user stats)
    weak_stats = db.query(UserLetterStat, Letter).join(
        Letter, UserLetterStat.letter_id == Letter.id
    ).filter(
        UserLetterStat.user_id == user_id,
        UserLetterStat.seen_count >= MIN_ATTEMPTS_FOR_WEAK_IDENTIFICATION,
        UserLetterStat.mastery_score < WEAK_LETTER_THRESHOLD
    ).order_by(UserLetterStat.mastery_score).limit(WEAK_LETTERS_SUMMARY_COUNT).all()

    overall_weak_letters = [
        {
            "name": letter.name,
            "mastery_score": stat.mastery_score,
            "accuracy": stat.correct_count / stat.seen_count if stat.seen_count > 0 else 0
        }
        for stat, letter in weak_stats
    ]

    # Calculate performance trend
    trend_data = calculate_trend(db, user_id, quiz.id, quiz.accuracy)

    return {
        "quiz_id": quiz.id,
        "correct_count": quiz.correct_count,
        "question_count": quiz.question_count,
        "accuracy": quiz.accuracy,
        "accuracy_percentage": round(quiz.accuracy * 100, 1),
        "strong_letters": strong_letters,
        "weak_letters": weak_letters,
        "quiz_history": quiz_history,
        "overall_weak_letters": overall_weak_letters,
        "trend": trend_data
    }
