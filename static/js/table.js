// Enhanced Poker Table JavaScript - Responsive Game Interface
class PokerTable {
    constructor() {
        this.socket = io();
        this.store = new GameStateStore();
        this.store.tableId = this.getTableIdFromUrl();
        this.betControls = new PokerBetControls();
        this.timer = new PokerTimer(() => {
            // Auto-fold disabled — timer is visual-only for now
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
        this.selectedDiscards = new Set(); // indices of cards selected for discard
        this.drawAction = null; // current draw/discard action option

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

        // Hand History button
        document.getElementById('hand-history-btn').addEventListener('click', () => {
            this.showHandHistory();
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

        this.socket.on('player_leaving', (data) => {
            this.handlePlayerLeaving(data);
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
            // Clear leaving players from previous hand
            if (this.store.leavingPlayers) {
                this.store.leavingPlayers.clear();
            }
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

        // If table allows bots, request to fill empty seats with bots
        this.socket.emit('fill_bots', { table_id: this.store.tableId });
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

        // Start/update timer for the current player's turn (visible to everyone)
        if (data.current_player && data.game_phase && data.game_phase !== 'waiting' && data.game_phase !== 'complete' && data.game_phase !== 'showdown') {
            // Only restart timer if the current player changed (new turn)
            if (this.timer.currentPlayerId !== data.current_player) {
                this.timer.start(data.time_limit || 30, data.current_player);
            } else {
                // Same player, just re-render the bar (DOM was rebuilt by renderPlayers)
                this.timer._updateTimerBar();
            }
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
        const isLeaving = this.store.leavingPlayers?.has(player.user_id);

        let playerInfoClass = 'player-info';
        if (isActive) playerInfoClass += ' active';
        if (isCurrentTurn) playerInfoClass += ' current-turn';
        if (isDisconnected) playerInfoClass += ' disconnected';
        if (hasFolded) playerInfoClass += ' folded';

        // Build position indicators (D, SB, BB)
        const positionIndicators = this.getPositionIndicators(player.seat_number);
        const leavingTag = isLeaving ? ' <span class="leaving-indicator">(leaving)</span>' : '';

        seat.innerHTML = `
            <div class="${playerInfoClass}">
                <div class="player-name">${PokerModals.escapeHtml(player.username)}${leavingTag}</div>
                <div class="player-chips">$${player.chip_stack || player.stack || 0}</div>
                <div class="player-action">${player.last_action || ''}</div>
                ${hasFolded ? '<div class="folded-indicator">FOLDED</div>' : ''}
                ${player.current_bet > 0 ? `<div class="player-bet">$${player.current_bet}</div>` : ''}
                ${positionIndicators}
            </div>
            <div class="player-cards${this._cardCountClasses(player.cards?.length || player.card_count || 0)}">
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

    _cardCountClasses(count) {
        if (count <= 2) return '';
        let classes = ' many-cards';
        if (count >= 5) classes += ` cards-${Math.min(count, 8)}`;
        return classes;
    }

    renderPlayerCards(player, isCurrentPlayer, hasFolded = false) {
        // If player has folded, don't show any cards (mucked)
        if (hasFolded) {
            return '';
        }

        // If player has card subsets (separated cards), render grouped display
        if (player.card_subsets && Object.keys(player.card_subsets).length > 0) {
            const subsetNames = Object.keys(player.card_subsets);
            return subsetNames.map((name, si) => {
                const cards = player.card_subsets[name];
                const cardHtml = cards.map(c => {
                    if (c === null) return '<div class="card card-back">\u{1F0A0}</div>';
                    return PokerCardUtils.createCardElement(c, false);
                }).join('');
                return `<div class="card-subset-group subset-${si}"><div class="subset-label">${name}</div>${cardHtml}</div>`;
            }).join('');
        }

        // Check if this player is the winning player
        const isWinningPlayer = this.showdown.winningCards && this.showdown.winningCards.playerId === player.user_id;

        // Check if we have showdown hole cards for this player (revealed at showdown)
        const showdownCards = this.showdown.showdownHoleCards && this.showdown.showdownHoleCards[player.user_id];

        // Check if draw phase and this is the current user whose turn it is
        const isDrawPhase = this.store.gameState?.game_phase === 'drawing';
        const isMyDrawTurn = isDrawPhase && isCurrentPlayer && this.store.isMyTurn && this.drawAction;

        // If player has visible cards (current player or showdown), display them
        // Cards array may contain null entries for face-down opponent cards (stud/expose)
        if (player.cards && player.cards.length > 0) {
            return player.cards.map((card, index) => {
                // null = face-down card (opponent's hidden card in stud/expose games)
                if (card === null) {
                    return '<div class="card card-back">\u{1F0A0}</div>';
                }
                if (isCurrentPlayer || player.cards_visible || showdownCards) {
                    // Check if this specific card was used in the winning hand
                    const isWinningCard = isWinningPlayer && this.showdown.winningCards && this.showdown.winningCards.holeCards.includes(card);
                    const selectableClass = isMyDrawTurn ? ' selectable' : '';
                    const selectedClass = isMyDrawTurn && this.selectedDiscards.has(index) ? ' selected' : '';
                    const dataAttrs = isMyDrawTurn ? ` data-card-index="${index}" data-card-value="${card}"` : '';
                    return PokerCardUtils.createCardElement(card, isWinningCard)
                        .replace('<div class="card ', `<div class="card${selectableClass}${selectedClass} `)
                        .replace(/data-rank="/, `${dataAttrs} data-rank="`);
                } else {
                    // Face-up card for opponent (mixed visibility)
                    return PokerCardUtils.createCardElement(card, false);
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
        const container = document.getElementById('community-cards');
        if (!container) return;

        // Handle missing or empty data
        if (!communityCards || !communityCards.layout) {
            container.style.display = 'none';
            return;
        }

        const layout = communityCards.layout;
        const cards = communityCards.cards || {};

        switch (layout.type) {
            case 'none':
                container.style.display = 'none';
                return;
            case 'linear':
                this._renderLinearLayout(container, cards, layout);
                break;
            case 'multi-row':
                this._renderMultiRowLayout(container, cards, layout);
                break;
            case 'branching':
                this._renderBranchingLayout(container, cards, layout);
                break;
            case 'grid':
                this._renderGridLayout(container, cards, layout);
                break;
            default:
                this._renderLinearLayout(container, cards, layout); // fallback
        }
        container.style.display = '';
    }

    _renderLinearLayout(container, cards, layout) {
        // Collect all cards from all subsets into one flat list
        const allCards = [];
        for (const subsetCards of Object.values(cards)) {
            for (const cardInfo of subsetCards) {
                allCards.push(cardInfo.card);
            }
        }

        // Determine total slot count: show empty placeholders for undealt cards
        const expectedCards = (layout && layout.expectedCards) || 0;
        const totalSlots = Math.max(allCards.length, expectedCards);

        if (totalSlots === 0) {
            container.style.display = 'none';
            return;
        }

        // Check if we can reuse existing slots
        let cardsContainer = container.querySelector('.cards-container');
        const existingSlots = cardsContainer ? cardsContainer.querySelectorAll('.card-slot') : [];
        const needsRebuild = !cardsContainer || existingSlots.length !== totalSlots;

        if (needsRebuild) {
            container.innerHTML = '';
            const label = document.createElement('div');
            label.className = 'board-label';
            label.textContent = 'Community Cards';
            container.appendChild(label);

            cardsContainer = document.createElement('div');
            cardsContainer.className = 'cards-container';

            for (let i = 0; i < totalSlots; i++) {
                const slot = document.createElement('div');
                slot.className = 'card-slot';
                slot.dataset.cardIndex = i;
                cardsContainer.appendChild(slot);
            }
            container.appendChild(cardsContainer);
        }

        // Update card content in each slot
        const slots = cardsContainer.querySelectorAll('.card-slot');
        for (let i = 0; i < totalSlots; i++) {
            const slot = slots[i];
            if (!slot) continue;

            if (i < allCards.length) {
                const cardStr = allCards[i];
                const isWinningCard = PokerCardUtils.isCardInWinningHand(cardStr, this.showdown.winningCards);
                slot.innerHTML = PokerCardUtils.createCardElement(cardStr, isWinningCard);
                slot.classList.add('has-card');
                if (isWinningCard) {
                    slot.classList.add('winning-card');
                } else {
                    slot.classList.remove('winning-card');
                }
            } else {
                // Empty placeholder slot
                slot.innerHTML = '';
                slot.classList.remove('has-card', 'winning-card');
            }
        }
    }

    _renderMultiRowLayout(container, cards, layout) {
        const rows = layout.rows || [];
        if (rows.length === 0) {
            this._renderLinearLayout(container, cards, layout);
            return;
        }

        // Check if we can reuse existing structure
        const existingRows = container.querySelectorAll('.board-row');
        const needsRebuild = existingRows.length !== rows.length ||
            container.querySelector('.cards-container:not(.board-row .cards-container)');

        if (needsRebuild) {
            container.innerHTML = '';
            for (const row of rows) {
                const rowDiv = document.createElement('div');
                rowDiv.className = 'board-row';
                rowDiv.dataset.subsets = JSON.stringify(row.subsets);

                const label = document.createElement('span');
                label.className = 'board-row-label';
                label.textContent = row.label || '';
                rowDiv.appendChild(label);

                const cardsDiv = document.createElement('div');
                cardsDiv.className = 'cards-container';
                rowDiv.appendChild(cardsDiv);

                container.appendChild(rowDiv);
            }
        }

        // Update cards in each row
        const rowDivs = container.querySelectorAll('.board-row');
        rowDivs.forEach((rowDiv, i) => {
            const row = rows[i];
            if (!row) return;
            const cardsDiv = rowDiv.querySelector('.cards-container');
            const rowCards = this._collectSubsetCards(cards, row.subsets);
            this._fillCardSlots(cardsDiv, rowCards);
        });
    }

    _renderBranchingLayout(container, cards, layout) {
        const rows = layout.rows || [];
        if (rows.length === 0) {
            this._renderLinearLayout(container, cards, layout);
            return;
        }

        // Check rebuild needed
        const existingRows = container.querySelectorAll('.branching-row');
        const needsRebuild = existingRows.length !== rows.length;

        if (needsRebuild) {
            container.innerHTML = '';
            for (const row of rows) {
                const rowDiv = document.createElement('div');
                rowDiv.className = 'branching-row';

                for (const subset of row.subsets) {
                    const group = document.createElement('div');
                    group.className = 'subset-group';
                    group.dataset.subset = subset;

                    const groupLabel = document.createElement('span');
                    groupLabel.className = 'subset-group-label';
                    groupLabel.textContent = subset;
                    group.appendChild(groupLabel);

                    const cardsDiv = document.createElement('div');
                    cardsDiv.className = 'cards-container';
                    group.appendChild(cardsDiv);

                    rowDiv.appendChild(group);
                }
                container.appendChild(rowDiv);
            }
        }

        // Update cards in each subset group
        const branchingRows = container.querySelectorAll('.branching-row');
        branchingRows.forEach((rowDiv, i) => {
            const row = rows[i];
            if (!row) return;
            const groups = rowDiv.querySelectorAll('.subset-group');
            groups.forEach((group, j) => {
                const subset = row.subsets[j];
                if (!subset) return;
                const cardsDiv = group.querySelector('.cards-container');
                const subsetCards = this._collectSubsetCards(cards, [subset]);
                this._fillCardSlots(cardsDiv, subsetCards);
            });
        });
    }

    _renderGridLayout(container, cards, layout) {
        const cells = layout.cells || [];
        const columns = layout.columns || 3;
        if (cells.length === 0) {
            this._renderLinearLayout(container, cards, layout);
            return;
        }

        // Check rebuild
        const existingGrid = container.querySelector('.grid-layout');
        const totalCells = cells.reduce((sum, row) => sum + row.length, 0);
        const existingCells = existingGrid ? existingGrid.querySelectorAll('.grid-cell') : [];
        const needsRebuild = !existingGrid || existingCells.length !== totalCells;

        if (needsRebuild) {
            container.innerHTML = '';
            const grid = document.createElement('div');
            grid.className = 'grid-layout';
            grid.style.gridTemplateColumns = `repeat(${columns}, var(--card-width))`;

            for (const row of cells) {
                for (const cell of row) {
                    const cellDiv = document.createElement('div');
                    cellDiv.className = 'grid-cell';
                    if (cell === null) cellDiv.classList.add('grid-cell-empty');
                    cellDiv.dataset.cell = JSON.stringify(cell);
                    grid.appendChild(cellDiv);
                }
            }
            container.appendChild(grid);
        }

        // Update cards in each cell
        const gridDiv = container.querySelector('.grid-layout');
        const cellDivs = gridDiv.querySelectorAll('.grid-cell');
        let cellIndex = 0;
        for (const row of cells) {
            for (const cell of row) {
                const cellDiv = cellDivs[cellIndex++];
                if (!cellDiv || cell === null) continue;
                const card = this._findGridCard(cards, cell);
                this._fillCardSlots(cellDiv, card ? [card] : [], 1);
            }
        }
    }

    /** Collect cards from multiple subsets into a flat array of card strings */
    _collectSubsetCards(cards, subsets) {
        const result = [];
        for (const subset of subsets) {
            const subsetCards = cards[subset] || [];
            for (const cardInfo of subsetCards) {
                result.push(cardInfo.card);
            }
        }
        return result;
    }

    /** Find a card in the grid by cell descriptor (string subset or array intersection) */
    _findGridCard(cards, cell) {
        if (typeof cell === 'string') {
            // Single subset name - find first card in that subset
            const subsetCards = cards[cell] || [];
            return subsetCards.length > 0 ? subsetCards[0].card : null;
        }
        if (Array.isArray(cell)) {
            // Intersection of multiple subsets - find card present in ALL listed subsets
            // Each subset should have exactly one card at this intersection
            const subsetArrays = cell.map(s => (cards[s] || []).map(c => c.card));
            if (subsetArrays.length === 0 || subsetArrays.some(a => a.length === 0)) return null;
            // Find card that appears in all subset arrays
            const first = subsetArrays[0];
            for (const cardStr of first) {
                if (subsetArrays.every(arr => arr.includes(cardStr))) {
                    return cardStr;
                }
            }
            return null;
        }
        return null;
    }

    /** Fill a container with card slots, reusing existing ones if count matches */
    _fillCardSlots(container, cardStrings, expectedCount) {
        const total = expectedCount || Math.max(cardStrings.length, 1);
        const existingSlots = container.querySelectorAll('.card-slot');

        if (existingSlots.length !== total) {
            container.innerHTML = '';
            for (let i = 0; i < total; i++) {
                const slot = document.createElement('div');
                slot.className = 'card-slot';
                container.appendChild(slot);
            }
        }

        const slots = container.querySelectorAll('.card-slot');
        for (let i = 0; i < total; i++) {
            const slot = slots[i];
            if (!slot) continue;
            if (i < cardStrings.length && cardStrings[i]) {
                const cardStr = cardStrings[i];
                const isWinning = PokerCardUtils.isCardInWinningHand(cardStr, this.showdown.winningCards);
                slot.innerHTML = PokerCardUtils.createCardElement(cardStr, isWinning);
                slot.classList.add('has-card');
                slot.classList.toggle('winning-card', isWinning);
            } else {
                slot.innerHTML = '';
                slot.classList.remove('has-card', 'winning-card');
            }
        }
    }

    /**
     * Check if a card is part of the winning hand
     */
    // Card utilities delegated to PokerCardUtils

    updateActionButtons() {
        const actionButtons = document.getElementById('action-buttons');
        const betControls = document.getElementById('bet-controls');

        if (!this.store.isMyTurn || this.store.validActions.length === 0) {
            actionButtons.innerHTML = '<div class=\"waiting-message\">Waiting for your turn...</div>';
            betControls.style.display = 'none';
            this.drawAction = null;
            return;
        }

        // Check for draw/discard/pass/expose/separate actions
        const drawAction = this.store.validActions.find(a =>
            a.type === 'draw' || a.type === 'discard' || a.type === 'pass' ||
            a.type === 'expose' || a.type === 'separate');
        if (drawAction) {
            this.drawAction = drawAction;
            this.selectedDiscards.clear();
            if (drawAction.type === 'separate') {
                this._renderSeparateControls(actionButtons, drawAction);
            } else {
                this._renderDrawControls(actionButtons, drawAction);
            }
            betControls.style.display = 'none';
            // Re-render players to make cards selectable
            this.renderPlayers();
            this._setupCardSelectionHandlers();
            return;
        }

        // Check for declare action
        const declareAction = this.store.validActions.find(a => a.type === 'declare');
        if (declareAction) {
            this.drawAction = null;
            this._renderDeclareControls(actionButtons, declareAction);
            betControls.style.display = 'none';
            return;
        }

        // Check for choose action
        const chooseAction = this.store.validActions.find(a => a.type === 'choose');
        if (chooseAction) {
            this.drawAction = null;
            this._renderChooseControls(actionButtons, chooseAction);
            betControls.style.display = 'none';
            return;
        }

        this.drawAction = null;
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

    _renderDrawControls(container, drawAction) {
        const minCards = drawAction.min_amount || 0;
        const maxCards = drawAction.max_amount || 0;
        const selected = this.selectedDiscards.size;
        const isPass = drawAction.type === 'pass';
        const isExpose = drawAction.type === 'expose';
        const actionName = isExpose ? 'Expose' : (isPass ? 'Pass' : (drawAction.type === 'discard' ? 'Discard' : 'Draw'));

        let buttonText;
        if (selected === 0) {
            if (isPass) {
                buttonText = `Select ${minCards} card${minCards > 1 ? 's' : ''} to pass`;
            } else if (isExpose) {
                buttonText = `Select ${minCards} card${minCards > 1 ? 's' : ''} to expose`;
            } else {
                buttonText = minCards === 0 ? 'Stand Pat' : `Select at least ${minCards} card${minCards > 1 ? 's' : ''}`;
            }
        } else {
            buttonText = `${actionName} ${selected}`;
        }

        const canSubmit = selected >= minCards && selected <= maxCards;
        let infoText;
        if (isExpose) {
            infoText = `Select card${maxCards > 1 ? 's' : ''} to expose (${minCards === maxCards ? minCards : `${minCards}-${maxCards}`})`;
        } else if (isPass) {
            infoText = `Select card${maxCards > 1 ? 's' : ''} to pass (${minCards === maxCards ? minCards : `${minCards}-${maxCards}`})`;
        } else {
            infoText = `Select cards to discard (${minCards}-${maxCards})`;
        }

        container.innerHTML = `
            <div class="draw-controls">
                <div class="draw-info">${infoText}</div>
                <button class="action-btn primary draw-submit-btn" ${canSubmit ? '' : 'disabled'}>
                    ${buttonText}
                </button>
            </div>
        `;

        container.querySelector('.draw-submit-btn')?.addEventListener('click', () => {
            if (canSubmit) this._submitDrawAction();
        });
    }

    _setupCardSelectionHandlers() {
        // Add click handlers to selectable cards
        document.querySelectorAll('.card.selectable').forEach(cardEl => {
            cardEl.addEventListener('click', (e) => {
                const index = parseInt(cardEl.dataset.cardIndex);
                if (isNaN(index)) return;

                if (this.selectedDiscards.has(index)) {
                    this.selectedDiscards.delete(index);
                    cardEl.classList.remove('selected');
                } else {
                    const maxCards = this.drawAction?.max_amount || 0;
                    if (this.selectedDiscards.size < maxCards) {
                        this.selectedDiscards.add(index);
                        cardEl.classList.add('selected');
                    }
                }

                // Update the draw button
                const actionButtons = document.getElementById('action-buttons');
                if (this.drawAction) {
                    this._renderDrawControls(actionButtons, this.drawAction);
                }
            });
        });
    }

    _submitDrawAction() {
        if (!this.drawAction) return;

        // Get the player's cards from game state
        const myPlayer = this.store.findPlayerByUserId(this.store.currentUser?.id);
        if (!myPlayer || !myPlayer.cards) return;

        // Map selected indices to card strings
        const selectedCards = [];
        this.selectedDiscards.forEach(index => {
            if (myPlayer.cards[index]) {
                selectedCards.push(myPlayer.cards[index]);
            }
        });

        const actionData = {
            action: this.drawAction.type,
            cards: selectedCards
        };

        this.sendPlayerAction(actionData);
        this.selectedDiscards.clear();
        this.drawAction = null;

        // Disable draw button
        document.querySelectorAll('.draw-submit-btn').forEach(btn => btn.disabled = true);
        this.timer.stop();
    }

    _renderSeparateControls(container, separateAction) {
        const subsets = separateAction.metadata?.subsets || [];
        if (subsets.length === 0) {
            // Fallback: render as generic draw
            this._renderDrawControls(container, separateAction);
            return;
        }

        // Initialize separate selections tracking
        if (!this.separateSelections || this.separateSelections.length !== subsets.length) {
            this.separateSelections = subsets.map(() => []);
        }

        // Determine current subset being filled
        let currentSubsetIndex = 0;
        for (let i = 0; i < subsets.length; i++) {
            if (this.separateSelections[i].length < subsets[i].count) {
                currentSubsetIndex = i;
                break;
            }
            if (i === subsets.length - 1) {
                currentSubsetIndex = subsets.length; // All filled
            }
        }

        const allFilled = currentSubsetIndex >= subsets.length;
        const totalAssigned = this.separateSelections.reduce((sum, s) => sum + s.length, 0);
        const totalNeeded = subsets.reduce((sum, s) => sum + s.count, 0);

        // Build info text
        let infoText;
        if (allFilled) {
            infoText = 'All cards assigned. Click Separate to confirm.';
        } else {
            const sub = subsets[currentSubsetIndex];
            const remaining = sub.count - this.separateSelections[currentSubsetIndex].length;
            infoText = `Assign ${remaining} card${remaining > 1 ? 's' : ''} to "${sub.name}"`;
        }

        // Build subset summary
        let summaryHtml = '<div class="separate-summary">';
        subsets.forEach((sub, i) => {
            const filled = this.separateSelections[i].length;
            const isCurrent = i === currentSubsetIndex && !allFilled;
            summaryHtml += `<span class="subset-tag subset-${i}${isCurrent ? ' current' : ''}">${sub.name}: ${filled}/${sub.count}</span>`;
        });
        summaryHtml += '</div>';

        container.innerHTML = `
            <div class="draw-controls">
                <div class="draw-info">${infoText}</div>
                ${summaryHtml}
                <div class="separate-buttons">
                    <button class="action-btn secondary separate-reset-btn" ${totalAssigned === 0 ? 'disabled' : ''}>Reset</button>
                    <button class="action-btn primary draw-submit-btn" ${allFilled ? '' : 'disabled'}>
                        Separate
                    </button>
                </div>
            </div>
        `;

        // Reset button handler
        container.querySelector('.separate-reset-btn')?.addEventListener('click', () => {
            this.separateSelections = subsets.map(() => []);
            this.selectedDiscards.clear();
            this.renderPlayers();
            this._setupSeparateCardHandlers(subsets);
            const actionButtons = document.getElementById('action-buttons');
            this._renderSeparateControls(actionButtons, separateAction);
        });

        // Submit button handler
        container.querySelector('.draw-submit-btn')?.addEventListener('click', () => {
            if (!allFilled) return;
            const myPlayer = this.store.findPlayerByUserId(this.store.currentUser?.id);
            if (!myPlayer || !myPlayer.cards) return;

            // Build flat ordered card list from selections
            const flatCards = [];
            this.separateSelections.forEach(indices => {
                indices.forEach(idx => {
                    if (myPlayer.cards[idx]) flatCards.push(myPlayer.cards[idx]);
                });
            });

            this.sendPlayerAction({ action: 'separate', cards: flatCards });
            this.separateSelections = null;
            this.selectedDiscards.clear();
            this.drawAction = null;
            document.querySelectorAll('.draw-submit-btn').forEach(btn => btn.disabled = true);
            this.timer.stop();
        });

        // Setup card click handlers for separate mode
        this._setupSeparateCardHandlers(subsets);
    }

    _setupSeparateCardHandlers(subsets) {
        document.querySelectorAll('.card.selectable').forEach(cardEl => {
            cardEl.addEventListener('click', () => {
                const index = parseInt(cardEl.dataset.cardIndex);
                if (isNaN(index)) return;

                // Check if this card is already assigned to a subset
                for (let i = 0; i < this.separateSelections.length; i++) {
                    const pos = this.separateSelections[i].indexOf(index);
                    if (pos !== -1) {
                        // Remove from this subset
                        this.separateSelections[i].splice(pos, 1);
                        this.selectedDiscards.delete(index);
                        cardEl.classList.remove('selected');
                        for (let j = 0; j < subsets.length; j++) cardEl.classList.remove(`subset-${j}`);
                        const actionButtons = document.getElementById('action-buttons');
                        this._renderSeparateControls(actionButtons, this.drawAction);
                        return;
                    }
                }

                // Find current unfilled subset
                let targetSubset = -1;
                for (let i = 0; i < subsets.length; i++) {
                    if (this.separateSelections[i].length < subsets[i].count) {
                        targetSubset = i;
                        break;
                    }
                }

                if (targetSubset === -1) return; // All full

                // Add to target subset
                this.separateSelections[targetSubset].push(index);
                this.selectedDiscards.add(index);
                cardEl.classList.add('selected', `subset-${targetSubset}`);

                const actionButtons = document.getElementById('action-buttons');
                this._renderSeparateControls(actionButtons, this.drawAction);
            });
        });
    }

    _renderDeclareControls(container, declareAction) {
        const options = declareAction.metadata?.options || ['high', 'low'];
        const perPot = declareAction.metadata?.per_pot || false;

        const optionLabels = {
            'high': 'High',
            'low': 'Low',
            'high_low': 'Both (Hi/Lo)'
        };

        let infoText = perPot ? 'Declare for each pot:' : 'Declare your hand:';

        let buttonsHtml = options.map(opt => {
            const label = optionLabels[opt] || opt;
            return `<button class="action-btn primary declare-btn" data-declaration="${opt}">${label}</button>`;
        }).join('');

        container.innerHTML = `
            <div class="draw-controls">
                <div class="draw-info">${infoText}</div>
                <div class="declare-buttons">${buttonsHtml}</div>
            </div>
        `;

        container.querySelectorAll('.declare-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const declaration = btn.dataset.declaration;
                this.sendPlayerAction({
                    action: 'declare',
                    declaration_data: [{ pot_index: -1, declaration: declaration }]
                });
                container.querySelectorAll('.declare-btn').forEach(b => b.disabled = true);
                this.timer.stop();
            });
        });
    }

    _renderChooseControls(container, chooseAction) {
        const options = chooseAction.metadata?.options || [];

        let buttonsHtml = options.map((opt, i) => {
            return `<button class="action-btn primary choose-btn" data-choice-index="${i}">${opt}</button>`;
        }).join('');

        container.innerHTML = `
            <div class="draw-controls">
                <div class="draw-info">Choose a game variant:</div>
                <div class="choose-buttons">${buttonsHtml}</div>
            </div>
        `;

        container.querySelectorAll('.choose-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const index = parseInt(btn.dataset.choiceIndex);
                this.sendPlayerAction({ action: 'choose', amount: index });
                container.querySelectorAll('.choose-btn').forEach(b => b.disabled = true);
                this.timer.stop();
            });
        });
    }

    createActionButton(action) {
        const button = document.createElement('button');
        const actionType = action.action_type || action.type;
        const actionTypeLower = actionType.toLowerCase();

        button.className = `action-btn ${actionTypeLower}`;
        button.dataset.action = actionTypeLower;

        // Use display_text if available, otherwise format the action type
        let buttonText = action.display_text || actionType.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());

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
        } else if ((action.action_type?.toLowerCase() === 'bring_in' || action.type?.toLowerCase() === 'bring_in') ||
                   (action.action_type?.toLowerCase() === 'complete' || action.type?.toLowerCase() === 'complete')) {
            // Bring-in and complete have fixed amounts from min_amount
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

            const result = await response.json();

            if (!response.ok || !result.success) {
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

    handlePlayerLeaving(data) {
        const username = data.username || 'A player';
        this.chat.displayChatMessage({
            type: 'system',
            message: `${username} is leaving after this hand`,
            timestamp: new Date().toISOString()
        });
        // Store leaving player ID so renderPlayers can show indicator
        if (!this.store.leavingPlayers) {
            this.store.leavingPlayers = new Set();
        }
        this.store.leavingPlayers.add(data.user_id);
        this.renderPlayers();
    }

    // Chat methods delegated to this.chat (PokerChat)

    // toggleMobilePanel delegated to this.responsive (PokerResponsive)

    leaveTable() {
        this.stopGameUpdateTimer();
        this.socket.emit('leave_table', { table_id: this.store.tableId });
        PokerModals.closeModal('leave-table-modal');

        // Show notification if hand is in progress
        const gs = this.store.gameState;
        if (gs && gs.game_state && !['waiting', 'complete'].includes(gs.game_state.toLowerCase())) {
            PokerModals.showNotification('Leaving after this hand...', 'info');
        }

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

        // Capture hand result for in-session history
        this.chat.captureHandResult(data);

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

    async showHandHistory() {
        const content = document.getElementById('hand-history-content');
        content.innerHTML = '<div class="hand-history-loading">Loading hand history...</div>';
        PokerModals.showModal('hand-history-modal');

        // Merge in-session history with DB history
        let hands = [];
        try {
            const response = await fetch(`/api/games/tables/${this.store.tableId}/hand-history?limit=20`);
            const data = await response.json();
            if (data.success && data.hands) {
                hands = data.hands;
            }
        } catch (err) {
            console.error('Failed to fetch hand history:', err);
        }

        // Fill in any in-session hands not yet in DB
        const dbHandNumbers = new Set(hands.map(h => h.hand_number));
        for (const sessionHand of this.chat.handHistory) {
            if (!dbHandNumbers.has(sessionHand.hand_number)) {
                hands.unshift(this._sessionHandToDisplay(sessionHand));
            }
        }

        // Sort by hand number descending
        hands.sort((a, b) => b.hand_number - a.hand_number);

        this.renderHandHistory(content, hands);
    }

    _sessionHandToDisplay(sessionHand) {
        // Convert in-session captured hand to display format matching DB to_dict()
        const results = sessionHand.hand_results || {};
        const winners = [];
        for (const pot of (results.pots || [])) {
            for (const wid of (pot.winners || [])) {
                if (!winners.includes(wid)) winners.push(wid);
            }
        }
        return {
            hand_number: sessionHand.hand_number,
            variant: sessionHand.variant,
            betting_structure: sessionHand.betting_structure,
            completed_at: sessionHand.timestamp,
            total_pot: results.total_pot || 0,
            winners: winners,
            results: results,
            players: [],
            _fromSession: true,
        };
    }

    renderHandHistory(container, hands) {
        if (!hands || hands.length === 0) {
            container.innerHTML = '<div class="hand-history-empty">No hands played yet.</div>';
            return;
        }

        let html = '<div class="hand-history-list">';
        for (const hand of hands) {
            const time = hand.completed_at
                ? new Date(hand.completed_at).toLocaleTimeString()
                : '';
            const totalPot = hand.total_pot || 0;

            // Build winner names
            let winnerDisplay = '';
            const winnerIds = hand.winners || [];
            if (winnerIds.length > 0 && hand.players && hand.players.length > 0) {
                const names = winnerIds.map(id => {
                    const p = hand.players.find(pl => pl.user_id === id);
                    return p ? p.username : id.substring(0, 8);
                });
                winnerDisplay = names.join(', ');
            } else if (winnerIds.length > 0) {
                // Try to get names from results winning_hands
                const results = hand.results || {};
                const winningHands = results.winning_hands || [];
                if (winningHands.length > 0) {
                    winnerDisplay = winnerIds.map(id => id.substring(0, 8)).join(', ');
                } else {
                    winnerDisplay = winnerIds.map(id => id.substring(0, 8)).join(', ');
                }
                // Check store players for names
                for (let i = 0; i < winnerIds.length; i++) {
                    const sp = this.store.findPlayerByUserId(winnerIds[i]);
                    if (sp) {
                        winnerDisplay = winnerDisplay.replace(
                            winnerIds[i].substring(0, 8),
                            sp.username
                        );
                    }
                }
            }

            const variant = hand.variant
                ? hand.variant.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
                : '';

            html += `
                <div class="hand-history-item" data-hand-index="${hand.hand_number}">
                    <div class="hand-history-summary" onclick="window.pokerTable.toggleHandDetail(this)">
                        <div class="hand-summary-left">
                            <span class="hand-number">#${hand.hand_number}</span>
                            <span class="hand-variant">${PokerModals.escapeHtml(variant)}</span>
                        </div>
                        <div class="hand-summary-right">
                            <span class="hand-pot">Pot: $${totalPot}</span>
                            ${winnerDisplay ? `<span class="hand-winner">Won by: ${PokerModals.escapeHtml(winnerDisplay)}</span>` : ''}
                            <span class="hand-time">${time}</span>
                        </div>
                    </div>
                    <div class="hand-history-detail" style="display: none;">
                        ${this._renderHandDetail(hand)}
                    </div>
                </div>
            `;
        }
        html += '</div>';
        container.innerHTML = html;
    }

    _renderHandDetail(hand) {
        const results = hand.results || {};
        let html = '';

        // Players
        if (hand.players && hand.players.length > 0) {
            html += '<div class="hand-detail-section"><strong>Players:</strong><ul class="hand-detail-players">';
            for (const p of hand.players) {
                html += `<li>${PokerModals.escapeHtml(p.username || 'Unknown')} — $${p.stack || 0}</li>`;
            }
            html += '</ul></div>';
        }

        // Pots
        const pots = results.pots || [];
        if (pots.length > 0) {
            html += '<div class="hand-detail-section"><strong>Pots:</strong><ul class="hand-detail-pots">';
            for (let i = 0; i < pots.length; i++) {
                const pot = pots[i];
                const potLabel = i === 0 ? 'Main pot' : `Side pot ${i}`;
                const winnerIds = pot.winners || [];
                // Try to resolve winner names
                let winNames = winnerIds.map(id => {
                    if (hand.players && hand.players.length > 0) {
                        const p = hand.players.find(pl => pl.user_id === id);
                        if (p) return p.username;
                    }
                    const sp = this.store.findPlayerByUserId(id);
                    return sp ? sp.username : id.substring(0, 8);
                });
                html += `<li>${potLabel}: $${pot.amount} — ${winNames.join(', ')}</li>`;
            }
            html += '</ul></div>';
        }

        // Winning hands
        const winningHands = results.winning_hands || [];
        if (winningHands.length > 0) {
            html += '<div class="hand-detail-section"><strong>Winning hands:</strong><ul class="hand-detail-winning">';
            for (const wh of winningHands) {
                const playerId = wh.player_id || '';
                let playerName = playerId.substring(0, 8);
                if (hand.players && hand.players.length > 0) {
                    const p = hand.players.find(pl => pl.user_id === playerId);
                    if (p) playerName = p.username;
                }
                const sp = this.store.findPlayerByUserId(playerId);
                if (sp) playerName = sp.username;

                const handDesc = wh.hand_description || wh.hand_name || '';
                const cards = (wh.cards || []).join(' ');
                html += `<li>${PokerModals.escapeHtml(playerName)}: ${PokerModals.escapeHtml(handDesc)} ${cards ? '[' + cards + ']' : ''}</li>`;
            }
            html += '</ul></div>';
        }

        if (!html) {
            html = '<div class="hand-detail-section">No details available.</div>';
        }

        return html;
    }

    toggleHandDetail(summaryEl) {
        const detail = summaryEl.nextElementSibling;
        if (detail) {
            detail.style.display = detail.style.display === 'none' ? 'block' : 'none';
        }
    }
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
