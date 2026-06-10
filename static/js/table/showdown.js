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
        console.log('DEBUG: displayShowdownResults called');
        console.log('DEBUG: handResults parameter:', handResults);

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
                console.log('DEBUG: Winning cards set:', this.winningCards);

                if (onRender) onRender();
            }

            console.log('DEBUG: Calling displayShowdownInChat');
            this._displayShowdownInChat(handResults);

            console.log('DEBUG: Calling showShowdownInActionBar');
            this._showShowdownInActionBar(handResults);

            console.log('DEBUG: Showdown display completed successfully');
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
        // so it must never stay up indefinitely
        clearTimeout(this._dismissTimer);
        this._dismissTimer = setTimeout(() => {
            this.hideShowdownBar();
        }, 10000);

        const closeBtn = showdownPanel.querySelector('.showdown-close-btn');
        if (closeBtn) {
            closeBtn.addEventListener('click', () => {
                this.hideShowdownBar();
            });
        }
    }

    _createActionBarShowdownContent(handResults) {
        let html = '<div class="showdown-bar">';

        // Winners section
        if (handResults.winning_hands && handResults.winning_hands.length > 0) {
            handResults.winning_hands.forEach(winningHand => {
                const playerName = this._getPlayerName(winningHand.player_id);
                const genericLabels = ['Hand', 'Best Hand', 'Unspecified'];
                const handTypeLabel = winningHand.hand_type && !genericLabels.includes(winningHand.hand_type)
                    ? ` (${PokerModals.escapeHtml(winningHand.hand_type)})`
                    : '';

                html += `
                    <div class="showdown-bar-winner">
                        <span class="showdown-bar-trophy">\u2605</span>
                        <strong>${PokerModals.escapeHtml(playerName)}</strong> wins${handTypeLabel} with
                        <strong>${PokerModals.escapeHtml(winningHand.hand_description)}</strong>
                    </div>
                `;
            });
        }

        // Pot section
        if (handResults.pots && handResults.pots.length > 0) {
            html += '<div class="showdown-bar-pots">';
            handResults.pots.forEach(pot => {
                const winnerNames = pot.winners.map(winnerId => PokerModals.escapeHtml(this._getPlayerName(winnerId)));
                const potType = pot.pot_type === 'main' ? 'Pot' : 'Side pot';
                const genericLabels = ['Hand', 'Best Hand', 'Unspecified'];
                const handTypeLabel = pot.hand_type && !genericLabels.includes(pot.hand_type)
                    ? ` (${PokerModals.escapeHtml(pot.hand_type)})`
                    : '';
                html += `<span class="showdown-bar-pot">${potType}${handTypeLabel}: $${pot.amount} \u2192 ${winnerNames.join(', ')}</span>`;
            });
            html += '</div>';
        }

        html += '<button class="showdown-close-btn" title="Close">&times;</button>';
        html += '</div>';
        return html;
    }
}
