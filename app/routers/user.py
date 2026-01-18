"""User management and bootstrap endpoints."""
import uuid
from datetime import datetime
from typing import Optional, List, Dict
from collections import defaultdict
from fastapi import APIRouter, Depends, Response, Request
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.db.database import get_db
from app.db.models import User, UserLetterStat, Letter, QuizAttempt, QuizQuestion
from app.services.mastery import get_mastery_state
from app.services.level_progression import get_level_progress, get_level_description
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

    # Apply spaced repetition mastery decay for overdue letters
    from app.services.spaced_repetition import apply_mastery_decay
    apply_mastery_decay(db, user_id)
    db.commit()

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

    # Get user for level progression data
    user = db.query(User).filter(User.id == user_id).first()
    level_progress = None
    current_level_info = None
    if user:
        level_progress = get_level_progress(user)
        current_level_info = get_level_description(user.current_level)

    # Get confusion matrix (commonly confused letter pairs)
    confusion_pairs = get_confusion_matrix(db, user_id, limit=5)

    return {
        "user_id": user_id,
        "total_quizzes": total_quizzes,
        "average_accuracy": avg_accuracy,
        "quiz_history": quiz_history,
        "mastery_summary": mastery_summary,
        "level_progress": level_progress,
        "current_level_info": current_level_info,
        "confusion_pairs": confusion_pairs
    }


def get_confusion_matrix(db: Session, user_id: str, limit: int = 10) -> List[Dict]:
    """
    Analyze incorrect answers to find commonly confused letter pairs.

    Returns top N letter pairs where the user consistently chooses the wrong letter.

    Args:
        db: Database session
        user_id: User UUID
        limit: Maximum pairs to return

    Returns:
        List of dicts with correct_letter, confused_with, count, and letter symbols
    """
    # Get all incorrect quiz questions for this user
    incorrect_questions = db.query(QuizQuestion).join(
        QuizAttempt, QuizQuestion.quiz_id == QuizAttempt.id
    ).filter(
        QuizAttempt.user_id == user_id,
        QuizQuestion.is_correct == 0,
        QuizQuestion.chosen_option.isnot(None),
        QuizQuestion.correct_option.isnot(None)
    ).all()

    if not incorrect_questions:
        return []

    # Build a map of letter id -> letter object
    letters = db.query(Letter).all()
    letter_by_id = {l.id: l for l in letters}
    letter_by_name = {l.name: l for l in letters}
    letter_by_upper = {l.uppercase: l for l in letters}
    letter_by_lower = {l.lowercase: l for l in letters}

    # Count confusion pairs (correct -> chosen)
    confusion_counts = defaultdict(int)

    for q in incorrect_questions:
        correct_letter = letter_by_id.get(q.letter_id)
        if not correct_letter:
            continue

        # Try to identify what letter was chosen
        chosen_letter = None
        chosen = q.chosen_option

        # Check if chosen option is a letter name
        if chosen in letter_by_name:
            chosen_letter = letter_by_name[chosen]
        # Check if chosen option is uppercase form
        elif chosen in letter_by_upper:
            chosen_letter = letter_by_upper[chosen]
        # Check if chosen option is lowercase form
        elif chosen in letter_by_lower:
            chosen_letter = letter_by_lower[chosen]

        if chosen_letter and chosen_letter.id != correct_letter.id:
            # Create a sorted pair key to count both directions
            pair_key = tuple(sorted([correct_letter.name, chosen_letter.name]))
            confusion_counts[pair_key] += 1

    if not confusion_counts:
        return []

    # Sort by count and take top N
    sorted_pairs = sorted(confusion_counts.items(), key=lambda x: x[1], reverse=True)[:limit]

    # Format results with letter info
    results = []
    for (letter1_name, letter2_name), count in sorted_pairs:
        l1 = letter_by_name.get(letter1_name)
        l2 = letter_by_name.get(letter2_name)
        if l1 and l2:
            results.append({
                "letter1": {
                    "name": l1.name,
                    "uppercase": l1.uppercase,
                    "lowercase": l1.lowercase
                },
                "letter2": {
                    "name": l2.name,
                    "uppercase": l2.uppercase,
                    "lowercase": l2.lowercase
                },
                "count": count
            })

    return results


@router.get("/letter/{letter_name}")
async def get_letter_details(
    letter_name: str,
    request: Request,
    response: Response,
    db: Session = Depends(get_db)
):
    """
    Get detailed information about a specific letter including user stats.

    Returns:
    - Letter details (name, uppercase, lowercase, position)
    - User stats (accuracy, streak, mastery score)
    - Similar letters that are commonly confused with this one
    """
    user_id = get_or_create_user(request, response, db)

    # Find the letter
    letter = db.query(Letter).filter(Letter.name == letter_name).first()
    if not letter:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Letter '{letter_name}' not found")

    # Get user stats for this letter
    stat = db.query(UserLetterStat).filter(
        UserLetterStat.user_id == user_id,
        UserLetterStat.letter_id == letter.id
    ).first()

    user_stats = None
    if stat:
        state = get_mastery_state(
            stat.seen_count,
            stat.correct_count,
            stat.current_streak
        )
        user_stats = {
            "seen_count": stat.seen_count,
            "correct_count": stat.correct_count,
            "incorrect_count": stat.incorrect_count,
            "accuracy": stat.correct_count / stat.seen_count if stat.seen_count > 0 else 0,
            "current_streak": stat.current_streak,
            "longest_streak": stat.longest_streak,
            "mastery_score": stat.mastery_score,
            "mastery_state": state.value,
            "last_result": stat.last_result
        }

    # Find commonly confused letters with this one
    confused_with = []
    confusion_data = get_confusion_matrix(db, user_id, limit=20)
    for pair in confusion_data:
        if pair["letter1"]["name"] == letter_name:
            confused_with.append({
                "name": pair["letter2"]["name"],
                "uppercase": pair["letter2"]["uppercase"],
                "lowercase": pair["letter2"]["lowercase"],
                "count": pair["count"]
            })
        elif pair["letter2"]["name"] == letter_name:
            confused_with.append({
                "name": pair["letter1"]["name"],
                "uppercase": pair["letter1"]["uppercase"],
                "lowercase": pair["letter1"]["lowercase"],
                "count": pair["count"]
            })

    # Audio file path
    from app.constants import AUDIO_PATH_TEMPLATE
    audio_file = AUDIO_PATH_TEMPLATE.format(letter_name=letter.name.lower())

    return {
        "letter": {
            "name": letter.name,
            "uppercase": letter.uppercase,
            "lowercase": letter.lowercase,
            "position": letter.position
        },
        "user_stats": user_stats,
        "confused_with": confused_with[:5],  # Top 5 confused letters
        "audio_file": audio_file
    }
