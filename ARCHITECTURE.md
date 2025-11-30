# Greek Alphabet Mastery - Architecture Documentation

## Overview

Greek Alphabet Mastery is a mobile-first web application that uses adaptive learning algorithms to help users master the Greek alphabet through spaced repetition and personalized question selection.

**Version:** 1.4.2
**Stack:** Python, FastAPI, SQLAlchemy, SQLite, Jinja2, Vanilla JavaScript

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                       Client Layer                           │
│  ┌────────────┐  ┌────────────┐  ┌──────────────────┐      │
│  │ index.html │  │ quiz.html  │  │ summary.html     │      │
│  └────────────┘  └────────────┘  └──────────────────┘      │
│         │               │                  │                 │
│         └───────────────┴──────────────────┘                 │
│                         │                                    │
│                    JavaScript                                │
│              (quiz.js, progress bars)                        │
└─────────────────────────┬───────────────────────────────────┘
                          │ HTTP/REST
                          │
┌─────────────────────────▼───────────────────────────────────┐
│                    FastAPI Application                       │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  main.py (Application Entry Point)                   │   │
│  │  - Rate Limiting (slowapi)                           │   │
│  │  - CSRF Protection (production)                      │   │
│  │  - Logging Configuration                             │   │
│  └────┬─────────────────────────────────────────────────┘   │
│       │                                                      │
│  ┌────▼────────────────┐      ┌─────────────────────┐       │
│  │   Routers           │      │   Services          │       │
│  │  ┌──────────────┐   │      │  ┌──────────────┐   │       │
│  │  │ user.py      │   │◄────►│  │ adaptive.py  │   │       │
│  │  ├──────────────┤   │      │  ├──────────────┤   │       │
│  │  │ quiz.py      │   │◄────►│  │ mastery.py   │   │       │
│  │  └──────────────┘   │      │  ├──────────────┤   │       │
│  │                     │      │  │quiz_generator│   │       │
│  │                     │      │  └──────────────┘   │       │
│  └──────────┬──────────┘      └─────────────────────┘       │
│             │                                                │
│  ┌──────────▼──────────────────────────────────────────┐    │
│  │  Database Layer (SQLAlchemy)                        │    │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────────────┐  │    │
│  │  │ models.py│  │ database │  │ init_db.py       │  │    │
│  │  │          │  │  .py     │  │ (auto-migration) │  │    │
│  │  └──────────┘  └──────────┘  └──────────────────┘  │    │
│  └──────────────────────┬───────────────────────────────┘    │
└─────────────────────────┼─────────────────────────────────── │
                          │
                   ┌──────▼──────┐
                   │   SQLite    │
                   │   Database  │
                   └─────────────┘
```

---

## Core Components

### 1. Data Models (`app/db/models.py`)

#### User
- **Purpose:** Track anonymous users via UUID cookies
- **Key Fields:** id (UUID), created_at, last_active_at
- **Relationships:** letter_stats, quiz_attempts

#### Letter
- **Purpose:** Store Greek alphabet letters
- **Key Fields:** name, uppercase, lowercase, position (1-24)
- **Relationships:** user_stats, quiz_questions

#### UserLetterStat
- **Purpose:** Track per-user per-letter mastery
- **Key Fields:**
  - Performance metrics: seen_count, correct_count, incorrect_count
  - Streak tracking: current_streak, longest_streak
  - Mastery: mastery_score (0.0-1.0), last_result
- **Indexes:**
  - `idx_user_mastery` (user_id, mastery_score) - for weak letter queries
  - `idx_user_seen_count` (user_id, seen_count) - for coverage tracking

#### QuizAttempt
- **Purpose:** Represent a quiz session (14 questions)
- **Key Fields:** started_at, completed_at, correct_count, accuracy
- **Indexes:** `idx_user_completed` (user_id, completed_at) - for history queries

#### QuizQuestion
- **Purpose:** Individual question within a quiz
- **Key Fields:**
  - question_type (LETTER_TO_NAME, NAME_TO_UPPER, NAME_TO_LOWER, AUDIO_TO_UPPER, AUDIO_TO_LOWER)
  - is_correct, chosen_option, correct_option
  - option_1, option_2, option_3, option_4 (stored to prevent regeneration issues)
- **Constraints:**
  - Unique constraint: (quiz_id, letter_id) - prevents duplicate letters in same quiz
- **Indexes:** `idx_quiz_correct` (quiz_id, is_correct) - for summary generation

---

### 2. Business Logic Services

#### Adaptive Selection (`app/services/adaptive.py`)

**Purpose:** Intelligently select letters for quizzes based on user proficiency

**Modes:**
1. **Balanced Mode** (first 10 quizzes)
   - Even distribution across all letters
   - Prefer less-seen letters
   - Avoid recent repetitions (last 3 questions)

2. **Adaptive Mode** (after 10 quizzes)
   - 60% weak letters (weighted by weakness score)
   - 40% coverage (all letters for retention)
   - Avoids recently selected letters

**Key Functions:**
- `should_use_adaptive_mode()`: Check if user has completed 10+ quizzes
- `select_letters_for_quiz()`: Main entry point, returns 14 letters
- `select_letter_balanced()`: Balanced mode selection
- `select_letter_adaptive()`: Adaptive mode selection

#### Mastery Calculation (`app/services/mastery.py`)

**Purpose:** Calculate and update mastery scores

**Mastery Score Formula:**
```
if seen_count < 3:
    score = min(accuracy * 0.5, 0.4)  # Cap low due to insufficient data
else:
    score = accuracy * 0.8 + min(current_streak, 5) * 0.04
    score = clamp(0.0, 1.0, score)
```

**Mastery States:**
- **UNSEEN:** seen_count == 0
- **LEARNING:** seen_count > 0 but not mastered
- **MASTERED:** seen_count >= 8 AND accuracy >= 0.9 AND current_streak >= 3

**Key Functions:**
- `calculate_mastery_score()`: Compute mastery from performance
- `get_mastery_state()`: Determine current state
- `update_letter_stats()`: Update stats after each answer

#### Quiz Generation (`app/services/quiz_generator.py`)

**Purpose:** Create quizzes and format questions

**Question Types:**
1. **LETTER_TO_NAME:** Show symbol, ask for name
2. **NAME_TO_UPPER:** Show name, ask for uppercase
3. **NAME_TO_LOWER:** Show name, ask for lowercase
4. **AUDIO_TO_UPPER:** Play audio, ask for uppercase
5. **AUDIO_TO_LOWER:** Play audio, ask for lowercase

**Process:**
1. Select 14 letters using adaptive algorithm
2. Generate mixed question types (roughly even distribution)
3. For each question:
   - Generate 3 distractors (SQL-level random sampling)
   - Format question with prompt, display, options, correct answer
   - Store options in database to prevent regeneration issues
4. Return formatted questions for frontend

**Key Optimizations:**
- SQL-level random sampling for distractors (vs. loading all letters)
- Pre-shuffle options to randomize correct answer position
- Store options in DB to maintain consistency on resume

---

### 3. API Endpoints

#### User Management (`app/routers/user.py`)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/user/initialize` | POST | Create/retrieve user session, set cookie |
| `/api/user/stats` | GET | Get overall user statistics and progress |

#### Quiz Operations (`app/routers/quiz.py`)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/quiz/start` | POST | Create new quiz with 14 questions |
| `/api/quiz/{quiz_id}/state` | GET | Resume in-progress quiz |
| `/api/quiz/{quiz_id}/answer` | POST | Submit answer, update stats |

**Answer Submission Flow:**
1. Verify quiz belongs to user
2. Check if already completed (400 if true)
3. Check if question already answered (return cached result)
4. Evaluate answer correctness
5. Update QuizQuestion record
6. Update UserLetterStat (seen_count, streak, mastery_score)
7. Check if last question:
   - If yes: Mark quiz complete, calculate accuracy, generate summary
   - If no: Return evaluation result
8. Commit transaction

**Summary Generation (N+1 Query Optimized):**
- Use `joinedload(QuizQuestion.letter)` for eager loading
- Analyze performance by letter
- Identify strong/weak letters in current quiz
- Fetch last 10 quiz scores
- Fetch top 5 weakest letters overall

#### Health Checks (`app/main.py`)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/health` | GET | Database connectivity check |
| `/readiness` | GET | Kubernetes/orchestration readiness check |

---

## Database Schema

```sql
CREATE TABLE users (
    id TEXT PRIMARY KEY,              -- UUID
    created_at DATETIME NOT NULL,
    last_active_at DATETIME NOT NULL
);

CREATE TABLE letters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,        -- "Alpha", "Beta", ...
    uppercase TEXT NOT NULL,          -- "Α", "Β", ...
    lowercase TEXT NOT NULL,          -- "α", "β", ...
    position INTEGER NOT NULL         -- 1-24
);

CREATE TABLE user_letter_stats (
    user_id TEXT,
    letter_id INTEGER,
    seen_count INTEGER DEFAULT 0,
    correct_count INTEGER DEFAULT 0,
    incorrect_count INTEGER DEFAULT 0,
    current_streak INTEGER DEFAULT 0,
    longest_streak INTEGER DEFAULT 0,
    last_seen_at DATETIME,
    last_result TEXT CHECK(last_result IN ('correct', 'incorrect')),
    mastery_score FLOAT DEFAULT 0.0,
    PRIMARY KEY (user_id, letter_id),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (letter_id) REFERENCES letters(id)
);
CREATE INDEX idx_user_mastery ON user_letter_stats(user_id, mastery_score);
CREATE INDEX idx_user_seen_count ON user_letter_stats(user_id, seen_count);

CREATE TABLE quiz_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    started_at DATETIME NOT NULL,
    completed_at DATETIME,
    question_count INTEGER DEFAULT 14,
    correct_count INTEGER DEFAULT 0,
    accuracy FLOAT,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
CREATE INDEX idx_user_completed ON quiz_attempts(user_id, completed_at);

CREATE TABLE quiz_questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    quiz_id INTEGER NOT NULL,
    letter_id INTEGER NOT NULL,
    question_type TEXT NOT NULL,      -- QuestionType enum
    is_correct INTEGER DEFAULT 0,     -- 0 or 1 (boolean)
    chosen_option TEXT,
    correct_option TEXT,
    option_1 TEXT,                    -- Stored for consistency
    option_2 TEXT,
    option_3 TEXT,
    option_4 TEXT,
    UNIQUE(quiz_id, letter_id),
    FOREIGN KEY (quiz_id) REFERENCES quiz_attempts(id),
    FOREIGN KEY (letter_id) REFERENCES letters(id)
);
CREATE INDEX idx_quiz_correct ON quiz_questions(quiz_id, is_correct);
```

---

## Configuration and Constants

### Configuration (`app/config.py`)

All configuration via environment variables:

| Variable | Default | Purpose |
|----------|---------|---------|
| `DATABASE_URL` | `sqlite:///data/greek_alphabet.db` | Database connection |
| `COOKIE_SECURE` | `false` | Require HTTPS for cookies |
| `COOKIE_MAX_AGE` | `31536000` (1 year) | Session duration |
| `ENVIRONMENT` | `development` | Environment name |
| `LOG_LEVEL` | Auto-detect | Logging level |
| `SECRET_KEY` | Dev default | Session/CSRF secret |

### Constants (`app/constants.py`)

Centralized magic numbers:

**Quiz Configuration:**
- `QUESTIONS_PER_QUIZ = 14`
- `DISTRACTOR_COUNT = 3`

**Adaptive Learning:**
- `ADAPTIVE_MODE_THRESHOLD = 10` (quizzes)
- `RECENT_SELECTION_WINDOW = 3` (questions)
- `WEAK_LETTER_RATIO = 0.6` (60%)

**Mastery:**
- `MASTERED_MIN_ATTEMPTS = 8`
- `MASTERED_MIN_ACCURACY = 0.9`
- `MASTERED_MIN_STREAK = 3`
- `MASTERY_ACCURACY_WEIGHT = 0.8`
- `MASTERY_STREAK_BONUS_PER_CORRECT = 0.04`

---

## Security Features

### 1. Rate Limiting
- **Implementation:** slowapi middleware
- **Default:** 100 requests/minute per IP
- **Quiz-specific:** Can be configured per endpoint

### 2. CSRF Protection
- **When:** Enabled in production (ENVIRONMENT=production)
- **Implementation:** Starlette SessionMiddleware
- **Secret:** Uses SECRET_KEY from environment

### 3. Session Management
- **Method:** HTTP-only cookies
- **Name:** `gam_uid`
- **Secure flag:** Enabled in production
- **SameSite:** `lax` (CSRF protection)

### 4. Input Validation
- **Framework:** Pydantic models with validators
- **Answer submission:** Non-empty, trimmed, max length
- **Question IDs:** Positive integers only

---

## Logging and Monitoring

### Structured Logging (`app/logging_config.py`)

**Development Mode:**
- Colored console output
- Human-readable format
- DEBUG level by default

**Production Mode:**
- JSON formatted logs
- Timestamp, level, logger, message, module, function, line
- Extra fields: user_id, quiz_id, question_id, request_id
- INFO level by default

**Log Locations:**
- Application startup/shutdown
- Database migrations
- Quiz creation and completion
- Answer submissions
- Errors and exceptions
- Health check failures

### Health Checks

**`/health` Endpoint:**
- Returns 200 OK when database is accessible
- Returns 503 Service Unavailable on DB failure
- Logs failures with full exception info

**`/readiness` Endpoint:**
- Kubernetes-compatible readiness probe
- Similar to health check but optimized for orchestration

---

## Auto-Migration System

### Implementation (`app/db/init_db.py`)

**Purpose:** Automatically apply schema changes on startup without manual migration scripts

**Features:**
1. **Idempotent:** Safe to run multiple times
2. **Detects missing columns** using SQLAlchemy inspector
3. **Detects missing indexes** using index introspection
4. **Applies changes atomically** with transaction rollback on failure
5. **Logs all operations** for audit trail

**Migration Process:**
```python
1. Check if tables exist (skip if none)
2. For each required schema change:
   a. Inspect current schema
   b. Detect if change is needed
   c. Apply ALTER TABLE or CREATE INDEX
   d. Handle race conditions gracefully
3. Commit all changes together
4. Log summary of applied migrations
```

**Supported Operations:**
- Add columns (QuizQuestion option fields)
- Create indexes (performance optimization)
- Safe for concurrent startups (uses IF NOT EXISTS)

---

## Performance Optimizations

### 1. Query Optimization

**N+1 Query Fix (Quiz Summary):**
```python
# Before: N+1 queries for letter data
questions = db.query(QuizQuestion).filter(...).all()
for q in questions:
    letter = q.letter  # Lazy load - separate query per question

# After: Eager loading
questions = db.query(QuizQuestion).options(
    joinedload(QuizQuestion.letter)
).filter(...).all()  # Single query with JOIN
```

**Random Sampling Optimization:**
```python
# Before: Load all letters, sample in Python
all_letters = db.query(Letter).filter(Letter.id != correct_id).all()
distractors = random.sample(all_letters, 3)

# After: SQL-level random sampling
distractors = db.query(Letter).filter(
    Letter.id != correct_id
).order_by(func.random()).limit(3).all()
```

### 2. Indexes

Strategic indexes for common query patterns:
- User mastery queries: `(user_id, mastery_score)`
- Weak letter identification: `(user_id, seen_count)`
- Quiz history: `(user_id, completed_at)`
- Question aggregation: `(quiz_id, is_correct)`

### 3. Database Connection Pooling

SQLAlchemy connection pooling configured for:
- Connection reuse
- Pre-ping to detect stale connections
- Thread-safe session management

---

## Deployment Guide

### Local Development

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run application
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 3. Access application
# http://localhost:8000
```

### Production Deployment

**Environment Variables:**
```bash
export ENVIRONMENT=production
export DATABASE_URL=postgresql://user:pass@host/dbname
export SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
export COOKIE_SECURE=true
export LOG_LEVEL=INFO
```

**Run with Gunicorn:**
```bash
gunicorn app.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --access-logfile - \
  --error-logfile -
```

**Docker Deployment:**
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ ./app/
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Kubernetes Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: greek-alphabet-mastery
spec:
  replicas: 3
  template:
    spec:
      containers:
      - name: app
        image: greek-alphabet:1.4.2
        ports:
        - containerPort: 8000
        env:
        - name: ENVIRONMENT
          value: "production"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /readiness
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 10
```

---

## Testing Strategy

### Unit Tests
- **Services:** mastery.py, adaptive.py, quiz_generator.py
- **Focus:** Business logic, calculations, algorithms
- **Coverage:** 90%+

### Integration Tests
- **API endpoints:** Full request/response cycle
- **Database:** In-memory SQLite for isolation
- **Focus:** End-to-end flows

### Error Scenario Tests
- Invalid inputs
- Non-existent resources
- Double submissions
- Race conditions
- Missing dependencies

### Concurrency Tests
- Concurrent answer submissions
- Concurrent quiz creation
- Stats update consistency
- Race condition handling

### Audio Question Tests
- Audio file path generation
- is_audio_question flag correctness
- Audio type distribution
- Quiz creation with/without audio

---

## Future Enhancements

### Potential Improvements
1. **PostgreSQL Migration:** For better concurrent write performance
2. **Redis Caching:** Cache user stats for faster queries
3. **WebSocket Support:** Real-time progress updates
4. **Advanced Analytics:** Learning curve visualization
5. **Spaced Repetition Scheduling:** Time-based review prompts
6. **Multi-language Support:** Internationalization
7. **Social Features:** Leaderboards, shared progress
8. **Mobile Apps:** Native iOS/Android clients

### Scalability Considerations
- **Database:** PostgreSQL with read replicas
- **Sessions:** Redis-backed sessions for multi-instance deployment
- **Static Assets:** CDN for audio files
- **Load Balancing:** Multiple app instances behind load balancer
- **Monitoring:** Prometheus metrics, Grafana dashboards

---

## Appendix: Key Algorithms

### Adaptive Letter Selection

```python
def select_letters_for_quiz(db, user_id, count=14):
    if completed_quizzes < 10:
        # Balanced mode: Even distribution
        for i in range(count):
            letter = select_balanced(avoid_recent_3)
            selected.append(letter)
    else:
        # Adaptive mode: 60% weak, 40% coverage
        for i in range(count):
            if i < 8:  # First 60%
                letter = select_from_weak_letters(weighted_by_weakness)
            else:
                letter = select_from_all_letters()
            selected.append(letter)
    return selected
```

### Mastery Score Update

```python
def update_after_answer(stat, is_correct):
    stat.seen_count += 1

    if is_correct:
        stat.correct_count += 1
        stat.current_streak += 1
        stat.longest_streak = max(stat.longest_streak, stat.current_streak)
    else:
        stat.incorrect_count += 1
        stat.current_streak = 0

    # Recalculate mastery score
    accuracy = stat.correct_count / stat.seen_count
    if stat.seen_count < 3:
        stat.mastery_score = min(accuracy * 0.5, 0.4)
    else:
        streak_bonus = min(stat.current_streak, 5) * 0.04
        stat.mastery_score = clamp(0.0, 1.0, accuracy * 0.8 + streak_bonus)
```

---

## Support and Maintenance

### Log Analysis
```bash
# View recent errors (production JSON logs)
grep '"level":"ERROR"' app.log | tail -n 50

# Count quiz completions
grep "Quiz completed" app.log | wc -l

# User activity
grep "user_id" app.log | cut -d'"' -f4 | sort | uniq -c
```

### Database Maintenance
```bash
# Backup SQLite database
sqlite3 data/greek_alphabet.db ".backup data/backup_$(date +%Y%m%d).db"

# Check database integrity
sqlite3 data/greek_alphabet.db "PRAGMA integrity_check;"

# View statistics
sqlite3 data/greek_alphabet.db "SELECT COUNT(*) FROM users; SELECT COUNT(*) FROM quiz_attempts;"
```

---

**Document Version:** 1.0
**Last Updated:** 2025-11-29
**Maintained By:** Development Team
