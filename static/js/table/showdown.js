// Showdown display and winning card state
class PokerShowdown {
    constructor(store, displayChatMessage) {
        this._store = store;
        this._displayChatMessage = displayChatMessage;
        this.winningCards = null;
        this.showdownHoleCards = null;
        this.lastDisplayedHandNumber = null;
    }

    getWinningCards() {
        return this.winningCards;
    }

    resetForNewHand() {
        this.winningCards = null;
        this.showdownHoleCards = null;
        this.hideShowdownBar();
        // Hide the legacy table overlay if visible
        const container = document.getElementById('showdown-results-container');
        if (container) {
            container.style.display = 'none';
        }
    }

    hideShowdownBar() {
        const actionBar = document.getElementById('action-bar');
        if (actionBar) {
            actionBar.classList.remove('showdown-active');
        }
        const showdownPanel = document.getElementById('showdown-panel');
        if (showdownPanel) {
            showdownPanel.style.display = 'none';
        }
        const actionPanel = document.getElementById('action-panel');
        if (actionPanel) {
            actionPanel.style.display = '';
        }
    }

    _findPlayer(userId) {
        return this._store.findPlayerByUserId(userId);
    }

    _getPlayerName(userId) {
        const player = this._findPlayer(userId);
        return player ? player.username : userId;
    }

    displayShowdownResults(handResults, onRender) {

        try {
            if (handResults.winning_hands && handResults.winning_hands.length > 0) {
                const winningHand = handResults.winning_hands[0];
                const usedHoleCards = winningHand.used_hole_cards || [];
                const winningHandCards = winningHand.cards || [];
                const communityCardsUsed = winningHandCards.filter(card =>
                    !usedHoleCards.includes(card)
                );

                this.winningCards = {
                    playerId: winningHand.player_id,
                    holeCards: usedHoleCards,
                    communityCards: communityCardsUsed,
                    allCards: winningHandCards
                };

                if (onRender) onRender();
            }

            this._displayShowdownInChat(handResults);

            this._showShowdownInActionBar(handResults);

        } catch (error) {
            console.error('DEBUG: Error in displayShowdownResults:', error);
        }
    }

    _displayShowdownInChat(handResults) {
        const players = this._store.players;

        if (handResults.total_pot) {
            this._displayChatMessage({
                type: 'game_action',
                action_type: 'showdown',
                message: `*** SHOW DOWN *** Total pot: $${handResults.total_pot}`,
                timestamp: new Date().toISOString()
            });
        }

        if (handResults.hands) {
            Object.entries(handResults.hands).forEach(([playerId, playerHands]) => {
                const player = this._findPlayer(playerId);
                const playerName = player ? player.username : playerId;

                if (playerHands && playerHands.length > 0) {
                    const hand = playerHands[0];
                    const playerHoleCards = player && player.cards && player.cards.length > 0
                        ? player.cards
                        : hand.used_hole_cards;
                    const holeCardsDisplay = PokerCardUtils.formatHoleCardsForDisplay(playerHoleCards);

                    this._displayChatMessage({
                        type: 'game_action',
                        action_type: 'showdown',
                        message: `${playerName}: shows [${holeCardsDisplay}] (${hand.hand_description})`,
                        timestamp: new Date().toISOString()
                    });
                }
            });
        }

        if (handResults.pots) {
            handResults.pots.forEach((pot, index) => {
                const potType = pot.pot_type === 'main' ? 'Main pot' : `Side pot-${pot.side_pot_index + 1}`;
                const genericLabels = ['Hand', 'Best Hand', 'Unspecified'];
                const handTypeLabel = pot.hand_type && !genericLabels.includes(pot.hand_type)
                    ? ` [${pot.hand_type}]`
                    : '';
                const winnerNames = pot.winners.map(winnerId => this._getPlayerName(winnerId));

                let potMessage;
                if (pot.split) {
                    const amountPerPlayer = Math.floor(pot.amount / pot.winners.length);
                    potMessage = `${winnerNames.join(' and ')} split the ${potType.toLowerCase()}${handTypeLabel} ($${pot.amount}) - $${amountPerPlayer} each`;
                } else {
                    potMessage = `${winnerNames.join(' and ')} collected $${pot.amount} from ${potType.toLowerCase()}${handTypeLabel}`;
                }

                this._displayChatMessage({
                    type: 'game_action',
                    action_type: 'showdown',
                    message: potMessage,
                    timestamp: new Date().toISOString()
                });
            });
        }

        const communityCards = this._store.gameState?.community_cards || {};
        const boardCards = [];
        const cardsData = communityCards.cards || {};
        for (const subsetCards of Object.values(cardsData)) {
            for (const cardInfo of subsetCards) {
                boardCards.push(cardInfo.card);
            }
        }

        if (boardCards.length > 0) {
            this._displayChatMessage({
                type: 'game_action',
                action_type: 'showdown',
                message: `*** SUMMARY *** Board [${boardCards.join(' ')}]`,
                timestamp: new Date().toISOString()
            });
        }

        if (handResults.winning_hands && handResults.winning_hands.length > 0) {
            const winningHand = handResults.winning_hands[0];
            const playerName = this._getPlayerName(winningHand.player_id);

            this._displayChatMessage({
                type: 'game_action',
                action_type: 'showdown',
                message: `${playerName} wins with ${winningHand.hand_description}`,
                timestamp: new Date().toISOString()
            });
        }
    }

    _showShowdownInActionBar(handResults) {
        const actionBar = document.getElementById('action-bar');
        const actionPanel = document.getElementById('action-panel');
        const showdownPanel = document.getElementById('showdown-panel');

        if (!actionBar || !showdownPanel) {
            console.error('Action bar not found for showdown display');
            return;
        }

        // Render into the dedicated panel — never replace the action panel's
        // contents, or the action buttons are destroyed for the next hand.
        showdownPanel.innerHTML = this._createActionBarShowdownContent(handResults);
        showdownPanel.style.display = '';
        if (actionPanel) {
            actionPanel.style.display = 'none';
        }
        actionBar.classList.add('showdown-active');

        // The ready overlay may have appeared already (socket event race) —
        // hide it while the showdown strip is up. The periodic game-state
        // refresh re-shows it once the strip is dismissed.
        const readyPanel = document.getElementById('ready-panel');
        if (readyPanel) {
            readyPanel.classList.add('hidden');
        }

        // Always auto-dismiss — the ready panel waits for the showdown strip,
        // so it must never stay up indefinitely. Longer window gives time to
        // study results in unusual/split games (the close button dismisses early).
        clearTimeout(this._dismissTimer);
        this._dismissTimer = setTimeout(() => {
            this.hideShowdownBar();
        }, 20000);

        const closeBtn = showdownPanel.querySelector('.showdown-close-btn');
        if (closeBtn) {
            closeBtn.addEventListener('click', () => {
                this.hideShowdownBar();
            });
        }
    }

    _createActionBarShowdownContent(handResults) {
        const GENERIC = ['Hand', 'Best Hand', 'Unspecified', ''];
        const typeClass = (t) => /low/i.test(t) ? 'low' : (/high/i.test(t) ? 'high' : '');
        let html = '<div class="showdown-bar">';

        // Header with total pot
        if (handResults.total_pot) {
            html += `<div class="showdown-bar-header">Showdown &mdash; Pot $${handResults.total_pot}</div>`;
        }

        // Winners grouped by hand type, so the High and Low halves of a split
        // pot are clearly labeled and separated.
        if (handResults.winning_hands && handResults.winning_hands.length > 0) {
            const groups = {};
            const order = [];
            handResults.winning_hands.forEach(wh => {
                const type = (wh.hand_type && !GENERIC.includes(wh.hand_type)) ? wh.hand_type : '';
                if (!(type in groups)) { groups[type] = []; order.push(type); }
                groups[type].push(wh);
            });

            html += '<div class="showdown-bar-winners">';
            order.forEach(type => {
                const tag = type
                    ? `<span class="showdown-type-tag ${typeClass(type)}">${PokerModals.escapeHtml(type)}</span>`
                    : '';
                groups[type].forEach(wh => {
                    const name = this._getPlayerName(wh.player_id);
                    html += `
                        <div class="showdown-bar-winner">
                            <span class="showdown-bar-trophy">\u2605</span>${tag}
                            <strong>${PokerModals.escapeHtml(name)}</strong>
                            <span class="showdown-bar-hand">${PokerModals.escapeHtml(wh.hand_description)}</span>
                        </div>
                    `;
                });
            });
            html += '</div>';
        }

        // Pot breakdown (main / side, with the half it pays and the amount)
        if (handResults.pots && handResults.pots.length > 0) {
            html += '<div class="showdown-bar-pots">';
            handResults.pots.forEach(pot => {
                const winnerNames = pot.winners.map(w => PokerModals.escapeHtml(this._getPlayerName(w)));
                const potType = pot.pot_type === 'main' ? 'Pot' : 'Side pot';
                const type = (pot.hand_type && !GENERIC.includes(pot.hand_type)) ? pot.hand_type : '';
                const tag = type ? ` <span class="showdown-type-tag ${typeClass(type)}">${PokerModals.escapeHtml(type)}</span>` : '';
                const splitNote = pot.split ? ` (split $${Math.floor(pot.amount / pot.winners.length)} each)` : '';
                html += `<span class="showdown-bar-pot">${potType}${tag}: $${pot.amount} \u2192 ${winnerNames.join(', ')}${splitNote}</span>`;
            });
            html += '</div>';
        }

        html += '<button class="showdown-close-btn" title="Close">&times;</button>';
        html += '</div>';
        return html;
    }
}
