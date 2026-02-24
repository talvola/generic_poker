// Card rendering and parsing utilities
class PokerCardUtils {
    static parseCardString(cardStr) {
        if (!cardStr || typeof cardStr !== 'string') {
            return null;
        }

        const suit = cardStr.slice(-1).toLowerCase();
        const rank = cardStr.slice(0, -1);

        if (!rank || !suit) {
            return null;
        }

        return { rank, suit };
    }

    static createCardElement(card, isWinning = false) {
        const originalCard = card;
        if (typeof card === 'string') {
            card = PokerCardUtils.parseCardString(card);
        }

        if (!card || !card.rank || !card.suit) {
            return '<div class="card card-back">\u{1F0A0}</div>';
        }

        const suitSymbols = {
            'h': '\u2665',
            'hearts': '\u2665',
            'd': '\u2666',
            'diamonds': '\u2666',
            'c': '\u2663',
            'clubs': '\u2663',
            's': '\u2660',
            'spades': '\u2660'
        };

        const colorClass = PokerCardUtils.getCardColorClass(card.suit);
        const winningClass = isWinning ? ' winning-hand-card' : '';

        return `
            <div class="card ${colorClass}${winningClass}" data-rank="${card.rank}" data-suit="${card.suit}">
                <div class="card-rank">${card.rank}</div>
                <div class="card-suit">${suitSymbols[card.suit] || card.suit}</div>
            </div>
        `;
    }

    static isCardInWinningHand(cardStr, winningCards) {
        if (!winningCards || !cardStr) return false;
        return winningCards.allCards.includes(cardStr);
    }

    static isFourColorDeck() {
        return localStorage.getItem('fourColorDeck') === 'true';
    }

    static setFourColorDeck(enabled) {
        localStorage.setItem('fourColorDeck', enabled ? 'true' : 'false');
    }

    static getCardColorClass(suit) {
        const s = suit.toLowerCase();
        if (PokerCardUtils.isFourColorDeck()) {
            if (s === 'h' || s === 'hearts') return 'red';
            if (s === 'd' || s === 'diamonds') return 'blue';
            if (s === 'c' || s === 'clubs') return 'green';
            return 'black'; // spades
        }
        const isRed = s === 'h' || s === 'hearts' || s === 'd' || s === 'diamonds';
        return isRed ? 'red' : 'black';
    }

    static formatCardsForDisplay(cards) {
        if (!cards || cards.length === 0) return '';
        return cards.map(card => PokerCardUtils.formatSingleCard(card)).join(' ');
    }

    static formatHoleCardsForDisplay(holeCards) {
        if (!holeCards || holeCards.length === 0) return '';
        return holeCards.map(card => PokerCardUtils.formatSingleCard(card)).join(' ');
    }

    static formatSingleCard(card) {
        if (typeof card === 'string') {
            return card;
        } else if (card && card.rank && card.suit) {
            const suitMap = {
                'hearts': 'h', 'h': 'h',
                'diamonds': 'd', 'd': 'd',
                'clubs': 'c', 'c': 'c',
                'spades': 's', 's': 's'
            };
            return `${card.rank}${suitMap[card.suit] || card.suit}`;
        }
        return String(card);
    }
}
