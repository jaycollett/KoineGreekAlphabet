"""User management and bootstrap endpoints."""
import uuid
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Response, Request
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.db.database import get_db
from app.db.models import User, UserLetterStat, Letter, QuizAttempt
from app.services.mastery import get_mastery_state
from app.config import settings

router = APIRouter(prefix="/api", tags=["user"])

COOKIE_NAME = "gam_uid"


def get_or_create_user(request: Request, response: Response, db: Session) -> str:
    """
    Get or create anonymous user based on cookie.

    Args:
        request: FastAPI request
        response: FastAPI response (to set cookie)
        db: Database session

    Returns:
        User UUID
    """
    user_id = request.cookies.get(COOKIE_NAME)

    if user_id:
        # Check if user exists in database
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            # Update last active
            user.last_active_at = datetime.utcnow()
            db.commit()
            return user_id

    # Create new user
    user_id = f"gam_{uuid.uuid4()}"
    user = User(id=user_id)
    db.add(user)

    # Initialize stats for all letters
    letters = db.query(Letter).all()
    for letter in letters:
        stat = UserLetterStat(user_id=user_id, letter_id=letter.id)
        db.add(stat)

    db.commit()

    # Set cookie with security settings from config
    response.set_cookie(
        key=COOKIE_NAME,
        value=user_id,
        max_age=settings.COOKIE_MAX_AGE,
        httponly=settings.COOKIE_HTTPONLY,
        samesite=settings.COOKIE_SAMESITE,
        secure=settings.COOKIE_SECURE  # Enable in production via COOKIE_SECURE=true env var
    )

    return user_id


@router.get("/bootstrap")
async def bootstrap(
    request: Request,
    response: Response,
    db: Session = Depends(get_db)
):
    """
    Bootstrap user session and return initial data.

    Returns:
    - User stats
    - Last 10 quiz scores
    - Per-letter mastery summary
    """
    user_id = get_or_create_user(request, response, db)

    # Get last 10 quiz attempts
    recent_quizzes = db.query(QuizAttempt).filter(
        QuizAttempt.user_id == user_id,
        QuizAttempt.completed_at.isnot(None)
    ).order_by(desc(QuizAttempt.completed_at)).limit(10).all()

    quiz_history = [
        {
            "quiz_id": quiz.id,
            "completed_at": quiz.completed_at.isoformat(),
            "correct_count": quiz.correct_count,
            "question_count": quiz.question_count,
            "accuracy": quiz.accuracy
        }
        for quiz in recent_quizzes
    ]

    # Get per-letter stats
    letter_stats = db.query(UserLetterStat, Letter).join(
        Letter, UserLetterStat.letter_id == Letter.id
    ).filter(
        UserLetterStat.user_id == user_id
    ).all()

    mastery_summary = {
        "strong": [],
        "ok": [],
        "weak": []
    }

    for stat, letter in letter_stats:
        if stat.seen_count == 0:
            continue

        state = get_mastery_state(
            stat.seen_count,
            stat.correct_count,
            stat.current_streak
        )

        letter_info = {
            "name": letter.name,
            "mastery_score": stat.mastery_score,
            "accuracy": stat.correct_count / stat.seen_count if stat.seen_count > 0 else 0
        }

        if state.value == "mastered":
            mastery_summary["strong"].append(letter_info)
        elif stat.mastery_score >= 0.5:
            mastery_summary["ok"].append(letter_info)
        else:
            mastery_summary["weak"].append(letter_info)

    # Sort each category by mastery score
    mastery_summary["strong"].sort(key=lambda x: x["mastery_score"], reverse=True)
    mastery_summary["ok"].sort(key=lambda x: x["mastery_score"], reverse=True)
    mastery_summary["weak"].sort(key=lambda x: x["mastery_score"])

    # Overall stats
    total_quizzes = db.query(QuizAttempt).filter(
        QuizAttempt.user_id == user_id,
        QuizAttempt.completed_at.isnot(None)
    ).count()

    avg_accuracy = None
    if quiz_history:
        avg_accuracy = sum(q["accuracy"] for q in quiz_history if q["accuracy"]) / len(quiz_history)

    return {
        "user_id": user_id,
        "total_quizzes": total_quizzes,
        "average_accuracy": avg_accuracy,
        "quiz_history": quiz_history,
        "mastery_summary": mastery_summary
    }
