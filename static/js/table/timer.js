// Turn timer with auto-fold callback
class PokerTimer {
    constructor(onTimeout) {
        this._onTimeout = onTimeout;
        this.timerInterval = null;
        this.timeBank = 30;
    }

    start(timeLimit) {
        this.stop();

        this.timeBank = timeLimit;
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
    }

    _updateDisplay() {
        const timerElement = document.getElementById('time-bank');
        if (timerElement) {
            timerElement.textContent = `${this.timeBank}s`;

            if (this.timeBank <= 10) {
                timerElement.style.color = 'var(--danger-color)';
            } else {
                timerElement.style.color = 'white';
            }
        }
    }
}
