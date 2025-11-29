// Summary page logic

function displaySummary() {
    const summaryData = sessionStorage.getItem('quizSummary');

    if (!summaryData) {
        // Redirect to home if no summary data
        window.location.href = '/';
        return;
    }

    const summary = JSON.parse(summaryData);

    document.getElementById('loading').classList.add('hidden');
    document.getElementById('summary-content').classList.remove('hidden');

    // Display score
    document.getElementById('score-display').textContent =
        `${summary.correct_count}/${summary.question_count}`;
    document.getElementById('accuracy-display').textContent =
        `${summary.accuracy_percentage}%`;

    // Feedback message
    const feedbackMessage = document.getElementById('feedback-message');
    if (summary.accuracy >= 0.9) {
        feedbackMessage.textContent = 'Excellent work!';
        feedbackMessage.className = 'text-lg text-green-400';
    } else if (summary.accuracy >= 0.7) {
        feedbackMessage.textContent = 'Good job! Keep practicing.';
        feedbackMessage.className = 'text-lg text-blue-400';
    } else {
        feedbackMessage.textContent = 'Keep practicing - you\'ll get there!';
        feedbackMessage.className = 'text-lg text-yellow-400';
    }

    // Strong letters
    if (summary.strong_letters && summary.strong_letters.length > 0) {
        document.getElementById('strong-section').classList.remove('hidden');
        document.getElementById('strong-letters').textContent =
            summary.strong_letters.join(', ');
    }

    // Weak letters in this quiz
    if (summary.weak_letters && summary.weak_letters.length > 0) {
        document.getElementById('weak-section').classList.remove('hidden');
        document.getElementById('weak-letters').textContent =
            summary.weak_letters.join(', ');
    }

    // Overall weak letters
    if (summary.overall_weak_letters && summary.overall_weak_letters.length > 0) {
        document.getElementById('overall-weak-section').classList.remove('hidden');
        const weakLettersEl = document.getElementById('overall-weak-letters');
        weakLettersEl.innerHTML = summary.overall_weak_letters.map(letter => `
            <div class="flex justify-between items-center bg-slate-600 border border-slate-500 rounded p-2">
                <span class="font-semibold text-gray-200">${letter.name}</span>
                <span class="text-sm text-gray-400">
                    ${Math.round(letter.accuracy * 100)}% accuracy
                </span>
            </div>
        `).join('');
    }

    // Quiz history
    if (summary.quiz_history && summary.quiz_history.length > 1) {
        document.getElementById('history-section').classList.remove('hidden');
        const historyEl = document.getElementById('quiz-history');
        historyEl.innerHTML = summary.quiz_history.slice(0, 5).map((quiz, index) => `
            <div class="flex justify-between items-center bg-slate-700 border border-slate-600 rounded p-2">
                <span class="text-sm text-gray-400">
                    ${index === 0 ? 'Just now' : 'Quiz ' + (index + 1)}
                </span>
                <span class="font-semibold ${quiz.accuracy >= 0.8 ? 'text-green-400' : 'text-yellow-400'}">
                    ${quiz.correct_count}/${14} (${Math.round(quiz.accuracy * 100)}%)
                </span>
            </div>
        `).join('');
    }
}

function startNewQuiz() {
    // Clear session storage
    sessionStorage.removeItem('quizSummary');
    window.location.href = '/quiz';
}

// Display summary on page load
displaySummary();
