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

// Letter Detail Modal
let currentLetterAudio = null;

async function openLetterDetailModal(letterName) {
    const modal = document.getElementById('letter-detail-modal');
    const loading = document.getElementById('letter-modal-loading');
    const content = document.getElementById('letter-modal-content');

    if (!modal) return;

    // Show modal with loading state
    modal.classList.remove('hidden');
    document.body.classList.add('modal-open');
    loading.classList.remove('hidden');
    content.classList.add('hidden');

    try {
        const response = await fetch(`/api/letter/${encodeURIComponent(letterName)}`);
        if (!response.ok) {
            throw new Error('Failed to load letter details');
        }

        const data = await response.json();

        // Update letter display
        document.getElementById('letter-modal-title').textContent = data.letter.name;
        document.getElementById('letter-uppercase').textContent = data.letter.uppercase;
        document.getElementById('letter-lowercase').textContent = data.letter.lowercase;
        document.getElementById('letter-position').textContent = `Letter #${data.letter.position} in the Greek alphabet`;

        // Store audio file for playback
        currentLetterAudio = data.audio_file;

        // Update stats if available
        const statsSection = document.getElementById('letter-stats-section');
        const noStatsSection = document.getElementById('letter-no-stats');

        if (data.user_stats && data.user_stats.seen_count > 0) {
            statsSection.classList.remove('hidden');
            noStatsSection.classList.add('hidden');

            document.getElementById('stat-accuracy').textContent =
                Math.round(data.user_stats.accuracy * 100) + '%';
            document.getElementById('stat-streak').textContent =
                data.user_stats.current_streak;
            document.getElementById('stat-mastery').textContent =
                Math.round(data.user_stats.mastery_score * 100) + '%';
            document.getElementById('stat-seen-count').textContent =
                `Practiced ${data.user_stats.seen_count} times (${data.user_stats.correct_count} correct)`;
        } else {
            statsSection.classList.add('hidden');
            noStatsSection.classList.remove('hidden');
        }

        // Update confused with section
        const confusedSection = document.getElementById('letter-confused-section');
        const confusedList = document.getElementById('confused-letters-list');

        if (data.confused_with && data.confused_with.length > 0) {
            confusedSection.classList.remove('hidden');
            confusedList.innerHTML = data.confused_with.map(letter => `
                <button
                    onclick="openLetterDetailModal('${letter.name}')"
                    class="bg-slate-700 hover:bg-slate-600 border border-slate-600 rounded-lg px-3 py-2 flex items-center gap-2 transition duration-200"
                >
                    <span class="text-white text-xl font-serif">${letter.uppercase}</span>
                    <span class="text-gray-400 text-sm">${letter.name}</span>
                    <span class="text-orange-400 text-xs">${letter.count}x</span>
                </button>
            `).join('');
        } else {
            confusedSection.classList.add('hidden');
        }

        // Show content
        loading.classList.add('hidden');
        content.classList.remove('hidden');

    } catch (error) {
        console.error('Error loading letter details:', error);
        loading.innerHTML = '<p class="text-red-400">Error loading letter details.</p>';
    }
}

function closeLetterDetailModal() {
    const modal = document.getElementById('letter-detail-modal');
    if (modal) {
        modal.classList.add('hidden');
        document.body.classList.remove('modal-open');
    }
    // Stop any playing audio
    if (currentLetterAudio) {
        currentLetterAudio = null;
    }
}

function playLetterAudio() {
    if (currentLetterAudio) {
        const audio = new Audio(currentLetterAudio);
        audio.play().catch(error => {
            console.error('Error playing audio:', error);
        });
    }
}

// Close modal on overlay click
document.addEventListener('DOMContentLoaded', function() {
    const howItWorksModal = document.getElementById('how-it-works-modal');
    if (howItWorksModal) {
        howItWorksModal.addEventListener('click', function(e) {
            if (e.target === howItWorksModal) {
                closeHowItWorksModal();
            }
        });
    }

    const letterModal = document.getElementById('letter-detail-modal');
    if (letterModal) {
        letterModal.addEventListener('click', function(e) {
            if (e.target === letterModal) {
                closeLetterDetailModal();
            }
        });
    }

    // Close modals on Escape key
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            closeHowItWorksModal();
            closeLetterDetailModal();
        }
    });
});
