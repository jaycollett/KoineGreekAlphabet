"""
Tests for the "How It Works" modal feature.

This test verifies that the modal HTML is properly integrated into all pages
and contains the expected content about adaptive learning, mastery levels,
and question types.
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app


client = TestClient(app)


class TestHowItWorksModal:
    """Test suite for the "How It Works" modal feature."""

    def test_modal_present_on_home_page(self):
        """Verify the modal HTML is present on the home page."""
        response = client.get('/')
        assert response.status_code == 200
        html = response.text

        # Check modal structure
        assert 'id="how-it-works-modal"' in html
        assert 'class="modal-overlay' in html
        assert 'class="modal-content' in html

    def test_help_button_present(self):
        """Verify the help button is present in the header."""
        response = client.get('/')
        assert response.status_code == 200
        html = response.text

        # Check help button
        assert 'openHowItWorksModal()' in html
        assert 'How It Works' in html

    def test_modal_contains_adaptive_learning_section(self):
        """Verify modal contains adaptive learning explanation."""
        response = client.get('/')
        assert response.status_code == 200
        html = response.text

        assert 'Your Progress is Adaptive' in html
        assert 'After 10 quizzes' in html
        assert '60%' in html
        assert '40%' in html

    def test_modal_contains_mastery_levels(self):
        """Verify modal explains all three mastery levels."""
        response = client.get('/')
        assert response.status_code == 200
        html = response.text

        assert 'Mastery Levels' in html
        assert 'Strong Letters' in html
        assert '90%+' in html
        assert 'Learning' in html
        assert 'Practice Needed' in html

    def test_modal_contains_accuracy_calculation(self):
        """Verify modal explains how accuracy is calculated."""
        response = client.get('/')
        assert response.status_code == 200
        html = response.text

        assert 'How Accuracy is Calculated' in html
        assert 'mastery score' in html
        assert 'overall accuracy' in html
        assert 'current correct streak' in html

    def test_modal_contains_all_question_types(self):
        """Verify modal lists all 5 question types."""
        response = client.get('/')
        assert response.status_code == 200
        html = response.text

        # Check all 5 question types are documented
        assert 'Question Types' in html
        assert 'Letter → Name' in html or 'Letter &rarr; Name' in html
        assert 'Name → Uppercase' in html or 'Name &rarr; Uppercase' in html
        assert 'Name → Lowercase' in html or 'Name &rarr; Lowercase' in html
        assert 'Audio → Uppercase' in html or 'Audio &rarr; Uppercase' in html
        assert 'Audio → Lowercase' in html or 'Audio &rarr; Lowercase' in html

    def test_modal_contains_practice_recommendations(self):
        """Verify modal includes practice recommendations."""
        response = client.get('/')
        assert response.status_code == 200
        html = response.text

        assert 'Practice Recommendations' in html
        assert 'Daily' in html
        assert '1-2 quizzes' in html
        assert 'Weekly' in html
        assert '5-10 quizzes' in html

    def test_modal_has_close_functionality(self):
        """Verify modal has close button and close function."""
        response = client.get('/')
        assert response.status_code == 200
        html = response.text

        assert 'closeHowItWorksModal()' in html
        assert 'class="modal-close-btn' in html or 'modal-close' in html

    def test_modal_styling_present(self):
        """Verify modal CSS styles are included."""
        response = client.get('/')
        assert response.status_code == 200
        html = response.text

        # Check key modal styles
        assert '.modal-overlay' in html
        assert '.modal-container' in html
        assert '.modal-content' in html
        assert 'fadeIn' in html or 'slideUp' in html

    def test_app_js_loaded_globally(self):
        """Verify app.js is loaded on all pages."""
        response = client.get('/')
        assert response.status_code == 200
        html = response.text

        assert 'src="/static/js/app.js"' in html

    def test_modal_has_mobile_responsive_styles(self):
        """Verify modal has mobile-responsive CSS."""
        response = client.get('/')
        assert response.status_code == 200
        html = response.text

        # Check for mobile media query
        assert '@media (max-width: 768px)' in html
        assert 'max-height: 95vh' in html or 'max-height: 90vh' in html

    def test_modal_prevents_body_scroll_when_open(self):
        """Verify modal prevents body scrolling when open."""
        response = client.get('/')
        assert response.status_code == 200
        html = response.text

        assert 'body.modal-open' in html
        assert 'overflow: hidden' in html
