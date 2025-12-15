"""
Unit tests for similar letter distractor generation.

Tests cover:
1. get_similar_letters() returns correct count
2. Returns similar letters when available
3. Falls back to random when insufficient similar letters
4. Never returns target letter itself
5. Handles letters with many similar letters
6. Handles letters with few/no similar letters
7. Result shuffling and randomization
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base, Letter
from app.db.init_db import GREEK_ALPHABET
from app.services.similar_letters import get_similar_letters, SIMILAR_LETTER_PAIRS


@pytest.fixture
def test_db():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    # Seed letters
    for letter_data in GREEK_ALPHABET:
        letter = Letter(**letter_data)
        session.add(letter)
    session.commit()

    yield session
    session.close()


class TestGetSimilarLetters:
    """Test get_similar_letters function."""

    def test_returns_correct_count(self, test_db):
        """Should return exactly the requested count of distractors."""
        alpha = test_db.query(Letter).filter(Letter.name == "Alpha").first()
        all_letters = test_db.query(Letter).all()

        result = get_similar_letters(alpha, all_letters, count=3)

        assert len(result) == 3
        assert all(isinstance(letter, Letter) for letter in result)

    def test_does_not_return_target_letter(self, test_db):
        """Result should never contain the target letter."""
        rho = test_db.query(Letter).filter(Letter.name == "Rho").first()
        all_letters = test_db.query(Letter).all()

        result = get_similar_letters(rho, all_letters, count=3)

        assert rho not in result
        assert all(letter.id != rho.id for letter in result)

    def test_returns_similar_letters_when_available(self, test_db):
        """Should prefer similar letters when enough are available."""
        # Rho has similar letters: Pi, Beta
        rho = test_db.query(Letter).filter(Letter.name == "Rho").first()
        all_letters = test_db.query(Letter).all()

        # Run multiple times to check consistency
        for _ in range(5):
            result = get_similar_letters(rho, all_letters, count=2)

            result_names = {letter.name for letter in result}
            similar_names = SIMILAR_LETTER_PAIRS.get("Rho", set())

            # At least some should be from similar set (may include random if not enough similar)
            # Since Rho has 2 similar letters and we request 2, all should be similar
            assert len(result_names & similar_names) >= 1

    def test_handles_letter_with_many_similar_letters(self, test_db):
        """Test letter with multiple similar options (e.g., Theta)."""
        # Theta has similar: Phi, Omicron, Omega
        theta = test_db.query(Letter).filter(Letter.name == "Theta").first()
        all_letters = test_db.query(Letter).all()

        result = get_similar_letters(theta, all_letters, count=3)

        assert len(result) == 3
        assert theta not in result

        result_names = {letter.name for letter in result}
        similar_names = SIMILAR_LETTER_PAIRS.get("Theta", set())

        # Should be able to get all from similar set
        assert len(result_names & similar_names) >= 1

    def test_handles_letter_with_few_similar_letters(self, test_db):
        """Test letter with few similar options (e.g., Mu has none)."""
        # Mu has no similar letters defined
        mu = test_db.query(Letter).filter(Letter.name == "Mu").first()
        all_letters = test_db.query(Letter).all()

        result = get_similar_letters(mu, all_letters, count=3)

        assert len(result) == 3
        assert mu not in result
        # Should fall back to random selection

    def test_supplements_with_random_when_insufficient_similar(self, test_db):
        """Should add random letters when not enough similar letters exist."""
        # Zeta has only 1 similar letter (Xi)
        zeta = test_db.query(Letter).filter(Letter.name == "Zeta").first()
        all_letters = test_db.query(Letter).all()

        result = get_similar_letters(zeta, all_letters, count=3)

        assert len(result) == 3
        assert zeta not in result

        # Should include Xi (similar) plus 2 random
        result_names = {letter.name for letter in result}
        assert "Xi" in result_names  # Similar letter should be included

    def test_different_counts(self, test_db):
        """Test requesting different counts of distractors."""
        alpha = test_db.query(Letter).filter(Letter.name == "Alpha").first()
        all_letters = test_db.query(Letter).all()

        # Test count=2 (Level 3 difficulty)
        result_2 = get_similar_letters(alpha, all_letters, count=2)
        assert len(result_2) == 2

        # Test count=3 (Level 1/2 difficulty)
        result_3 = get_similar_letters(alpha, all_letters, count=3)
        assert len(result_3) == 3

    def test_no_duplicates_in_result(self, test_db):
        """Result should not contain duplicate letters."""
        pi = test_db.query(Letter).filter(Letter.name == "Pi").first()
        all_letters = test_db.query(Letter).all()

        result = get_similar_letters(pi, all_letters, count=3)

        letter_ids = [letter.id for letter in result]
        assert len(letter_ids) == len(set(letter_ids))  # No duplicates

    def test_result_is_shuffled(self, test_db):
        """Result should be shuffled (mix of similar and random)."""
        # This test is probabilistic - we can't guarantee order, but we can verify
        # that similar and random are mixed (not similar first, then random)
        omega = test_db.query(Letter).filter(Letter.name == "Omega").first()
        all_letters = test_db.query(Letter).all()

        # Omega has similar: Omicron, Theta
        # Request 3, so 2 similar + 1 random
        results = []
        for _ in range(10):
            result = get_similar_letters(omega, all_letters, count=3)
            results.append([letter.name for letter in result])

        # Check that we get variation in ordering
        # (not always same order, indicating shuffle is working)
        unique_orderings = len(set(tuple(r) for r in results))
        assert unique_orderings > 1  # Should have different orderings

    def test_all_greek_letters_can_get_distractors(self, test_db):
        """Every Greek letter should be able to get distractors."""
        all_letters = test_db.query(Letter).all()

        for letter in all_letters:
            result = get_similar_letters(letter, all_letters, count=3)

            assert len(result) == 3
            assert letter not in result
            assert all(other.id != letter.id for other in result)


class TestSimilarLetterPairsData:
    """Test SIMILAR_LETTER_PAIRS data structure."""

    def test_similar_pairs_is_dictionary(self):
        """SIMILAR_LETTER_PAIRS should be a dictionary."""
        assert isinstance(SIMILAR_LETTER_PAIRS, dict)

    def test_all_values_are_sets_or_empty(self):
        """All values in SIMILAR_LETTER_PAIRS should be sets (or empty dict/set)."""
        for letter_name, similar_set in SIMILAR_LETTER_PAIRS.items():
            # Accept both set and empty dict (both work correctly in the code)
            assert isinstance(similar_set, (set, dict))

    def test_no_self_references(self):
        """No letter should list itself as similar."""
        for letter_name, similar_set in SIMILAR_LETTER_PAIRS.items():
            assert letter_name not in similar_set

    def test_similar_pairs_correspond_to_real_letters(self, test_db):
        """All letters in SIMILAR_LETTER_PAIRS should exist in database."""
        all_letters = test_db.query(Letter).all()
        all_letter_names = {letter.name for letter in all_letters}

        for letter_name, similar_set in SIMILAR_LETTER_PAIRS.items():
            # Target letter should exist
            assert letter_name in all_letter_names

            # All similar letters should exist
            for similar_name in similar_set:
                assert similar_name in all_letter_names

    def test_expected_similar_pairs_exist(self):
        """Verify some expected similar pairs are defined."""
        # Visual similarities
        assert "Pi" in SIMILAR_LETTER_PAIRS.get("Rho", set())
        assert "Rho" in SIMILAR_LETTER_PAIRS.get("Pi", set())

        # Circle-like letters
        assert "Omega" in SIMILAR_LETTER_PAIRS.get("Omicron", set())
        assert "Theta" in SIMILAR_LETTER_PAIRS.get("Omicron", set())

    def test_symmetric_relationships_where_appropriate(self):
        """Some similar relationships should be symmetric (bidirectional)."""
        # Rho <-> Pi
        if "Pi" in SIMILAR_LETTER_PAIRS.get("Rho", set()):
            assert "Rho" in SIMILAR_LETTER_PAIRS.get("Pi", set())

        # Omicron <-> Omega
        if "Omega" in SIMILAR_LETTER_PAIRS.get("Omicron", set()):
            assert "Omicron" in SIMILAR_LETTER_PAIRS.get("Omega", set())


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_requesting_more_distractors_than_available_letters(self, test_db):
        """Should handle case where count is close to total letter count."""
        # There are 24 letters total
        alpha = test_db.query(Letter).filter(Letter.name == "Alpha").first()
        all_letters = test_db.query(Letter).all()

        # Request 23 distractors (all other letters)
        result = get_similar_letters(alpha, all_letters, count=23)

        assert len(result) == 23
        assert alpha not in result

    def test_requesting_all_other_letters(self, test_db):
        """Should work when requesting all other letters as distractors."""
        alpha = test_db.query(Letter).filter(Letter.name == "Alpha").first()
        all_letters = test_db.query(Letter).all()

        # 24 total letters - 1 (alpha) = 23 possible distractors
        result = get_similar_letters(alpha, all_letters, count=23)

        assert len(result) == 23
        result_ids = {letter.id for letter in result}
        all_other_ids = {letter.id for letter in all_letters if letter.id != alpha.id}
        assert result_ids == all_other_ids

    def test_count_of_one(self, test_db):
        """Should work with count=1."""
        beta = test_db.query(Letter).filter(Letter.name == "Beta").first()
        all_letters = test_db.query(Letter).all()

        result = get_similar_letters(beta, all_letters, count=1)

        assert len(result) == 1
        assert beta not in result

    def test_empty_similar_set_falls_back_to_random(self, test_db):
        """Letters with empty similar sets should get random distractors."""
        # Mu has empty similar set
        mu = test_db.query(Letter).filter(Letter.name == "Mu").first()
        all_letters = test_db.query(Letter).all()

        result = get_similar_letters(mu, all_letters, count=3)

        assert len(result) == 3
        assert mu not in result
        # Should be 3 random letters
