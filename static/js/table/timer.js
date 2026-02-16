// Turn timer with auto-fold callback and visual countdown on player seat
class PokerTimer {
    constructor(onTimeout) {
        this._onTimeout = onTimeout;
        this.timerInterval = null;
        this.timeBank = 30;
        this.totalTime = 30;
        this.currentPlayerId = null;
    }

    start(timeLimit, playerId) {
        this.stop();

        this.timeBank = timeLimit;
        this.totalTime = timeLimit;
        this.currentPlayerId = playerId || null;
        this._updateDisplay();

        this.timerInterval = setInterval(() => {
            if (this.timeBank <= 0) {
                this.stop();
                if (this._onTimeout) {
                    this._onTimeout();
                }
                return;
            }

            this.timeBank--;
            this._updateDisplay();
        }, 1000);
    }

    stop() {
        if (this.timerInterval) {
            clearInterval(this.timerInterval);
            this.timerInterval = null;
        }
        // Clear any existing timer bar
        this._clearTimerBar();
        this.currentPlayerId = null;
    }

    _updateDisplay() {
        // Update the info panel text
        const timerElement = document.getElementById('time-bank');
        if (timerElement) {
            timerElement.textContent = `${this.timeBank}s`;

            if (this.timeBank <= 10) {
                timerElement.style.color = 'var(--danger-color)';
            } else {
                timerElement.style.color = 'white';
            }
        }

        // Update the timer bar on the active player's seat
        this._updateTimerBar();
    }

    _updateTimerBar() {
        // Find the current-turn player seat
        const seat = this.currentPlayerId
            ? document.querySelector(`.player-seat[data-player-id="${this.currentPlayerId}"]`)
            : document.querySelector('.player-info.current-turn')?.closest('.player-seat');

        if (!seat) return;

        let bar = seat.querySelector('.turn-timer-bar');
        if (!bar) {
            bar = document.createElement('div');
            bar.className = 'turn-timer-bar';
            bar.innerHTML = '<div class="turn-timer-fill"></div><span class="turn-timer-text"></span>';
            seat.querySelector('.player-info')?.appendChild(bar);
        }

        const fraction = this.totalTime > 0 ? this.timeBank / this.totalTime : 0;
        const fill = bar.querySelector('.turn-timer-fill');
        const text = bar.querySelector('.turn-timer-text');

        if (fill) {
            fill.style.width = `${fraction * 100}%`;

            // Color transitions: green → yellow → red
            if (fraction > 0.5) {
                fill.style.background = 'var(--success-color)';
            } else if (fraction > 0.25) {
                fill.style.background = '#f0ad4e';
            } else {
                fill.style.background = 'var(--danger-color)';
            }
        }
        if (text) {
            text.textContent = `${this.timeBank}s`;
        }
    }

    _clearTimerBar() {
        document.querySelectorAll('.turn-timer-bar').forEach(bar => bar.remove());
    }
}
