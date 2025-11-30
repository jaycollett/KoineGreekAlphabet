// Shared utilities for the application

function showError(message) {
    console.error(message);
    alert(message);
}

function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString();
}

function formatAccuracy(accuracy) {
    return Math.round(accuracy * 100);
}

// Modal functions
function openHowItWorksModal() {
    const modal = document.getElementById('how-it-works-modal');
    if (modal) {
        modal.classList.remove('hidden');
        document.body.classList.add('modal-open');
    }
}

function closeHowItWorksModal() {
    const modal = document.getElementById('how-it-works-modal');
    if (modal) {
        modal.classList.add('hidden');
        document.body.classList.remove('modal-open');
    }
}

// Close modal on overlay click
document.addEventListener('DOMContentLoaded', function() {
    const modal = document.getElementById('how-it-works-modal');
    if (modal) {
        modal.addEventListener('click', function(e) {
            if (e.target === modal) {
                closeHowItWorksModal();
            }
        });
    }

    // Close modal on Escape key
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            closeHowItWorksModal();
        }
    });
});
