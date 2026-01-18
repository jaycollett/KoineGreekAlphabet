"""Mastery score calculation and state determination."""
from enum import Enum
from typing import Dict, Any
from app.db.models import UserLetterStat
from app.constants import (
    MASTERY_MIN_ATTEMPTS,
    MASTERY_ACCURACY_WEIGHT,
    MASTERY_STREAK_BONUS_PER_CORRECT,
    MAX_STREAK_FOR_MASTERY,
    MASTERED_MIN_ATTEMPTS,
    MASTERED_MIN_ACCURACY,
    MASTERED_MIN_STREAK
)


class MasteryState(str, Enum):
    """Mastery state for a letter."""
    UNSEEN = "unseen"
    LEARNING = "learning"
    MASTERED = "mastered"


def calculate_mastery_score(seen_count: int, correct_count: int, current_streak: int) -> float:
    """
    Calculate mastery score for a letter based on performance.

    Formula:
    - If seen_count < MASTERY_MIN_ATTEMPTS: Cap score low (not enough data)
    - Otherwise: Base on accuracy with streak bonus
    - mastery_score = clamp(0, 1, accuracy * MASTERY_ACCURACY_WEIGHT + min(current_streak, MAX_STREAK_FOR_MASTERY) * MASTERY_STREAK_BONUS_PER_CORRECT)

    Args:
        seen_count: Total times this letter has been seen
        correct_count: Number of correct answers
        current_streak: Current consecutive correct answers

    Returns:
        Float between 0.0 and 1.0 representing mastery level
    """
    if seen_count == 0:
        return 0.0

    accuracy = correct_count / max(1, seen_count)

    # Not enough data yet - cap the score
    if seen_count < MASTERY_MIN_ATTEMPTS:
        return min(accuracy * 0.5, 0.4)

    # Standard formula with streak bonus
    streak_bonus = min(current_streak, MAX_STREAK_FOR_MASTERY) * MASTERY_STREAK_BONUS_PER_CORRECT
    score = accuracy * MASTERY_ACCURACY_WEIGHT + streak_bonus

    # Clamp between 0 and 1
    return max(0.0, min(1.0, score))


def get_mastery_state(seen_count: int, correct_count: int, current_streak: int) -> MasteryState:
    """
    Determine mastery state based on performance criteria.

    States:
    - UNSEEN: Never attempted (seen_count == 0)
    - LEARNING: Attempted but not mastered
    - MASTERED: At least MASTERED_MIN_ATTEMPTS attempts AND
                accuracy >= MASTERED_MIN_ACCURACY AND
                streak >= MASTERED_MIN_STREAK

    Args:
        seen_count: Total times this letter has been seen
        correct_count: Number of correct answers
        current_streak: Current consecutive correct answers

    Returns:
        MasteryState enum value
    """
    if seen_count == 0:
        return MasteryState.UNSEEN

    accuracy = correct_count / seen_count

    # Mastery criteria defined by constants
    if (seen_count >= MASTERED_MIN_ATTEMPTS and
        accuracy >= MASTERED_MIN_ACCURACY and
        current_streak >= MASTERED_MIN_STREAK):
        return MasteryState.MASTERED

    return MasteryState.LEARNING


def update_letter_stats(
    stat: UserLetterStat,
    is_correct: bool
) -> Dict[str, Any]:
    """
    Update user letter statistics after an answer.

    Updates:
    - seen_count, correct/incorrect counts
    - current_streak, longest_streak
    - last_result
    - mastery_score (recalculated)

    Args:
        stat: UserLetterStat object to update
        is_correct: Whether the answer was correct

    Returns:
        Dictionary with updated values for easy inspection
    """
    stat.seen_count += 1

    if is_correct:
        stat.correct_count += 1
        stat.current_streak += 1
        stat.longest_streak = max(stat.longest_streak, stat.current_streak)
        stat.last_result = "correct"
    else:
        stat.incorrect_count += 1
        stat.current_streak = 0
        stat.last_result = "incorrect"

    # Recalculate mastery score
    stat.mastery_score = calculate_mastery_score(
        stat.seen_count,
        stat.correct_count,
        stat.current_streak
    )

    # Update spaced repetition schedule
    from app.services.spaced_repetition import update_sr_schedule, schedule_initial_review
    update_sr_schedule(stat, is_correct)

    # If letter just reached mastery threshold, schedule initial review
    schedule_initial_review(stat)

    return {
        "seen_count": stat.seen_count,
        "correct_count": stat.correct_count,
        "incorrect_count": stat.incorrect_count,
        "current_streak": stat.current_streak,
        "longest_streak": stat.longest_streak,
        "mastery_score": stat.mastery_score,
        "mastery_state": get_mastery_state(
            stat.seen_count,
            stat.correct_count,
            stat.current_streak
        ).value
    }
