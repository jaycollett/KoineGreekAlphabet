"""
Database migration: Add option columns, indexes, and constraints

This migration adds:
1. Four option columns to quiz_questions table to store multiple choice options
2. Unique constraint on quiz_questions (quiz_id, letter_id)
3. Indexes on user_letter_stats (user_id, mastery_score) and (user_id, seen_count)
4. Index on quiz_attempts (user_id, completed_at)
5. Index on quiz_questions (quiz_id, is_correct)

Run this migration by executing: python migrations/001_add_options_and_indexes.py
"""

import sqlite3
import sys
import os

# Get database path
DATABASE_PATH = os.getenv("DATABASE_URL", "sqlite:///./greek_alphabet_mastery.db")
if DATABASE_PATH.startswith("sqlite:///"):
    DATABASE_PATH = DATABASE_PATH.replace("sqlite:///", "")
    if DATABASE_PATH.startswith("./"):
        DATABASE_PATH = DATABASE_PATH[2:]


def migrate():
    """Apply the migration to the database."""
    print(f"Connecting to database: {DATABASE_PATH}")

    if not os.path.exists(DATABASE_PATH):
        print(f"ERROR: Database file not found at {DATABASE_PATH}")
        print("Please ensure the database exists before running migration.")
        sys.exit(1)

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    try:
        # Check if migration is already applied
        cursor.execute("PRAGMA table_info(quiz_questions)")
        columns = [col[1] for col in cursor.fetchall()]

        if 'option_1' in columns:
            print("Migration already applied. Skipping.")
            return

        print("Starting migration...")

        # Step 1: Add option columns to quiz_questions
        print("Adding option columns to quiz_questions...")
        cursor.execute("ALTER TABLE quiz_questions ADD COLUMN option_1 TEXT")
        cursor.execute("ALTER TABLE quiz_questions ADD COLUMN option_2 TEXT")
        cursor.execute("ALTER TABLE quiz_questions ADD COLUMN option_3 TEXT")
        cursor.execute("ALTER TABLE quiz_questions ADD COLUMN option_4 TEXT")

        # Step 2: Create indexes on user_letter_stats
        print("Creating indexes on user_letter_stats...")
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_user_mastery
            ON user_letter_stats(user_id, mastery_score)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_user_seen_count
            ON user_letter_stats(user_id, seen_count)
        """)

        # Step 3: Create index on quiz_attempts
        print("Creating index on quiz_attempts...")
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_user_completed
            ON quiz_attempts(user_id, completed_at)
        """)

        # Step 4: Create index on quiz_questions
        print("Creating index on quiz_questions...")
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_quiz_correct
            ON quiz_questions(quiz_id, is_correct)
        """)

        # Step 5: Add unique constraint to quiz_questions
        # SQLite doesn't support adding constraints to existing tables directly
        # We need to recreate the table with the constraint
        print("Adding unique constraint to quiz_questions...")

        # Check if constraint already exists
        cursor.execute("""
            SELECT sql FROM sqlite_master
            WHERE type='table' AND name='quiz_questions'
        """)
        table_sql = cursor.fetchone()[0]

        if 'uq_quiz_question' not in table_sql:
            print("Recreating quiz_questions table with unique constraint...")

            # Create new table with constraint
            cursor.execute("""
                CREATE TABLE quiz_questions_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    quiz_id INTEGER NOT NULL,
                    letter_id INTEGER NOT NULL,
                    question_type TEXT NOT NULL,
                    is_correct INTEGER NOT NULL DEFAULT 0,
                    chosen_option TEXT,
                    correct_option TEXT,
                    option_1 TEXT,
                    option_2 TEXT,
                    option_3 TEXT,
                    option_4 TEXT,
                    FOREIGN KEY (quiz_id) REFERENCES quiz_attempts(id),
                    FOREIGN KEY (letter_id) REFERENCES letters(id),
                    CONSTRAINT uq_quiz_question UNIQUE (quiz_id, letter_id)
                )
            """)

            # Copy data from old table
            cursor.execute("""
                INSERT INTO quiz_questions_new
                (id, quiz_id, letter_id, question_type, is_correct,
                 chosen_option, correct_option, option_1, option_2, option_3, option_4)
                SELECT id, quiz_id, letter_id, question_type, is_correct,
                       chosen_option, correct_option, option_1, option_2, option_3, option_4
                FROM quiz_questions
            """)

            # Drop old table
            cursor.execute("DROP TABLE quiz_questions")

            # Rename new table
            cursor.execute("ALTER TABLE quiz_questions_new RENAME TO quiz_questions")

            # Recreate index on new table
            cursor.execute("""
                CREATE INDEX idx_quiz_correct
                ON quiz_questions(quiz_id, is_correct)
            """)
        else:
            print("Unique constraint already exists.")

        # Commit changes
        conn.commit()
        print("Migration completed successfully!")

    except Exception as e:
        conn.rollback()
        print(f"ERROR during migration: {e}")
        sys.exit(1)
    finally:
        conn.close()


def rollback():
    """Rollback the migration (remove added columns and indexes)."""
    print(f"Rolling back migration on database: {DATABASE_PATH}")

    if not os.path.exists(DATABASE_PATH):
        print(f"ERROR: Database file not found at {DATABASE_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    try:
        print("Starting rollback...")

        # Drop indexes
        print("Dropping indexes...")
        cursor.execute("DROP INDEX IF EXISTS idx_user_mastery")
        cursor.execute("DROP INDEX IF EXISTS idx_user_seen_count")
        cursor.execute("DROP INDEX IF EXISTS idx_user_completed")
        cursor.execute("DROP INDEX IF EXISTS idx_quiz_correct")

        # SQLite doesn't support dropping columns or constraints directly
        # To remove option columns, we'd need to recreate the table
        print("Recreating quiz_questions table without new columns...")

        cursor.execute("""
            CREATE TABLE quiz_questions_rollback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                quiz_id INTEGER NOT NULL,
                letter_id INTEGER NOT NULL,
                question_type TEXT NOT NULL,
                is_correct INTEGER NOT NULL DEFAULT 0,
                chosen_option TEXT,
                correct_option TEXT,
                FOREIGN KEY (quiz_id) REFERENCES quiz_attempts(id),
                FOREIGN KEY (letter_id) REFERENCES letters(id)
            )
        """)

        cursor.execute("""
            INSERT INTO quiz_questions_rollback
            (id, quiz_id, letter_id, question_type, is_correct, chosen_option, correct_option)
            SELECT id, quiz_id, letter_id, question_type, is_correct, chosen_option, correct_option
            FROM quiz_questions
        """)

        cursor.execute("DROP TABLE quiz_questions")
        cursor.execute("ALTER TABLE quiz_questions_rollback RENAME TO quiz_questions")

        conn.commit()
        print("Rollback completed successfully!")

    except Exception as e:
        conn.rollback()
        print(f"ERROR during rollback: {e}")
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "rollback":
        rollback()
    else:
        migrate()
