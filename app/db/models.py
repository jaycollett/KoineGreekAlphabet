"""SQLAlchemy models for Greek Alphabet Mastery application."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Float, ForeignKey, CheckConstraint
from sqlalchemy.orm import relationship
from app.db.database import Base


class User(Base):
    """Anonymous user tracked by UUID cookie."""
    __tablename__ = "users"

    id = Column(Text, primary_key=True)  # UUID from gam_uid cookie
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_active_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    letter_stats = relationship("UserLetterStat", back_populates="user", cascade="all, delete-orphan")
    quiz_attempts = relationship("QuizAttempt", back_populates="user", cascade="all, delete-orphan")


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

    # Relationships
    quiz = relationship("QuizAttempt", back_populates="questions")
    letter = relationship("Letter", back_populates="quiz_questions")
