# Greek Alphabet Mastery Dockerfile
FROM python:3.11-slim

# Build argument for version
ARG VERSION=dev

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/
COPY pytest.ini .
COPY tests/ ./tests/

# Replace version placeholder in template
RUN sed -i "s/__VERSION__/${VERSION}/g" /app/app/templates/base.html

# Create directory for database (will be mounted as volume in production)
RUN mkdir -p /app/data

# Note: Database initialization happens automatically on first startup
# via the auto-migration system in app/db/init_db.py

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
