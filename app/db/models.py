"""SQLAlchemy models for Greek Alphabet Mastery application."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Float, ForeignKey, CheckConstraint, UniqueConstraint, Index
from sqlalchemy.orm import relationship
from app.db.database import Base


class User(Base):
    """Anonymous user tracked by UUID cookie."""
    __tablename__ = "users"

    id = Column(Text, primary_key=True)  # UUID from gam_uid cookie
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_active_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Difficulty progression tracking
    current_level = Column(Integer, CheckConstraint("current_level >= 1 AND current_level <= 3"), nullable=False, default=1)
    consecutive_perfect_streak = Column(Integer, CheckConstraint("consecutive_perfect_streak >= 0"), nullable=False, default=0)
    level_up_count = Column(Integer, CheckConstraint("level_up_count >= 0"), nullable=False, default=0)

    # Index for analytics queries
    __table_args__ = (
        Index('idx_users_level', 'current_level'),
    )

    # Relationships
    letter_stats = relationship("UserLetterStat", back_populates="user", cascade="all, delete-orphan")
    quiz_attempts = relationship("QuizAttempt", back_populates="user", cascade="all, delete-orphan")
    level_progressions = relationship("LevelProgression", back_populates="user", cascade="all, delete-orphan")


class Letter(Base):
    """Greek alphabet letter with name and symbols."""
    __tablename__ = "letters"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(Text, unique=True, nullable=False)  # e.g., "Alpha"
    uppercase = Column(Text, nullable=False)  # e.g., "Α"
    lowercase = Column(Text, nullable=False)  # e.g., "α"
    position = Column(Integer, nullable=False)  # 1-24

    # Relationships
    user_stats = relationship("UserLetterStat", back_populates="letter")
    quiz_questions = relationship("QuizQuestion", back_populates="letter")


class UserLetterStat(Base):
    """Per-user per-letter mastery tracking."""
    __tablename__ = "user_letter_stats"

    user_id = Column(Text, ForeignKey("users.id"), primary_key=True)
    letter_id = Column(Integer, ForeignKey("letters.id"), primary_key=True)
    seen_count = Column(Integer, nullable=False, default=0)
    correct_count = Column(Integer, nullable=False, default=0)
    incorrect_count = Column(Integer, nullable=False, default=0)
    current_streak = Column(Integer, nullable=False, default=0)
    longest_streak = Column(Integer, nullable=False, default=0)
    last_seen_at = Column(DateTime, nullable=True)
    last_result = Column(Text, CheckConstraint("last_result IN ('correct', 'incorrect')"), nullable=True)
    mastery_score = Column(Float, nullable=False, default=0.0)

    # Spaced repetition scheduling
    next_review_at = Column(DateTime, nullable=True)  # When letter is due for review
    sr_interval_level = Column(Integer, nullable=False, default=0)  # Interval level (0-4)
    last_review_result = Column(Text, CheckConstraint("last_review_result IN ('correct', 'incorrect')"), nullable=True)

    # Indexes for query performance
    __table_args__ = (
        Index('idx_user_mastery', 'user_id', 'mastery_score'),
        Index('idx_user_seen_count', 'user_id', 'seen_count'),
        Index('idx_user_next_review', 'user_id', 'next_review_at'),
    )

    # Relationships
    user = relationship("User", back_populates="letter_stats")
    letter = relationship("Letter", back_populates="user_stats")


class QuizAttempt(Base):
    """Quiz session containing 14 questions."""
    __tablename__ = "quiz_attempts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Text, ForeignKey("users.id"), nullable=False)
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    question_count = Column(Integer, nullable=False, default=14)
    correct_count = Column(Integer, nullable=False, default=0)
    accuracy = Column(Float, nullable=True)

    # Index for query performance
    __table_args__ = (
        Index('idx_user_completed', 'user_id', 'completed_at'),
    )

    # Relationships
    user = relationship("User", back_populates="quiz_attempts")
    questions = relationship("QuizQuestion", back_populates="quiz", cascade="all, delete-orphan")


class QuizQuestion(Base):
    """Individual question within a quiz."""
    __tablename__ = "quiz_questions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    quiz_id = Column(Integer, ForeignKey("quiz_attempts.id"), nullable=False)
    letter_id = Column(Integer, ForeignKey("letters.id"), nullable=False)
    question_type = Column(Text, nullable=False)  # 'LETTER_TO_NAME', 'NAME_TO_UPPER', 'NAME_TO_LOWER'
    is_correct = Column(Integer, nullable=False, default=0)  # 0 or 1 (SQLite boolean)
    chosen_option = Column(Text, nullable=True)
    correct_option = Column(Text, nullable=True)

    # Store the 4 multiple choice options to prevent regeneration issues
    option_1 = Column(Text, nullable=True)
    option_2 = Column(Text, nullable=True)
    option_3 = Column(Text, nullable=True)
    option_4 = Column(Text, nullable=True)

    # Response time tracking for analytics
    response_time_ms = Column(Integer, nullable=True)  # Time to answer in milliseconds

    # Constraints and indexes
    __table_args__ = (
        UniqueConstraint('quiz_id', 'letter_id', name='uq_quiz_question'),
        Index('idx_quiz_correct', 'quiz_id', 'is_correct'),
    )

    # Relationships
    quiz = relationship("QuizAttempt", back_populates="questions")
    letter = relationship("Letter", back_populates="quiz_questions")


class LevelProgression(Base):
    """Historical tracking of user difficulty level advancements."""
    __tablename__ = "level_progressions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Text, ForeignKey("users.id"), nullable=False)
    from_level = Column(Integer, CheckConstraint("from_level >= 1 AND from_level <= 3"), nullable=False)
    to_level = Column(Integer, CheckConstraint("to_level >= 1 AND to_level <= 3"), nullable=False)
    achieved_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    perfect_streak_count = Column(Integer, nullable=False)  # Number of perfect quizzes that triggered level-up

    # Constraints and indexes
    __table_args__ = (
        CheckConstraint("to_level = from_level + 1", name="ck_level_progression_increment"),
        Index('idx_level_progressions_user', 'user_id', 'achieved_at'),
    )

    # Relationships
    user = relationship("User", back_populates="level_progressions")
