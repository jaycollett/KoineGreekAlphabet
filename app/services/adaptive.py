"""Adaptive question selection algorithm."""
import random
from typing import List, Tuple
from sqlalchemy.orm import Session
from app.db.models import Letter, UserLetterStat, QuizAttempt
from app.services.mastery import MasteryState, get_mastery_state


def get_total_questions_answered(db: Session, user_id: str) -> int:
    """
    Get total number of questions answered by user across all quizzes.

    Args:
        db: Database session
        user_id: User UUID

    Returns:
        Total question count
    """
    result = db.query(QuizAttempt).filter(
        QuizAttempt.user_id == user_id,
        QuizAttempt.completed_at.isnot(None)
    ).count()
    return result * 14  # Each quiz has 14 questions


def should_use_adaptive_mode(db: Session, user_id: str) -> bool:
    """
    Determine if adaptive mode should be active.

    Adaptive mode activates after 10 completed quizzes (140 questions).

    Args:
        db: Database session
        user_id: User UUID

    Returns:
        True if adaptive mode should be used
    """
    completed_quizzes = db.query(QuizAttempt).filter(
        QuizAttempt.user_id == user_id,
        QuizAttempt.completed_at.isnot(None)
    ).count()
    return completed_quizzes >= 10


def get_user_letter_stats_map(db: Session, user_id: str) -> dict:
    """
    Get all user letter stats as a dictionary keyed by letter_id.

    Args:
        db: Database session
        user_id: User UUID

    Returns:
        Dictionary mapping letter_id to UserLetterStat object
    """
    stats = db.query(UserLetterStat).filter(
        UserLetterStat.user_id == user_id
    ).all()
    return {stat.letter_id: stat for stat in stats}


def select_letter_balanced(
    db: Session,
    all_letters: List[Letter],
    stats_map: dict,
    recent_selections: List[int]
) -> Letter:
    """
    Select a letter using balanced mode (before adaptive threshold).

    Strategy:
    - Spread questions across all letters
    - Prefer letters with fewer exposures
    - Avoid recent repetitions

    Args:
        db: Database session
        all_letters: List of all Letter objects
        stats_map: Dictionary of letter_id -> UserLetterStat
        recent_selections: Recently selected letter IDs to avoid

    Returns:
        Selected Letter object
    """
    # Calculate weights based on inverse of seen_count
    weights = []
    eligible_letters = []

    for letter in all_letters:
        # Reduce weight if recently selected
        if letter.id in recent_selections[-3:]:  # Last 3 questions
            continue

        stat = stats_map.get(letter.id)
        seen_count = stat.seen_count if stat else 0

        # Weight inversely proportional to exposure (unseen = highest weight)
        weight = 1.0 / (seen_count + 1)
        weights.append(weight)
        eligible_letters.append(letter)

    if not eligible_letters:
        # Fallback: all letters are recent, just pick randomly
        return random.choice(all_letters)

    return random.choices(eligible_letters, weights=weights, k=1)[0]


def select_letter_adaptive(
    db: Session,
    all_letters: List[Letter],
    stats_map: dict,
    recent_selections: List[int],
    force_weak: bool = False
) -> Letter:
    """
    Select a letter using adaptive mode (after 10 quizzes).

    Strategy:
    - 60% from weaker letters (non-mastered, weighted by weakness)
    - 40% from all letters (for coverage)

    Args:
        db: Database session
        all_letters: List of all Letter objects
        stats_map: Dictionary of letter_id -> UserLetterStat
        recent_selections: Recently selected letter IDs to avoid
        force_weak: If True, force selection from weak letters (for 60% quota)

    Returns:
        Selected Letter object
    """
    # Partition into mastered and non-mastered
    mastered_letters = []
    weak_letters = []
    weakness_weights = []

    for letter in all_letters:
        # Reduce weight if recently selected
        if letter.id in recent_selections[-3:]:
            continue

        stat = stats_map.get(letter.id)

        if stat:
            state = get_mastery_state(
                stat.seen_count,
                stat.correct_count,
                stat.current_streak
            )
            weakness_score = 1.0 - stat.mastery_score

            if state == MasteryState.MASTERED:
                mastered_letters.append(letter)
            else:
                weak_letters.append(letter)
                weakness_weights.append(weakness_score)
        else:
            # Unseen letters are considered weak
            weak_letters.append(letter)
            weakness_weights.append(1.0)

    # If force_weak or we're in the 60% quota, select from weak letters
    if force_weak and weak_letters:
        return random.choices(weak_letters, weights=weakness_weights, k=1)[0]

    # For the 40% quota, select from all eligible letters
    all_eligible = weak_letters + mastered_letters
    if not all_eligible:
        # Fallback: all letters are recent
        return random.choice(all_letters)

    # Equal weight for coverage selection
    return random.choice(all_eligible)


def select_letters_for_quiz(
    db: Session,
    user_id: str,
    count: int = 14
) -> List[Letter]:
    """
    Select letters for a new quiz using appropriate strategy.

    Args:
        db: Database session
        user_id: User UUID
        count: Number of letters to select (default 14)

    Returns:
        List of Letter objects for the quiz
    """
    all_letters = db.query(Letter).all()
    stats_map = get_user_letter_stats_map(db, user_id)
    use_adaptive = should_use_adaptive_mode(db, user_id)

    selected_letters = []
    recent_selections = []

    for i in range(count):
        if use_adaptive:
            # 60% weak, 40% coverage
            # For 14 questions: first 8-9 from weak, rest from all
            force_weak = i < int(count * 0.6)
            letter = select_letter_adaptive(
                db, all_letters, stats_map, recent_selections, force_weak
            )
        else:
            letter = select_letter_balanced(
                db, all_letters, stats_map, recent_selections
            )

        selected_letters.append(letter)
        recent_selections.append(letter.id)

    return selected_letters
