// Bet slider, input, and quick-bet state management
class PokerBetControls {
    constructor() {
        this.betAmount = 0;
        this.minBet = 0;
        this.maxBet = 0;
    }

    getBetAmount() {
        return this.betAmount;
    }

    setup(minBet, maxBet, betAmount) {
        this.minBet = minBet;
        this.maxBet = maxBet;
        this.betAmount = betAmount;

        const slider = document.getElementById('bet-slider');
        const amountInput = document.getElementById('bet-amount');

        slider.min = this.minBet;
        slider.max = this.maxBet;
        slider.value = this.betAmount;

        amountInput.min = this.minBet;
        amountInput.max = this.maxBet;
        amountInput.value = this.betAmount;

        this.updateBetButtonText();
    }

    updateBetAmount(sliderValue) {
        const percentage = sliderValue / 100;
        this.betAmount = Math.round(this.minBet + (this.maxBet - this.minBet) * percentage);

        document.getElementById('bet-amount').value = this.betAmount;
        this.updateBetButtonText();
    }

    updateBetFromInput(inputValue) {
        this.betAmount = Math.max(this.minBet, Math.min(this.maxBet, parseInt(inputValue) || this.minBet));

        const percentage = ((this.betAmount - this.minBet) / (this.maxBet - this.minBet)) * 100;
        document.getElementById('bet-slider').value = percentage;

        this.updateBetButtonText();
    }

    updateBetButtonText() {
        const betButton = document.querySelector('.action-btn[data-action="bet"]');
        const raiseButton = document.querySelector('.action-btn[data-action="raise"]');

        if (betButton) {
            betButton.textContent = `Bet $${this.betAmount}`;
        }
        if (raiseButton) {
            raiseButton.textContent = `Raise $${this.betAmount}`;
        }
    }

    handleQuickBet(action, potAmount) {
        switch (action) {
            case 'min':
                this.betAmount = this.minBet;
                break;
            case 'pot':
                this.betAmount = Math.min(potAmount, this.maxBet);
                break;
            case 'half-pot':
                this.betAmount = Math.min(Math.floor(potAmount / 2), this.maxBet);
                break;
            case 'all-in':
                this.betAmount = this.maxBet;
                break;
        }

        document.getElementById('bet-amount').value = this.betAmount;
        const percentage = ((this.betAmount - this.minBet) / (this.maxBet - this.minBet)) * 100;
        document.getElementById('bet-slider').value = percentage;

        this.updateBetButtonText();
    }
}
