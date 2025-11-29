"""Mastery score calculation and state determination."""
from enum import Enum
from typing import Dict
from app.db.models import UserLetterStat


class MasteryState(str, Enum):
    """Mastery state for a letter."""
    UNSEEN = "unseen"
    LEARNING = "learning"
    MASTERED = "mastered"


def calculate_mastery_score(seen_count: int, correct_count: int, current_streak: int) -> float:
    """
    Calculate mastery score for a letter based on performance.

    Formula:
    - If seen_count < 3: Cap score low (not enough data)
    - Otherwise: Base on accuracy with streak bonus
    - mastery_score = clamp(0, 1, accuracy * 0.8 + min(current_streak, 5) * 0.04)

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
    if seen_count < 3:
        return min(accuracy * 0.5, 0.4)

    # Standard formula with streak bonus
    streak_bonus = min(current_streak, 5) * 0.04
    score = accuracy * 0.8 + streak_bonus

    # Clamp between 0 and 1
    return max(0.0, min(1.0, score))


def get_mastery_state(seen_count: int, correct_count: int, current_streak: int) -> MasteryState:
    """
    Determine mastery state based on performance criteria.

    States:
    - UNSEEN: Never attempted (seen_count == 0)
    - LEARNING: Attempted but not mastered
    - MASTERED: At least 8 attempts AND accuracy >= 0.9 AND streak >= 3

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

    # Mastery criteria: 8+ attempts, 90%+ accuracy, 3+ streak
    if seen_count >= 8 and accuracy >= 0.9 and current_streak >= 3:
        return MasteryState.MASTERED

    return MasteryState.LEARNING


def update_letter_stats(
    stat: UserLetterStat,
    is_correct: bool
) -> Dict[str, any]:
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
