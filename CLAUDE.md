# CLAUDE.md

Do not make any changes until you have 95% confidence in what you need to build. Ask me follow-up questions until you reach that confidence.

## Project Overview

Mobile-first adaptive quiz app for mastering Greek letter recognition (uppercase + lowercase). 14-question quizzes, three question types (letter->name, name->uppercase, name->lowercase). Anonymous users via UUID cookie. After 10 quizzes, questions adapt: 60% weak letters, 40% coverage.

## Tech Stack

Python + FastAPI + SQLite + Jinja2 templates. Docker-containerized.

## Commands

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
python -m app.db.init_db                        # Seed Greek alphabet
pytest                                           # All tests
pytest --cov=app --cov-report=html              # With coverage
docker build -t greek-alphabet-mastery .
```

## Release

Semver WITHOUT 'v' prefix. Tag, push, create GitHub release -> auto-builds to `ghcr.io/jaycollett/koinegreekalphabet`.

## Key Constraints

- Quiz size fixed at 14 questions
- Three question types, mixed randomly
- Adaptive mode triggers after exactly 10 quizzes (140 questions)
- Mastery: 8+ attempts AND 90%+ accuracy AND 3+ current streak
- Mobile-first: large touch targets mandatory

## API

- `GET /api/bootstrap` - Init user session, return stats
- `POST /api/quiz/start` - Generate 14 questions
- `POST /api/quiz/{id}/answer` - Submit answer, get feedback/summary
