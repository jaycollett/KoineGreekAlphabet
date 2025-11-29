# Greek Alphabet Mastery

A mobile-first adaptive quiz application to help users master recognition of all 24 Greek letters (uppercase and lowercase).

## Features

- **14-Question Quizzes**: Short, focused practice sessions
- **Three Question Types**: Letter→name, name→uppercase, name→lowercase
- **Adaptive Learning**: After 10 quizzes, focuses on weaker letters (60% weak, 40% coverage)
- **Anonymous Tracking**: No login required - uses browser cookies
- **Mobile-First Design**: Large touch targets, clean interface optimized for smartphones
- **Progress Tracking**: View quiz history, accuracy stats, and per-letter mastery

## Tech Stack

- **Backend**: Python 3.11+ with FastAPI
- **Database**: SQLite with SQLAlchemy ORM
- **Frontend**: Jinja2 templates with Tailwind CSS
- **Testing**: pytest with coverage reporting

## Quick Start

### Using Docker (Recommended)

```bash
# Build and run with docker-compose
docker-compose up --build

# Access the application at http://localhost:8000
```

### Local Development

#### Prerequisites

- Python 3.11 or higher
- pip or uv for package management

#### Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd KoineGreekAlphabet
   ```

2. **Create virtual environment**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Initialize the database**
   ```bash
   python -m app.db.init_db
   ```

   This creates the SQLite database and seeds it with all 24 Greek letters.

5. **Run the application**
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

6. **Access the application**
   Open your browser to http://localhost:8000

## Running Tests

### Run all tests
```bash
pytest
```

### Run with coverage report
```bash
pytest --cov=app --cov-report=html
```

### Run specific test file
```bash
pytest tests/test_mastery.py -v
```

### Run single test
```bash
pytest tests/test_mastery.py::TestMasteryScoreCalculation::test_perfect_performance -v
```

## Project Structure

```
KoineGreekAlphabet/
├── app/
│   ├── db/
│   │   ├── database.py       # Database configuration
│   │   ├── models.py          # SQLAlchemy models
│   │   └── init_db.py         # Database initialization & seeding
│   ├── routers/
│   │   ├── user.py            # User bootstrap endpoints
│   │   └── quiz.py            # Quiz endpoints
│   ├── services/
│   │   ├── mastery.py         # Mastery score calculation
│   │   ├── adaptive.py        # Adaptive letter selection
│   │   └── quiz_generator.py # Quiz generation logic
│   ├── static/
│   │   └── js/                # Frontend JavaScript
│   ├── templates/             # Jinja2 HTML templates
│   └── main.py                # FastAPI application
├── tests/                     # Test suite
├── requirements.txt           # Python dependencies
├── Dockerfile                 # Docker configuration
├── docker-compose.yml         # Docker Compose setup
├── pytest.ini                 # pytest configuration
├── CLAUDE.md                  # Claude Code guidance
└── README.md                  # This file
```

## How It Works

### User Tracking
- Users are tracked anonymously via a browser cookie (`gam_uid`)
- No registration or login required
- All progress is stored in SQLite

### Quiz Flow
1. User starts a quiz (14 questions)
2. Questions mix three types randomly:
   - Show letter, ask for name
   - Show name, ask for uppercase
   - Show name, ask for lowercase
3. Each answer updates per-letter statistics
4. After completion, view summary with strengths/weaknesses

### Adaptive Algorithm

**Initial Phase (< 10 quizzes)**:
- Balanced selection across all letters
- Ensures broad exposure to the alphabet

**Adaptive Phase (≥ 10 quizzes)**:
- 60% of questions from weaker letters (weighted by weakness score)
- 40% from all letters (for coverage and retention)

### Mastery Calculation

Each letter per user has a mastery score (0.0-1.0) based on:
- Accuracy: `correct_count / seen_count`
- Streak: Current consecutive correct answers
- Minimum attempts: Requires ≥3 attempts for reliable score

**Mastery States**:
- **Unseen**: Never attempted
- **Learning**: Attempted but not mastered
- **Mastered**: ≥8 attempts, ≥90% accuracy, ≥3 streak

## API Endpoints

### User Management
- `GET /api/bootstrap`: Initialize user session, return stats

### Quiz Operations
- `POST /api/quiz/start`: Start new quiz, get 14 questions
- `POST /api/quiz/{quiz_id}/answer`: Submit answer, update stats

### Application Pages
- `GET /`: Home page with stats and start button
- `GET /quiz`: Quiz interface
- `GET /summary`: Quiz summary after completion

## Development

### Linting
```bash
ruff check app/ tests/
```

### Database Management

**Reset database**:
```bash
rm greek_alphabet_mastery.db
python -m app.db.init_db
```

**Inspect database**:
```bash
sqlite3 greek_alphabet_mastery.db
.tables
SELECT * FROM letters;
```

## Configuration

The application uses sensible defaults:
- Database: `greek_alphabet_mastery.db` (SQLite)
- Server: `0.0.0.0:8000`
- Cookie: `gam_uid` with 1-year expiration

## License

See LICENSE file for details.

## Contributing

This is an educational project. Feel free to fork and adapt for your own learning needs.
