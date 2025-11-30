# Deployment Checklist for Bug Fixes

## Pre-Deployment

- [ ] **Review Changes**
  - Read `/home/jay/SourceCode/KoineGreekAlphabet/FIXES_SUMMARY.md` for complete details
  - Understand what each fix addresses

- [ ] **Verify Implementation**
  ```bash
  python3 verify_fixes.py
  ```
  Expected: "19/19 checks passed"

- [ ] **Backup Database**
  ```bash
  cp greek_alphabet_mastery.db greek_alphabet_mastery.db.backup-$(date +%Y%m%d)
  ```

## Deployment Steps

### 1. Apply Database Migration

```bash
cd /home/jay/SourceCode/KoineGreekAlphabet
python3 migrations/001_add_options_and_indexes.py
```

Expected output:
```
Connecting to database: ...
Starting migration...
Adding option columns to quiz_questions...
Creating indexes on user_letter_stats...
Creating index on quiz_attempts...
Creating index on quiz_questions...
Adding unique constraint to quiz_questions...
Migration completed successfully!
```

### 2. Configure Environment (Production Only)

For production deployment, set these environment variables:

```bash
export COOKIE_SECURE=true
export ENVIRONMENT=production
export DATABASE_URL=sqlite:///data/greek_alphabet.db  # Or your DB path
```

For development, these defaults are used:
- `COOKIE_SECURE=false`
- `ENVIRONMENT=development`

### 3. Install Dependencies (if needed)

```bash
pip install -r requirements.txt
```

### 4. Run Tests (Optional but Recommended)

```bash
# Install test dependencies first
pip install pytest pytest-cov

# Run new test suite
pytest tests/test_fixes.py -v

# Run all tests
pytest tests/ -v

# With coverage report
pytest tests/test_fixes.py --cov=app --cov-report=html
```

### 5. Restart Application

**Using Docker:**
```bash
docker-compose down
docker-compose up -d --build
```

**Using uvicorn directly:**
```bash
# Stop current process
pkill -f uvicorn

# Start with new code
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

**Using systemd service:**
```bash
sudo systemctl restart greek-alphabet-mastery
```

## Post-Deployment Verification

### 1. Check Application Health

```bash
curl http://localhost:8000/health
```

Expected: `{"status":"healthy"}`

### 2. Test Quiz Functionality

Manual testing checklist:

- [ ] **Start a new quiz**
  - Visit `/quiz`
  - Quiz loads with 14 questions
  - Options display correctly

- [ ] **Answer questions**
  - Submit answers
  - Correct/incorrect feedback shows
  - Progress updates properly

- [ ] **Quiz state restoration**
  - Start a quiz
  - Refresh the page mid-quiz
  - Quiz resumes with same questions and options (critical fix)
  - Answer a resumed question successfully

- [ ] **Duplicate submission handling**
  - Try double-clicking answer button
  - Should not double-count (critical fix)

- [ ] **Audio questions (if enabled)**
  - Audio plays automatically
  - Can replay audio
  - No memory issues on multiple questions

- [ ] **Quiz completion**
  - Complete all 14 questions
  - Summary page shows correctly
  - Accuracy calculated properly

### 3. Check Database

```bash
sqlite3 greek_alphabet_mastery.db
```

Verify schema changes:
```sql
-- Check option columns exist
PRAGMA table_info(quiz_questions);
-- Should show option_1, option_2, option_3, option_4

-- Check indexes exist
.indexes
-- Should show: idx_user_mastery, idx_user_seen_count, idx_user_completed, idx_quiz_correct

-- Check unique constraint exists
SELECT sql FROM sqlite_master WHERE type='table' AND name='quiz_questions';
-- Should contain: CONSTRAINT uq_quiz_question UNIQUE (quiz_id, letter_id)

-- Exit
.quit
```

### 4. Browser Console Check

Open browser DevTools Console (F12) and:

- [ ] No JavaScript errors
- [ ] Audio objects are cleaned up (check in Memory profiler)
- [ ] Cookies are set with correct flags (check in Application tab)

### 5. Performance Check

Monitor query performance:

```sql
-- This query should be fast with new indexes
EXPLAIN QUERY PLAN
SELECT * FROM user_letter_stats
WHERE user_id = 'gam_xxx' AND mastery_score < 0.5
ORDER BY mastery_score;

-- Should show "SEARCH" with "USING INDEX idx_user_mastery"
```

## Rollback Procedure (If Needed)

If issues occur, rollback the migration:

```bash
# 1. Stop application
docker-compose down
# or: pkill -f uvicorn

# 2. Restore database backup
cp greek_alphabet_mastery.db.backup-YYYYMMDD greek_alphabet_mastery.db

# Or rollback migration
python3 migrations/001_add_options_and_indexes.py rollback

# 3. Revert code changes
git revert HEAD  # or git reset --hard <previous-commit>

# 4. Restart application
docker-compose up -d
```

## Monitoring

After deployment, monitor for:

- [ ] Application error logs
- [ ] Database performance metrics
- [ ] User session cookies set correctly
- [ ] Quiz completion rates
- [ ] Any duplicate submission errors (should be none)

## Known Issues & Limitations

1. **Existing incomplete quizzes:**
   - Old quizzes won't have saved options
   - Users should start fresh quizzes
   - Resume will still work but may regenerate options for old quizzes

2. **Browser compatibility:**
   - Audio cleanup requires modern browsers
   - IE11 not supported

3. **Cookie security:**
   - Requires HTTPS in production for secure flag
   - Works without HTTPS in development

## Support Contacts

If issues arise:
1. Check application logs
2. Review `/home/jay/SourceCode/KoineGreekAlphabet/FIXES_SUMMARY.md`
3. Run verification: `python3 verify_fixes.py`
4. Check test output: `pytest tests/test_fixes.py -v`

## Success Criteria

Deployment is successful when:

- ✅ Migration completes without errors
- ✅ Application starts and health check passes
- ✅ Users can start and complete quizzes
- ✅ Quiz state restoration works correctly
- ✅ No duplicate submission issues
- ✅ All tests pass
- ✅ No errors in application logs
- ✅ Performance is improved (queries use indexes)

---

**Last Updated:** 2025-11-29
**Version:** 1.1.0
**Status:** Ready for deployment
