"""Application configuration settings.

This module provides centralized configuration management for the Greek Alphabet
Mastery application. All settings can be overridden via environment variables.

Environment Variables:
    DATABASE_URL: SQLAlchemy database connection URL
        Default: sqlite:///data/greek_alphabet.db
        Example (PostgreSQL): postgresql://user:pass@localhost/greek_alphabet
        Example (MySQL): mysql+pymysql://user:pass@localhost/greek_alphabet

    COOKIE_SECURE: Whether to require HTTPS for session cookies
        Default: false
        Production: true
        Note: Must be 'true' (case-insensitive) to enable

    COOKIE_MAX_AGE: Session cookie duration in seconds
        Default: 31536000 (1 year)
        Example: 86400 (1 day), 604800 (1 week)

    ENVIRONMENT: Deployment environment name
        Default: development
        Options: development, staging, production
        Affects: logging format, cookie security defaults

    LOG_LEVEL: Logging verbosity level
        Default: INFO (production), DEBUG (development)
        Options: DEBUG, INFO, WARNING, ERROR, CRITICAL

    SECRET_KEY: Secret key for session encryption and CSRF protection
        Default: dev-secret-key-change-in-production
        Production: MUST be set to a random, secure value
        Generate with: python -c "import secrets; print(secrets.token_urlsafe(32))"

Usage:
    >>> from app.config import settings
    >>> print(settings.DATABASE_URL)
    >>> if settings.is_production:
    ...     print("Running in production mode")
"""
import os


class Settings:
    """Application settings loaded from environment variables.

    All attributes can be overridden by setting the corresponding environment
    variable. Boolean values are case-insensitive ('true', 'True', 'TRUE' all work).
    """

    # Cookie security settings
    COOKIE_SECURE: bool = os.getenv("COOKIE_SECURE", "false").lower() == "true"
    """Require HTTPS for session cookies. Must be True in production."""

    COOKIE_HTTPONLY: bool = True
    """Prevent JavaScript access to session cookies (XSS protection)."""

    COOKIE_SAMESITE: str = "lax"
    """Cookie SameSite policy for CSRF protection. Options: strict, lax, none."""

    COOKIE_MAX_AGE: int = int(os.getenv("COOKIE_MAX_AGE", str(365 * 24 * 60 * 60)))
    """Session cookie lifetime in seconds. Default: 1 year."""

    # Database settings
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///data/greek_alphabet.db")
    """SQLAlchemy database connection URL. Supports SQLite, PostgreSQL, MySQL."""

    # Application settings
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    """Deployment environment: development, staging, or production."""

    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "")
    """Logging level. Empty string means auto-detect based on ENVIRONMENT."""

    # Security settings
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
    """Secret key for session encryption and CSRF tokens. MUST change in production."""

    @property
    def is_production(self) -> bool:
        """Check if running in production environment.

        Returns:
            True if ENVIRONMENT is 'production' (case-insensitive)
        """
        return self.ENVIRONMENT.lower() == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development environment.

        Returns:
            True if ENVIRONMENT is 'development' (case-insensitive)
        """
        return self.ENVIRONMENT.lower() == "development"


settings = Settings()
"""Global settings instance. Import and use throughout the application."""
