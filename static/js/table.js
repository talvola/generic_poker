// Enhanced Poker Table JavaScript - Responsive Game Interface
class PokerTable {
    constructor() {
        this.socket = io();
        this.tableId = this.getTableIdFromUrl();
        this.currentUser = null;
        this.gameState = null;
        this.players = {};
        this.isMyTurn = false;
        this.validActions = [];
        this.betAmount = 0;
        this.minBet = 0;
        this.maxBet = 0;
        this.potAmount = 0;
        this.handNumber = 1;
        this.timeBank = 30;
        this.timerInterval = null;
        this.isMobile = window.innerWidth <= 768;
        this.isLandscape = window.innerHeight < window.innerWidth;
        this.lastDisplayedHandNumber = null; // Track last hand number for showdown display

        this.init();
    }

    init() {
        this.setupEventListeners();
        this.setupSocketEvents();
        this.setupTouchSupport();
        this.setupResponsiveHandlers();
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
            this.showModal('leave-table-modal');
        });

        document.getElementById('confirm-leave-btn').addEventListener('click', () => {
            this.leaveTable();
        });

        // Chat
        document.getElementById('chat-input').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                this.sendChatMessage();
            }
        });

        document.getElementById('send-chat').addEventListener('click', () => {
            this.sendChatMessage();
        });

        document.getElementById('chat-toggle').addEventListener('click', () => {
            this.toggleChat();
        });

        // Bet controls
        document.getElementById('bet-slider').addEventListener('input', (e) => {
            this.updateBetAmount(e.target.value);
        });

        document.getElementById('bet-amount').addEventListener('input', (e) => {
            this.updateBetFromInput(e.target.value);
        });

        // Quick bet buttons
        document.querySelectorAll('.quick-bet-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                this.handleQuickBet(e.target.dataset.action);
            });
        });

        // Mobile action bar
        document.getElementById('mobile-chat-toggle').addEventListener('click', () => {
            this.toggleMobilePanel('chat');
        });

        document.getElementById('mobile-info-toggle').addEventListener('click', () => {
            this.toggleMobilePanel('info');
        });

        document.getElementById('mobile-settings-toggle').addEventListener('click', () => {
            this.toggleMobilePanel('settings');
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
                    this.closeModal(modal.id);
                }
            });
        });

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            this.handleKeyboardShortcuts(e);
        });

        // Window resize
        window.addEventListener('resize', () => {
            this.handleResize();
        });

        // Orientation change
        window.addEventListener('orientationchange', () => {
            setTimeout(() => {
                this.handleOrientationChange();
            }, 100);
        });
    }

    setupSocketEvents() {
        this.socket.on('connect', () => {
            console.log('Connected to server');
            this.showNotification('Connected to table', 'success');
        });

        this.socket.on('disconnect', () => {
            console.log('Disconnected from server');
            this.showNotification('Disconnected from server', 'error');
            this.showLoadingOverlay('Reconnecting...');
        });

        this.socket.on('game_state', (data) => {
            this.updateGameState(data);
        });

        this.socket.on('player_action', (data) => {
            this.handlePlayerAction(data);
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
            this.displayChatMessage(data);
        });

        this.socket.on('turn_timer', (data) => {
            this.updateTurnTimer(data);
        });

        this.socket.on('error', (data) => {
            this.showNotification(data.message || 'An error occurred', 'error');
        });

        this.socket.on('table_joined', (data) => {
            console.log('DEBUG: Successfully joined table room:', data);
            this.hideLoadingOverlay();
            this.showNotification('Connected to table', 'success');
        });

        this.socket.on('table_closed', (data) => {
            this.showNotification('Table has been closed', 'warning');
            setTimeout(() => {
                window.location.href = '/lobby';
            }, 3000);
        });

        this.socket.on('table_left', (data) => {
            this.showNotification(data.message || 'Left table successfully', 'success');
            // Redirect to lobby after a short delay
            setTimeout(() => {
                window.location.href = '/lobby';
            }, 1000);
        });

        // Ready status events
        this.socket.on('ready_status_update', (data) => {
            console.log('DEBUG: Received ready status update:', data);
            this.updateReadyStatus(data.ready_status);
        });

        this.socket.on('hand_starting', (data) => {
            console.log('DEBUG: Hand starting:', data);
            this.showNotification(data.message || 'Hand starting...', 'success');
            // Hide ready panel, show action panel
            this.showReadyPanel(false);
        });

        this.socket.on('game_state_update', (data) => {
            console.log('DEBUG: Game state update received:', data);
            this.updateGameState(data);
        });
    }

    setupTouchSupport() {
        if (!('ontouchstart' in window)) return;

        // Add touch event listeners for action buttons
        document.addEventListener('touchstart', (e) => {
            if (e.target.classList.contains('action-btn')) {
                e.target.classList.add('touch-active');
            }
        });

        document.addEventListener('touchend', (e) => {
            if (e.target.classList.contains('action-btn')) {
                e.target.classList.remove('touch-active');
            }
        });

        // Swipe gestures for quick actions
        let touchStartX = 0;
        let touchStartY = 0;

        document.addEventListener('touchstart', (e) => {
            touchStartX = e.touches[0].clientX;
            touchStartY = e.touches[0].clientY;
        });

        document.addEventListener('touchend', (e) => {
            if (!this.isMyTurn) return;

            const touchEndX = e.changedTouches[0].clientX;
            const touchEndY = e.changedTouches[0].clientY;
            const deltaX = touchEndX - touchStartX;
            const deltaY = touchEndY - touchStartY;

            // Only process swipes on the table area
            if (!e.target.closest('.poker-table')) return;

            // Minimum swipe distance
            if (Math.abs(deltaX) < 50 && Math.abs(deltaY) < 50) return;

            // Determine swipe direction
            if (Math.abs(deltaX) > Math.abs(deltaY)) {
                // Horizontal swipe
                if (deltaX > 0) {
                    // Swipe right - Call/Check
                    this.handleQuickAction('call');
                } else {
                    // Swipe left - Fold
                    this.handleQuickAction('fold');
                }
            } else {
                // Vertical swipe
                if (deltaY < 0) {
                    // Swipe up - Raise/Bet
                    this.handleQuickAction('raise');
                }
            }
        });
    }

    setupResponsiveHandlers() {
        // Handle responsive breakpoints
        this.updateResponsiveLayout();

        // Adjust card sizes based on screen size
        this.adjustCardSizes();

        // Optimize touch targets for mobile
        if (this.isMobile) {
            this.optimizeTouchTargets();
        }
    }

    connectToTable() {
        this.socket.emit('connect_to_table_room', { table_id: this.tableId });

        // Start periodic game state updates
        this.startGameUpdateTimer();

        // Request initial ready status
        this.requestReadyStatus();
    }

    // Ready system methods
    requestReadyStatus() {
        this.socket.emit('request_ready_status', { table_id: this.tableId });
    }

    toggleReady() {
        const readyBtn = document.getElementById('ready-btn');
        const isCurrentlyReady = readyBtn.classList.contains('is-ready');

        // Toggle ready state
        this.socket.emit('set_ready', {
            table_id: this.tableId,
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
                    <span class="ready-player-name">${this.escapeHtml(player.username)}</span>
                    <span class="ready-status-icon">${player.is_ready ? '✓' : '○'}</span>
                `;
                readyPlayers.appendChild(indicator);
            });
        }

        // Update ready button state for current user
        if (readyBtn && this.currentUser) {
            const myStatus = readyStatus.players.find(p => p.user_id === this.currentUser.id);
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
            this.socket.emit('request_game_state', { table_id: this.tableId });
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
        console.log('DEBUG: Game state value:', data.game_state);
        console.log('DEBUG: Has hand_results:', !!data.hand_results);

        this.gameState = data;
        this.currentUser = data.current_user;
        // Convert players array to seat-indexed object for proper rendering
        if (Array.isArray(data.players)) {
            this.players = {};
            data.players.forEach(player => {
                this.players[player.seat_number] = player;
            });
        } else {
            this.players = data.players || {};
        }
        this.isMyTurn = data.current_player === this.currentUser?.id;
        this.validActions = data.valid_actions || [];
        this.potAmount = data.pot_amount || 0;
        this.handNumber = data.hand_number || 1;

        console.log('DEBUG: currentUser:', this.currentUser);
        console.log('DEBUG: current_player:', data.current_player);
        console.log('DEBUG: isMyTurn:', this.isMyTurn);

        // Show/hide ready panel based on game state
        // If no game state or game is complete, show ready panel
        if (!data.game_state || data.game_state === 'complete' || data.game_state === 'waiting') {
            this.showReadyPanel(true);
            // Request ready status update
            this.requestReadyStatus();
        } else {
            this.showReadyPanel(false);
        }
        
        // Check if hand is complete (showdown finished)
        if (data.game_state === 'complete') {
            console.log('DEBUG: Game state is complete');
            if (data.hand_results) {
                // Only display showdown results once per hand
                const currentHandNumber = data.hand_number || this.handNumber;
                if (!this.lastDisplayedHandNumber || this.lastDisplayedHandNumber !== currentHandNumber) {
                    console.log('DEBUG: Hand complete detected with results in game state');
                    console.log('DEBUG: Hand results data:', data.hand_results);
                    console.log('DEBUG: Current players data:', this.players);
                    this.displayShowdownResults(data.hand_results);
                    this.lastDisplayedHandNumber = currentHandNumber;
                } else {
                    console.log('DEBUG: Showdown results already displayed for hand', currentHandNumber);
                }
            } else {
                console.log('DEBUG: Game state is complete but no hand_results found');
            }
        } else {
            console.log('DEBUG: Game state is not complete, it is:', data.game_state);
        }
        
        // Update debug panel
        this.updateDebugPanel();

        // Hide loading overlay now that we have game state
        this.hideLoadingOverlay();

        this.renderPlayers();
        this.renderCommunityCards(data.community_cards);
        this.updatePotDisplay({ amount: this.potAmount, side_pots: data.side_pots });
        this.updateActionButtons();
        this.updateGameInfo();
        this.updateDealerButton(data.dealer_position);

        if (this.isMyTurn) {
            this.startTurnTimer(data.time_limit || 30);
            // Load available actions from the PlayerActionManager
            this.loadAvailableActions();
        } else {
            this.stopTurnTimer();
        }
    }

    async fetchAndDisplayHandResults() {
        try {
            console.log('DEBUG: Fetching hand results for table:', this.tableId);
            const response = await fetch(`/api/games/sessions/${this.tableId}/hand-result`);
            const result = await response.json();
            
            console.log('DEBUG: Hand result response:', result);

            if (result.success && result.hand_result) {
                // Display the showdown results
                this.displayShowdownResults(result.hand_result);
            } else {
                console.log('DEBUG: No hand results available:', result.error);
            }
        } catch (error) {
            console.error('Failed to fetch hand results:', error);
        }
    }

    renderPlayers() {
        const seatsContainer = document.getElementById('player-seats');
        seatsContainer.innerHTML = '';

        // Iterate through players by seat number to maintain proper positioning
        Object.entries(this.players).forEach(([seatNumber, player]) => {
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

        const isCurrentPlayer = player.user_id === this.currentUser?.id;
        const isCurrentTurn = this.gameState?.current_player === player.id;
        const isActive = player.is_active;
        const isDisconnected = player.is_disconnected;
        const hasFolded = player.has_folded;

        let playerInfoClass = 'player-info';
        if (isActive) playerInfoClass += ' active';
        if (isCurrentTurn) playerInfoClass += ' current-turn';
        if (isDisconnected) playerInfoClass += ' disconnected';
        if (hasFolded) playerInfoClass += ' folded';

        seat.innerHTML = `
            <div class=\"${playerInfoClass}\">
                <div class=\"player-name\">${this.escapeHtml(player.username)}</div>
                <div class=\"player-chips\">$${player.chip_stack || player.stack || 0}</div>
                <div class=\"player-action\">${player.last_action || ''}</div>
                ${hasFolded ? '<div class="folded-indicator">FOLDED</div>' : ''}
                ${player.current_bet > 0 ? `<div class=\"player-bet\">$${player.current_bet}</div>` : ''}
            </div>
            <div class=\"player-cards\">
                ${this.renderPlayerCards(player, isCurrentPlayer, hasFolded)}
            </div>
        `;

        return seat;
    }

    renderPlayerCards(player, isCurrentPlayer, hasFolded = false) {
        // If player has folded, don't show any cards (mucked)
        if (hasFolded) {
            return '';
        }

        if (!player.cards || player.cards.length === 0) {
            return '';
        }

        return player.cards.map(card => {
            if (isCurrentPlayer || player.cards_visible) {
                return this.createCardElement(card);
            } else {
                return '<div class=\"card card-back\">🂠</div>';
            }
        }).join('');
    }

    renderCommunityCards(communityCards) {
        if (!communityCards) return;

        const cardSlots = document.querySelectorAll('.card-slot');
        const cardTypes = ['flop1', 'flop2', 'flop3', 'turn', 'river'];

        cardTypes.forEach((cardType, index) => {
            const slot = document.querySelector(`[data-card=\"${cardType}\"]`);
            if (!slot) return;

            if (communityCards[cardType]) {
                slot.innerHTML = this.createCardElement(communityCards[cardType]);
                slot.classList.add('has-card');
            } else {
                slot.innerHTML = '';
                slot.classList.remove('has-card');
            }
        });
    }

    createCardElement(card) {
        if (!card || !card.rank || !card.suit) {
            return '<div class=\"card card-back\">🂠</div>';
        }

        const suitSymbols = {
            'h': '♥',
            'hearts': '♥',
            'd': '♦', 
            'diamonds': '♦',
            'c': '♣',
            'clubs': '♣',
            's': '♠',
            'spades': '♠'
        };

        const isRed = card.suit === 'h' || card.suit === 'hearts' || card.suit === 'd' || card.suit === 'diamonds';
        const colorClass = isRed ? 'red' : 'black';

        return `
            <div class=\"card ${colorClass}\" data-rank=\"${card.rank}\" data-suit=\"${card.suit}\">
                <div class=\"card-rank\">${card.rank}</div>
                <div class=\"card-suit\">${suitSymbols[card.suit] || card.suit}</div>
            </div>
        `;
    }

    updateActionButtons() {
        const actionButtons = document.getElementById('action-buttons');
        const betControls = document.getElementById('bet-controls');
        
        console.log('DEBUG: updateActionButtons called');
        console.log('DEBUG: isMyTurn:', this.isMyTurn);
        console.log('DEBUG: validActions:', this.validActions);
        console.log('DEBUG: validActions.length:', this.validActions.length);

        if (!this.isMyTurn || this.validActions.length === 0) {
            actionButtons.innerHTML = '<div class=\"waiting-message\">Waiting for your turn...</div>';
            betControls.style.display = 'none';
            return;
        }

        actionButtons.innerHTML = '';
        let showBetControls = false;

        this.validActions.forEach(action => {
            const button = this.createActionButton(action);
            actionButtons.appendChild(button);

            if (action.type === 'bet' || action.type === 'raise') {
                showBetControls = true;
                this.minBet = action.min_amount || 0;
                this.maxBet = action.max_amount || 0;
                this.betAmount = this.minBet;
            }
        });

        betControls.style.display = showBetControls ? 'block' : 'none';

        if (showBetControls) {
            this.setupBetControls();
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

        if (action.type === 'call' && action.amount) {
            buttonText = `Call $${action.amount}`;
        } else if (action.type === 'bet' || action.type === 'raise') {
            buttonText = `${buttonText} $${this.betAmount}`;
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

    setupBetControls() {
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
        const betButton = document.querySelector('.action-btn[data-action=\"bet\"]');
        const raiseButton = document.querySelector('.action-btn[data-action=\"raise\"]');

        if (betButton) {
            betButton.textContent = `Bet $${this.betAmount}`;
        }
        if (raiseButton) {
            raiseButton.textContent = `Raise $${this.betAmount}`;
        }
    }

    handleQuickBet(action) {
        switch (action) {
            case 'min':
                this.betAmount = this.minBet;
                break;
            case 'pot':
                this.betAmount = Math.min(this.potAmount, this.maxBet);
                break;
            case 'half-pot':
                this.betAmount = Math.min(Math.floor(this.potAmount / 2), this.maxBet);
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

    handlePlayerAction(action) {
        if (!this.isMyTurn) return;

        let actionData = {
            action: action.action_type || action.type
        };

        if ((action.action_type === 'BET' || action.action_type === 'RAISE') || 
            (action.type === 'bet' || action.type === 'raise')) {
            actionData.amount = this.betAmount;
        } else if ((action.action_type === 'CALL' || action.type === 'call') && 
                   (action.default_amount || action.amount)) {
            actionData.amount = action.default_amount || action.amount;
        }

        // Send action via HTTP API instead of WebSocket for better reliability
        this.sendPlayerAction(actionData);

        // Disable action buttons to prevent double-clicking
        document.querySelectorAll('.action-btn').forEach(btn => {
            btn.disabled = true;
        });

        this.stopTurnTimer();
    }

    async sendPlayerAction(actionData) {
        try {
            const response = await fetch(`/api/games/sessions/${this.tableId}/action`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(actionData)
            });

            const result = await response.json();

            if (!result.success) {
                this.showNotification(result.error || 'Action failed', 'error');
                // Re-enable action buttons on error
                document.querySelectorAll('.action-btn').forEach(btn => {
                    btn.disabled = false;
                });
            } else {
                this.showNotification('Action processed', 'success');
                // Game state will be updated via WebSocket events
            }
        } catch (error) {
            console.error('Failed to send player action:', error);
            this.showNotification('Failed to send action', 'error');
            // Re-enable action buttons on error
            document.querySelectorAll('.action-btn').forEach(btn => {
                btn.disabled = false;
            });
        }
    }

    async requestGameState() {
        try {
            const response = await fetch(`/api/games/sessions/${this.tableId}/state`);
            const result = await response.json();

            if (result.success && result.game_state) {
                this.updateGameState(result.game_state);
            }
        } catch (error) {
            console.error('Failed to get game state:', error);
        }
    }

    async loadAvailableActions() {
        try {
            console.log('DEBUG: Loading available actions for table:', this.tableId);
            const response = await fetch(`/api/games/sessions/${this.tableId}/actions`);
            const result = await response.json();
            
            console.log('DEBUG: Actions response:', result);

            if (result.success) {
                this.validActions = result.actions || [];
                console.log('DEBUG: Set validActions to:', this.validActions);
                this.updateActionButtons();
            }
        } catch (error) {
            console.error('Failed to load available actions:', error);
        }
    }

    handleQuickAction(actionType) {
        const validAction = this.validActions.find(a => a.type === actionType);
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
                    const cardHtml = this.createCardElement(card);
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

        this.potAmount = data.amount || 0;
    }

    updateDealerButton(dealerPosition) {
        const dealerButton = document.getElementById('dealer-button');
        const playerSeat = document.querySelector(`[data-position=\"${dealerPosition}\"]`);

        if (dealerButton && playerSeat) {
            const seatRect = playerSeat.getBoundingClientRect();
            const tableRect = document.querySelector('.poker-table').getBoundingClientRect();

            dealerButton.style.left = `${seatRect.left - tableRect.left + 10}px`;
            dealerButton.style.top = `${seatRect.top - tableRect.top + 10}px`;
        }
    }

    startTurnTimer(timeLimit) {
        this.timeBank = timeLimit;
        this.updateTimerDisplay();

        this.timerInterval = setInterval(() => {
            this.timeBank--;
            this.updateTimerDisplay();

            if (this.timeBank <= 0) {
                this.stopTurnTimer();
                // Auto-fold if time runs out
                const foldAction = this.validActions.find(a => a.type === 'fold');
                if (foldAction) {
                    this.handlePlayerAction(foldAction);
                }
            }
        }, 1000);
    }

    stopTurnTimer() {
        if (this.timerInterval) {
            clearInterval(this.timerInterval);
            this.timerInterval = null;
        }
    }

    updateTimerDisplay() {
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

    updateGameInfo() {
        document.getElementById('hand-number').textContent = this.handNumber;
        document.getElementById('player-count').textContent =
            `${Object.keys(this.players).length}/${this.gameState?.max_players || 9}`;
    }

    handlePlayerJoined(data) {
        this.showNotification(`${data.player.username} joined the table`, 'info');
        this.displayChatMessage({
            type: 'system',
            message: `${data.player.username} joined the table`,
            timestamp: new Date().toISOString()
        });
    }

    handlePlayerLeft(data) {
        this.showNotification(`${data.player.username} left the table`, 'info');
        this.displayChatMessage({
            type: 'system',
            message: `${data.player.username} left the table`,
            timestamp: new Date().toISOString()
        });
    }

    handleHandComplete(data) {
        this.showNotification('Hand complete', 'success');

        // Show hand results
        if (data.winners && data.winners.length > 0) {
            const winnerNames = data.winners.map(w => w.username).join(', ');
            this.displayChatMessage({
                type: 'system',
                message: `${winnerNames} won $${data.pot_amount}`,
                timestamp: new Date().toISOString()
            });
        }

        // Reset action buttons
        setTimeout(() => {
            this.updateActionButtons();
        }, 2000);
    }

    sendChatMessage() {
        const input = document.getElementById('chat-input');
        const message = input.value.trim();

        if (!message) return;

        this.socket.emit('chat_message', {
            table_id: this.tableId,
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
            messageElement.innerHTML = `<div class=\"message-text\">${this.escapeHtml(data.message)}</div>`;
        } else if (data.type === 'game_action') {
            messageElement.className = 'chat-message game-action';
            const timestamp = new Date(data.timestamp).toLocaleTimeString();
            
            // Add special styling for different action types
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
                <div class=\"game-action-content ${actionClass}\">
                    <span class=\"action-message\">${this.escapeHtml(data.message)}</span>
                    <span class=\"action-timestamp\">${timestamp}</span>
                </div>
            `;
        } else {
            messageElement.className = 'chat-message player';
            // Handle both timestamp and created_at fields for compatibility
            const timeValue = data.timestamp || data.created_at;
            const timestamp = timeValue ? new Date(timeValue).toLocaleTimeString() : '';
            messageElement.innerHTML = `
                <div class=\"message-header\">
                    <span class=\"chat-username\">${this.escapeHtml(data.username || 'Unknown')}</span>
                    <span class=\"chat-timestamp\">${timestamp}</span>
                </div>
                <div class=\"message-text\">${this.escapeHtml(data.message)}</div>
            `;
        }

        messagesContainer.appendChild(messageElement);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    toggleChat() {
        const chatSection = document.getElementById('chat-section');
        chatSection.classList.toggle('collapsed');
    }

    toggleMobilePanel(panelType) {
        // Implementation for mobile panel toggling
        const sidePanel = document.getElementById('side-panel');

        if (this.isMobile) {
            sidePanel.style.display = sidePanel.style.display === 'none' ? 'flex' : 'none';
        }
    }

    leaveTable() {
        this.stopGameUpdateTimer();
        this.socket.emit('leave_table', { table_id: this.tableId });
        this.closeModal('leave-table-modal');

        setTimeout(() => {
            window.location.href = '/lobby';
        }, 1000);
    }

    handleKeyboardShortcuts(e) {
        if (!this.isMyTurn) return;

        // Don't process shortcuts if user is typing in an input
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

        const key = e.key.toLowerCase();
        let action = null;

        switch (key) {
            case 'f':
                action = this.validActions.find(a => a.type === 'fold');
                break;
            case 'c':
                action = this.validActions.find(a => a.type === 'call' || a.type === 'check');
                break;
            case 'b':
                action = this.validActions.find(a => a.type === 'bet');
                break;
            case 'r':
                action = this.validActions.find(a => a.type === 'raise');
                break;
            case 'a':
                // All-in
                this.handleQuickBet('all-in');
                return;
            case 'escape':
                this.closeAllModals();
                return;
        }

        if (action) {
            e.preventDefault();
            this.handlePlayerAction(action);
        }
    }

    handleResize() {
        const wasMobile = this.isMobile;
        this.isMobile = window.innerWidth <= 768;

        if (wasMobile !== this.isMobile) {
            this.updateResponsiveLayout();
            this.adjustCardSizes();

            if (this.isMobile) {
                this.optimizeTouchTargets();
            }
        }
    }

    handleOrientationChange() {
        this.isLandscape = window.innerHeight < window.innerWidth;
        this.updateResponsiveLayout();

        // Adjust table size for landscape mode on mobile
        if (this.isMobile && this.isLandscape) {
            const table = document.querySelector('.poker-table');
            if (table) {
                table.style.height = '250px';
            }
        }
    }

    updateResponsiveLayout() {
        const app = document.getElementById('app');

        if (this.isMobile) {
            app.classList.add('mobile-layout');
        } else {
            app.classList.remove('mobile-layout');
        }
    }

    adjustCardSizes() {
        const root = document.documentElement;

        if (this.isMobile) {
            root.style.setProperty('--card-width', '45px');
            root.style.setProperty('--card-height', '63px');
        } else {
            root.style.setProperty('--card-width', '60px');
            root.style.setProperty('--card-height', '84px');
        }
    }

    optimizeTouchTargets() {
        // Ensure touch targets are at least 44px
        const actionButtons = document.querySelectorAll('.action-btn');
        actionButtons.forEach(btn => {
            btn.style.minHeight = '60px';
            btn.style.fontSize = '1.1rem';
        });
    }

    showModal(modalId) {
        const modal = document.getElementById(modalId);
        modal.classList.add('show');

        // Focus first input if available
        const firstInput = modal.querySelector('input, button');
        if (firstInput) {
            setTimeout(() => firstInput.focus(), 100);
        }
    }

    closeModal(modalId) {
        const modal = document.getElementById(modalId);
        modal.classList.remove('show');
    }

    closeAllModals() {
        document.querySelectorAll('.modal.show').forEach(modal => {
            this.closeModal(modal.id);
        });
    }

    showNotification(message, type = 'info', duration = 4000) {
        const container = document.getElementById('notification-container');

        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        notification.innerHTML = `
            ${this.escapeHtml(message)}
            <button class=\"notification-close\" onclick=\"this.parentElement.remove()\">&times;</button>
        `;

        container.appendChild(notification);

        // Animate in
        setTimeout(() => {
            notification.classList.add('show');
        }, 10);

        // Auto-remove
        setTimeout(() => {
            if (notification.parentElement) {
                notification.classList.remove('show');
                setTimeout(() => {
                    if (notification.parentElement) {
                        notification.remove();
                    }
                }, 300);
            }
        }, duration);
    }

    showLoadingOverlay(text = 'Loading...') {
        const overlay = document.getElementById('loading-overlay');
        const loadingText = document.querySelector('.loading-text');

        if (loadingText) {
            loadingText.textContent = text;
        }

        overlay.classList.remove('hidden');
    }

    hideLoadingOverlay() {
        const overlay = document.getElementById('loading-overlay');
        overlay.classList.add('hidden');
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    updateDebugPanel() {
        // Update debug information
        document.getElementById('debug-current-player').textContent = 
            this.gameState?.current_player || '-';
        document.getElementById('debug-my-turn').textContent = 
            this.isMyTurn ? 'Yes' : 'No';
        document.getElementById('debug-game-state').textContent = 
            this.gameState?.game_state || '-';
        
        // Format valid actions for display
        const actionsDisplay = this.validActions.length > 0 
            ? JSON.stringify(this.validActions, null, 2)
            : 'None';
        document.getElementById('debug-actions').textContent = actionsDisplay;
    }

    toggleDebugPanel() {
        const debugContent = document.getElementById('debug-content');
        const isVisible = debugContent.style.display !== 'none';
        debugContent.style.display = isVisible ? 'none' : 'block';
    }

    handleHandComplete(data) {
        this.showNotification('Hand complete', 'success');

        // Show detailed hand results if available
        if (data.hand_results) {
            // Only display showdown results once per hand
            const currentHandNumber = data.hand_number || this.handNumber;
            if (!this.lastDisplayedHandNumber || this.lastDisplayedHandNumber !== currentHandNumber) {
                this.displayShowdownResults(data.hand_results);
                this.lastDisplayedHandNumber = currentHandNumber;
            } else {
                console.log('DEBUG: Showdown results already displayed for hand', currentHandNumber);
            }
        } else if (data.winners && data.winners.length > 0) {
            // Fallback to simple winner display
            const winnerNames = data.winners.map(w => w.username).join(', ');
            this.displayChatMessage({
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

    displayShowdownResults(handResults) {
        console.log('DEBUG: displayShowdownResults called');
        console.log('DEBUG: handResults parameter:', handResults);
        
        try {
            // Display in chat log with detailed information
            console.log('DEBUG: Calling displayShowdownInChat');
            this.displayShowdownInChat(handResults);
            
            // Show visual showdown overlay (optional)
            console.log('DEBUG: Calling showShowdownOverlay');
            this.showShowdownOverlay(handResults);
            
            console.log('DEBUG: Showdown display completed successfully');
        } catch (error) {
            console.error('DEBUG: Error in displayShowdownResults:', error);
        }
    }

    displayShowdownInChat(handResults) {
        // Display pot information
        if (handResults.total_pot) {
            this.displayChatMessage({
                type: 'game_action',
                action_type: 'showdown',
                message: `*** SHOW DOWN *** Total pot: $${handResults.total_pot}`,
                timestamp: new Date().toISOString()
            });
        }

        // Display each player's hand
        if (handResults.hands) {
            Object.entries(handResults.hands).forEach(([playerId, playerHands]) => {
                const player = this.players[Object.keys(this.players).find(key => 
                    this.players[key].user_id === playerId
                )];
                const playerName = player ? player.username : playerId;

                if (playerHands && playerHands.length > 0) {
                    const hand = playerHands[0]; // Use first hand for display
                    const cardsDisplay = this.formatCardsForDisplay(hand.cards);
                    const holeCardsDisplay = this.formatHoleCardsForDisplay(hand.used_hole_cards);
                    
                    let handMessage = `${playerName}: shows [${holeCardsDisplay}] (${hand.hand_description})`;
                    
                    this.displayChatMessage({
                        type: 'game_action',
                        action_type: 'showdown',
                        message: handMessage,
                        timestamp: new Date().toISOString()
                    });
                }
            });
        }

        // Display pot distribution
        if (handResults.pots) {
            handResults.pots.forEach((pot, index) => {
                const potType = pot.pot_type === 'main' ? 'Main pot' : `Side pot-${pot.side_pot_index + 1}`;
                const winnerNames = pot.winners.map(winnerId => {
                    const player = this.players[Object.keys(this.players).find(key => 
                        this.players[key].user_id === winnerId
                    )];
                    return player ? player.username : winnerId;
                });

                let potMessage;
                if (pot.split) {
                    const amountPerPlayer = Math.floor(pot.amount / pot.winners.length);
                    potMessage = `${winnerNames.join(' and ')} split the ${potType.toLowerCase()} ($${pot.amount}) - $${amountPerPlayer} each`;
                } else {
                    potMessage = `${winnerNames.join(' and ')} collected $${pot.amount} from ${potType.toLowerCase()}`;
                }

                this.displayChatMessage({
                    type: 'game_action',
                    action_type: 'showdown',
                    message: potMessage,
                    timestamp: new Date().toISOString()
                });
            });
        }

        // Display summary
        if (handResults.winning_hands && handResults.winning_hands.length > 0) {
            const winningHand = handResults.winning_hands[0];
            const player = this.players[Object.keys(this.players).find(key => 
                this.players[key].user_id === winningHand.player_id
            )];
            const playerName = player ? player.username : winningHand.player_id;

            this.displayChatMessage({
                type: 'game_action',
                action_type: 'showdown',
                message: `*** SUMMARY *** ${playerName} wins with ${winningHand.hand_description}`,
                timestamp: new Date().toISOString()
            });
        }
    }

    formatCardsForDisplay(cards) {
        if (!cards || cards.length === 0) return '';
        return cards.map(card => this.formatSingleCard(card)).join(' ');
    }

    formatHoleCardsForDisplay(holeCards) {
        if (!holeCards || holeCards.length === 0) return '';
        return holeCards.map(card => this.formatSingleCard(card)).join(' ');
    }

    formatSingleCard(card) {
        if (typeof card === 'string') {
            // Handle string format like "As" or "Kh"
            return card;
        } else if (card && card.rank && card.suit) {
            // Handle object format
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

    showShowdownOverlay(handResults) {
        // Show showdown results in the container below the table instead of modal overlay
        const container = document.getElementById('showdown-results-container');
        const content = document.getElementById('showdown-results-content');
        
        if (!container || !content) {
            console.error('Showdown results container not found');
            return;
        }
        
        // Create the showdown content
        content.innerHTML = this.createShowdownContainerContent(handResults);
        
        // Show the container
        container.style.display = 'block';
        
        // Auto-hide after 10 seconds
        setTimeout(() => {
            container.style.display = 'none';
        }, 10000);
        
        // Add close button functionality
        const closeBtn = content.querySelector('.showdown-close-btn');
        if (closeBtn) {
            closeBtn.addEventListener('click', () => {
                container.style.display = 'none';
            });
        }
    }

    createShowdownContainerContent(handResults) {
        let content = `
            <button class="showdown-close-btn" title="Close">&times;</button>
            <div class="showdown-results-header">Showdown Results</div>
            <div class="showdown-results-body">
        `;
        
        // Show winning hands
        if (handResults.winning_hands && handResults.winning_hands.length > 0) {
            handResults.winning_hands.forEach(winningHand => {
                const player = this.players[Object.keys(this.players).find(key => 
                    this.players[key].user_id === winningHand.player_id
                )];
                const playerName = player ? player.username : winningHand.player_id;
                
                content += `
                    <div class="showdown-hand-result showdown-winner">
                        <strong>${this.escapeHtml(playerName)}</strong> wins with <strong>${this.escapeHtml(winningHand.hand_description)}</strong>
                        <br>
                        <span style="font-family: monospace;">${this.formatCardsForDisplay(winningHand.cards)}</span>
                    </div>
                `;
            });
        }
        
        // Show all player hands
        if (handResults.hands) {
            Object.entries(handResults.hands).forEach(([playerId, playerHands]) => {
                const player = this.players[Object.keys(this.players).find(key => 
                    this.players[key].user_id === playerId
                )];
                const playerName = player ? player.username : playerId;
                
                // Skip if this player already shown as winner
                const isWinner = handResults.winning_hands && handResults.winning_hands.some(w => w.player_id === playerId);
                if (!isWinner && playerHands && playerHands.length > 0) {
                    const hand = playerHands[0];
                    content += `
                        <div class="showdown-hand-result">
                            <strong>${this.escapeHtml(playerName)}</strong>: ${this.escapeHtml(hand.hand_description)}
                            <br>
                            <span style="font-family: monospace;">${this.formatCardsForDisplay(hand.cards)}</span>
                        </div>
                    `;
                }
            });
        }
        
        // Show pot distribution
        if (handResults.pots && handResults.pots.length > 0) {
            content += '<div style="margin-top: 1rem; padding-top: 1rem; border-top: 1px solid rgba(255,255,255,0.3);">';
            handResults.pots.forEach(pot => {
                const winnerNames = pot.winners.map(winnerId => {
                    const player = this.players[Object.keys(this.players).find(key => 
                        this.players[key].user_id === winnerId
                    )];
                    return player ? player.username : winnerId;
                });
                
                const potType = pot.pot_type === 'main' ? 'Main pot' : `Side pot`;
                content += `
                    <div style="margin-bottom: 0.5rem;">
                        <strong>${potType}: $${pot.amount}</strong> → ${winnerNames.join(', ')}
                    </div>
                `;
            });
            content += '</div>';
        }
        
        content += '</div>';
        return content;
    }

    createShowdownOverlayContent(handResults) {
        let content = '<div class="showdown-content">';
        content += '<div class="showdown-header">Showdown Results</div>';
        
        // Show winning hands
        if (handResults.winning_hands && handResults.winning_hands.length > 0) {
            content += '<div class="winning-hands">';
            handResults.winning_hands.forEach(winningHand => {
                const player = this.players[Object.keys(this.players).find(key => 
                    this.players[key].user_id === winningHand.player_id
                )];
                const playerName = player ? player.username : winningHand.player_id;
                
                content += `
                    <div class="winning-hand">
                        <div class="winner-name">${this.escapeHtml(playerName)}</div>
                        <div class="winner-hand">${this.escapeHtml(winningHand.hand_description)}</div>
                        <div class="winner-cards">${this.formatCardsForDisplay(winningHand.cards)}</div>
                    </div>
                `;
            });
            content += '</div>';
        }
        
        // Show pot distribution
        if (handResults.pots && handResults.pots.length > 0) {
            content += '<div class="pot-distribution">';
            handResults.pots.forEach(pot => {
                const winnerNames = pot.winners.map(winnerId => {
                    const player = this.players[Object.keys(this.players).find(key => 
                        this.players[key].user_id === winnerId
                    )];
                    return player ? player.username : winnerId;
                });
                
                content += `
                    <div class="pot-award">
                        <span class="pot-winners">${this.escapeHtml(winnerNames.join(', '))}</span>
                        <span class="pot-amount">$${pot.amount}</span>
                    </div>
                `;
            });
            content += '</div>';
        }
        
        content += '<div class="showdown-close">Click to close</div>';
        content += '</div>';
        
        return content;
    }
}

// Global functions for modal management (called from HTML)
window.closeModal = function (modalId) {
    if (window.pokerTable) {
        window.pokerTable.closeModal(modalId);
    }
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
    
    .waiting-message {
        color: rgba(255, 255, 255, 0.7);
        font-style: italic;
        text-align: center;
        padding: 1rem;
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
                    targetElement.innerHTML = this.table.createCardElement(card);
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
        if (this.table.gameState?.settings?.audio_enabled) {
            this.loadSounds();
        }
    }

    loadSounds() {
        // Implementation for loading and playing sound effects
        // This would load actual audio files in a real implementation
    }

    playSound(soundName) {
        if (this.sounds[soundName] && this.table.gameState?.settings?.audio_enabled) {
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

        this.table.socket.on('reconnecting', () => {
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
        if (this.table.isMyTurn) {
            const callAction = this.table.validActions.find(a => a.type === 'call' || a.type === 'check');
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
        if (touchCount === 2 && this.table.isMyTurn) {
            this.table.handleQuickBet('all-in');
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

// Seat assignment functionality
function joinSeat(seatNumber) {
    if (typeof tableGame !== 'undefined' && tableGame.socket) {
        // Show buy-in prompt
        const buyInAmount = prompt(`Enter buy-in amount (minimum $${tableGame.minimumBuyin || 100}):`);

        if (buyInAmount && !isNaN(buyInAmount)) {
            const amount = parseInt(buyInAmount);

            if (amount >= (tableGame.minimumBuyin || 100)) {
                tableGame.socket.emit('join_table', {
                    table_id: tableGame.tableId,
                    seat_number: seatNumber,
                    buy_in_amount: amount
                });
            } else {
                alert(`Minimum buy-in is $${tableGame.minimumBuyin || 100}`);
            }
        }
    }
}

// Enhanced table game class with seat assignment
if (typeof TableGame !== 'undefined') {
    // Add seat assignment methods to existing TableGame class
    TableGame.prototype.handleSeatAssignment = function (data) {
        if (data.success) {
            this.showNotification(`Joined seat ${data.seat_number} with $${data.buy_in_amount}`, 'success');

            // Show seat assignment notification
            this.showSeatAssignmentNotification(data.seat_number, data.buy_in_amount);

            // Update player display
            this.updatePlayerSeats();
        } else {
            this.showNotification(data.message || 'Failed to join seat', 'error');
        }
    };

    TableGame.prototype.showSeatAssignmentNotification = function (seatNumber, buyInAmount) {
        const notification = document.createElement('div');
        notification.className = 'seat-assignment-notification';
        notification.innerHTML = `
            <div>Welcome to Seat ${seatNumber}!</div>
            <div>Buy-in: $${buyInAmount}</div>
        `;

        document.body.appendChild(notification);

        setTimeout(() => {
            if (notification.parentElement) {
                notification.remove();
            }
        }, 3000);
    };

    TableGame.prototype.updatePlayerSeats = function () {
        // This would update the seat display based on current game state
        // For now, just refresh the page to show updated seats
        setTimeout(() => {
            window.location.reload();
        }, 1000);
    };
}