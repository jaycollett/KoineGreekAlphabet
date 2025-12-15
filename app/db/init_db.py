"""Database initialization and Greek alphabet seeding with auto-migration."""
import logging
from typing import Set, List
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError
from app.db.database import engine, SessionLocal, Base
from app.db.models import Letter

logger = logging.getLogger(__name__)

# Complete Greek alphabet with uppercase and lowercase
GREEK_ALPHABET = [
    {"name": "Alpha", "uppercase": "Α", "lowercase": "α", "position": 1},
    {"name": "Beta", "uppercase": "Β", "lowercase": "β", "position": 2},
    {"name": "Gamma", "uppercase": "Γ", "lowercase": "γ", "position": 3},
    {"name": "Delta", "uppercase": "Δ", "lowercase": "δ", "position": 4},
    {"name": "Epsilon", "uppercase": "Ε", "lowercase": "ε", "position": 5},
    {"name": "Zeta", "uppercase": "Ζ", "lowercase": "ζ", "position": 6},
    {"name": "Eta", "uppercase": "Η", "lowercase": "η", "position": 7},
    {"name": "Theta", "uppercase": "Θ", "lowercase": "θ", "position": 8},
    {"name": "Iota", "uppercase": "Ι", "lowercase": "ι", "position": 9},
    {"name": "Kappa", "uppercase": "Κ", "lowercase": "κ", "position": 10},
    {"name": "Lambda", "uppercase": "Λ", "lowercase": "λ", "position": 11},
    {"name": "Mu", "uppercase": "Μ", "lowercase": "μ", "position": 12},
    {"name": "Nu", "uppercase": "Ν", "lowercase": "ν", "position": 13},
    {"name": "Xi", "uppercase": "Ξ", "lowercase": "ξ", "position": 14},
    {"name": "Omicron", "uppercase": "Ο", "lowercase": "ο", "position": 15},
    {"name": "Pi", "uppercase": "Π", "lowercase": "π", "position": 16},
    {"name": "Rho", "uppercase": "Ρ", "lowercase": "ρ", "position": 17},
    {"name": "Sigma", "uppercase": "Σ", "lowercase": "σ", "position": 18},
    {"name": "Tau", "uppercase": "Τ", "lowercase": "τ", "position": 19},
    {"name": "Upsilon", "uppercase": "Υ", "lowercase": "υ", "position": 20},
    {"name": "Phi", "uppercase": "Φ", "lowercase": "φ", "position": 21},
    {"name": "Chi", "uppercase": "Χ", "lowercase": "χ", "position": 22},
    {"name": "Psi", "uppercase": "Ψ", "lowercase": "ψ", "position": 23},
    {"name": "Omega", "uppercase": "Ω", "lowercase": "ω", "position": 24},
]


def seed_letters(db: Session) -> None:
    """Seed the letters table with the Greek alphabet."""
    # Check if already seeded
    existing_count = db.query(Letter).count()
    if existing_count > 0:
        print(f"Letters table already contains {existing_count} entries. Skipping seed.")
        return

    print("Seeding Greek alphabet...")
    for letter_data in GREEK_ALPHABET:
        letter = Letter(**letter_data)
        db.add(letter)

    db.commit()
    print(f"Successfully seeded {len(GREEK_ALPHABET)} Greek letters.")


def check_column_exists(inspector, table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    try:
        columns = [col['name'] for col in inspector.get_columns(table_name)]
        return column_name in columns
    except Exception as e:
        logger.warning(f"Error checking column {column_name} in {table_name}: {e}")
        return False


def check_index_exists(inspector, table_name: str, index_name: str) -> bool:
    """Check if an index exists on a table."""
    try:
        indexes = inspector.get_indexes(table_name)
        return any(idx['name'] == index_name for idx in indexes)
    except Exception as e:
        logger.warning(f"Error checking index {index_name} in {table_name}: {e}")
        return False


def apply_schema_migrations(db: Session) -> None:
    """
    Apply schema migrations automatically on startup.

    This function detects and applies necessary schema changes:
    - Add missing columns to QuizQuestion (option_1, option_2, option_3, option_4)
    - Add indexes for query performance
    - Add unique constraints

    All operations are idempotent and safe for production.
    """
    inspector = inspect(engine)

    # Get list of existing tables
    existing_tables = inspector.get_table_names()

    if not existing_tables:
        logger.info("No existing tables found. Schema will be created from scratch.")
        return

    logger.info("Checking for necessary schema migrations...")
    migrations_applied = []

    # Migration 1: Add option columns to quiz_questions table
    if 'quiz_questions' in existing_tables:
        option_columns = ['option_1', 'option_2', 'option_3', 'option_4']

        for col in option_columns:
            if not check_column_exists(inspector, 'quiz_questions', col):
                try:
                    logger.info(f"Adding column {col} to quiz_questions table...")
                    db.execute(text(f"ALTER TABLE quiz_questions ADD COLUMN {col} TEXT"))
                    migrations_applied.append(f"Added column quiz_questions.{col}")
                except OperationalError as e:
                    # Column might already exist (race condition)
                    logger.warning(f"Could not add column {col}: {e}")

    # Migration 2: Add indexes to user_letter_stats
    if 'user_letter_stats' in existing_tables:
        indexes_to_add = [
            ('idx_user_mastery', 'CREATE INDEX IF NOT EXISTS idx_user_mastery ON user_letter_stats (user_id, mastery_score)'),
            ('idx_user_seen_count', 'CREATE INDEX IF NOT EXISTS idx_user_seen_count ON user_letter_stats (user_id, seen_count)')
        ]

        for idx_name, sql in indexes_to_add:
            if not check_index_exists(inspector, 'user_letter_stats', idx_name):
                try:
                    logger.info(f"Creating index {idx_name}...")
                    db.execute(text(sql))
                    migrations_applied.append(f"Created index {idx_name}")
                except OperationalError as e:
                    logger.warning(f"Could not create index {idx_name}: {e}")

    # Migration 3: Add indexes to quiz_attempts
    if 'quiz_attempts' in existing_tables:
        if not check_index_exists(inspector, 'quiz_attempts', 'idx_user_completed'):
            try:
                logger.info("Creating index idx_user_completed...")
                db.execute(text('CREATE INDEX IF NOT EXISTS idx_user_completed ON quiz_attempts (user_id, completed_at)'))
                migrations_applied.append("Created index idx_user_completed")
            except OperationalError as e:
                logger.warning(f"Could not create index idx_user_completed: {e}")

    # Migration 4: Add index to quiz_questions
    if 'quiz_questions' in existing_tables:
        if not check_index_exists(inspector, 'quiz_questions', 'idx_quiz_correct'):
            try:
                logger.info("Creating index idx_quiz_correct...")
                db.execute(text('CREATE INDEX IF NOT EXISTS idx_quiz_correct ON quiz_questions (quiz_id, is_correct)'))
                migrations_applied.append("Created index idx_quiz_correct")
            except OperationalError as e:
                logger.warning(f"Could not create index idx_quiz_correct: {e}")

    # Migration 5: Add difficulty progression columns to users table
    if 'users' in existing_tables:
        difficulty_columns = [
            ('current_level', 'INTEGER NOT NULL DEFAULT 1'),
            ('consecutive_perfect_streak', 'INTEGER NOT NULL DEFAULT 0'),
            ('level_up_count', 'INTEGER NOT NULL DEFAULT 0')
        ]

        for col_name, col_def in difficulty_columns:
            if not check_column_exists(inspector, 'users', col_name):
                try:
                    logger.info(f"Adding column {col_name} to users table...")
                    db.execute(text(f"ALTER TABLE users ADD COLUMN {col_name} {col_def}"))
                    migrations_applied.append(f"Added column users.{col_name}")
                except OperationalError as e:
                    logger.warning(f"Could not add column {col_name}: {e}")

    # Migration 6: Create level_progressions table
    if 'level_progressions' not in existing_tables:
        try:
            logger.info("Creating level_progressions table...")
            db.execute(text("""
                CREATE TABLE level_progressions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    from_level INTEGER NOT NULL,
                    to_level INTEGER NOT NULL,
                    achieved_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    perfect_streak_count INTEGER NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    CHECK (from_level >= 1 AND from_level <= 3),
                    CHECK (to_level >= 1 AND to_level <= 3),
                    CHECK (to_level = from_level + 1)
                )
            """))
            migrations_applied.append("Created table level_progressions")
        except OperationalError as e:
            logger.warning(f"Could not create table level_progressions: {e}")

    # Migration 7: Add index to level_progressions
    if 'level_progressions' in existing_tables or 'level_progressions' not in existing_tables:
        # Check again after potential creation
        if 'level_progressions' in inspector.get_table_names():
            if not check_index_exists(inspector, 'level_progressions', 'idx_level_progressions_user'):
                try:
                    logger.info("Creating index idx_level_progressions_user...")
                    db.execute(text('CREATE INDEX IF NOT EXISTS idx_level_progressions_user ON level_progressions (user_id, achieved_at DESC)'))
                    migrations_applied.append("Created index idx_level_progressions_user")
                except OperationalError as e:
                    logger.warning(f"Could not create index idx_level_progressions_user: {e}")

    # Commit all migrations
    if migrations_applied:
        try:
            db.commit()
            logger.info(f"Applied {len(migrations_applied)} schema migrations:")
            for migration in migrations_applied:
                logger.info(f"  - {migration}")
        except Exception as e:
            db.rollback()
            logger.error(f"Error committing migrations: {e}")
            raise
    else:
        logger.info("No schema migrations needed. Database is up to date.")


def init_db() -> None:
    """
    Initialize database: create tables, apply migrations, and seed data.

    This function:
    1. Creates all tables from SQLAlchemy models
    2. Applies any necessary schema migrations
    3. Seeds initial data (Greek alphabet)

    Safe to call multiple times - all operations are idempotent.
    """
    logger.info("Initializing database...")

    # Create all tables (idempotent - does nothing if tables exist)
    logger.info("Creating database tables from models...")
    Base.metadata.create_all(bind=engine)
    logger.info("Tables created/verified successfully.")

    db = SessionLocal()
    try:
        # Apply any pending schema migrations
        apply_schema_migrations(db)

        # Seed initial data
        seed_letters(db)

        logger.info("Database initialization complete.")
    except Exception as e:
        logger.error(f"Error during database initialization: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    # Set up basic logging for standalone execution
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    init_db()
    print("Database initialization complete.")
