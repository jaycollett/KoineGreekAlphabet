-- ============================================================================
-- Difficulty Progression: Common SQL Queries
-- ============================================================================
-- Quick reference for common operations on difficulty progression schema.
-- See difficulty_progression_schema.md for detailed explanations.

-- ============================================================================
-- 1. CHECK USER'S CURRENT LEVEL AND STREAK
-- ============================================================================
-- Get user's current progression state
SELECT
    current_level,
    consecutive_perfect_streak,
    level_up_count,
    CASE
        WHEN current_level < 3 AND consecutive_perfect_streak >= 10 THEN 'YES'
        ELSE 'NO'
    END as can_level_up,
    CASE
        WHEN current_level < 3 THEN 10 - consecutive_perfect_streak
        ELSE NULL
    END as quizzes_until_next_level
FROM users
WHERE id = ?;


-- ============================================================================
-- 2. UPDATE STREAK AFTER QUIZ COMPLETION
-- ============================================================================
-- If quiz was perfect (14/14):
UPDATE users
SET consecutive_perfect_streak = consecutive_perfect_streak + 1,
    last_active_at = CURRENT_TIMESTAMP
WHERE id = ?;

-- If quiz was not perfect:
UPDATE users
SET consecutive_perfect_streak = 0,
    last_active_at = CURRENT_TIMESTAMP
WHERE id = ?;


-- ============================================================================
-- 3. LEVEL UP USER (Use Transaction)
-- ============================================================================
-- IMPORTANT: This must be executed as a transaction (all-or-nothing)

BEGIN TRANSACTION;

-- Insert progression record
INSERT INTO level_progressions (user_id, from_level, to_level, perfect_streak_count)
SELECT id, current_level, current_level + 1, consecutive_perfect_streak
FROM users
WHERE id = ?
  AND current_level < 3
  AND consecutive_perfect_streak >= 10;

-- Update user to next level
UPDATE users
SET current_level = current_level + 1,
    consecutive_perfect_streak = 0,
    level_up_count = level_up_count + 1
WHERE id = ?
  AND current_level < 3
  AND consecutive_perfect_streak >= 10;

COMMIT;


-- ============================================================================
-- 4. GET USER'S PROGRESSION HISTORY
-- ============================================================================
-- Get all level-ups for a user (most recent first)
SELECT
    from_level,
    to_level,
    achieved_at,
    perfect_streak_count
FROM level_progressions
WHERE user_id = ?
ORDER BY achieved_at DESC;


-- ============================================================================
-- 5. ANALYTICS: LEVEL DISTRIBUTION
-- ============================================================================
-- Count how many users are at each level
SELECT
    current_level,
    COUNT(*) as user_count,
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM users), 2) as percentage
FROM users
GROUP BY current_level
ORDER BY current_level;


-- ============================================================================
-- 6. ANALYTICS: USERS CLOSE TO LEVEL-UP (Leaderboard)
-- ============================================================================
-- Find users with 5+ consecutive perfect scores (close to leveling up)
SELECT
    id,
    current_level,
    consecutive_perfect_streak,
    10 - consecutive_perfect_streak as quizzes_remaining,
    last_active_at
FROM users
WHERE current_level < 3
  AND consecutive_perfect_streak >= 5
ORDER BY consecutive_perfect_streak DESC, current_level DESC
LIMIT 10;


-- ============================================================================
-- 7. ANALYTICS: AVERAGE TIME TO REACH EACH LEVEL
-- ============================================================================
-- Calculate average days from user creation to reaching level 2
SELECT
    'Level 2' as achievement,
    ROUND(AVG(JULIANDAY(lp.achieved_at) - JULIANDAY(u.created_at)), 1) as avg_days,
    COUNT(*) as user_count
FROM level_progressions lp
JOIN users u ON lp.user_id = u.id
WHERE lp.to_level = 2;

-- Calculate average days from user creation to reaching level 3
SELECT
    'Level 3' as achievement,
    ROUND(AVG(JULIANDAY(lp.achieved_at) - JULIANDAY(u.created_at)), 1) as avg_days,
    COUNT(*) as user_count
FROM level_progressions lp
JOIN users u ON lp.user_id = u.id
WHERE lp.to_level = 3;


-- ============================================================================
-- 8. ANALYTICS: TIME BETWEEN LEVEL-UPS
-- ============================================================================
-- Average time from level 1 to level 2, then level 2 to level 3
WITH level_times AS (
    SELECT
        user_id,
        from_level,
        to_level,
        achieved_at,
        LAG(achieved_at) OVER (PARTITION BY user_id ORDER BY achieved_at) as prev_achieved_at
    FROM level_progressions
)
SELECT
    from_level,
    to_level,
    COUNT(*) as progression_count,
    ROUND(AVG(JULIANDAY(achieved_at) - JULIANDAY(prev_achieved_at)), 1) as avg_days_between_levels
FROM level_times
WHERE prev_achieved_at IS NOT NULL
GROUP BY from_level, to_level;


-- ============================================================================
-- 9. ANALYTICS: QUIZ PERFORMANCE BY LEVEL
-- ============================================================================
-- Average accuracy for quizzes taken at each level
-- This is a complex query that joins progression history with quiz attempts

WITH user_level_periods AS (
    -- For each user, determine when they were at each level
    SELECT
        u.id as user_id,
        1 as level,
        u.created_at as level_start,
        COALESCE(
            (SELECT achieved_at FROM level_progressions WHERE user_id = u.id AND to_level = 2),
            datetime('now')
        ) as level_end
    FROM users u

    UNION ALL

    SELECT
        u.id as user_id,
        2 as level,
        lp2.achieved_at as level_start,
        COALESCE(
            (SELECT achieved_at FROM level_progressions WHERE user_id = u.id AND to_level = 3),
            datetime('now')
        ) as level_end
    FROM users u
    JOIN level_progressions lp2 ON u.id = lp2.user_id AND lp2.to_level = 2

    UNION ALL

    SELECT
        u.id as user_id,
        3 as level,
        lp3.achieved_at as level_start,
        datetime('now') as level_end
    FROM users u
    JOIN level_progressions lp3 ON u.id = lp3.user_id AND lp3.to_level = 3
)
SELECT
    ulp.level,
    COUNT(DISTINCT qa.id) as total_quizzes,
    ROUND(AVG(qa.accuracy), 3) as avg_accuracy,
    SUM(CASE WHEN qa.accuracy = 1.0 THEN 1 ELSE 0 END) as perfect_quizzes,
    ROUND(
        SUM(CASE WHEN qa.accuracy = 1.0 THEN 1 ELSE 0 END) * 100.0 / COUNT(qa.id),
        2
    ) as perfect_rate_pct
FROM user_level_periods ulp
JOIN quiz_attempts qa
    ON qa.user_id = ulp.user_id
    AND qa.completed_at >= ulp.level_start
    AND qa.completed_at < ulp.level_end
GROUP BY ulp.level
ORDER BY ulp.level;


-- ============================================================================
-- 10. BOOTSTRAP DATA FOR FRONTEND
-- ============================================================================
-- Get all user progression data needed for UI rendering
SELECT
    u.id,
    u.current_level,
    u.consecutive_perfect_streak,
    u.level_up_count,
    CASE
        WHEN u.current_level < 3 AND u.consecutive_perfect_streak >= 10 THEN 1
        ELSE 0
    END as can_level_up,
    CASE
        WHEN u.current_level < 3 THEN 10 - u.consecutive_perfect_streak
        ELSE NULL
    END as quizzes_until_next_level,
    (SELECT COUNT(*) FROM level_progressions WHERE user_id = u.id) as total_progressions,
    (SELECT MAX(achieved_at) FROM level_progressions WHERE user_id = u.id) as last_level_up_at
FROM users u
WHERE u.id = ?;


-- ============================================================================
-- 11. TESTING QUERIES
-- ============================================================================

-- Verify migration applied correctly
PRAGMA table_info(users);
-- Should include: current_level, consecutive_perfect_streak, level_up_count

-- Verify table created
SELECT name FROM sqlite_master WHERE type='table' AND name='level_progressions';

-- Verify indexes created
SELECT name FROM sqlite_master
WHERE type='index'
  AND name IN ('idx_users_level', 'idx_level_progressions_user');

-- Test CHECK constraint (should FAIL)
INSERT INTO users (id, current_level) VALUES ('test-fail', 5);

-- Test CHECK constraint (should SUCCEED)
INSERT INTO users (id, current_level) VALUES ('test-success', 2);

-- Clean up test data
DELETE FROM users WHERE id LIKE 'test-%';


-- ============================================================================
-- 12. DATA CLEANUP / MAINTENANCE
-- ============================================================================

-- Find users with inconsistent state (for debugging)
SELECT
    id,
    current_level,
    level_up_count,
    (SELECT COUNT(*) FROM level_progressions WHERE user_id = users.id) as actual_progressions
FROM users
WHERE level_up_count != (SELECT COUNT(*) FROM level_progressions WHERE user_id = users.id);

-- Fix inconsistent level_up_count (if needed)
UPDATE users
SET level_up_count = (
    SELECT COUNT(*) FROM level_progressions WHERE user_id = users.id
)
WHERE level_up_count != (SELECT COUNT(*) FROM level_progressions WHERE user_id = users.id);

-- Find users at level 3 with streak > 0 (should be reset, but just in case)
SELECT id, current_level, consecutive_perfect_streak
FROM users
WHERE current_level = 3 AND consecutive_perfect_streak > 0;


-- ============================================================================
-- 13. ROLLBACK CHECKS (After Rollback)
-- ============================================================================

-- Verify table dropped
SELECT name FROM sqlite_master WHERE type='table' AND name='level_progressions';
-- Should return nothing

-- Verify columns removed
PRAGMA table_info(users);
-- Should NOT include: current_level, consecutive_perfect_streak, level_up_count

-- Verify indexes dropped
SELECT name FROM sqlite_master WHERE type='index' AND name='idx_users_level';
-- Should return nothing
