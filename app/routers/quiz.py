"""Quiz operation endpoints."""
from datetime import datetime
from typing import Dict
from fastapi import APIRouter, Depends, Request, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.db.database import get_db
from app.db.models import QuizAttempt, QuizQuestion, UserLetterStat, Letter
from app.services.quiz_generator import create_quiz, evaluate_answer
from app.services.mastery import update_letter_stats, get_mastery_state

router = APIRouter(prefix="/api/quiz", tags=["quiz"])

COOKIE_NAME = "gam_uid"


class AnswerSubmission(BaseModel):
    """Request body for answer submission."""
    question_id: int
    selected_option: str


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

        # Get the correct answer and reconstruct options
        # Note: We need to regenerate options since we don't store them
        from app.services.quiz_generator import generate_distractors, format_question
        distractors = generate_distractors(db, letter, count=3)
        formatted = format_question(letter, qtype, distractors)

        formatted_questions.append({
            "question_id": question.id,
            "question_number": i + 1,
            "prompt": formatted["prompt"],
            "display_letter": formatted["display_letter"],
            "options": formatted["options"],
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

    # Verify quiz belongs to user
    quiz = db.query(QuizAttempt).filter(QuizAttempt.id == quiz_id).first()
    if not quiz or quiz.user_id != user_id:
        raise HTTPException(status_code=404, detail="Quiz not found")

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
    # Get questions with letter info
    questions_with_letters = db.query(QuizQuestion, Letter).join(
        Letter, QuizQuestion.letter_id == Letter.id
    ).filter(
        QuizQuestion.quiz_id == quiz.id
    ).all()

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
        if perf["total"] >= 2:  # Only consider letters seen multiple times
            if perf["correct"] == perf["total"]:
                strong_letters.append(letter_name)
            elif perf["correct"] == 0:
                weak_letters.append(letter_name)

    # Get last 10 quiz scores
    recent_quizzes = db.query(QuizAttempt).filter(
        QuizAttempt.user_id == user_id,
        QuizAttempt.completed_at.isnot(None)
    ).order_by(desc(QuizAttempt.completed_at)).limit(10).all()

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
        UserLetterStat.seen_count >= 3,
        UserLetterStat.mastery_score < 0.5
    ).order_by(UserLetterStat.mastery_score).limit(5).all()

    overall_weak_letters = [
        {
            "name": letter.name,
            "mastery_score": stat.mastery_score,
            "accuracy": stat.correct_count / stat.seen_count if stat.seen_count > 0 else 0
        }
        for stat, letter in weak_stats
    ]

    return {
        "quiz_id": quiz.id,
        "correct_count": quiz.correct_count,
        "question_count": quiz.question_count,
        "accuracy": quiz.accuracy,
        "accuracy_percentage": round(quiz.accuracy * 100, 1),
        "strong_letters": strong_letters,
        "weak_letters": weak_letters,
        "quiz_history": quiz_history,
        "overall_weak_letters": overall_weak_letters
    }
