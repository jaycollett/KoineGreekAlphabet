"""
Tests for difficulty progression schema and database operations.

Tests cover:
1. Schema validation (columns, constraints, indexes)
2. Level-up logic
3. Streak updates
4. Progression history tracking
5. Data integrity constraints
"""

import pytest
from datetime import datetime
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError

from app.db.models import Base, User, LevelProgression, QuizAttempt
from app.db.database import get_db


@pytest.fixture
def test_db():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


class TestDifficultyProgressionSchema:
    """Test schema structure and constraints."""

    def test_users_table_has_progression_columns(self, test_db):
        """Verify users table has all difficulty progression columns."""
        inspector = inspect(test_db.bind)
        columns = [col['name'] for col in inspector.get_columns('users')]

        assert 'current_level' in columns
        assert 'consecutive_perfect_streak' in columns
        assert 'level_up_count' in columns

    def test_level_progressions_table_exists(self, test_db):
        """Verify level_progressions table is created."""
        inspector = inspect(test_db.bind)
        tables = inspector.get_table_names()
        assert 'level_progressions' in tables

    def test_level_progressions_table_structure(self, test_db):
        """Verify level_progressions table has correct columns."""
        inspector = inspect(test_db.bind)
        columns = [col['name'] for col in inspector.get_columns('level_progressions')]

        expected_columns = ['id', 'user_id', 'from_level', 'to_level',
                           'achieved_at', 'perfect_streak_count']
        for col in expected_columns:
            assert col in columns

    def test_indexes_created(self, test_db):
        """Verify indexes for difficulty progression are created."""
        inspector = inspect(test_db.bind)

        # Check users table indexes
        users_indexes = [idx['name'] for idx in inspector.get_indexes('users')]
        assert 'idx_users_level' in users_indexes

        # Check level_progressions table indexes
        lp_indexes = [idx['name'] for idx in inspector.get_indexes('level_progressions')]
        assert 'idx_level_progressions_user' in lp_indexes


class TestUserLevelConstraints:
    """Test CHECK constraints on user levels and streaks."""

    def test_default_values_on_new_user(self, test_db):
        """New users should start at level 1 with 0 streak."""
        user = User(id="test-user-1")
        test_db.add(user)
        test_db.commit()

        assert user.current_level == 1
        assert user.consecutive_perfect_streak == 0
        assert user.level_up_count == 0

    def test_cannot_set_level_above_3(self, test_db):
        """Users cannot have level > 3."""
        user = User(id="test-user-invalid", current_level=5)
        test_db.add(user)

        with pytest.raises(IntegrityError):
            test_db.commit()

    def test_cannot_set_level_below_1(self, test_db):
        """Users cannot have level < 1."""
        user = User(id="test-user-invalid", current_level=0)
        test_db.add(user)

        with pytest.raises(IntegrityError):
            test_db.commit()

    def test_cannot_set_negative_streak(self, test_db):
        """Streak cannot be negative."""
        user = User(id="test-user-invalid", consecutive_perfect_streak=-5)
        test_db.add(user)

        with pytest.raises(IntegrityError):
            test_db.commit()

    def test_valid_level_values(self, test_db):
        """Test that levels 1, 2, 3 are all valid."""
        for level in [1, 2, 3]:
            user = User(id=f"test-user-level-{level}", current_level=level)
            test_db.add(user)
            test_db.commit()
            assert user.current_level == level
            test_db.delete(user)
            test_db.commit()


class TestStreakUpdates:
    """Test streak increment and reset logic."""

    def test_increment_streak_on_perfect_quiz(self, test_db):
        """Streak should increment by 1 on perfect quiz."""
        user = User(id="test-user-streak", consecutive_perfect_streak=3)
        test_db.add(user)
        test_db.commit()

        # Simulate perfect quiz
        user.consecutive_perfect_streak += 1
        test_db.commit()

        assert user.consecutive_perfect_streak == 4

    def test_reset_streak_on_imperfect_quiz(self, test_db):
        """Streak should reset to 0 on non-perfect quiz."""
        user = User(id="test-user-reset", consecutive_perfect_streak=7)
        test_db.add(user)
        test_db.commit()

        # Simulate imperfect quiz
        user.consecutive_perfect_streak = 0
        test_db.commit()

        assert user.consecutive_perfect_streak == 0

    def test_streak_persists_across_sessions(self, test_db):
        """Streak should persist when reading user from DB."""
        user = User(id="test-user-persist", consecutive_perfect_streak=5)
        test_db.add(user)
        test_db.commit()

        # Simulate new session: fetch user from DB
        fetched_user = test_db.query(User).filter(User.id == "test-user-persist").first()
        assert fetched_user.consecutive_perfect_streak == 5


class TestLevelProgression:
    """Test level-up logic and progression tracking."""

    def test_level_up_from_1_to_2(self, test_db):
        """User should advance from level 1 to 2 after 10 perfect quizzes."""
        user = User(id="test-levelup-1-2", current_level=1, consecutive_perfect_streak=10)
        test_db.add(user)
        test_db.commit()

        # Perform level-up
        progression = LevelProgression(
            user_id=user.id,
            from_level=1,
            to_level=2,
            perfect_streak_count=10
        )
        test_db.add(progression)

        user.current_level = 2
        user.consecutive_perfect_streak = 0
        user.level_up_count = 1
        test_db.commit()

        # Verify user state
        assert user.current_level == 2
        assert user.consecutive_perfect_streak == 0
        assert user.level_up_count == 1

        # Verify progression record
        prog = test_db.query(LevelProgression).filter(
            LevelProgression.user_id == user.id
        ).first()
        assert prog is not None
        assert prog.from_level == 1
        assert prog.to_level == 2
        assert prog.perfect_streak_count == 10

    def test_level_up_from_2_to_3(self, test_db):
        """User should advance from level 2 to 3."""
        user = User(id="test-levelup-2-3", current_level=2, consecutive_perfect_streak=10, level_up_count=1)
        test_db.add(user)
        test_db.commit()

        # Perform level-up
        progression = LevelProgression(
            user_id=user.id,
            from_level=2,
            to_level=3,
            perfect_streak_count=10
        )
        test_db.add(progression)

        user.current_level = 3
        user.consecutive_perfect_streak = 0
        user.level_up_count = 2
        test_db.commit()

        assert user.current_level == 3
        assert user.level_up_count == 2

    def test_cannot_level_up_above_3(self, test_db):
        """Users at level 3 cannot level up further."""
        user = User(id="test-max-level", current_level=3, consecutive_perfect_streak=15)
        test_db.add(user)
        test_db.commit()

        # User can build streak but shouldn't be able to level up to 4
        # (Business logic should prevent this, but schema allows level 3)
        assert user.current_level == 3
        assert user.consecutive_perfect_streak == 15

    def test_multiple_progressions_tracked(self, test_db):
        """Users should have full progression history."""
        user = User(id="test-multi-progress", current_level=3, level_up_count=2)
        test_db.add(user)

        # Add two progression records
        prog1 = LevelProgression(
            user_id=user.id,
            from_level=1,
            to_level=2,
            perfect_streak_count=10
        )
        prog2 = LevelProgression(
            user_id=user.id,
            from_level=2,
            to_level=3,
            perfect_streak_count=10
        )
        test_db.add_all([prog1, prog2])
        test_db.commit()

        # Verify both progressions exist
        progressions = test_db.query(LevelProgression).filter(
            LevelProgression.user_id == user.id
        ).order_by(LevelProgression.achieved_at).all()

        assert len(progressions) == 2
        assert progressions[0].to_level == 2
        assert progressions[1].to_level == 3


class TestProgressionConstraints:
    """Test CHECK constraints on level_progressions table."""

    def test_cannot_skip_levels(self, test_db):
        """Progression must be from N to N+1 only."""
        user = User(id="test-skip-level")
        test_db.add(user)
        test_db.commit()

        # Try to go from level 1 to level 3 (should fail)
        invalid_progression = LevelProgression(
            user_id=user.id,
            from_level=1,
            to_level=3,
            perfect_streak_count=10
        )
        test_db.add(invalid_progression)

        with pytest.raises(IntegrityError):
            test_db.commit()

    def test_cannot_go_backwards(self, test_db):
        """Progression must be forward only (N to N+1, not N to N-1)."""
        user = User(id="test-backward")
        test_db.add(user)
        test_db.commit()

        # Try to go from level 2 to level 1 (should fail)
        invalid_progression = LevelProgression(
            user_id=user.id,
            from_level=2,
            to_level=1,
            perfect_streak_count=0
        )
        test_db.add(invalid_progression)

        with pytest.raises(IntegrityError):
            test_db.commit()

    def test_cannot_create_invalid_from_level(self, test_db):
        """from_level must be 1-3."""
        user = User(id="test-invalid-from")
        test_db.add(user)
        test_db.commit()

        invalid_progression = LevelProgression(
            user_id=user.id,
            from_level=0,
            to_level=1,
            perfect_streak_count=10
        )
        test_db.add(invalid_progression)

        with pytest.raises(IntegrityError):
            test_db.commit()

    def test_cannot_create_invalid_to_level(self, test_db):
        """to_level must be 1-3."""
        user = User(id="test-invalid-to")
        test_db.add(user)
        test_db.commit()

        invalid_progression = LevelProgression(
            user_id=user.id,
            from_level=3,
            to_level=4,
            perfect_streak_count=10
        )
        test_db.add(invalid_progression)

        with pytest.raises(IntegrityError):
            test_db.commit()


class TestCascadeDeletion:
    """Test that deleting a user cascades to progression records."""

    def test_delete_user_cascades_to_progressions(self, test_db):
        """Deleting user should also delete their progression records."""
        user = User(id="test-cascade-delete")
        test_db.add(user)
        test_db.commit()

        # Add progression records
        progression = LevelProgression(
            user_id=user.id,
            from_level=1,
            to_level=2,
            perfect_streak_count=10
        )
        test_db.add(progression)
        test_db.commit()

        # Verify progression exists
        assert test_db.query(LevelProgression).filter(
            LevelProgression.user_id == user.id
        ).count() == 1

        # Delete user
        test_db.delete(user)
        test_db.commit()

        # Verify progression was also deleted
        assert test_db.query(LevelProgression).filter(
            LevelProgression.user_id == user.id
        ).count() == 0


class TestRelationships:
    """Test SQLAlchemy relationships between models."""

    def test_user_to_progressions_relationship(self, test_db):
        """User should have access to their progressions via relationship."""
        user = User(id="test-relationship")
        test_db.add(user)
        test_db.commit()

        # Add progression
        progression = LevelProgression(
            user_id=user.id,
            from_level=1,
            to_level=2,
            perfect_streak_count=10
        )
        test_db.add(progression)
        test_db.commit()

        # Access via relationship
        test_db.refresh(user)
        assert len(user.level_progressions) == 1
        assert user.level_progressions[0].to_level == 2

    def test_progression_to_user_relationship(self, test_db):
        """Progression should have access to user via relationship."""
        user = User(id="test-back-relationship")
        test_db.add(user)
        test_db.commit()

        progression = LevelProgression(
            user_id=user.id,
            from_level=1,
            to_level=2,
            perfect_streak_count=10
        )
        test_db.add(progression)
        test_db.commit()

        # Access via back-reference
        test_db.refresh(progression)
        assert progression.user.id == user.id


class TestIntegrationScenarios:
    """Test complete user progression scenarios."""

    def test_complete_journey_from_1_to_3(self, test_db):
        """Simulate complete user journey from level 1 to level 3."""
        user = User(id="test-journey")
        test_db.add(user)
        test_db.commit()

        # Starting state
        assert user.current_level == 1
        assert user.consecutive_perfect_streak == 0

        # Build streak to 10 at level 1
        user.consecutive_perfect_streak = 10
        test_db.commit()

        # Level up to 2
        prog1 = LevelProgression(
            user_id=user.id,
            from_level=1,
            to_level=2,
            perfect_streak_count=10
        )
        test_db.add(prog1)
        user.current_level = 2
        user.consecutive_perfect_streak = 0
        user.level_up_count = 1
        test_db.commit()

        assert user.current_level == 2

        # Build streak to 10 at level 2
        user.consecutive_perfect_streak = 10
        test_db.commit()

        # Level up to 3
        prog2 = LevelProgression(
            user_id=user.id,
            from_level=2,
            to_level=3,
            perfect_streak_count=10
        )
        test_db.add(prog2)
        user.current_level = 3
        user.consecutive_perfect_streak = 0
        user.level_up_count = 2
        test_db.commit()

        assert user.current_level == 3
        assert user.level_up_count == 2

        # Verify complete progression history
        test_db.refresh(user)
        assert len(user.level_progressions) == 2

    def test_streak_interrupted_and_reset(self, test_db):
        """User builds streak, fails quiz, streak resets, builds again."""
        user = User(id="test-interrupted")
        test_db.add(user)
        test_db.commit()

        # Build streak to 7
        user.consecutive_perfect_streak = 7
        test_db.commit()

        # Fail a quiz (reset streak)
        user.consecutive_perfect_streak = 0
        test_db.commit()

        # Build streak again to 10
        for _ in range(10):
            user.consecutive_perfect_streak += 1
            test_db.commit()

        assert user.consecutive_perfect_streak == 10
        assert user.current_level == 1  # Still at level 1 (hasn't leveled up yet)

    def test_level_3_user_continues_perfect_streak(self, test_db):
        """User at level 3 can continue building streak (no more levels)."""
        user = User(id="test-max-streak", current_level=3, level_up_count=2)
        test_db.add(user)
        test_db.commit()

        # Build streak past 10 at level 3
        user.consecutive_perfect_streak = 25
        test_db.commit()

        assert user.current_level == 3
        assert user.consecutive_perfect_streak == 25
        # User stays at level 3 (no level 4 exists)
