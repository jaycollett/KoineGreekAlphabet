# Difficulty Progression Schema Design

## Overview

This schema design adds 3-level difficulty progression tracking to the Greek Alphabet quiz application. Users advance to the next level after achieving 10 consecutive perfect scores (14/14 correct answers).

## Schema Changes

### 1. Users Table Additions

Three new columns track the user's current progression state:

```sql
ALTER TABLE users ADD COLUMN current_level INTEGER NOT NULL DEFAULT 1;
ALTER TABLE users ADD COLUMN consecutive_perfect_streak INTEGER NOT NULL DEFAULT 0;
ALTER TABLE users ADD COLUMN level_up_count INTEGER NOT NULL DEFAULT 0;
```

**Column Descriptions:**

- `current_level` (1-3): User's current difficulty level. All users start at level 1.
- `consecutive_perfect_streak`: Count of consecutive quizzes with 14/14 correct. Resets to 0 on any non-perfect quiz.
- `level_up_count`: Total number of times user has leveled up (0-2). Useful for analytics.

**Constraints:**

```sql
CHECK (current_level >= 1 AND current_level <= 3)
CHECK (consecutive_perfect_streak >= 0)
CHECK (level_up_count >= 0)
```

### 2. New Table: level_progressions

Historical audit trail of all level-up events:

```sql
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
);
```

**Column Descriptions:**

- `from_level`: Level user was at before progression
- `to_level`: Level user advanced to (always from_level + 1)
- `achieved_at`: Timestamp when level-up occurred
- `perfect_streak_count`: Number of perfect quizzes that triggered level-up (should be 10)

### 3. Indexes

```sql
-- Analytics: how many users at each level
CREATE INDEX idx_users_level ON users(current_level);

-- User progression history (most recent first)
CREATE INDEX idx_level_progressions_user ON level_progressions(user_id, achieved_at DESC);
```

## Design Decisions

### 1. Denormalized State in Users Table

**Decision:** Store `current_level` and `consecutive_perfect_streak` directly in users table.

**Rationale:**
- These values are queried on every quiz attempt (to determine difficulty and check for level-up)
- Denormalizing avoids expensive JOINs or aggregation queries
- Values are single source of truth and updated atomically with quiz completion
- Small footprint (3 integers per user)

**Trade-off:** Slightly more complex update logic, but much faster reads (99% of operations).

### 2. Separate level_progressions Table for History

**Decision:** Create dedicated table instead of adding timestamp columns to users.

**Rationale:**
- Supports unlimited future level expansion (not just 3 levels)
- Clean audit trail for analytics (e.g., "how long does it take users to reach level 2?")
- Doesn't bloat users table with rarely-accessed data
- Can be queried independently for leaderboards or achievements

**Trade-off:** Extra table and JOIN for historical queries, but these are infrequent.

### 3. No Per-Level Statistics

**Decision:** Do NOT track separate mastery/accuracy per level (for now).

**Rationale:**
- Can be derived on-demand by filtering `quiz_attempts` based on `level_progressions` date ranges
- Avoids premature optimization and complex denormalization
- Keeps schema simple for v1 release
- Easy to add later if analytics require it (via migration)

**Derivation Example:**
```sql
-- Get all quiz attempts for user at level 2
SELECT qa.*
FROM quiz_attempts qa
LEFT JOIN level_progressions lp_start
  ON qa.user_id = lp_start.user_id
  AND lp_start.to_level = 2
LEFT JOIN level_progressions lp_end
  ON qa.user_id = lp_end.user_id
  AND lp_end.to_level = 3
WHERE qa.user_id = ?
  AND qa.completed_at >= lp_start.achieved_at
  AND (lp_end.achieved_at IS NULL OR qa.completed_at < lp_end.achieved_at);
```

### 4. CHECK Constraints for Data Integrity

**Decision:** Use CHECK constraints on all level-related columns.

**Rationale:**
- Prevents invalid states (e.g., level 0, level 5, negative streaks)
- Enforces business rule that levels only increment by 1
- SQLite enforces these at database level (defense in depth)
- Self-documenting schema

**Trade-off:** Requires table recreation in SQLite (no ALTER TABLE ADD CONSTRAINT), but migration handles this safely.

### 5. Cascade Deletion

**Decision:** Use `ON DELETE CASCADE` for `level_progressions.user_id` foreign key.

**Rationale:**
- If user is deleted (GDPR compliance, data cleanup), their progression history should also be deleted
- Maintains referential integrity automatically
- Prevents orphaned records

### 6. Index Strategy

**Indexes Added:**
- `idx_users_level`: Supports analytics queries ("how many users at level 3?")
- `idx_level_progressions_user`: Supports user history queries with date filtering

**Indexes NOT Added:**
- No index on `users.consecutive_perfect_streak`: Only used in WHERE with user_id (already indexed by PK)
- No index on `level_progressions.achieved_at` alone: Always queried with user_id (covered by composite index)

**Rationale:** Balance query performance with write overhead and storage. Each index adds cost to INSERT/UPDATE operations.

## Sample Queries

### 1. Check User's Current Level

```sql
SELECT current_level, consecutive_perfect_streak
FROM users
WHERE id = ?;
```

**Performance:** Primary key lookup, instant.

### 2. Update Streak After Quiz Completion

**Case A: Perfect Score (14/14)**

```sql
UPDATE users
SET consecutive_perfect_streak = consecutive_perfect_streak + 1,
    last_active_at = CURRENT_TIMESTAMP
WHERE id = ?;
```

**Case B: Non-Perfect Score**

```sql
UPDATE users
SET consecutive_perfect_streak = 0,
    last_active_at = CURRENT_TIMESTAMP
WHERE id = ?;
```

**Performance:** Primary key update, instant.

### 3. Level Up User (Transaction Required)

```sql
BEGIN TRANSACTION;

-- Step 1: Get current state
SELECT current_level, consecutive_perfect_streak
FROM users
WHERE id = ?;

-- Step 2: Insert progression record
INSERT INTO level_progressions (user_id, from_level, to_level, perfect_streak_count)
VALUES (?, current_level, current_level + 1, 10);

-- Step 3: Update user to next level
UPDATE users
SET current_level = current_level + 1,
    consecutive_perfect_streak = 0,
    level_up_count = level_up_count + 1
WHERE id = ?;

COMMIT;
```

**Rationale:**
- Transaction ensures atomicity (all-or-nothing)
- Reset streak to 0 after level-up (start fresh for next level)
- Record historical event with exact streak count (should be 10)

**Rollback Strategy:** If transaction fails, nothing changes. Safe to retry.

### 4. Get User's Progression History

```sql
SELECT from_level, to_level, achieved_at, perfect_streak_count
FROM level_progressions
WHERE user_id = ?
ORDER BY achieved_at DESC;
```

**Performance:** Uses `idx_level_progressions_user` index. Fast even with thousands of records.

### 5. Analytics: Level Distribution

```sql
SELECT current_level, COUNT(*) as user_count
FROM users
GROUP BY current_level
ORDER BY current_level;
```

**Performance:** Full table scan with grouping. Uses `idx_users_level` for optimization.

**Expected Output:**
```
current_level | user_count
--------------|-----------
1             | 8520
2             | 2103
3             | 377
```

### 6. Analytics: Time to Level 2

```sql
SELECT
    AVG(JULIANDAY(lp.achieved_at) - JULIANDAY(u.created_at)) as avg_days_to_level_2
FROM level_progressions lp
JOIN users u ON lp.user_id = u.id
WHERE lp.to_level = 2;
```

**Performance:** Full scan of level_progressions (acceptable for analytics).

### 7. Check If User Can Level Up

```sql
SELECT
    current_level,
    consecutive_perfect_streak,
    CASE
        WHEN current_level < 3 AND consecutive_perfect_streak >= 10 THEN 1
        ELSE 0
    END as can_level_up
FROM users
WHERE id = ?;
```

**Business Logic:**
- Can level up if: `current_level < 3` AND `consecutive_perfect_streak >= 10`
- Level 3 is max (no level 4)

### 8. Get Users Close to Level-Up (Leaderboard)

```sql
SELECT
    id,
    current_level,
    consecutive_perfect_streak,
    10 - consecutive_perfect_streak as quizzes_remaining
FROM users
WHERE current_level < 3
  AND consecutive_perfect_streak >= 5
ORDER BY consecutive_perfect_streak DESC, current_level DESC
LIMIT 10;
```

**Use Case:** Show users who are close to leveling up (5+ streak).

## Migration Safety

### Pre-Migration Backup

```bash
# Always backup database before migration
cp greek_alphabet_mastery.db greek_alphabet_mastery.db.backup
```

### Running Migration

```bash
python migrations/002_add_difficulty_progression.py
```

### Rollback (If Needed)

```bash
python migrations/002_add_difficulty_progression.py rollback
```

**Rollback Effects:**
- Drops `level_progressions` table (historical data LOST)
- Removes difficulty columns from users table
- Drops indexes

**IMPORTANT:** Rollback is destructive. Progression data cannot be recovered after rollback.

## Testing the Migration

### Test 1: Verify Columns Added

```sql
PRAGMA table_info(users);
-- Should show: current_level, consecutive_perfect_streak, level_up_count
```

### Test 2: Verify Table Created

```sql
SELECT name FROM sqlite_master WHERE type='table' AND name='level_progressions';
-- Should return: level_progressions
```

### Test 3: Verify Indexes Created

```sql
SELECT name FROM sqlite_master WHERE type='index' AND name IN ('idx_users_level', 'idx_level_progressions_user');
-- Should return both index names
```

### Test 4: Verify Constraints Enforced

```sql
-- Should FAIL (level too high)
INSERT INTO users (id, current_level) VALUES ('test-user', 5);

-- Should FAIL (level too low)
INSERT INTO users (id, current_level) VALUES ('test-user', 0);

-- Should SUCCEED
INSERT INTO users (id, current_level) VALUES ('test-user', 2);
```

### Test 5: Verify CASCADE Deletion

```sql
-- Create test user with progression
INSERT INTO users (id) VALUES ('test-cascade');
INSERT INTO level_progressions (user_id, from_level, to_level, perfect_streak_count)
VALUES ('test-cascade', 1, 2, 10);

-- Delete user
DELETE FROM users WHERE id = 'test-cascade';

-- Verify progression also deleted
SELECT COUNT(*) FROM level_progressions WHERE user_id = 'test-cascade';
-- Should return: 0
```

## Python Integration Examples

### Example 1: Update Streak After Quiz

```python
from app.db.database import get_db
from app.db.models import User, QuizAttempt

def update_streak_after_quiz(user_id: str, quiz_id: int, db: Session):
    """Update user's perfect streak based on quiz result."""
    quiz = db.query(QuizAttempt).filter(QuizAttempt.id == quiz_id).first()
    user = db.query(User).filter(User.id == user_id).first()

    is_perfect = (quiz.correct_count == quiz.question_count)

    if is_perfect:
        user.consecutive_perfect_streak += 1
    else:
        user.consecutive_perfect_streak = 0

    db.commit()
    return user.consecutive_perfect_streak
```

### Example 2: Check and Perform Level-Up

```python
from app.db.models import User, LevelProgression

def check_and_level_up(user_id: str, db: Session) -> bool:
    """Check if user should level up and perform level-up if eligible.

    Returns:
        True if level-up occurred, False otherwise.
    """
    user = db.query(User).filter(User.id == user_id).first()

    # Check if eligible for level-up
    if user.current_level >= 3:
        return False  # Already at max level

    if user.consecutive_perfect_streak < 10:
        return False  # Not enough consecutive perfect scores

    # Perform level-up
    progression = LevelProgression(
        user_id=user.id,
        from_level=user.current_level,
        to_level=user.current_level + 1,
        perfect_streak_count=user.consecutive_perfect_streak
    )
    db.add(progression)

    user.current_level += 1
    user.consecutive_perfect_streak = 0  # Reset for next level
    user.level_up_count += 1

    db.commit()
    return True
```

### Example 3: Get User Progression History

```python
from app.db.models import LevelProgression
from typing import List
from datetime import datetime

def get_user_progression_history(user_id: str, db: Session) -> List[dict]:
    """Get chronological list of user's level-ups."""
    progressions = db.query(LevelProgression)\
        .filter(LevelProgression.user_id == user_id)\
        .order_by(LevelProgression.achieved_at.desc())\
        .all()

    return [
        {
            "from_level": p.from_level,
            "to_level": p.to_level,
            "achieved_at": p.achieved_at.isoformat(),
            "perfect_streak_count": p.perfect_streak_count
        }
        for p in progressions
    ]
```

### Example 4: Bootstrap API Response

```python
def get_bootstrap_data(user_id: str, db: Session) -> dict:
    """Get user data for frontend bootstrap."""
    user = db.query(User).filter(User.id == user_id).first()

    return {
        "user_id": user.id,
        "current_level": user.current_level,
        "consecutive_perfect_streak": user.consecutive_perfect_streak,
        "level_up_count": user.level_up_count,
        "can_level_up": (
            user.current_level < 3 and
            user.consecutive_perfect_streak >= 10
        ),
        "quizzes_until_level_up": max(
            0, 10 - user.consecutive_perfect_streak
        ) if user.current_level < 3 else None
    }
```

## Future Enhancements (Not in Scope)

### Option 1: Per-Level Mastery Tracking

Add columns to `user_letter_stats`:
```sql
ALTER TABLE user_letter_stats ADD COLUMN level_1_correct INTEGER DEFAULT 0;
ALTER TABLE user_letter_stats ADD COLUMN level_1_attempts INTEGER DEFAULT 0;
-- Repeat for level_2, level_3
```

**Trade-off:** Increases complexity and storage, but enables richer analytics.

### Option 2: Difficulty Modifiers Per Level

Store difficulty settings in dedicated table:
```sql
CREATE TABLE level_settings (
    level INTEGER PRIMARY KEY,
    question_count INTEGER NOT NULL,
    time_limit_seconds INTEGER,
    adaptive_threshold INTEGER
);
```

**Use Case:** Make level 2 have 20 questions, level 3 have 30 questions, etc.

### Option 3: Achievement System

Track milestones beyond just levels:
```sql
CREATE TABLE achievements (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    level_requirement INTEGER,
    streak_requirement INTEGER
);

CREATE TABLE user_achievements (
    user_id TEXT,
    achievement_id INTEGER,
    earned_at TIMESTAMP,
    PRIMARY KEY (user_id, achievement_id)
);
```

## Summary

This schema design provides:

1. **Minimal, focused additions**: 3 columns + 1 table
2. **Strong data integrity**: CHECK constraints enforce business rules
3. **Efficient queries**: Strategic indexes support common operations
4. **Historical audit trail**: level_progressions table tracks all transitions
5. **Safe migration**: Idempotent script with rollback support
6. **Future-proof**: Easy to extend for more levels or features

All operations are efficient for SQLite and follow best practices for local data workflows.
