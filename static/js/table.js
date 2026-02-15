// Enhanced Poker Table JavaScript - Responsive Game Interface
class PokerTable {
    constructor() {
        this.socket = io();
        this.store = new GameStateStore();
        this.store.tableId = this.getTableIdFromUrl();
        this.betControls = new PokerBetControls();
        this.timer = new PokerTimer(() => {
            const foldAction = this.store.validActions.find(a => a.type === 'fold' || a.action_type === 'fold');
            if (foldAction) {
                this.handlePlayerAction(foldAction);
            }
        });
        this.responsive = new PokerResponsive(
            (actionType) => this.handleQuickAction(actionType),
            this.store
        );
        this.showdown = new PokerShowdown(
            this.store,
            (data) => this.chat.displayChatMessage(data)
        );
        this.chat = new PokerChat(() => this.socket, this.store);

        this.init();
    }

    init() {
        this.setupEventListeners();
        this.setupSocketEvents();
        this.responsive.setupTouchSupport();
        this.responsive.setupResponsiveHandlers();
        this.connectToTable();
        // Don't hide loading overlay until we receive game state
    }

    getTableIdFromUrl() {
        const pathParts = window.location.pathname.split('/');
        return pathParts[pathParts.length - 1];
    }

    setupEventListeners() {
        // Leave table
        document.getElementById('leave-table-btn').addEventListener('click', () => {
            PokerModals.showModal('leave-table-modal');
        });

        document.getElementById('confirm-leave-btn').addEventListener('click', () => {
            this.leaveTable();
        });

        // Chat
        document.getElementById('chat-input').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                this.chat.sendChatMessage();
            }
        });

        document.getElementById('send-chat').addEventListener('click', () => {
            this.chat.sendChatMessage();
        });

        document.getElementById('chat-toggle').addEventListener('click', () => {
            this.chat.toggleChat();
        });

        // Bet controls
        document.getElementById('bet-slider').addEventListener('input', (e) => {
            this.betControls.updateBetAmount(e.target.value);
        });

        document.getElementById('bet-amount').addEventListener('input', (e) => {
            this.betControls.updateBetFromInput(e.target.value);
        });

        // Quick bet buttons
        document.querySelectorAll('.quick-bet-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                this.betControls.handleQuickBet(e.target.dataset.action, this.store.potAmount);
            });
        });

        // Mobile action bar
        document.getElementById('mobile-chat-toggle').addEventListener('click', () => {
            this.responsive.toggleMobilePanel('chat');
        });

        document.getElementById('mobile-info-toggle').addEventListener('click', () => {
            this.responsive.toggleMobilePanel('info');
        });

        document.getElementById('mobile-settings-toggle').addEventListener('click', () => {
            this.responsive.toggleMobilePanel('settings');
        });

        // Debug toggle
        document.getElementById('debug-toggle').addEventListener('click', () => {
            this.toggleDebugPanel();
        });

        // Ready button
        const readyBtn = document.getElementById('ready-btn');
        if (readyBtn) {
            readyBtn.addEventListener('click', () => {
                this.toggleReady();
            });
        }

        // Modal close on background click
        document.querySelectorAll('.modal').forEach(modal => {
            modal.addEventListener('click', (e) => {
                if (e.target === modal) {
                    PokerModals.closeModal(modal.id);
                }
            });
        });

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            this.handleKeyboardShortcuts(e);
        });

        // Window resize
        window.addEventListener('resize', () => {
            this.responsive.handleResize();
        });

        // Orientation change
        window.addEventListener('orientationchange', () => {
            setTimeout(() => {
                this.responsive.handleOrientationChange();
            }, 100);
        });
    }

    setupSocketEvents() {
        this.socket.on('connect', () => {
            console.log('Connected to server');
            PokerModals.hideLoadingOverlay();
            // Re-join the table room (needed after reconnect)
            if (this.store.tableId) {
                this.socket.emit('connect_to_table_room', { table_id: this.store.tableId });
            }
        });

        this.socket.on('disconnect', () => {
            console.log('Disconnected from server');
            PokerModals.showLoadingOverlay('Reconnecting...');
        });

        this.socket.on('game_state', (data) => {
            this.updateGameState(data);
        });

        this.socket.on('player_action', (data) => {
            // Informational broadcast — action messages already come via chat_message event.
            // Do NOT call handlePlayerAction here (that would re-send the action to the server).
            console.log('Player action broadcast:', data);
        });

        this.socket.on('hand_complete', (data) => {
            this.handleHandComplete(data);
        });

        this.socket.on('cards_dealt', (data) => {
            this.animateCardDealing(data);
        });

        this.socket.on('pot_update', (data) => {
            this.updatePotDisplay(data);
        });

        this.socket.on('player_joined', (data) => {
            this.handlePlayerJoined(data);
        });

        this.socket.on('player_left', (data) => {
            this.handlePlayerLeft(data);
        });

        this.socket.on('chat_message', (data) => {
            console.log('DEBUG: Received chat message:', data);
            this.chat.displayChatMessage(data);
        });

        this.socket.on('turn_timer', (data) => {
            this.updateTurnTimer(data);
        });

        this.socket.on('error', (data) => {
            PokerModals.showNotification(data.message || 'An error occurred', 'error');
        });

        this.socket.on('table_joined', (data) => {
            console.log('DEBUG: Successfully joined table room:', data);
            PokerModals.hideLoadingOverlay();
        });

        this.socket.on('table_closed', (data) => {
            PokerModals.showNotification('Table has been closed', 'warning');
            setTimeout(() => {
                window.location.href = '/';
            }, 3000);
        });

        this.socket.on('table_left', (data) => {
            PokerModals.showNotification(data.message || 'Left table successfully', 'success');
            // Redirect to lobby after a short delay
            setTimeout(() => {
                window.location.href = '/';
            }, 1000);
        });

        // Ready status events
        this.socket.on('ready_status_update', (data) => {
            console.log('DEBUG: Received ready status update:', data);
            this.updateReadyStatus(data.ready_status);
        });

        this.socket.on('hand_starting', (data) => {
            console.log('DEBUG: Hand starting:', data);
            // Hide ready panel, show action panel
            this.showReadyPanel(false);
            // Reset tracking for new hand
            this.chat.resetForNewHand();
            this.showdown.resetForNewHand();
        });

        this.socket.on('game_state_update', (data) => {
            console.log('DEBUG: Game state update received:', data);
            this.updateGameState(data);
        });
    }

    // Touch/responsive methods delegated to this.responsive (PokerResponsive)

    connectToTable() {
        this.socket.emit('connect_to_table_room', { table_id: this.store.tableId });

        // Start periodic game state updates
        this.startGameUpdateTimer();

        // Request initial ready status
        this.requestReadyStatus();
    }

    // Ready system methods
    requestReadyStatus() {
        this.socket.emit('request_ready_status', { table_id: this.store.tableId });
    }

    toggleReady() {
        const readyBtn = document.getElementById('ready-btn');
        const isCurrentlyReady = readyBtn.classList.contains('is-ready');

        // Toggle ready state
        this.socket.emit('set_ready', {
            table_id: this.store.tableId,
            ready: !isCurrentlyReady
        });

        // Disable button temporarily to prevent double-clicking
        readyBtn.disabled = true;
        setTimeout(() => {
            readyBtn.disabled = false;
        }, 500);
    }

    updateReadyStatus(readyStatus) {
        console.log('DEBUG: Updating ready status:', readyStatus);

        const readyPanel = document.getElementById('ready-panel');
        const actionPanel = document.getElementById('action-panel');
        const readyBtn = document.getElementById('ready-btn');
        const readyCount = document.getElementById('ready-count');
        const readyPlayers = document.getElementById('ready-players');
        const readyHint = readyPanel.querySelector('.ready-hint');

        if (!readyStatus || !readyStatus.players) {
            return;
        }

        // Update ready count
        if (readyCount) {
            readyCount.textContent = `${readyStatus.ready_count}/${readyStatus.player_count} players ready`;
        }

        // Update hint text
        if (readyHint) {
            if (readyStatus.player_count < readyStatus.min_players) {
                readyHint.textContent = `Need at least ${readyStatus.min_players} players to start`;
            } else if (!readyStatus.all_ready) {
                readyHint.textContent = 'Waiting for all players to be ready';
            } else {
                readyHint.textContent = 'All players ready - starting hand...';
            }
        }

        // Update player indicators
        if (readyPlayers) {
            readyPlayers.innerHTML = '';
            readyStatus.players.forEach(player => {
                const indicator = document.createElement('div');
                indicator.className = `ready-player-indicator ${player.is_ready ? 'ready' : 'not-ready'}`;
                indicator.innerHTML = `
                    <span class="ready-player-name">${PokerModals.escapeHtml(player.username)}</span>
                    <span class="ready-status-icon">${player.is_ready ? '✓' : '○'}</span>
                `;
                readyPlayers.appendChild(indicator);
            });
        }

        // Update ready button state for current user
        if (readyBtn && this.store.currentUser) {
            const myStatus = readyStatus.players.find(p => p.user_id === this.store.currentUser.id);
            if (myStatus) {
                if (myStatus.is_ready) {
                    readyBtn.classList.add('is-ready');
                    readyBtn.textContent = 'Cancel Ready';
                } else {
                    readyBtn.classList.remove('is-ready');
                    readyBtn.textContent = 'Ready';
                }
            }
        }
    }

    showReadyPanel(show) {
        const readyPanel = document.getElementById('ready-panel');
        const actionPanel = document.getElementById('action-panel');

        if (show) {
            readyPanel.classList.remove('hidden');
            actionPanel.style.display = 'none';
        } else {
            readyPanel.classList.add('hidden');
            actionPanel.style.display = 'block';
        }
    }

    startGameUpdateTimer() {
        // Request game updates every 5 seconds to handle bot actions
        this.gameUpdateInterval = setInterval(() => {
            this.socket.emit('request_game_state', { table_id: this.store.tableId });
        }, 5000);
    }
    
    stopGameUpdateTimer() {
        if (this.gameUpdateInterval) {
            clearInterval(this.gameUpdateInterval);
            this.gameUpdateInterval = null;
        }
    }

    updateGameState(data) {
        console.log('DEBUG: updateGameState called with data:', data);
        console.log('DEBUG: Game phase value:', data.game_phase);
        console.log('DEBUG: Has hand_results:', !!data.hand_results);

        this.store.update(data);

        console.log('DEBUG: currentUser:', this.store.currentUser);
        console.log('DEBUG: current_player:', data.current_player);
        console.log('DEBUG: isMyTurn:', this.store.isMyTurn);

        // Show/hide ready panel based on game phase
        // If no game phase or game is complete/waiting, show ready panel
        if (!data.game_phase || data.game_phase === 'complete' || data.game_phase === 'waiting') {
            this.showReadyPanel(true);
            // Request ready status update
            this.requestReadyStatus();
        } else {
            this.showReadyPanel(false);
        }

        // Showdown display is handled by the hand_complete event (handleHandComplete).
        // No need to duplicate here — game_state_update with phase 'complete' just updates UI state.
        
        // Update debug panel
        this.updateDebugPanel();

        // Hide loading overlay now that we have game state
        PokerModals.hideLoadingOverlay();

        this.renderPlayers();
        this.chat.announceHoleCards();
        this.chat.announceCommunityCards(data.community_cards);
        this.renderCommunityCards(data.community_cards);
        this.updatePotDisplay({ amount: this.store.potAmount, side_pots: data.side_pots });
        this.updateActionButtons();
        this.updateGameInfo();
        this.updateDealerButton(data.dealer_position);

        if (this.store.isMyTurn) {
            this.timer.start(data.time_limit || 30);
            // WebSocket already provides valid_actions in game state - no need for separate API call
        } else {
            this.timer.stop();
        }
    }

    async fetchAndDisplayHandResults() {
        try {
            console.log('DEBUG: Fetching hand results for table:', this.store.tableId);
            const response = await fetch(`/game/sessions/${this.store.tableId}/hand-result`);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            const result = await response.json();

            console.log('DEBUG: Hand result response:', result);

            if (result.success && result.hand_result) {
                // Display the showdown results
                this.showdown.displayShowdownResults(result.hand_result, () => {
                        this.renderPlayers();
                        this.renderCommunityCards(this.store.gameState?.community_cards);
                    });
            } else {
                console.log('DEBUG: No hand results available:', result.error);
            }
        } catch (error) {
            console.error('Failed to fetch hand results:', error);
            PokerModals.showNotification('Failed to load hand results', 'error');
        }
    }

    renderPlayers() {
        const seatsContainer = document.getElementById('player-seats');
        seatsContainer.innerHTML = '';

        // Iterate through players by seat number to maintain proper positioning
        Object.entries(this.store.players).forEach(([seatNumber, player]) => {
            // Convert seat number to 0-based position for CSS (seat 1 = position 0)
            const position = parseInt(seatNumber) - 1;
            const seat = this.createPlayerSeat(player, position);
            seatsContainer.appendChild(seat);
        });
    }

    createPlayerSeat(player, position) {
        const seat = document.createElement('div');
        seat.className = 'player-seat';
        seat.dataset.position = position;
        seat.dataset.playerId = player.id;

        const isCurrentPlayer = player.user_id === this.store.currentUser?.id;
        const isCurrentTurn = this.store.gameState?.current_player === player.id;
        const isActive = player.is_active;
        const isDisconnected = player.is_disconnected;
        const hasFolded = player.has_folded;

        let playerInfoClass = 'player-info';
        if (isActive) playerInfoClass += ' active';
        if (isCurrentTurn) playerInfoClass += ' current-turn';
        if (isDisconnected) playerInfoClass += ' disconnected';
        if (hasFolded) playerInfoClass += ' folded';

        // Build position indicators (D, SB, BB)
        const positionIndicators = this.getPositionIndicators(player.seat_number);

        seat.innerHTML = `
            <div class="${playerInfoClass}">
                <div class="player-name">${PokerModals.escapeHtml(player.username)}</div>
                <div class="player-chips">$${player.chip_stack || player.stack || 0}</div>
                <div class="player-action">${player.last_action || ''}</div>
                ${hasFolded ? '<div class="folded-indicator">FOLDED</div>' : ''}
                ${player.current_bet > 0 ? `<div class="player-bet">$${player.current_bet}</div>` : ''}
                ${positionIndicators}
            </div>
            <div class="player-cards${(player.cards?.length || player.card_count || 0) > 2 ? ' many-cards' : ''}">
                ${this.renderPlayerCards(player, isCurrentPlayer, hasFolded)}
            </div>
        `;

        return seat;
    }

    getPositionIndicators(seatNumber) {
        if (!this.store.gameState) return '';

        const indicators = [];
        const dealerPos = this.store.gameState.dealer_position;
        const sbPos = this.store.gameState.small_blind_position;
        const bbPos = this.store.gameState.big_blind_position;

        // Check if this seat has any position indicator
        if (seatNumber === dealerPos) {
            indicators.push('<span class="position-indicator dealer" title="Dealer">D</span>');
        }
        if (seatNumber === sbPos) {
            indicators.push('<span class="position-indicator small-blind" title="Small Blind">SB</span>');
        }
        if (seatNumber === bbPos) {
            indicators.push('<span class="position-indicator big-blind" title="Big Blind">BB</span>');
        }

        if (indicators.length === 0) return '';

        return `<div class="position-indicators">${indicators.join('')}</div>`;
    }

    renderPlayerCards(player, isCurrentPlayer, hasFolded = false) {
        // If player has folded, don't show any cards (mucked)
        if (hasFolded) {
            return '';
        }

        // Check if this player is the winning player
        const isWinningPlayer = this.showdown.winningCards && this.showdown.winningCards.playerId === player.user_id;

        // Check if we have showdown hole cards for this player (revealed at showdown)
        const showdownCards = this.showdown.showdownHoleCards && this.showdown.showdownHoleCards[player.user_id];

        // If player has visible cards (current player or showdown), display them
        if (player.cards && player.cards.length > 0) {
            return player.cards.map(card => {
                if (isCurrentPlayer || player.cards_visible || showdownCards) {
                    // Check if this specific card was used in the winning hand
                    const isWinningCard = isWinningPlayer && this.showdown.winningCards && this.showdown.winningCards.holeCards.includes(card);
                    return PokerCardUtils.createCardElement(card, isWinningCard);
                } else {
                    return '<div class="card card-back">🂠</div>';
                }
            }).join('');
        }

        // At showdown, if we have revealed hole cards for this player, show them
        if (showdownCards && showdownCards.length > 0) {
            return showdownCards.map(card => {
                const isWinningCard = isWinningPlayer && this.showdown.winningCards && this.showdown.winningCards.holeCards.includes(card);
                return PokerCardUtils.createCardElement(card, isWinningCard);
            }).join('');
        }

        // For other players: show card backs based on card_count
        // This handles the case where we know the player has cards but can't see them
        if (player.card_count && player.card_count > 0) {
            let cardBacks = '';
            for (let i = 0; i < player.card_count; i++) {
                cardBacks += '<div class="card card-back">🂠</div>';
            }
            return cardBacks;
        }

        return '';
    }

    renderCommunityCards(communityCards) {
        if (!communityCards) return;

        const cardSlots = document.querySelectorAll('.card-slot');
        const cardTypes = ['flop1', 'flop2', 'flop3', 'turn', 'river'];

        cardTypes.forEach((cardType, index) => {
            const slot = document.querySelector(`[data-card=\"${cardType}\"]`);
            if (!slot) return;

            if (communityCards[cardType]) {
                const cardStr = communityCards[cardType];
                const isWinningCard = PokerCardUtils.isCardInWinningHand(cardStr, this.showdown.winningCards);
                slot.innerHTML = PokerCardUtils.createCardElement(cardStr, isWinningCard);
                slot.classList.add('has-card');
                if (isWinningCard) {
                    slot.classList.add('winning-card');
                } else {
                    slot.classList.remove('winning-card');
                }
            } else {
                slot.innerHTML = '';
                slot.classList.remove('has-card');
                slot.classList.remove('winning-card');
            }
        });
    }

    /**
     * Check if a card is part of the winning hand
     */
    // Card utilities delegated to PokerCardUtils

    updateActionButtons() {
        const actionButtons = document.getElementById('action-buttons');
        const betControls = document.getElementById('bet-controls');
        
        console.log('DEBUG: updateActionButtons called');
        console.log('DEBUG: isMyTurn:', this.store.isMyTurn);
        console.log('DEBUG: validActions:', this.store.validActions);
        console.log('DEBUG: validActions.length:', this.store.validActions.length);

        if (!this.store.isMyTurn || this.store.validActions.length === 0) {
            actionButtons.innerHTML = '<div class=\"waiting-message\">Waiting for your turn...</div>';
            betControls.style.display = 'none';
            return;
        }

        actionButtons.innerHTML = '';
        let showBetControls = false;

        this.store.validActions.forEach(action => {
            const button = this.createActionButton(action);
            actionButtons.appendChild(button);

            if (action.type === 'bet' || action.type === 'raise') {
                showBetControls = true;
                this.betControls.minBet = action.min_amount || 0;
                this.betControls.maxBet = action.max_amount || 0;
                this.betControls.betAmount = this.betControls.minBet;
            }
        });

        betControls.style.display = showBetControls ? 'block' : 'none';

        if (showBetControls) {
            this.betControls.setup(this.betControls.minBet, this.betControls.maxBet, this.betControls.betAmount);
        }
    }

    createActionButton(action) {
        const button = document.createElement('button');
        const actionType = action.action_type || action.type;
        const actionTypeLower = actionType.toLowerCase();
        
        button.className = `action-btn ${actionTypeLower}`;
        button.dataset.action = actionTypeLower;

        // Use display_text if available, otherwise format the action type
        let buttonText = action.display_text || actionType.charAt(0).toUpperCase() + actionType.slice(1).toLowerCase();

        if (action.type === 'call' && (action.min_amount || action.amount)) {
            buttonText = `Call $${action.min_amount || action.amount}`;
        } else if (action.type === 'bet' || action.type === 'raise') {
            buttonText = `${buttonText} $${this.betControls.getBetAmount()}`;
        }

        button.textContent = buttonText;
        button.addEventListener('click', () => {
            this.handlePlayerAction(action);
        });

        // Add keyboard shortcut hint
        const shortcuts = {
            'fold': 'F',
            'check': 'C',
            'call': 'C',
            'bet': 'B',
            'raise': 'R'
        };

        if (shortcuts[action.type]) {
            button.title = `Press ${shortcuts[action.type]} key`;
        }

        return button;
    }

    // Bet control methods delegated to this.betControls (PokerBetControls)

    handlePlayerAction(action) {
        if (!this.store.isMyTurn) return;

        let actionData = {
            action: action.action_type || action.type
        };

        if ((action.action_type === 'BET' || action.action_type === 'RAISE') ||
            (action.type === 'bet' || action.type === 'raise')) {
            actionData.amount = this.betControls.getBetAmount();
        } else if ((action.action_type?.toLowerCase() === 'call' || action.type?.toLowerCase() === 'call')) {
            // Get call amount from min_amount (WebSocket format) or default_amount/amount (API format)
            actionData.amount = action.min_amount || action.default_amount || action.amount;
        }

        console.log('DEBUG: Sending action:', actionData, 'from action:', action);

        // Send action via HTTP API instead of WebSocket for better reliability
        this.sendPlayerAction(actionData);

        // Disable action buttons to prevent double-clicking
        document.querySelectorAll('.action-btn').forEach(btn => {
            btn.disabled = true;
        });

        this.timer.stop();
    }

    async sendPlayerAction(actionData) {
        try {
            const response = await fetch(`/game/sessions/${this.store.tableId}/action`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(actionData)
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            const result = await response.json();

            if (!result.success) {
                PokerModals.showNotification(result.error || 'Action failed', 'error');
                // Re-enable action buttons on error
                document.querySelectorAll('.action-btn').forEach(btn => {
                    btn.disabled = false;
                });
            } else {
                // Action success — game state will update via WebSocket
                // Game state will be updated via WebSocket events
            }
        } catch (error) {
            console.error('Failed to send player action:', error);
            PokerModals.showNotification('Failed to send action', 'error');
            // Re-enable action buttons on error
            document.querySelectorAll('.action-btn').forEach(btn => {
                btn.disabled = false;
            });
        }
    }

    async requestGameState() {
        try {
            const response = await fetch(`/game/sessions/${this.store.tableId}/state`);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            const result = await response.json();

            if (result.success && result.game_state) {
                this.updateGameState(result.game_state);
            }
        } catch (error) {
            console.error('Failed to get game state:', error);
            PokerModals.showNotification('Failed to refresh game state', 'error');
        }
    }

    async loadAvailableActions() {
        try {
            console.log('DEBUG: Loading available actions for table:', this.store.tableId);
            const response = await fetch(`/game/sessions/${this.store.tableId}/actions`);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            const result = await response.json();

            console.log('DEBUG: Actions response:', result);

            if (result.success) {
                // Normalize: server sends action_type, frontend also uses type
                this.store.validActions = (result.actions || []).map(a => ({
                    ...a,
                    type: a.action_type || a.type,
                    action_type: a.action_type || a.type
                }));
                console.log('DEBUG: Set validActions to:', this.store.validActions);
                this.updateActionButtons();
            }
        } catch (error) {
            console.error('Failed to load available actions:', error);
            PokerModals.showNotification('Failed to load actions', 'error');
        }
    }

    handleQuickAction(actionType) {
        const validAction = this.store.validActions.find(a => a.type === actionType);
        if (validAction) {
            this.handlePlayerAction(validAction);
        }
    }

    animateCardDealing(data) {
        const { cards, target } = data;

        cards.forEach((card, index) => {
            setTimeout(() => {
                const cardElement = document.querySelector(`[data-card=\"${target}\"]`);
                if (cardElement) {
                    const cardHtml = PokerCardUtils.createCardElement(card);
                    cardElement.innerHTML = cardHtml;
                    cardElement.classList.add('has-card');

                    const cardDiv = cardElement.querySelector('.card');
                    if (cardDiv) {
                        cardDiv.classList.add('dealing');
                    }
                }
            }, index * 200);
        });
    }

    updatePotDisplay(data) {
        const potAmount = document.querySelector('.pot-amount');
        const sidePots = document.getElementById('side-pots');

        if (potAmount) {
            potAmount.textContent = `$${data.amount || 0}`;
        }

        if (sidePots && data.side_pots && data.side_pots.length > 0) {
            sidePots.innerHTML = data.side_pots.map(pot =>
                `<div class=\"side-pot\">Side Pot: $${pot.amount}</div>`
            ).join('');
        } else if (sidePots) {
            sidePots.innerHTML = '';
        }

        this.store.potAmount = data.amount || 0;
    }

    updateDealerButton(dealerPosition) {
        const dealerButton = document.getElementById('dealer-button');
        if (!dealerButton) return;

        // Hide dealer button if game hasn't started (waiting phase or no valid position)
        const gamePhase = this.store.gameState?.game_phase;
        if (!gamePhase || gamePhase === 'waiting' || !dealerPosition || dealerPosition <= 0) {
            dealerButton.style.display = 'none';
            return;
        }

        // Show and position the dealer button
        dealerButton.style.display = 'flex';

        // Convert 1-based seat number to 0-based position (seat 1 = position 0)
        const position = dealerPosition - 1;
        const playerSeat = document.querySelector(`[data-position=\"${position}\"]`);

        if (playerSeat) {
            const seatRect = playerSeat.getBoundingClientRect();
            const tableRect = document.querySelector('.poker-table').getBoundingClientRect();

            dealerButton.style.left = `${seatRect.left - tableRect.left + 10}px`;
            dealerButton.style.top = `${seatRect.top - tableRect.top + 10}px`;
        }
    }

    // Timer methods delegated to this.timer (PokerTimer)

    updateGameInfo() {
        document.getElementById('hand-number').textContent = this.store.handNumber;
        document.getElementById('player-count').textContent =
            `${Object.keys(this.store.players).length}/${this.store.gameState?.max_players || 9}`;
    }

    handlePlayerJoined(data) {
        // Handle both formats: {player: {username}} or {user_id, username}
        const username = data.player?.username || data.username || 'A player';
        this.chat.displayChatMessage({
            type: 'system',
            message: `${username} joined the table`,
            timestamp: new Date().toISOString()
        });
        // Request game state update to refresh player list
        this.socket.emit('request_game_state', { table_id: this.store.tableId });
    }

    handlePlayerLeft(data) {
        // Handle both formats: {player: {username}} or {user_id, username}
        const username = data.player?.username || data.username || 'A player';
        this.chat.displayChatMessage({
            type: 'system',
            message: `${username} left the table`,
            timestamp: new Date().toISOString()
        });
        // Request game state update to refresh player list
        this.socket.emit('request_game_state', { table_id: this.store.tableId });
    }

    // Chat methods delegated to this.chat (PokerChat)

    // toggleMobilePanel delegated to this.responsive (PokerResponsive)

    leaveTable() {
        this.stopGameUpdateTimer();
        this.socket.emit('leave_table', { table_id: this.store.tableId });
        PokerModals.closeModal('leave-table-modal');

        setTimeout(() => {
            window.location.href = '/';
        }, 1000);
    }

    handleKeyboardShortcuts(e) {
        if (!this.store.isMyTurn) return;

        // Don't process shortcuts if user is typing in an input
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

        const key = e.key.toLowerCase();
        let action = null;

        switch (key) {
            case 'f':
                action = this.store.validActions.find(a => a.type === 'fold');
                break;
            case 'c':
                action = this.store.validActions.find(a => a.type === 'call' || a.type === 'check');
                break;
            case 'b':
                action = this.store.validActions.find(a => a.type === 'bet');
                break;
            case 'r':
                action = this.store.validActions.find(a => a.type === 'raise');
                break;
            case 'a':
                // All-in
                this.betControls.handleQuickBet('all-in', this.store.potAmount);
                return;
            case 'escape':
                PokerModals.closeAllModals();
                return;
        }

        if (action) {
            e.preventDefault();
            this.handlePlayerAction(action);
        }
    }

    // Resize/orientation/layout methods delegated to this.responsive (PokerResponsive)

    // Modal/notification/loading utilities delegated to PokerModals

    updateDebugPanel() {
        // Update debug information
        document.getElementById('debug-current-player').textContent = 
            this.store.gameState?.current_player || '-';
        document.getElementById('debug-my-turn').textContent = 
            this.store.isMyTurn ? 'Yes' : 'No';
        document.getElementById('debug-game-state').textContent = 
            this.store.gameState?.game_state || '-';
        
        // Format valid actions for display
        const actionsDisplay = this.store.validActions.length > 0 
            ? JSON.stringify(this.store.validActions, null, 2)
            : 'None';
        document.getElementById('debug-actions').textContent = actionsDisplay;
    }

    toggleDebugPanel() {
        const debugContent = document.getElementById('debug-content');
        const isVisible = debugContent.style.display !== 'none';
        debugContent.style.display = isVisible ? 'none' : 'block';
    }

    handleHandComplete(data) {
        console.log('DEBUG: handleHandComplete called with data:', data);

        // Store revealed hole cards for showdown display
        if (data.hand_results && data.hand_results.player_hole_cards) {
            this.showdown.showdownHoleCards = data.hand_results.player_hole_cards;
            console.log('DEBUG: Stored showdown hole cards:', this.showdown.showdownHoleCards);
            // Re-render players to show all cards
            this.renderPlayers();
        }

        // Show detailed hand results if available
        if (data.hand_results) {
            console.log('DEBUG: hand_results found:', data.hand_results);
            // hand_complete is the primary showdown handler — always display.
            // Set lastDisplayedHandNumber to prevent the game_state_update fallback from re-displaying.
            this.showdown.lastDisplayedHandNumber = (this.showdown.lastDisplayedHandNumber || 0) + 1;
            this.showdown.displayShowdownResults(data.hand_results, () => {
                this.renderPlayers();
                this.renderCommunityCards(this.store.gameState?.community_cards);
            });
        } else if (data.winners && data.winners.length > 0) {
            // Fallback to simple winner display
            const winnerNames = data.winners.map(w => w.username).join(', ');
            this.chat.displayChatMessage({
                type: 'system',
                message: `${winnerNames} won ${data.pot_amount}`,
                timestamp: new Date().toISOString()
            });
        }

        // Reset action buttons
        setTimeout(() => {
            this.updateActionButtons();
        }, 2000);
    }

    // Hole/community card announcements delegated to this.chat (PokerChat)

    // Showdown methods delegated to this.showdown (PokerShowdown)
}

// Global functions for modal management (called from HTML)
window.closeModal = function (modalId) {
    PokerModals.closeModal(modalId);
};

// Initialize table when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.pokerTable = new PokerTable();
});

// Add touch-specific CSS
const style = document.createElement('style');
style.textContent = `
    .touch-active {
        transform: scale(0.95) !important;
        opacity: 0.8 !important;
    }
    
    .mobile-layout .side-panel {
        position: fixed;
        top: 0;
        right: -100%;
        height: 100vh;
        width: 300px;
        background: rgba(0, 0, 0, 0.95);
        z-index: 500;
        transition: right 0.3s ease;
    }
    
    .mobile-layout .side-panel.show {
        right: 0;
    }
    
    @media (max-width: 768px) {
        .action-btn {
            touch-action: manipulation;
        }
        
        .bet-slider {
            height: 12px;
        }
        
        .bet-slider::-webkit-slider-thumb {
            width: 24px;
            height: 24px;
        }
        
        .bet-slider::-moz-range-thumb {
            width: 24px;
            height: 24px;
        }
    }
`;
document.head.appendChild(style);

// Additional Enhanced Features and Visual Feedback
class PokerTableEnhancements {
    constructor(pokerTable) {
        this.table = pokerTable;
        this.setupEnhancements();
    }

    setupEnhancements() {
        this.setupCardAnimations();
        this.setupChipAnimations();
        this.setupSoundEffects();
        this.setupVisualFeedback();
        this.setupGestureRecognition();
    }

    setupCardAnimations() {
        // Enhanced card dealing animation
        this.cardDealingQueue = [];
        this.isDealing = false;
    }

    animateCardDeal(cards, target, delay = 200) {
        if (this.isDealing) {
            this.cardDealingQueue.push({ cards, target, delay });
            return;
        }

        this.isDealing = true;

        cards.forEach((card, index) => {
            setTimeout(() => {
                this.dealSingleCard(card, target);

                if (index === cards.length - 1) {
                    setTimeout(() => {
                        this.isDealing = false;
                        this.processCardQueue();
                    }, delay);
                }
            }, index * delay);
        });
    }

    dealSingleCard(card, target) {
        const targetElement = document.querySelector(`[data-card="${target}"]`);
        if (!targetElement) return;

        // Create temporary card element for animation
        const tempCard = document.createElement('div');
        tempCard.className = 'card card-back';
        tempCard.style.position = 'absolute';
        tempCard.style.top = '-100px';
        tempCard.style.left = '50%';
        tempCard.style.transform = 'translateX(-50%) rotate(180deg)';
        tempCard.style.zIndex = '100';

        document.querySelector('.poker-table').appendChild(tempCard);

        // Animate to target position
        setTimeout(() => {
            const targetRect = targetElement.getBoundingClientRect();
            const tableRect = document.querySelector('.poker-table').getBoundingClientRect();

            tempCard.style.transition = 'all 0.5s ease-out';
            tempCard.style.top = `${targetRect.top - tableRect.top}px`;
            tempCard.style.left = `${targetRect.left - tableRect.left}px`;
            tempCard.style.transform = 'rotate(0deg)';

            setTimeout(() => {
                // Flip to show actual card
                tempCard.classList.add('flip-out');

                setTimeout(() => {
                    targetElement.innerHTML = PokerCardUtils.createCardElement(card);
                    targetElement.classList.add('has-card');

                    const newCard = targetElement.querySelector('.card');
                    if (newCard) {
                        newCard.classList.add('flip-in');
                    }

                    tempCard.remove();
                }, 200);
            }, 500);
        }, 50);
    }

    processCardQueue() {
        if (this.cardDealingQueue.length > 0) {
            const next = this.cardDealingQueue.shift();
            this.animateCardDeal(next.cards, next.target, next.delay);
        }
    }

    setupChipAnimations() {
        this.chipAnimationQueue = [];
    }

    animateChipsToPot(fromElement, amount) {
        const potElement = document.querySelector('.pot-info');
        if (!fromElement || !potElement) return;

        const fromRect = fromElement.getBoundingClientRect();
        const potRect = potElement.getBoundingClientRect();

        // Create multiple chip elements for larger bets
        const chipCount = Math.min(Math.ceil(amount / 100), 5);

        for (let i = 0; i < chipCount; i++) {
            setTimeout(() => {
                this.createChipAnimation(fromRect, potRect);
            }, i * 100);
        }

        // Update pot amount with animation
        setTimeout(() => {
            const potAmount = document.querySelector('.pot-amount');
            if (potAmount) {
                potAmount.classList.add('growing');
                setTimeout(() => {
                    potAmount.classList.remove('growing');
                }, 500);
            }
        }, chipCount * 100 + 500);
    }

    createChipAnimation(fromRect, toRect) {
        const chip = document.createElement('div');
        chip.className = 'chip-animation';
        chip.style.left = `${fromRect.left + fromRect.width / 2}px`;
        chip.style.top = `${fromRect.top + fromRect.height / 2}px`;

        document.body.appendChild(chip);

        // Animate to pot
        setTimeout(() => {
            chip.style.transition = 'all 1s cubic-bezier(0.25, 0.46, 0.45, 0.94)';
            chip.style.left = `${toRect.left + toRect.width / 2}px`;
            chip.style.top = `${toRect.top + toRect.height / 2}px`;

            setTimeout(() => {
                chip.remove();
            }, 1000);
        }, 50);
    }

    setupSoundEffects() {
        // Placeholder for sound effects
        this.sounds = {
            cardDeal: null,
            chipMove: null,
            buttonClick: null,
            notification: null
        };

        // Load sounds if audio is enabled
        if (this.table.store.gameState?.settings?.audio_enabled) {
            this.loadSounds();
        }
    }

    loadSounds() {
        // Implementation for loading and playing sound effects
        // This would load actual audio files in a real implementation
    }

    playSound(soundName) {
        if (this.sounds[soundName] && this.table.store.gameState?.settings?.audio_enabled) {
            this.sounds[soundName].play().catch(() => {
                // Ignore audio play errors
            });
        }
    }

    setupVisualFeedback() {
        // Enhanced visual feedback for actions
        this.setupActionFeedback();
        this.setupConnectionStatus();
        this.setupPerformanceMonitoring();
    }

    setupActionFeedback() {
        // Add visual feedback when actions are processed
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('action-btn')) {
                this.showActionFeedback(e.target);
            }
        });
    }

    showActionFeedback(button) {
        button.classList.add('processing');

        // Create ripple effect
        const ripple = document.createElement('div');
        ripple.className = 'ripple-effect';
        ripple.style.position = 'absolute';
        ripple.style.borderRadius = '50%';
        ripple.style.background = 'rgba(255, 255, 255, 0.6)';
        ripple.style.transform = 'scale(0)';
        ripple.style.animation = 'ripple 0.6s linear';
        ripple.style.left = '50%';
        ripple.style.top = '50%';
        ripple.style.width = '20px';
        ripple.style.height = '20px';
        ripple.style.marginLeft = '-10px';
        ripple.style.marginTop = '-10px';

        button.style.position = 'relative';
        button.appendChild(ripple);

        setTimeout(() => {
            button.classList.remove('processing');
            ripple.remove();
        }, 600);
    }

    setupConnectionStatus() {
        this.connectionStatus = document.createElement('div');
        this.connectionStatus.className = 'connection-status connected';
        this.connectionStatus.textContent = 'Connected';
        document.body.appendChild(this.connectionStatus);

        // Hide after a few seconds
        setTimeout(() => {
            this.connectionStatus.style.opacity = '0';
        }, 3000);

        // Show/hide based on connection status
        this.table.socket.on('connect', () => {
            this.updateConnectionStatus('connected', 'Connected');
        });

        this.table.socket.on('disconnect', () => {
            this.updateConnectionStatus('disconnected', 'Disconnected');
        });

        this.table.socket.io.on('reconnect_attempt', () => {
            this.updateConnectionStatus('reconnecting', 'Reconnecting...');
        });
    }

    updateConnectionStatus(status, text) {
        this.connectionStatus.className = `connection-status ${status}`;
        this.connectionStatus.textContent = text;
        this.connectionStatus.style.opacity = '1';

        if (status === 'connected') {
            setTimeout(() => {
                this.connectionStatus.style.opacity = '0';
            }, 3000);
        }
    }

    setupPerformanceMonitoring() {
        // Monitor performance and adjust animations accordingly
        this.performanceMetrics = {
            frameRate: 60,
            lastFrameTime: performance.now(),
            frameCount: 0
        };

        this.monitorPerformance();
    }

    monitorPerformance() {
        const now = performance.now();
        this.performanceMetrics.frameCount++;

        if (now - this.performanceMetrics.lastFrameTime >= 1000) {
            this.performanceMetrics.frameRate = this.performanceMetrics.frameCount;
            this.performanceMetrics.frameCount = 0;
            this.performanceMetrics.lastFrameTime = now;

            // Adjust animations based on performance
            if (this.performanceMetrics.frameRate < 30) {
                this.reduceAnimations();
            } else if (this.performanceMetrics.frameRate > 50) {
                this.enableFullAnimations();
            }
        }

        requestAnimationFrame(() => this.monitorPerformance());
    }

    reduceAnimations() {
        document.documentElement.style.setProperty('--transition', 'all 0.1s ease');
        document.body.classList.add('reduced-animations');
    }

    enableFullAnimations() {
        document.documentElement.style.setProperty('--transition', 'all 0.3s ease');
        document.body.classList.remove('reduced-animations');
    }

    setupGestureRecognition() {
        // Enhanced gesture recognition for mobile
        if (!('ontouchstart' in window)) return;

        this.gestureState = {
            startX: 0,
            startY: 0,
            startTime: 0,
            isGesturing: false
        };

        this.setupAdvancedGestures();
    }

    setupAdvancedGestures() {
        let touchStartTime = 0;
        let touchCount = 0;

        document.addEventListener('touchstart', (e) => {
            touchStartTime = Date.now();
            touchCount = e.touches.length;

            this.gestureState.startX = e.touches[0].clientX;
            this.gestureState.startY = e.touches[0].clientY;
            this.gestureState.startTime = touchStartTime;
            this.gestureState.isGesturing = true;
        });

        document.addEventListener('touchend', (e) => {
            if (!this.gestureState.isGesturing) return;

            const touchEndTime = Date.now();
            const touchDuration = touchEndTime - touchStartTime;
            const deltaX = e.changedTouches[0].clientX - this.gestureState.startX;
            const deltaY = e.changedTouches[0].clientY - this.gestureState.startY;

            // Double tap detection
            if (touchDuration < 300 && Math.abs(deltaX) < 10 && Math.abs(deltaY) < 10) {
                this.handleDoubleTap(e);
            }

            // Long press detection
            if (touchDuration > 500 && Math.abs(deltaX) < 10 && Math.abs(deltaY) < 10) {
                this.handleLongPress(e);
            }

            // Multi-touch gestures
            if (touchCount > 1) {
                this.handleMultiTouch(e, touchCount);
            }

            this.gestureState.isGesturing = false;
        });
    }

    handleDoubleTap(e) {
        // Double tap to check/call
        if (this.table.store.isMyTurn) {
            const callAction = this.table.store.validActions.find(a => a.type === 'call' || a.type === 'check');
            if (callAction) {
                this.table.handlePlayerAction(callAction);
            }
        }
    }

    handleLongPress(e) {
        // Long press to show action menu or hand strength
        if (e.target.closest('.player-cards')) {
            this.showHandStrength(e.target.closest('.player-cards'));
        }
    }

    handleMultiTouch(e, touchCount) {
        // Two-finger tap for all-in
        if (touchCount === 2 && this.table.store.isMyTurn) {
            this.table.betControls.handleQuickBet('all-in', this.table.store.potAmount);
        }
    }

    showHandStrength(playerCards) {
        // Show hand strength indicator (placeholder)
        const strengthIndicator = document.createElement('div');
        strengthIndicator.className = 'hand-strength';
        strengthIndicator.textContent = 'Calculating...';

        playerCards.appendChild(strengthIndicator);

        setTimeout(() => {
            strengthIndicator.remove();
        }, 2000);
    }

    // Utility methods for enhanced features
    createRippleEffect(element, x, y) {
        const ripple = document.createElement('div');
        const rect = element.getBoundingClientRect();
        const size = Math.max(rect.width, rect.height);

        ripple.style.width = ripple.style.height = size + 'px';
        ripple.style.left = (x - rect.left - size / 2) + 'px';
        ripple.style.top = (y - rect.top - size / 2) + 'px';
        ripple.className = 'ripple';

        element.appendChild(ripple);

        setTimeout(() => {
            ripple.remove();
        }, 600);
    }

    showTooltip(element, text, duration = 2000) {
        const tooltip = document.createElement('div');
        tooltip.className = 'tooltip';
        tooltip.textContent = text;
        tooltip.style.position = 'absolute';
        tooltip.style.background = 'rgba(0, 0, 0, 0.8)';
        tooltip.style.color = 'white';
        tooltip.style.padding = '0.5rem';
        tooltip.style.borderRadius = '4px';
        tooltip.style.fontSize = '0.8rem';
        tooltip.style.zIndex = '1000';
        tooltip.style.pointerEvents = 'none';

        const rect = element.getBoundingClientRect();
        tooltip.style.left = rect.left + rect.width / 2 + 'px';
        tooltip.style.top = rect.top - 40 + 'px';
        tooltip.style.transform = 'translateX(-50%)';

        document.body.appendChild(tooltip);

        setTimeout(() => {
            tooltip.remove();
        }, duration);
    }

    highlightElement(element, duration = 1000) {
        element.style.boxShadow = '0 0 20px rgba(255, 215, 0, 0.8)';
        element.style.transform = 'scale(1.02)';

        setTimeout(() => {
            element.style.boxShadow = '';
            element.style.transform = '';
        }, duration);
    }
}

// Add ripple animation CSS
const rippleStyle = document.createElement('style');
rippleStyle.textContent = `
    @keyframes ripple {
        to {
            transform: scale(4);
            opacity: 0;
        }
    }
    
    .ripple {
        position: absolute;
        border-radius: 50%;
        background: rgba(255, 255, 255, 0.6);
        transform: scale(0);
        animation: ripple 0.6s linear;
        pointer-events: none;
    }
    
    .reduced-animations * {
        animation-duration: 0.1s !important;
        transition-duration: 0.1s !important;
    }
    
    .tooltip {
        animation: fadeIn 0.3s ease;
    }
`;
document.head.appendChild(rippleStyle);

// Extend the main PokerTable class
document.addEventListener('DOMContentLoaded', () => {
    // Wait for the main PokerTable to be initialized
    setTimeout(() => {
        if (window.pokerTable) {
            window.pokerTable.enhancements = new PokerTableEnhancements(window.pokerTable);
        }
    }, 100);
});

// Seat assignment functionality (called from template onclick)
function joinSeat(seatNumber) {
    if (window.pokerTable && window.pokerTable.socket) {
        const buyInAmount = prompt(`Enter buy-in amount (minimum $100):`);

        if (buyInAmount && !isNaN(buyInAmount)) {
            const amount = parseInt(buyInAmount);

            if (amount >= 100) {
                window.pokerTable.socket.emit('join_table', {
                    table_id: window.pokerTable.store.tableId,
                    seat_number: seatNumber,
                    buy_in_amount: amount
                });
            } else {
                alert('Minimum buy-in is $100');
            }
        }
    }
}