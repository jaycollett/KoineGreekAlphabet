"""Spaced Repetition Scheduling Service.

Implements a simplified SM-2 inspired algorithm for scheduling letter reviews.
Letters advance through intervals (1d, 3d, 7d, 14d, 30d) when answered correctly
at a high mastery level, or reset to the beginning when answered incorrectly.
"""

from datetime import datetime, timedelta
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.db.models import UserLetterStat, Letter
from app.constants import (
    SR_INTERVALS_DAYS,
    SR_PRIORITY_WEIGHT,
    SR_MASTERY_DECAY_PER_DAY,
    SR_MIN_MASTERY_FOR_SCHEDULING,
    SR_MAX_INTERVAL_LEVEL
)


def calculate_next_review(interval_level: int) -> datetime:
    """
    Calculate the next review date based on interval level.

    Args:
        interval_level: Current interval level (0-4)

    Returns:
        DateTime for next scheduled review
    """
    # Clamp to valid range
    level = max(0, min(interval_level, SR_MAX_INTERVAL_LEVEL))
    days = SR_INTERVALS_DAYS[level]
    return datetime.utcnow() + timedelta(days=days)


def update_sr_schedule(stat: UserLetterStat, is_correct: bool) -> None:
    """
    Update spaced repetition schedule after an answer.

    If correct and at high mastery:
    - Advance interval level (up to max)
    - Schedule next review at new interval

    If incorrect:
    - Reset interval level to 0
    - Schedule immediate review (next day)

    Args:
        stat: UserLetterStat to update
        is_correct: Whether the answer was correct
    """
    if is_correct and stat.mastery_score >= SR_MIN_MASTERY_FOR_SCHEDULING:
        # Advance interval level (cap at max)
        if stat.sr_interval_level < SR_MAX_INTERVAL_LEVEL:
            stat.sr_interval_level += 1
        stat.last_review_result = 'correct'
    else:
        # Reset on incorrect answer
        stat.sr_interval_level = 0
        stat.last_review_result = 'incorrect' if not is_correct else 'correct'

    # Calculate and set next review date
    stat.next_review_at = calculate_next_review(stat.sr_interval_level)


def get_letters_due_for_review(
    db: Session,
    user_id: str,
    limit: Optional[int] = None
) -> List[UserLetterStat]:
    """
    Get letters that are due or overdue for review.

    A letter is due if:
    - next_review_at is set and <= current time
    - Has been scheduled into SR (mastery_score >= threshold)

    Args:
        db: Database session
        user_id: User UUID
        limit: Optional maximum number of letters to return

    Returns:
        List of UserLetterStat objects due for review, ordered by most overdue first
    """
    now = datetime.utcnow()

    query = db.query(UserLetterStat).filter(
        and_(
            UserLetterStat.user_id == user_id,
            UserLetterStat.next_review_at.isnot(None),
            UserLetterStat.next_review_at <= now
        )
    ).order_by(UserLetterStat.next_review_at.asc())

    if limit:
        query = query.limit(limit)

    return query.all()


def apply_mastery_decay(db: Session, user_id: str) -> int:
    """
    Apply mastery decay to overdue letters.

    Letters that are past their review date lose mastery at a rate of
    SR_MASTERY_DECAY_PER_DAY per day overdue.

    Args:
        db: Database session
        user_id: User UUID

    Returns:
        Number of letters that had mastery decayed
    """
    now = datetime.utcnow()
    decayed_count = 0

    # Get all letters that are overdue
    overdue_stats = db.query(UserLetterStat).filter(
        and_(
            UserLetterStat.user_id == user_id,
            UserLetterStat.next_review_at.isnot(None),
            UserLetterStat.next_review_at < now,
            UserLetterStat.mastery_score > 0
        )
    ).all()

    for stat in overdue_stats:
        # Calculate days overdue
        days_overdue = (now - stat.next_review_at).days

        if days_overdue > 0:
            # Apply decay
            decay = days_overdue * SR_MASTERY_DECAY_PER_DAY
            new_mastery = max(0.0, stat.mastery_score - decay)

            if new_mastery < stat.mastery_score:
                stat.mastery_score = new_mastery
                decayed_count += 1

    if decayed_count > 0:
        db.flush()

    return decayed_count


def get_sr_weight_for_letter(stat: UserLetterStat) -> float:
    """
    Get the selection weight for a letter based on SR schedule.

    Letters due for review get a weight boost.
    Letters not yet in SR system return 1.0 (neutral weight).

    Args:
        stat: UserLetterStat to evaluate

    Returns:
        Weight multiplier (1.0 = neutral, SR_PRIORITY_WEIGHT = boosted)
    """
    if stat.next_review_at is None:
        return 1.0

    now = datetime.utcnow()

    if stat.next_review_at <= now:
        # Due or overdue - boost priority
        return SR_PRIORITY_WEIGHT

    return 1.0


def schedule_initial_review(stat: UserLetterStat) -> None:
    """
    Schedule a letter for spaced repetition if it meets the criteria.

    Called when a letter reaches the mastery threshold for the first time.

    Args:
        stat: UserLetterStat to potentially schedule
    """
    if stat.mastery_score >= SR_MIN_MASTERY_FOR_SCHEDULING and stat.next_review_at is None:
        stat.sr_interval_level = 0
        stat.next_review_at = calculate_next_review(0)


def get_sr_status(stat: UserLetterStat) -> dict:
    """
    Get human-readable spaced repetition status for a letter.

    Args:
        stat: UserLetterStat to evaluate

    Returns:
        Dict with SR status information
    """
    if stat.next_review_at is None:
        return {
            "scheduled": False,
            "status": "not_scheduled",
            "message": "Not yet in spaced repetition"
        }

    now = datetime.utcnow()
    days_until_review = (stat.next_review_at - now).days

    if days_until_review < 0:
        return {
            "scheduled": True,
            "status": "overdue",
            "days_overdue": abs(days_until_review),
            "interval_level": stat.sr_interval_level,
            "message": f"Overdue by {abs(days_until_review)} day(s)"
        }
    elif days_until_review == 0:
        return {
            "scheduled": True,
            "status": "due_today",
            "interval_level": stat.sr_interval_level,
            "message": "Due for review today"
        }
    else:
        return {
            "scheduled": True,
            "status": "scheduled",
            "days_until_review": days_until_review,
            "interval_level": stat.sr_interval_level,
            "message": f"Review in {days_until_review} day(s)"
        }
