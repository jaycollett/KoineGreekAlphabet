"""Level progression logic for difficulty system."""
from datetime import datetime
from typing import Optional, Dict
from sqlalchemy.orm import Session
from app.db.models import User, LevelProgression, QuizAttempt
from app.constants import PERFECT_STREAK_FOR_LEVEL_UP, QUESTIONS_PER_QUIZ


def check_and_update_level(
    db: Session,
    user: User,
    quiz: QuizAttempt
) -> Optional[Dict]:
    """
    Check if user should level up after completing a quiz.

    Updates user's consecutive_perfect_streak and performs level-up if criteria met.
    Level-up criteria:
    - 10 consecutive perfect quizzes (14/14 correct)
    - Current level < 3

    Args:
        db: Database session
        user: User object
        quiz: Completed QuizAttempt object

    Returns:
        Dictionary with level-up info if leveled up, None otherwise:
        {
            "leveled_up": True,
            "from_level": 1,
            "to_level": 2,
            "streak_count": 10
        }
    """
    is_perfect = quiz.correct_count == QUESTIONS_PER_QUIZ

    if is_perfect:
        # Increment streak
        user.consecutive_perfect_streak += 1

        # Check for level-up
        if (user.consecutive_perfect_streak >= PERFECT_STREAK_FOR_LEVEL_UP
            and user.current_level < 3):

            # Perform level-up
            from_level = user.current_level
            to_level = from_level + 1

            # Create level progression record
            progression = LevelProgression(
                user_id=user.id,
                from_level=from_level,
                to_level=to_level,
                achieved_at=datetime.utcnow(),
                perfect_streak_count=user.consecutive_perfect_streak
            )
            db.add(progression)

            # Update user level
            user.current_level = to_level
            user.level_up_count += 1

            # Reset streak after level-up
            user.consecutive_perfect_streak = 0

            db.flush()

            return {
                "leveled_up": True,
                "from_level": from_level,
                "to_level": to_level,
                "streak_count": PERFECT_STREAK_FOR_LEVEL_UP
            }

        # No level-up but perfect quiz
        return None

    else:
        # Non-perfect quiz resets streak
        user.consecutive_perfect_streak = 0
        return None


def get_level_progress(user: User) -> Dict:
    """
    Get user's progress toward next level.

    Args:
        user: User object

    Returns:
        Dictionary with level progress:
        {
            "current_level": 2,
            "max_level": 3,
            "can_level_up": True,
            "perfect_streak": 5,
            "required_streak": 10,
            "progress_percentage": 50.0
        }
    """
    can_level_up = user.current_level < 3
    progress_percentage = 0.0

    if can_level_up:
        progress_percentage = (user.consecutive_perfect_streak / PERFECT_STREAK_FOR_LEVEL_UP) * 100

    return {
        "current_level": user.current_level,
        "max_level": 3,
        "can_level_up": can_level_up,
        "perfect_streak": user.consecutive_perfect_streak,
        "required_streak": PERFECT_STREAK_FOR_LEVEL_UP,
        "progress_percentage": round(progress_percentage, 1)
    }


def get_level_description(level: int) -> Dict:
    """
    Get description of difficulty mechanics for a given level.

    Args:
        level: Difficulty level (1-3)

    Returns:
        Dictionary with level mechanics description:
        {
            "level": 2,
            "name": "Intermediate",
            "audio_ratio": 65,
            "distractor_count": 3,
            "distractor_type": "similar"
        }
    """
    descriptions = {
        1: {
            "level": 1,
            "name": "Beginner",
            "audio_ratio": 40,
            "distractor_count": 3,
            "distractor_type": "random",
            "description": "Mixed visual and audio questions with random distractors"
        },
        2: {
            "level": 2,
            "name": "Intermediate",
            "audio_ratio": 65,
            "distractor_count": 3,
            "distractor_type": "similar",
            "description": "More audio questions with visually/phonetically similar distractors"
        },
        3: {
            "level": 3,
            "name": "Advanced",
            "audio_ratio": 80,
            "distractor_count": 2,
            "distractor_type": "similar",
            "description": "Mostly audio questions with fewer, visually similar options"
        }
    }

    return descriptions.get(level, descriptions[1])
