// Quiz page logic

let currentQuiz = null;
let currentQuestionIndex = 0;
let correctCount = 0;
let awaitingNext = false;
let currentAudio = null;
let questionStartTime = null;  // Track when question was displayed

async function startQuiz() {
    try {
        // Check if there's a saved quiz to resume
        const savedQuizId = sessionStorage.getItem('currentQuizId');

        if (savedQuizId) {
            console.log('Attempting to resume quiz', savedQuizId);
            const resumed = await resumeQuiz(parseInt(savedQuizId));
            if (resumed) {
                return; // Successfully resumed
            }
            // If resume failed, continue to start new quiz
            sessionStorage.removeItem('currentQuizId');
        }

        // Start a new quiz
        const includeAudio = localStorage.getItem('includeAudioQuestions') !== 'false';
        const response = await fetch('/api/quiz/start', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                include_audio: includeAudio
            })
        });

        if (!response.ok) {
            throw new Error('Failed to start quiz');
        }

        const data = await response.json();
        currentQuiz = data;
        currentQuestionIndex = 0;
        correctCount = 0;
        awaitingNext = false;

        // Save quiz ID for resume
        sessionStorage.setItem('currentQuizId', data.quiz_id);

        document.getElementById('loading').classList.add('hidden');
        document.getElementById('quiz-content').classList.remove('hidden');

        displayQuestion();
    } catch (error) {
        console.error('Error starting quiz:', error);
        showError('Failed to start quiz. Please try again.');
    }
}

async function resumeQuiz(quizId) {
    try {
        const response = await fetch(`/api/quiz/${quizId}/state`);

        if (!response.ok) {
            console.log('Cannot resume quiz, will start new one');
            return false;
        }

        const data = await response.json();
        currentQuiz = data;
        correctCount = data.correct_count;

        // Find the first unanswered question
        currentQuestionIndex = data.questions.findIndex(q => !q.is_answered);

        if (currentQuestionIndex === -1) {
            // All questions answered but not completed (edge case)
            console.log('All questions answered, starting new quiz');
            return false;
        }

        awaitingNext = false;

        document.getElementById('loading').classList.add('hidden');
        document.getElementById('quiz-content').classList.remove('hidden');

        console.log(`Resumed quiz at question ${currentQuestionIndex + 1}`);
        displayQuestion();

        return true;
    } catch (error) {
        console.error('Error resuming quiz:', error);
        return false;
    }
}

function displayQuestion() {
    if (!currentQuiz || currentQuestionIndex >= currentQuiz.questions.length) {
        return;
    }

    const question = currentQuiz.questions[currentQuestionIndex];

    // Update progress
    document.getElementById('current-question').textContent = question.question_number;
    document.getElementById('total-questions').textContent = currentQuiz.question_count;
    document.getElementById('correct-count').textContent = correctCount;

    const progress = (currentQuestionIndex / currentQuiz.question_count) * 100;
    document.getElementById('progress-bar').style.width = progress + '%';

    // Update ARIA attributes for accessibility
    updateProgressBarAria();

    // Display question prompt
    document.getElementById('question-prompt').textContent = question.prompt;

    // Display letter or audio player
    const letterDisplay = document.getElementById('letter-display');
    const audioDisplay = document.getElementById('audio-display');

    if (question.is_audio_question) {
        // Show audio player for audio questions
        letterDisplay.classList.add('hidden');
        audioDisplay.classList.remove('hidden');

        // Clean up previous audio to prevent memory leak
        if (currentAudio) {
            currentAudio.pause();
            currentAudio.src = '';  // Release resources
            currentAudio = null;
        }
        currentAudio = new Audio(question.audio_file);

        // Preload and play with a small delay
        currentAudio.load();
        setTimeout(() => {
            currentAudio.play().catch(error => {
                console.error('Error playing audio:', error);
            });
        }, 350); // 350ms delay to ensure audio is buffered
    } else if (question.display_letter) {
        // Show Greek letter
        audioDisplay.classList.add('hidden');
        letterDisplay.classList.remove('hidden');
        document.getElementById('display-letter').textContent = question.display_letter;
    } else {
        // Hide both
        letterDisplay.classList.add('hidden');
        audioDisplay.classList.add('hidden');
    }

    // Display options with dark theme
    const optionsContainer = document.getElementById('options-container');
    optionsContainer.innerHTML = question.options.map((option, index) => `
        <button
            class="quiz-option w-full bg-slate-700 hover:bg-slate-600 border-2 border-slate-600 hover:border-blue-500 rounded-lg p-4 text-center font-bold text-white transition duration-200 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 focus:ring-offset-slate-800"
            onclick="selectAnswer('${escapeHtml(option)}', ${question.question_id}, '${escapeHtml(question.correct_answer)}')"
            data-option="${escapeHtml(option)}"
            data-option-index="${index}"
            aria-label="Answer option: ${escapeHtml(option)}"
        >
            ${escapeHtml(option)}
        </button>
    `).join('');

    // Hide next button
    document.getElementById('next-button-container').classList.add('hidden');
    awaitingNext = false;

    // Start timing for response time analytics
    questionStartTime = Date.now();

    // Focus first option for keyboard users (with slight delay for DOM update)
    setTimeout(() => {
        const firstOption = optionsContainer.querySelector('button');
        if (firstOption) {
            firstOption.focus();
        }
    }, 100);
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

async function selectAnswer(selectedOption, questionId, correctAnswer) {
    if (awaitingNext) {
        return; // Prevent multiple submissions
    }

    awaitingNext = true;

    // Calculate response time
    const responseTimeMs = questionStartTime ? Date.now() - questionStartTime : null;

    // Disable all option buttons
    const buttons = document.querySelectorAll('#options-container button');
    buttons.forEach(btn => {
        btn.disabled = true;
        btn.classList.remove('hover:bg-slate-600', 'hover:border-blue-500');
    });

    try {
        const requestBody = {
            question_id: questionId,
            selected_option: selectedOption
        };
        // Only include response time if we tracked it
        if (responseTimeMs !== null) {
            requestBody.response_time_ms = responseTimeMs;
        }

        const response = await fetch(`/api/quiz/${currentQuiz.quiz_id}/answer`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestBody)
        });

        if (!response.ok) {
            throw new Error('Failed to submit answer');
        }

        const result = await response.json();

        // Update correct count
        if (result.is_correct) {
            correctCount++;
            document.getElementById('correct-count').textContent = correctCount;
        }

        // Highlight buttons based on answer
        buttons.forEach(btn => {
            const btnOption = btn.getAttribute('data-option');

            if (btnOption === correctAnswer) {
                // Always highlight correct answer in green
                btn.classList.add('correct');
                // Add "Correct Answer" label
                const label = document.createElement('span');
                label.className = 'answer-label';
                label.textContent = 'Correct Answer';
                btn.appendChild(label);
            } else if (btnOption === selectedOption && !result.is_correct) {
                // Highlight wrong selection in red
                btn.classList.add('incorrect');
                // Add "Your Answer" label
                const label = document.createElement('span');
                label.className = 'answer-label';
                label.textContent = 'Your Answer';
                btn.appendChild(label);
            } else {
                // Dim other options
                btn.style.opacity = '0.4';
            }
        });

        // Show next button
        const nextButtonContainer = document.getElementById('next-button-container');
        nextButtonContainer.classList.remove('hidden');

        // If last question, change button text and clear saved quiz
        if (result.is_last_question) {
            sessionStorage.removeItem('currentQuizId');
            document.getElementById('next-button').textContent = 'View Summary';
            document.getElementById('next-button').onclick = function() {
                // Store summary data and navigate
                sessionStorage.setItem('quizSummary', JSON.stringify(result.summary));
                window.location.href = '/summary';
            };
            // Auto-advance to summary after 2 seconds
            setTimeout(() => {
                if (awaitingNext) {
                    sessionStorage.setItem('quizSummary', JSON.stringify(result.summary));
                    window.location.href = '/summary';
                }
            }, 2000);
        } else {
            document.getElementById('next-button').textContent = 'Next Question';
            document.getElementById('next-button').onclick = nextQuestion;
            // Auto-advance to next question after 2 seconds
            setTimeout(() => {
                if (awaitingNext) {
                    nextQuestion();
                }
            }, 2000);
        }
    } catch (error) {
        console.error('Error submitting answer:', error);
        showError('Failed to submit answer. Please try again.');
        awaitingNext = false;

        // Re-enable buttons
        buttons.forEach(btn => {
            btn.disabled = false;
            btn.classList.add('hover:bg-slate-600', 'hover:border-blue-500');
        });
    }
}

function nextQuestion() {
    currentQuestionIndex++;
    displayQuestion();
}

function showError(message) {
    alert(message);
}

function playAudioAgain() {
    if (currentAudio) {
        currentAudio.currentTime = 0;
        currentAudio.play().catch(error => {
            console.error('Error playing audio:', error);
        });
    }
}

// Keyboard navigation for answer options
document.addEventListener('keydown', function(e) {
    if (awaitingNext) return;

    const optionsContainer = document.getElementById('options-container');
    if (!optionsContainer) return;

    const buttons = optionsContainer.querySelectorAll('button:not(:disabled)');
    if (buttons.length === 0) return;

    const focusedElement = document.activeElement;
    const currentIndex = Array.from(buttons).indexOf(focusedElement);

    switch (e.key) {
        case 'ArrowDown':
        case 'ArrowRight':
            e.preventDefault();
            if (currentIndex >= 0 && currentIndex < buttons.length - 1) {
                buttons[currentIndex + 1].focus();
            } else if (currentIndex === -1) {
                buttons[0].focus();
            }
            break;
        case 'ArrowUp':
        case 'ArrowLeft':
            e.preventDefault();
            if (currentIndex > 0) {
                buttons[currentIndex - 1].focus();
            } else if (currentIndex === -1) {
                buttons[buttons.length - 1].focus();
            }
            break;
        case '1':
        case '2':
        case '3':
        case '4':
            // Number keys for quick selection
            const optionIndex = parseInt(e.key) - 1;
            if (optionIndex >= 0 && optionIndex < buttons.length) {
                buttons[optionIndex].click();
            }
            break;
    }
});

// Update progress bar ARIA attributes
function updateProgressBarAria() {
    const progressBar = document.getElementById('quiz-progress');
    if (progressBar && currentQuiz) {
        progressBar.setAttribute('aria-valuenow', currentQuestionIndex);
        progressBar.setAttribute('aria-valuemax', currentQuiz.question_count);
    }
}

// Start quiz on page load
startQuiz();
