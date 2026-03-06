# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Greek Alphabet Mastery** is a mobile-first adaptive quiz application that helps users master recognition of all Greek letters (uppercase and lowercase) through focused, adaptive quizzes.

Key characteristics:
- **No login/accounts**: Anonymous user tracking via browser cookie (UUID-based)
- **14-question quizzes**: Short, focused sessions with three question types (letter→name, name→uppercase, name→lowercase)
- **Adaptive learning**: After 10 quizzes, questions focus on weaker letters (60% weak, 40% coverage)
- **Mobile-first UX**: Large touch targets, clean interface, minimal distraction

## Tech Stack

- **Backend**: Python + FastAPI + uvicorn
- **Database**: SQLite (with SQLAlchemy or raw sqlite3)
- **Frontend**: Server-rendered Jinja2 templates + responsive CSS + minimal JavaScript
- **Testing**: pytest for unit and integration tests
- **Containerization**: Docker with optional docker-compose

## Development Commands

### Setup and Running
```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # or: .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
# or if using uv:
uv pip install -r requirements.txt

# Run development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Initialize database (seed Greek alphabet)
python -m app.db.init_db
```

### Testing
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/test_adaptive_logic.py

# Run single test
pytest tests/test_adaptive_logic.py::test_mastery_calculation -v
```

### Docker
```bash
# Build image
docker build -t greek-alphabet-mastery .

# Run container
docker run -p 8000:8000 greek-alphabet-mastery

# Using docker-compose
docker-compose up --build

# Pull published image (after release)
docker pull ghcr.io/jaycollett/koinegreekalphabet:latest
docker pull ghcr.io/jaycollett/koinegreekalphabet:1.0.0
```

## Release Process

Follows **semantic versioning** (MAJOR.MINOR.PATCH). No 'v' prefix in version numbers (use `1.0.0`, not `v1.0.0`).

### Creating a Release

1. Commit and push all changes to main
2. Tag and push: `git tag 1.0.0 && git push origin 1.0.0`
3. Create a GitHub Release from the tag with a changelog description
4. GitHub Actions (`.github/workflows/docker-publish.yml`) auto-builds and publishes to `ghcr.io/jaycollett/koinegreekalphabet:{version}` and `:latest`

### Release Checklist

- [ ] All tests passing (`pytest`) and Docker build works locally
- [ ] CHANGELOG updated, no uncommitted changes

### Emergency Rollback

Roll back by pulling and running the previous version tag: `docker run -p 8000:8000 ghcr.io/jaycollett/koinegreekalphabet:{previous-version}`

## Architecture

### Core Data Model (SQLite)

Five main tables:

1. **`users`**: Tracks anonymous users via UUID cookie (`gam_uid`)
2. **`letters`**: 24 Greek letters with name, uppercase, lowercase, position
3. **`user_letter_stats`**: Per-user per-letter mastery tracking
   - `seen_count`, `correct_count`, `incorrect_count`
   - `current_streak`, `longest_streak`
   - `mastery_score` (0.0-1.0): Derived from accuracy and streak
   - `last_seen_at`, `last_result`
4. **`quiz_attempts`**: Quiz sessions (14 questions each)
5. **`quiz_questions`**: Individual questions with type, correctness, chosen/correct options

### Mastery States

Each letter per user transitions through:
- **Unseen/New**: `seen_count == 0`
- **Learning**: Started but not mastered
- **Mastered**: `seen_count ≥ 8` AND `accuracy ≥ 0.9` AND `current_streak ≥ 3`

Mastered letters appear less frequently but are still included for retention.

### Adaptive Algorithm

**Before 10 quizzes**: Balanced selection across all letters for broad exposure.

**After 10 quizzes**:
- 60% of questions from **weaker letters** (weighted by `weakness_score = 1 - mastery_score`)
- 40% from **all letters** (including mastered) for coverage

Question types are evenly mixed: letter→name, name→uppercase, name→lowercase.

### API Endpoints

- `GET /`: Serve main application HTML
- `GET /api/bootstrap`: Initialize user session, return stats and last 10 quiz scores
- `POST /api/quiz/start`: Create new quiz, generate 14 questions, return quiz data
- `POST /api/quiz/{quiz_id}/answer`: Submit answer, update stats, return feedback/summary

### Frontend Structure

Server-rendered templates with:
- **Home screen**: Start quiz button, last score, strengths/weaknesses summary
- **Quiz screen**: Question prompt, 4 large answer buttons, progress indicator
- **Summary screen**: Score, accuracy, weak/strong letters, last 10 quiz history

## Project File Structure

Expected layout:
```
app/
  __init__.py
  main.py              # FastAPI app initialization
  db/
    models.py          # SQLAlchemy models or schema
    database.py        # DB connection, session management
    init_db.py         # Seed script for letters table
  routers/
    quiz.py            # Quiz endpoints
    user.py            # User/bootstrap endpoints
  services/
    adaptive.py        # Adaptive question selection logic
    mastery.py         # Mastery score calculation
    quiz_generator.py  # Generate questions
  templates/
    index.html
    quiz.html
    summary.html
  static/
    css/
      styles.css
    js/
      quiz.js
tests/
  test_adaptive_logic.py
  test_mastery.py
  test_quiz_endpoints.py
Dockerfile
docker-compose.yml
requirements.txt
```

## Key Implementation Notes

### User Identity
- On first visit: generate UUID, create user record, set `gam_uid` cookie with long expiration
- On subsequent requests: read cookie, lookup user, reinitialize if missing
- No user input required; process is transparent

### Mastery Score Calculation
Suggested formula (can be refined):
```python
if seen_count < 3:
    mastery_score = min(accuracy * 0.5, 0.4)  # Cap low until sufficient data
else:
    mastery_score = clamp(0, 1, accuracy * 0.8 + min(current_streak, 5) * 0.04)
```

Where `accuracy = correct_count / max(1, seen_count)`.

### Question Generation
- Randomly select question type (letter→name, name→uppercase, name→lowercase)
- Select target letter using adaptive algorithm
- Generate 3 distractor options from other Greek letters
- Avoid showing same letter in rapid succession (cooldown logic)

### Stats Updates on Answer
After each answer:
1. Update `user_letter_stats`: increment seen/correct/incorrect, update streak
2. Recalculate `mastery_score`
3. Set `last_seen_at`, `last_result`
4. Increment `quiz_attempts.correct_count` if correct
5. If last question: compute quiz accuracy, set `completed_at`

## Testing Strategy

### Unit Tests
- Mastery score calculation for various scenarios (new user, learning, mastered, regression)
- Adaptive selection algorithm: verify 60/40 split, weighted selection, coverage
- Question generation: correct type distribution, no duplicates in distractors

### Integration Tests
- Full quiz flow: start → 14 answers → summary
- User initialization via cookie
- Stats persistence across quizzes
- Transition from balanced to adaptive mode after 10 quizzes

### CI/CD
GitHub Actions workflow:
- Install dependencies
- Run linting (ruff/flake8 if configured)
- Run pytest with coverage report
- Fail if coverage below threshold (e.g., 80%)

## Specialist Agents Available

- **python-project-engineer**: Backend logic, FastAPI endpoints, adaptive algorithm, tests, schema/SQL
- **code-quality-engineer**: Code review, refactoring, test strategy, pytest config, CI setup
- **devops-ubuntu-assistant**: Local environment setup, Docker, dependency installation

## Important Constraints

- Mobile-first design is mandatory: large touch targets, readable on small screens
- Quiz size is fixed at 14 questions
- Question types are fixed (3 types, mixed randomly)
- Adaptive mode triggers after exactly 10 quizzes (140 questions)
- Mastery criteria are strict: 8+ attempts, 90%+ accuracy, 3+ streak
