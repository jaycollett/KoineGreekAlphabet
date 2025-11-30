# Database Migrations

This directory contains database migration scripts for the Greek Alphabet Mastery application.

## Running Migrations

### Apply Migration

To apply the migration to your database:

```bash
python migrations/001_add_options_and_indexes.py
```

The script will automatically detect your database location from the `DATABASE_URL` environment variable, or use the default SQLite database path.

### Rollback Migration

To rollback the migration:

```bash
python migrations/001_add_options_and_indexes.py rollback
```

**Warning:** Rollback will remove the option columns from quiz_questions, which means any saved quiz options will be lost.

## Migration 001: Add Options and Indexes

**File:** `001_add_options_and_indexes.py`

**Changes:**
1. Adds `option_1`, `option_2`, `option_3`, `option_4` columns to `quiz_questions` table
2. Adds unique constraint on `quiz_questions(quiz_id, letter_id)` to prevent duplicate questions
3. Adds index on `user_letter_stats(user_id, mastery_score)` for performance
4. Adds index on `user_letter_stats(user_id, seen_count)` for performance
5. Adds index on `quiz_attempts(user_id, completed_at)` for performance
6. Adds index on `quiz_questions(quiz_id, is_correct)` for performance

**Purpose:**
- Fixes quiz state restoration bug by storing options in database
- Prevents race conditions with unique constraint
- Improves query performance with indexes

**Safety:**
- The migration checks if it has already been applied
- All changes are wrapped in a transaction
- Rollback functionality is provided

## Best Practices

1. **Backup your database** before running migrations
2. Run migrations in a test environment first
3. Check the migration output for any errors
4. Test your application after applying migrations

## Future Migrations

When creating new migrations:
1. Use sequential numbering (002, 003, etc.)
2. Include descriptive names in the filename
3. Add rollback functionality
4. Test thoroughly before applying to production
5. Document all changes in this README
