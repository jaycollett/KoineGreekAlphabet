# syntax=docker/dockerfile:1.7
#
# Greek Alphabet Mastery Dockerfile.
#
# Two-stage Alpine build. Every extension-bearing dependency here
# (pydantic-core, uvloop, httptools, watchfiles, SQLAlchemy's C accelerators)
# publishes musllinux wheels, so musl costs nothing and drops the Debian-slim
# perl-base/ncurses CVE backlog. Python raised 3.11 -> 3.13.

# ---- Stage 1: build the virtualenv ----
FROM python:3.13-alpine AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Build-only compilers, replacing the previous `apt-get install gcc`.
RUN apk add --no-cache build-base libffi-dev openssl-dev

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# ---- Stage 2: runtime ----
FROM python:3.13-alpine

# Build argument for version
ARG VERSION=dev

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

RUN apk add --no-cache libffi openssl libstdc++

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv

# Copy application code
COPY app/ ./app/
COPY pytest.ini .
COPY tests/ ./tests/

# Replace version placeholder in template
RUN sed -i "s/__VERSION__/${VERSION}/g" /app/app/templates/base.html

# Create directory for database (will be mounted as volume in production) and
# drop to a non-root user.
#
# Note: Database initialization happens automatically on first startup
# via the auto-migration system in app/db/init_db.py
RUN addgroup -g 1000 -S appuser \
    && adduser -u 1000 -S -G appuser -H -s /sbin/nologin appuser \
    && mkdir -p /app/data \
    && chown -R appuser:appuser /app

USER 1000:1000

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
