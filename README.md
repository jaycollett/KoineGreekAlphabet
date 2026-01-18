# Greek Alphabet Mastery

A mobile-first adaptive quiz application to help users master recognition of all 24 Greek letters (uppercase and lowercase). Featuring intelligent spaced repetition, audio pronunciation support, and comprehensive progress tracking.

**Version:** 1.8.4

## Features

### Core Learning Features
- **14-Question Quizzes**: Short, focused practice sessions
- **Five Question Types**:
  - Letter→name recognition
  - Name→uppercase symbol
  - Name→lowercase symbol
  - Audio→uppercase (with pronunciation)
  - Audio→lowercase (with pronunciation)
- **Adaptive Learning**: After 10 quizzes, focuses on weaker letters (60% weak, 40% coverage)
- **Spaced Repetition**: Avoids repeating letters within 3 questions
- **Anonymous Tracking**: No login required - uses secure browser cookies
- **Mobile-First Design**: Large touch targets, clean interface optimized for smartphones
- **Progress Tracking**: View quiz history, accuracy stats, and per-letter mastery scores

### Technical Features (v1.8.4)
- **Auto-Migration System**: Database schema updates automatically on startup
- **Performance Optimized**: Eager loading and SQL-level random sampling
- **Structured Logging**: JSON logs for production, colored output for development
- **Health Checks**: Database verification endpoints for monitoring
- **Rate Limiting**: Protection against abuse (configurable per endpoint)
- **CSRF Protection**: Enabled automatically in production
- **Enhanced API Documentation**: OpenAPI/Swagger UI with detailed endpoint descriptions

## Tech Stack

- **Backend**: Python 3.11+ with FastAPI
- **Database**: SQLite with SQLAlchemy ORM (PostgreSQL-ready)
- **Frontend**: Jinja2 templates with Tailwind CSS
- **Testing**: pytest with comprehensive coverage
- **Security**: slowapi rate limiting, CSRF protection
- **Monitoring**: Structured logging, health checks

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
- `POST /api/user/initialize`: Initialize user session, set cookie
- `GET /api/user/stats`: Get user statistics and progress

### Quiz Operations
- `POST /api/quiz/start`: Start new quiz with 14 questions
- `GET /api/quiz/{quiz_id}/state`: Resume in-progress quiz
- `POST /api/quiz/{quiz_id}/answer`: Submit answer, update stats

### Health & Monitoring
- `GET /health`: Health check with database verification
- `GET /readiness`: Kubernetes-compatible readiness probe

### Application Pages
- `GET /`: Home page with stats and start button
- `GET /quiz`: Quiz interface
- `GET /summary`: Quiz summary after completion

### API Documentation
- `GET /api/docs`: Interactive Swagger UI documentation
- `GET /api/redoc`: ReDoc-style API documentation

## Production Deployment

### Environment Variables

```bash
# Required for production
export ENVIRONMENT=production
export SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
export COOKIE_SECURE=true

# Optional customization
export DATABASE_URL=postgresql://user:pass@host/dbname  # Default: SQLite
export LOG_LEVEL=INFO                                    # Default: INFO
export COOKIE_MAX_AGE=31536000                          # Default: 1 year
```

### Docker Deployment

**Dockerfile** (already included):
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ ./app/
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Build and run:**
```bash
docker build -t greek-alphabet:1.4.2 .
docker run -d -p 8000:8000 \
  -e ENVIRONMENT=production \
  -e SECRET_KEY=your-secret-key \
  -e COOKIE_SECURE=true \
  greek-alphabet:1.4.2
```

### Kubernetes Deployment

**Deployment manifest:**
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: greek-alphabet-mastery
spec:
  replicas: 3
  selector:
    matchLabels:
      app: greek-alphabet
  template:
    metadata:
      labels:
        app: greek-alphabet
    spec:
      containers:
      - name: app
        image: greek-alphabet:1.4.2
        ports:
        - containerPort: 8000
        env:
        - name: ENVIRONMENT
          value: "production"
        - name: SECRET_KEY
          valueFrom:
            secretKeyRef:
              name: app-secrets
              key: secret-key
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: app-secrets
              key: database-url
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
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
```

### Production with Gunicorn

```bash
# Install gunicorn
pip install gunicorn

# Run with 4 workers
gunicorn app.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --access-logfile - \
  --error-logfile - \
  --log-level info
```

## Development

### Linting
```bash
ruff check app/ tests/
```

### Running Tests

**All tests:**
```bash
pytest
```

**With coverage:**
```bash
pytest --cov=app --cov-report=html
open htmlcov/index.html
```

**Specific test categories:**
```bash
pytest tests/test_error_scenarios.py -v    # Error handling tests
pytest tests/test_concurrency.py -v        # Concurrency tests
pytest tests/test_quiz_generator.py -v     # Quiz generation tests
```

### Database Management

**Reset database:**
```bash
rm data/greek_alphabet.db
python -m app.db.init_db
```

**Inspect database:**
```bash
sqlite3 data/greek_alphabet.db
.tables
SELECT * FROM letters;
SELECT COUNT(*) FROM users;
SELECT COUNT(*) FROM quiz_attempts WHERE completed_at IS NOT NULL;
```

**Backup database:**
```bash
sqlite3 data/greek_alphabet.db ".backup data/backup_$(date +%Y%m%d).db"
```

### Verify Improvements

Run the verification script to check all implemented improvements:
```bash
python verify_improvements.py
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite:///data/greek_alphabet.db` | Database connection string |
| `ENVIRONMENT` | `development` | Environment (development, staging, production) |
| `SECRET_KEY` | Dev default | Secret key for sessions/CSRF (MUST change in prod) |
| `COOKIE_SECURE` | `false` | Require HTTPS for cookies |
| `COOKIE_MAX_AGE` | `31536000` | Cookie lifetime in seconds (1 year) |
| `LOG_LEVEL` | Auto-detect | Logging level (DEBUG, INFO, WARNING, ERROR) |

### Application Constants

Key configurable values are defined in `app/constants.py`:
- Quiz size: 14 questions
- Distractor count: 3 options
- Adaptive threshold: 10 quizzes
- Mastery requirements: 8+ attempts, 90%+ accuracy, 3+ streak

See `app/constants.py` for full list and documentation.

## Monitoring and Observability

### Structured Logging

**Development:**
- Colored console output
- Human-readable format
- DEBUG level

**Production:**
- JSON formatted logs
- Includes: timestamp, level, logger, message, module, function, line
- Extra fields: user_id, quiz_id, question_id
- INFO level

**Example log entry (production):**
```json
{
  "timestamp": "2025-11-29T10:30:00.000000Z",
  "level": "INFO",
  "logger": "app.routers.quiz",
  "message": "Quiz completed",
  "module": "quiz",
  "function": "submit_answer",
  "line": 234,
  "user_id": "123e4567-e89b-12d3-a456-426614174000",
  "quiz_id": 42
}
```

### Health Checks

**`/health` endpoint:**
- Returns 200 OK when healthy
- Returns 503 Service Unavailable when database is down
- Includes: status, database status, timestamp, environment

**`/readiness` endpoint:**
- Kubernetes-compatible readiness probe
- Returns 200 when ready to accept traffic
- Returns 503 when not ready

**Example monitoring setup:**
```bash
# Prometheus scraping (if metrics added)
curl http://localhost:8000/metrics

# Simple uptime monitoring
while true; do
  curl -f http://localhost:8000/health || echo "Service down!"
  sleep 30
done
```

## Architecture

For detailed architecture documentation, see [ARCHITECTURE.md](./ARCHITECTURE.md).

Key architectural highlights:
- **Adaptive Learning Algorithm**: Balances exposure vs. focused practice
- **Mastery Calculation**: Combines accuracy, consistency, and streak
- **Auto-Migration System**: Schema updates applied automatically on startup
- **Performance Optimizations**: Eager loading, SQL-level sampling
- **Security**: Rate limiting, CSRF protection, secure sessions

## Testing

The test suite includes:
- **Unit Tests**: Business logic, mastery calculation, adaptive selection
- **Integration Tests**: Full API request/response cycles
- **Error Scenario Tests**: Invalid inputs, edge cases, error paths
- **Concurrency Tests**: Race conditions, concurrent operations
- **Audio Tests**: Audio question format, file paths, type distribution

**Test coverage:** 90%+ (aim for 95%)

Run tests before deploying:
```bash
pytest --cov=app --cov-report=term-missing
```

## License

See LICENSE file for details.

## Contributing

This is an educational project. Feel free to fork and adapt for your own learning needs.
