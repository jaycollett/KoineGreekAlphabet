"""Pytest fixtures for testing."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.database import Base
from app.db.models import User, Letter
from app.db.init_db import GREEK_ALPHABET


@pytest.fixture(scope="function")
def test_db():
    """Create a test database for each test."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    # Seed Greek alphabet
    for letter_data in GREEK_ALPHABET:
        letter = Letter(**letter_data)
        db.add(letter)
    db.commit()

    yield db

    db.close()


@pytest.fixture
def test_user(test_db):
    """Create a test user."""
    user = User(id="test_user_123")
    test_db.add(user)
    test_db.commit()
    return user
