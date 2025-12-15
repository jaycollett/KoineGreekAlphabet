"""
Database migration: Add difficulty progression tracking

This migration adds support for 3-level difficulty progression:
1. Adds columns to users table: current_level, consecutive_perfect_streak, level_up_count
2. Creates level_progressions table for historical audit trail
3. Adds indexes for efficient queries
4. Adds CHECK constraints to enforce valid level values (1-3)

Users progress to the next level after 10 consecutive perfect scores (14/14).

Run this migration by executing: python migrations/002_add_difficulty_progression.py
"""

import sqlite3
import sys
import os
from datetime import datetime

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
        cursor.execute("PRAGMA table_info(users)")
        columns = [col[1] for col in cursor.fetchall()]

        if 'current_level' in columns:
            print("Migration already applied. Skipping.")
            return

        print("Starting migration...")

        # Step 1: Add difficulty progression columns to users table
        print("Adding difficulty progression columns to users table...")

        cursor.execute("""
            ALTER TABLE users
            ADD COLUMN current_level INTEGER NOT NULL DEFAULT 1
        """)

        cursor.execute("""
            ALTER TABLE users
            ADD COLUMN consecutive_perfect_streak INTEGER NOT NULL DEFAULT 0
        """)

        cursor.execute("""
            ALTER TABLE users
            ADD COLUMN level_up_count INTEGER NOT NULL DEFAULT 0
        """)

        # Step 2: Create level_progressions table for historical tracking
        print("Creating level_progressions table...")

        cursor.execute("""
            CREATE TABLE level_progressions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                from_level INTEGER NOT NULL,
                to_level INTEGER NOT NULL,
                achieved_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                perfect_streak_count INTEGER NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                CHECK (from_level >= 1 AND from_level <= 3),
                CHECK (to_level >= 1 AND to_level <= 3),
                CHECK (to_level = from_level + 1)
            )
        """)

        # Step 3: Create indexes for efficient queries
        print("Creating indexes...")

        # Index for finding user's progression history
        cursor.execute("""
            CREATE INDEX idx_level_progressions_user
            ON level_progressions(user_id, achieved_at DESC)
        """)

        # Index for analytics queries (how many users at each level)
        cursor.execute("""
            CREATE INDEX idx_users_level
            ON users(current_level)
        """)

        # Step 4: Add CHECK constraint to users.current_level
        # SQLite requires table recreation to add CHECK constraints
        print("Recreating users table with CHECK constraint...")

        cursor.execute("""
            SELECT sql FROM sqlite_master
            WHERE type='table' AND name='users'
        """)
        table_sql = cursor.fetchone()[0]

        # Only recreate if CHECK constraint not already present
        if 'CHECK (current_level >= 1 AND current_level <= 3)' not in table_sql:
            cursor.execute("""
                CREATE TABLE users_new (
                    id TEXT PRIMARY KEY,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    last_active_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    current_level INTEGER NOT NULL DEFAULT 1,
                    consecutive_perfect_streak INTEGER NOT NULL DEFAULT 0,
                    level_up_count INTEGER NOT NULL DEFAULT 0,
                    CHECK (current_level >= 1 AND current_level <= 3),
                    CHECK (consecutive_perfect_streak >= 0),
                    CHECK (level_up_count >= 0)
                )
            """)

            # Copy data from old table
            cursor.execute("""
                INSERT INTO users_new
                (id, created_at, last_active_at, current_level,
                 consecutive_perfect_streak, level_up_count)
                SELECT id, created_at, last_active_at, current_level,
                       consecutive_perfect_streak, level_up_count
                FROM users
            """)

            # Drop old table
            cursor.execute("DROP TABLE users")

            # Rename new table
            cursor.execute("ALTER TABLE users_new RENAME TO users")

            # Recreate index on users.current_level
            cursor.execute("""
                CREATE INDEX idx_users_level
                ON users(current_level)
            """)
        else:
            print("CHECK constraint already exists on users table.")

        # Commit changes
        conn.commit()
        print("Migration completed successfully!")
        print("\nSummary:")
        print("- Added current_level, consecutive_perfect_streak, level_up_count to users table")
        print("- Created level_progressions table for historical tracking")
        print("- Added indexes for efficient queries")
        print("- Added CHECK constraints to enforce valid level values (1-3)")

    except Exception as e:
        conn.rollback()
        print(f"ERROR during migration: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        conn.close()


def rollback():
    """Rollback the migration (remove added columns and table)."""
    print(f"Rolling back migration on database: {DATABASE_PATH}")

    if not os.path.exists(DATABASE_PATH):
        print(f"ERROR: Database file not found at {DATABASE_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    try:
        print("Starting rollback...")

        # Step 1: Drop level_progressions table
        print("Dropping level_progressions table...")
        cursor.execute("DROP TABLE IF EXISTS level_progressions")

        # Step 2: Drop indexes
        print("Dropping indexes...")
        cursor.execute("DROP INDEX IF EXISTS idx_level_progressions_user")
        cursor.execute("DROP INDEX IF EXISTS idx_users_level")

        # Step 3: Recreate users table without new columns
        print("Recreating users table without difficulty progression columns...")

        cursor.execute("""
            CREATE TABLE users_rollback (
                id TEXT PRIMARY KEY,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                last_active_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            INSERT INTO users_rollback (id, created_at, last_active_at)
            SELECT id, created_at, last_active_at
            FROM users
        """)

        cursor.execute("DROP TABLE users")
        cursor.execute("ALTER TABLE users_rollback RENAME TO users")

        conn.commit()
        print("Rollback completed successfully!")

    except Exception as e:
        conn.rollback()
        print(f"ERROR during rollback: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "rollback":
        rollback()
    else:
        migrate()
