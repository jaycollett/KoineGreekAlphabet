"""Application-wide constants and configuration values.

This module centralizes all magic numbers and hardcoded values used throughout
the application, making them easier to maintain and adjust.
"""

# Quiz Configuration
QUESTIONS_PER_QUIZ = 14
"""Number of questions in each quiz session."""

DISTRACTOR_COUNT = 3
"""Number of incorrect answer options to show with each question."""

# Adaptive Learning Configuration
ADAPTIVE_MODE_THRESHOLD = 10
"""Number of completed quizzes required before adaptive mode activates."""

RECENT_SELECTION_WINDOW = 3
"""Avoid repeating the same letter within this many consecutive questions."""

WEAK_LETTER_RATIO = 0.6
"""Proportion of questions (60%) that focus on weak letters in adaptive mode."""

# Mastery Calculation
MASTERY_THRESHOLD = 0.8
"""Minimum mastery score (0.0-1.0) considered proficient."""

MAX_STREAK_FOR_MASTERY = 5
"""Maximum consecutive correct answers that contribute to mastery bonus."""

MASTERY_MIN_ATTEMPTS = 3
"""Minimum number of attempts before mastery score is fully trusted."""

MASTERY_ACCURACY_WEIGHT = 0.8
"""Weight given to accuracy in mastery score calculation (80%)."""

MASTERY_STREAK_BONUS_PER_CORRECT = 0.04
"""Bonus added to mastery score per consecutive correct answer (4% each)."""

# Mastery State Thresholds
MASTERED_MIN_ATTEMPTS = 8
"""Minimum number of attempts required to achieve MASTERED state."""

MASTERED_MIN_ACCURACY = 0.9
"""Minimum accuracy (90%) required to achieve MASTERED state."""

MASTERED_MIN_STREAK = 3
"""Minimum consecutive correct streak required to achieve MASTERED state."""

# Summary and History
RECENT_QUIZ_HISTORY_LIMIT = 10
"""Number of recent quiz results to show in summary."""

WEAK_LETTERS_SUMMARY_COUNT = 5
"""Number of weakest letters to highlight in overall statistics."""

MIN_ATTEMPTS_FOR_WEAK_IDENTIFICATION = 3
"""Minimum attempts before a letter is considered for weak letter identification."""

WEAK_LETTER_THRESHOLD = 0.5
"""Maximum mastery score to be identified as a weak letter."""

# Question Analysis Thresholds
MIN_LETTER_OCCURRENCES_IN_QUIZ = 2
"""Minimum times a letter must appear in a quiz to be analyzed for strength/weakness."""

# Cookie Configuration
COOKIE_NAME = "gam_uid"
"""Name of the cookie used to store user UUID."""

# Rate Limiting
QUIZ_START_RATE_LIMIT = "10/minute"
"""Maximum number of quiz starts allowed per minute per user."""

ANSWER_SUBMISSION_RATE_LIMIT = "60/minute"
"""Maximum number of answer submissions allowed per minute per user."""

# Logging
DEFAULT_LOG_LEVEL = "INFO"
"""Default logging level for the application."""

# Audio Configuration
AUDIO_PATH_TEMPLATE = "/static/audio/{letter_name}.mp3"
"""Template for generating audio file paths. {letter_name} will be replaced with lowercase letter name."""
