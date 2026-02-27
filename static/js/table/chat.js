// Chat I/O and hand history announcements
class PokerChat {
    constructor(getSocket, store) {
        this._getSocket = getSocket;
        this._store = store;
        this.holeCardsAnnounced = false;
        this.lastAnnouncedCommunityCardCount = 0;
        this.handHistory = []; // In-session hand history captured from hand_complete events
        this._unreadCount = 0;
    }

    resetForNewHand() {
        this.lastAnnouncedCommunityCardCount = 0;
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

        // Update unread badge if widget is collapsed
        const widget = document.getElementById('chat-widget');
        if (widget && widget.classList.contains('collapsed')) {
            this._unreadCount++;
            this._updateUnreadBadge();
        }
    }

    toggleChat() {
        const widget = document.getElementById('chat-widget');
        if (widget) {
            widget.classList.toggle('collapsed');
            if (!widget.classList.contains('collapsed')) {
                this._unreadCount = 0;
                this._updateUnreadBadge();
                // Scroll to bottom when opening
                const messages = document.getElementById('chat-messages');
                if (messages) messages.scrollTop = messages.scrollHeight;
            }
        }
    }

    _updateUnreadBadge() {
        const badge = document.getElementById('chat-unread-badge');
        if (!badge) return;
        if (this._unreadCount > 0) {
            badge.textContent = this._unreadCount > 99 ? '99+' : this._unreadCount;
            badge.style.display = '';
        } else {
            badge.style.display = 'none';
        }
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
        if (!communityCards || !communityCards.cards) return;

        // Flatten all cards from all subsets
        const allCards = [];
        for (const subsetCards of Object.values(communityCards.cards)) {
            for (const cardInfo of subsetCards) {
                allCards.push(cardInfo.card);
            }
        }

        const lastCount = this.lastAnnouncedCommunityCardCount;
        const currentCount = allCards.length;

        if (currentCount === lastCount || currentCount === 0) return;

        // Announce based on card count transitions (Hold'em-style labels)
        if (lastCount === 0 && currentCount >= 3) {
            const flopCards = allCards.slice(0, 3);
            this.displayChatMessage({
                type: 'game_action',
                action_type: 'deal',
                message: `*** FLOP *** [${flopCards.join(' ')}]`,
                timestamp: new Date().toISOString()
            });
        }

        if (lastCount <= 3 && currentCount >= 4) {
            const board = allCards.slice(0, 3).join(' ');
            this.displayChatMessage({
                type: 'game_action',
                action_type: 'deal',
                message: `*** TURN *** [${board}] [${allCards[3]}]`,
                timestamp: new Date().toISOString()
            });
        }

        if (lastCount <= 4 && currentCount >= 5) {
            const board = allCards.slice(0, 4).join(' ');
            this.displayChatMessage({
                type: 'game_action',
                action_type: 'deal',
                message: `*** RIVER *** [${board}] [${allCards[4]}]`,
                timestamp: new Date().toISOString()
            });
        }

        // For non-standard deals (e.g., 1 or 2 cards at a time), announce generically
        if (lastCount > 0 && currentCount > lastCount && !(lastCount === 0 && currentCount >= 3) &&
            !(lastCount <= 3 && currentCount >= 4) && !(lastCount <= 4 && currentCount >= 5)) {
            const newCards = allCards.slice(lastCount);
            this.displayChatMessage({
                type: 'game_action',
                action_type: 'deal',
                message: `*** COMMUNITY CARDS *** [${newCards.join(' ')}]`,
                timestamp: new Date().toISOString()
            });
        }

        this.lastAnnouncedCommunityCardCount = currentCount;
    }

    captureHandResult(data) {
        // Store hand result from hand_complete event for in-session history
        const entry = {
            hand_number: data.hand_number || this.handHistory.length + 1,
            hand_results: data.hand_results || {},
            timestamp: new Date().toISOString(),
            variant: this._store.gameState?.variant || '',
            betting_structure: this._store.gameState?.betting_structure || '',
        };
        this.handHistory.unshift(entry); // Most recent first
        // Keep at most 50 in-session
        if (this.handHistory.length > 50) {
            this.handHistory.length = 50;
        }
    }
}
