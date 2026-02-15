// Chat I/O and hand history announcements
class PokerChat {
    constructor(getSocket, store) {
        this._getSocket = getSocket;
        this._store = store;
        this.holeCardsAnnounced = false;
        this.lastAnnouncedCommunityCards = {};
    }

    resetForNewHand() {
        this.lastAnnouncedCommunityCards = {};
        this.holeCardsAnnounced = false;
    }

    sendChatMessage() {
        const input = document.getElementById('chat-input');
        const message = input.value.trim();

        if (!message) return;

        this._getSocket().emit('chat_message', {
            table_id: this._store.tableId,
            message: message
        });

        input.value = '';
    }

    displayChatMessage(data) {
        console.log('DEBUG: Displaying chat message:', data);
        const messagesContainer = document.getElementById('chat-messages');
        const messageElement = document.createElement('div');

        if (data.type === 'system') {
            messageElement.className = 'chat-message system';
            messageElement.innerHTML = `<div class="message-text">${PokerModals.escapeHtml(data.message)}</div>`;
        } else if (data.type === 'game_action') {
            messageElement.className = 'chat-message game-action';
            const timestamp = new Date(data.timestamp).toLocaleTimeString();

            let actionClass = '';
            if (data.action_type === 'forced_bet') {
                actionClass = 'forced-bet';
            } else if (data.action_type === 'player_action') {
                actionClass = 'player-action';
            } else if (data.action_type === 'deal') {
                actionClass = 'deal-action';
            } else if (data.action_type === 'phase_change') {
                actionClass = 'phase-change';
            } else if (data.action_type === 'showdown') {
                actionClass = 'showdown-action';
            }

            messageElement.innerHTML = `
                <div class="game-action-content ${actionClass}">
                    <span class="action-message">${PokerModals.escapeHtml(data.message)}</span>
                    <span class="action-timestamp">${timestamp}</span>
                </div>
            `;
        } else {
            messageElement.className = 'chat-message player';
            const timeValue = data.timestamp || data.created_at;
            const timestamp = timeValue ? new Date(timeValue).toLocaleTimeString() : '';
            messageElement.innerHTML = `
                <div class="message-header">
                    <span class="chat-username">${PokerModals.escapeHtml(data.username || 'Unknown')}</span>
                    <span class="chat-timestamp">${timestamp}</span>
                </div>
                <div class="message-text">${PokerModals.escapeHtml(data.message)}</div>
            `;
        }

        messagesContainer.appendChild(messageElement);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    toggleChat() {
        const chatSection = document.getElementById('chat-section');
        chatSection.classList.toggle('collapsed');
    }

    announceHoleCards() {
        if (this.holeCardsAnnounced) return;

        const currentUserId = this._store.currentUser?.id;
        if (!currentUserId) return;

        const myPlayer = this._store.findPlayerByUserId(currentUserId);
        if (!myPlayer || !myPlayer.cards || myPlayer.cards.length === 0) return;

        this.holeCardsAnnounced = true;

        this.displayChatMessage({
            type: 'game_action',
            action_type: 'deal',
            message: '*** HOLE CARDS ***',
            timestamp: new Date().toISOString()
        });

        const cardsDisplay = PokerCardUtils.formatHoleCardsForDisplay(myPlayer.cards);
        this.displayChatMessage({
            type: 'game_action',
            action_type: 'deal',
            message: `Dealt to ${myPlayer.username} [${cardsDisplay}]`,
            timestamp: new Date().toISOString()
        });
    }

    announceCommunityCards(communityCards) {
        if (!communityCards) return;

        const currentCards = {
            flop1: communityCards.flop1 || null,
            flop2: communityCards.flop2 || null,
            flop3: communityCards.flop3 || null,
            turn: communityCards.turn || null,
            river: communityCards.river || null
        };

        const lastCards = this.lastAnnouncedCommunityCards;

        const hasFlop = currentCards.flop1 && currentCards.flop2 && currentCards.flop3;
        const hadFlop = lastCards.flop1 && lastCards.flop2 && lastCards.flop3;

        if (hasFlop && !hadFlop) {
            const flopCards = [currentCards.flop1, currentCards.flop2, currentCards.flop3];
            this.displayChatMessage({
                type: 'game_action',
                action_type: 'deal',
                message: `*** FLOP *** [${flopCards.join(' ')}]`,
                timestamp: new Date().toISOString()
            });
        }

        if (currentCards.turn && !lastCards.turn) {
            const board = [currentCards.flop1, currentCards.flop2, currentCards.flop3].join(' ');
            this.displayChatMessage({
                type: 'game_action',
                action_type: 'deal',
                message: `*** TURN *** [${board}] [${currentCards.turn}]`,
                timestamp: new Date().toISOString()
            });
        }

        if (currentCards.river && !lastCards.river) {
            const board = [currentCards.flop1, currentCards.flop2, currentCards.flop3, currentCards.turn].join(' ');
            this.displayChatMessage({
                type: 'game_action',
                action_type: 'deal',
                message: `*** RIVER *** [${board}] [${currentCards.river}]`,
                timestamp: new Date().toISOString()
            });
        }

        this.lastAnnouncedCommunityCards = { ...currentCards };
    }
}
