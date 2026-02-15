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

        const isRed = card.suit === 'h' || card.suit === 'hearts' || card.suit === 'd' || card.suit === 'diamonds';
        const colorClass = isRed ? 'red' : 'black';
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
