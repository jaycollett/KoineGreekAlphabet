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

    // Display level-up celebration if applicable
    if (summary.leveled_up && summary.new_level) {
        displayLevelUpCelebration(summary.new_level, summary.level_progress);
    } else if (summary.level_progress) {
        // Show level progress update if not leveled up
        displayLevelProgress(summary.level_progress);

        // Show streak status banner
        displayStreakStatus(summary.accuracy, summary.level_progress);
    }

    // Display score
    document.getElementById('score-display').textContent =
        `${summary.correct_count}/${summary.question_count}`;
    document.getElementById('accuracy-display').textContent =
        `${summary.accuracy_percentage}%`;

    // Display average response time if available
    if (summary.avg_response_time_ms !== null && summary.avg_response_time_ms !== undefined) {
        const responseTimeDisplay = document.getElementById('response-time-display');
        const avgResponseTime = document.getElementById('avg-response-time');
        const seconds = (summary.avg_response_time_ms / 1000).toFixed(1);
        avgResponseTime.textContent = `${seconds}s`;
        responseTimeDisplay.classList.remove('hidden');
    }

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

    // Display trend indicator
    if (summary.trend && summary.trend.change_percent != null && summary.trend.recent_average != null) {
        document.getElementById('trend-section').classList.remove('hidden');
        const trendIndicator = document.getElementById('trend-indicator');
        const trendText = document.getElementById('trend-text');
        const trendDetails = document.getElementById('trend-details');

        const changePercent = Math.abs(summary.trend.change_percent || 0);
        const recentAverage = summary.trend.recent_average || 0;

        if (summary.trend.trend === 'up') {
            trendIndicator.textContent = '↑';
            trendIndicator.className = 'text-4xl font-bold text-green-400';
            trendText.textContent = 'Improving!';
            trendText.className = 'text-lg text-green-400 font-semibold';
            trendDetails.textContent = `${changePercent}% above recent average (${recentAverage}%)`;
        } else if (summary.trend.trend === 'down') {
            trendIndicator.textContent = '↓';
            trendIndicator.className = 'text-4xl font-bold text-yellow-400';
            trendText.textContent = 'Keep practicing';
            trendText.className = 'text-lg text-yellow-400 font-semibold';
            trendDetails.textContent = `${changePercent}% below recent average (${recentAverage}%)`;
        } else {
            trendIndicator.textContent = '→';
            trendIndicator.className = 'text-4xl font-bold text-blue-400';
            trendText.textContent = 'Stable';
            trendText.className = 'text-lg text-blue-400 font-semibold';
            trendDetails.textContent = `Consistent with recent average (${recentAverage}%)`;
        }
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
                <span class="font-semibold text-gray-200">${letter.name || 'Unknown'}</span>
                <span class="text-sm text-gray-400">
                    ${Math.round((letter.accuracy || 0) * 100)}% accuracy
                </span>
            </div>
        `).join('');
    }

    // Quiz history
    if (summary.quiz_history && summary.quiz_history.length > 1) {
        document.getElementById('history-section').classList.remove('hidden');
        const historyEl = document.getElementById('quiz-history');
        historyEl.innerHTML = summary.quiz_history.slice(0, 5).map((quiz, index) => {
            const accuracy = quiz.accuracy || 0;
            const correctCount = quiz.correct_count || 0;
            return `
                <div class="flex justify-between items-center bg-slate-700 border border-slate-600 rounded p-2">
                    <span class="text-sm text-gray-400">
                        ${index === 0 ? 'Just now' : 'Quiz ' + (index + 1)}
                    </span>
                    <span class="font-semibold ${accuracy >= 0.8 ? 'text-green-400' : 'text-yellow-400'}">
                        ${correctCount}/14 (${Math.round(accuracy * 100)}%)
                    </span>
                </div>
            `;
        }).join('');
    }
}

function displayLevelUpCelebration(newLevel, levelProgress) {
    const banner = document.getElementById('level-up-banner');
    const title = document.getElementById('level-up-title');
    const message = document.getElementById('level-up-message');

    // Level descriptions
    const levelDescriptions = {
        1: 'Beginner',
        2: 'Intermediate',
        3: 'Advanced'
    };

    title.textContent = 'Level Up!';

    if (newLevel === 3) {
        message.textContent = `You've reached Level ${newLevel} - ${levelDescriptions[newLevel]}! Maximum level achieved!`;
    } else {
        message.textContent = `You've reached Level ${newLevel} - ${levelDescriptions[newLevel]}!`;
    }

    banner.classList.remove('hidden');

    // Auto-hide after 10 seconds (but keep in DOM for accessibility)
    setTimeout(() => {
        banner.style.animation = 'fadeOut 1s ease-out forwards';
        setTimeout(() => {
            banner.style.display = 'none';
        }, 1000);
    }, 10000);
}

function displayStreakStatus(accuracy, levelProgress) {
    const banner = document.getElementById('streak-status-banner');
    const content = document.getElementById('streak-status-content');

    if (!banner || !content) return;

    const isPerfect = accuracy >= 1.0;
    const currentStreak = levelProgress.perfect_streak || 0;
    const requiredStreak = levelProgress.required_streak || 5;
    const canLevelUp = levelProgress.can_level_up !== false;

    if (isPerfect && currentStreak > 0 && canLevelUp) {
        // Perfect quiz - streak continues
        banner.classList.remove('hidden');
        content.className = 'rounded-lg p-4 text-center bg-green-900/30 border-2 border-green-500';

        if (currentStreak === requiredStreak - 1) {
            content.innerHTML = `
                <div class="text-2xl mb-2">🔥</div>
                <div class="text-green-400 font-bold text-lg">Perfect! ${currentStreak}/${requiredStreak} streak!</div>
                <div class="text-green-300 text-sm mt-1">One more perfect quiz to level up!</div>
            `;
        } else {
            content.innerHTML = `
                <div class="text-2xl mb-2">✨</div>
                <div class="text-green-400 font-bold text-lg">Perfect! Streak: ${currentStreak}/${requiredStreak}</div>
                <div class="text-green-300 text-sm mt-1">Keep it up! ${requiredStreak - currentStreak} more to level up.</div>
            `;
        }
    } else if (!isPerfect && currentStreak === 0 && levelProgress.previous_streak > 0) {
        // Streak was reset (this quiz broke it)
        banner.classList.remove('hidden');
        content.className = 'rounded-lg p-4 text-center bg-yellow-900/30 border-2 border-yellow-500';
        content.innerHTML = `
            <div class="text-2xl mb-2">💪</div>
            <div class="text-yellow-400 font-bold">Streak reset - but you've got this!</div>
            <div class="text-yellow-300 text-sm mt-1">Start fresh and build your streak again.</div>
        `;
    } else {
        banner.classList.add('hidden');
    }
}

function displayLevelProgress(levelProgress) {
    const section = document.getElementById('level-progress-section');
    const levelInfo = document.getElementById('level-progress-info');
    const progressPercent = document.getElementById('level-progress-percent-summary');
    const progressFill = document.getElementById('level-progress-fill-summary');
    const helperText = document.getElementById('level-progress-helper-summary');

    // Level descriptions
    const levelDescriptions = {
        1: 'Beginner',
        2: 'Intermediate',
        3: 'Advanced'
    };

    // Use correct field names from backend with safe fallbacks
    const progress = levelProgress.progress_percentage || 0;
    const currentStreak = levelProgress.perfect_streak || 0;
    const requiredStreak = levelProgress.required_streak || 5;

    levelInfo.textContent = `Level ${levelProgress.current_level} - ${levelDescriptions[levelProgress.current_level]}`;
    progressPercent.textContent = `${Math.round(progress)}%`;
    progressFill.style.width = `${progress}%`;

    if (levelProgress.current_level === 3 && progress >= 100) {
        helperText.innerHTML = '<span class="text-yellow-400 font-semibold">Max level achieved!</span>';
    } else if (currentStreak > 0) {
        helperText.textContent = `${currentStreak}/${requiredStreak} perfect quizzes - Complete ${requiredStreak - currentStreak} more to level up`;
    } else {
        helperText.textContent = 'Complete perfect quizzes to level up';
    }

    section.classList.remove('hidden');
}

function startNewQuiz() {
    // Clear session storage
    sessionStorage.removeItem('quizSummary');
    window.location.href = '/quiz';
}

// Display summary on page load
displaySummary();
