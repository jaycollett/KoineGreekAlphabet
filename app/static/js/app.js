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
