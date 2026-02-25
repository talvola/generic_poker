// Lobby JavaScript - Enhanced Poker Platform
class PokerLobby {
    constructor() {
        this.socket = io();
        this.tables = [];
        this.userTables = [];  // Table IDs where current user is seated
        this.variants = [];    // Available game variants from API
        this.variantMap = {};   // variant_name -> display_name lookup
        this.filters = {
            variant: '',
            stakes: '',
            structure: '',
            players: ''
        };

        this.init();
    }

    init() {
        this.setupEventListeners();
        this.setupSocketEvents();
        this.loadVariants();
        this.loadTables();
        this.setupStakesConfiguration();
    }

    setupEventListeners() {
        // Action buttons
        document.getElementById('create-table-btn').addEventListener('click', () => {
            this.showModal('create-table-modal');
        });

        document.getElementById('join-private-btn').addEventListener('click', () => {
            this.showModal('join-private-modal');
        });

        document.getElementById('refresh-tables-btn').addEventListener('click', () => {
            this.loadTables();
        });

        // Filter changes
        document.getElementById('variant-filter').addEventListener('change', (e) => {
            this.filters.variant = e.target.value;
            this.filterTables();
        });

        document.getElementById('stakes-filter').addEventListener('change', (e) => {
            this.filters.stakes = e.target.value;
            this.filterTables();
        });

        document.getElementById('structure-filter').addEventListener('change', (e) => {
            this.filters.structure = e.target.value;
            this.filterTables();
        });

        document.getElementById('players-filter').addEventListener('change', (e) => {
            this.filters.players = e.target.value;
            this.filterTables();
        });

        // Form submissions
        document.getElementById('create-table-form').addEventListener('submit', (e) => {
            e.preventDefault();
            this.createTable();
        });

        document.getElementById('join-private-form').addEventListener('submit', (e) => {
            e.preventDefault();
            this.joinPrivateTable();
        });

        // Private table checkbox
        document.getElementById('is-private').addEventListener('change', (e) => {
            const privateOptions = document.getElementById('private-options');
            privateOptions.style.display = e.target.checked ? 'block' : 'none';
        });

        // Game variant change - update available betting structures and show rules link
        document.getElementById('game-variant').addEventListener('change', (e) => {
            this.updateBettingStructureOptions(e.target.value);
            const rulesLink = document.getElementById('view-rules-link');
            if (rulesLink) {
                rulesLink.style.display = e.target.value ? 'inline' : 'none';
            }
        });

        // Betting structure change
        document.getElementById('betting-structure').addEventListener('change', (e) => {
            this.updateStakesInputs(e.target.value);
        });

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
            if (e.key === 'Escape') {
                this.closeAllModals();
            }
        });
    }

    setupSocketEvents() {
        this.socket.on('connect', () => {
            console.log('Connected to server');
            this.showNotification('Connected to server', 'success');
            this.loadTables();
        });

        this.socket.on('disconnect', () => {
            console.log('Disconnected from server');
            this.showNotification('Disconnected from server', 'error');
        });

        this.socket.on('table_list', (data) => {
            this.tables = data.tables || [];
            this.userTables = data.user_tables || [];  // Tables where user is seated
            this.renderTables();
        });

        this.socket.on('table_created', (data) => {
            this.showNotification('Table created successfully!', 'success');
            this.closeModal('create-table-modal');
            this.loadTables();

            // Optionally redirect to the table
            if (data.table_id) {
                window.location.href = `/table/${data.table_id}`;
            }
        });

        this.socket.on('table_joined', (data) => {
            this.showNotification('Joined table successfully!', 'success');
            this.closeAllModals();

            // Redirect to the table
            if (data.table_id) {
                window.location.href = `/table/${data.table_id}`;
            }
        });

        this.socket.on('error', (data) => {
            this.showNotification(data.message || 'An error occurred', 'error');
        });

        this.socket.on('table_updated', (data) => {
            // Update specific table in the list
            const tableIndex = this.tables.findIndex(t => t.id === data.table.id);
            if (tableIndex !== -1) {
                this.tables[tableIndex] = data.table;
                this.renderTables();
            }
        });

        this.socket.on('table_list_updated', (data) => {
            // A table was created or deleted — reload the full table list
            this.loadTables();
        });
    }

    setupStakesConfiguration() {
        // Initialize with no-limit structure
        this.updateStakesInputs('no-limit');
    }

    async loadVariants() {
        try {
            const response = await fetch('/table/variants');
            const data = await response.json();
            if (data.success) {
                this.variants = data.variants;
                // Build lookup map
                this.variantMap = {};
                for (const v of this.variants) {
                    this.variantMap[v.name] = v.display_name;
                }
                this.populateVariantDropdowns();
            }
        } catch (error) {
            console.error('Failed to load variants:', error);
        }
    }

    populateVariantDropdowns() {
        // Group variants by category
        const categoryOrder = ['Mixed', "Hold'em", 'Omaha', 'Stud', 'Draw', 'Pineapple', 'Dramaha', 'Straight', 'Other'];
        const grouped = {};
        for (const v of this.variants) {
            const cat = v.category || 'Other';
            if (!grouped[cat]) grouped[cat] = [];
            grouped[cat].push(v);
        }

        // Build optgroup HTML for the create-table dropdown
        const createSelect = document.getElementById('game-variant');
        let createHtml = '<option value="">Select a variant</option>';
        for (const cat of categoryOrder) {
            const games = grouped[cat];
            if (!games || games.length === 0) continue;
            createHtml += `<optgroup label="${cat}">`;
            for (const g of games) {
                createHtml += `<option value="${g.name}">${g.display_name}</option>`;
            }
            createHtml += '</optgroup>';
        }
        createSelect.innerHTML = createHtml;

        // Build flat list for filter dropdown (just unique variants seen in tables)
        const filterSelect = document.getElementById('variant-filter');
        let filterHtml = '<option value="">All Variants</option>';
        for (const cat of categoryOrder) {
            const games = grouped[cat];
            if (!games || games.length === 0) continue;
            filterHtml += `<optgroup label="${cat}">`;
            for (const g of games) {
                filterHtml += `<option value="${g.name}">${g.display_name}</option>`;
            }
            filterHtml += '</optgroup>';
        }
        filterSelect.innerHTML = filterHtml;
    }

    updateBettingStructureOptions(variantName) {
        const structSelect = document.getElementById('betting-structure');
        const variant = this.variants.find(v => v.name === variantName);
        if (!variant) {
            // Reset to all structures
            structSelect.innerHTML = `
                <option value="">Select structure</option>
                <option value="no-limit">No Limit</option>
                <option value="pot-limit">Pot Limit</option>
                <option value="limit">Limit</option>
            `;
            return;
        }

        const structMap = {
            'No Limit': 'no-limit',
            'Pot Limit': 'pot-limit',
            'Limit': 'limit'
        };
        const displayMap = {
            'no-limit': 'No Limit',
            'pot-limit': 'Pot Limit',
            'limit': 'Limit'
        };

        let html = '<option value="">Select structure</option>';
        for (const bs of variant.betting_structures) {
            const val = structMap[bs] || bs.toLowerCase().replace(' ', '-');
            const label = displayMap[val] || bs;
            html += `<option value="${val}">${label}</option>`;
        }
        structSelect.innerHTML = html;

        // Auto-select if only one option
        if (variant.betting_structures.length === 1) {
            structSelect.value = structMap[variant.betting_structures[0]] || '';
            this.updateStakesInputs(structSelect.value);
        }
    }

    updateStakesInputs(structure) {
        const stakesInputs = document.getElementById('stakes-inputs');

        if (structure === 'limit') {
            stakesInputs.innerHTML = `
                <div class="form-group">
                    <label for="small-bet">Small Bet ($):</label>
                    <input type="number" id="small-bet" name="small_bet" value="10" min="1" step="1" required>
                </div>
                <div class="form-group">
                    <label for="big-bet">Big Bet ($):</label>
                    <input type="number" id="big-bet" name="big_bet" value="20" min="1" step="1" required>
                </div>
                <div class="form-group">
                    <label for="ante">Ante ($):</label>
                    <input type="number" id="ante" name="ante" value="0" min="0" step="0.01">
                </div>
            `;
        } else {
            stakesInputs.innerHTML = `
                <div class="form-group">
                    <label for="small-blind">Small Blind ($):</label>
                    <input type="number" id="small-blind" name="small_blind" value="1" min="0.01" step="0.01" required>
                </div>
                <div class="form-group">
                    <label for="big-blind">Big Blind ($):</label>
                    <input type="number" id="big-blind" name="big_blind" value="2" min="0.01" step="0.01" required>
                </div>
            `;
        }
    }

    loadTables() {
        const refreshBtn = document.getElementById('refresh-tables-btn');
        refreshBtn.classList.add('loading');

        this.socket.emit('get_table_list', {});

        // Remove loading state after a delay
        setTimeout(() => {
            refreshBtn.classList.remove('loading');
        }, 1000);
    }

    renderTables() {
        const tableGrid = document.getElementById('table-grid');
        const tableCount = document.getElementById('table-count');

        // Filter tables based on current filters
        const filteredTables = this.getFilteredTables();

        tableCount.textContent = filteredTables.length;

        if (filteredTables.length === 0) {
            tableGrid.innerHTML = `
                <div class="no-tables" id="no-tables">
                    <div class="no-tables-icon">🎲</div>
                    <h3>No tables found</h3>
                    <p>Create a new table or adjust your filters to see available games.</p>
                </div>
            `;
            return;
        }

        tableGrid.innerHTML = filteredTables.map(table => this.renderTableCard(table)).join('');

        // Add event listeners to table cards
        this.setupTableCardEvents();
    }

    renderTableCard(table) {
        const isFull = table.current_players >= table.max_players;
        const statusClass = isFull ? 'full' : (table.current_players > 0 ? 'playing' : 'waiting');
        const statusText = isFull ? 'Full' : (table.current_players > 0 ? 'Playing' : 'Waiting');

        // Generate player indicators
        const playerDots = Array.from({ length: table.max_players }, (_, i) =>
            `<div class="player-dot ${i < table.current_players ? 'filled' : ''}"></div>`
        ).join('');

        // Format stakes display
        const stakesDisplay = this.formatStakes(table.stakes, table.betting_structure);

        return `
            <div class="table-card ${isFull ? 'full' : ''} ${table.is_private ? 'private' : ''} ${table.allow_bots ? 'has-bots' : ''}"
                 data-table-id="${table.id}">
                ${table.is_private ? '<div class="private-indicator">Private</div>' : ''}

                <div class="table-header-info">
                    <div>
                        <div class="table-name">${this.escapeHtml(table.name)}</div>
                        <div class="table-variant">${this.formatVariantName(table.variant)} <span class="table-id-tag">#${table.id.substring(0, 6)}</span></div>
                    </div>
                    <div class="table-status">
                        <div class="status-badge status-${statusClass}">${statusText}</div>
                    </div>
                </div>

                <div class="table-details">
                    <div class="detail-item">
                        <div class="detail-label">Stakes</div>
                        <div class="detail-value stakes">${stakesDisplay}</div>
                    </div>
                    <div class="detail-item">
                        <div class="detail-label">Structure</div>
                        <div class="detail-value">${this.formatStructure(table.betting_structure)}</div>
                    </div>
                    <div class="detail-item">
                        <div class="detail-label">Players</div>
                        <div class="detail-value players-count">
                            ${table.current_players}/${table.max_players}
                            <div class="players-indicator">${playerDots}</div>
                        </div>
                    </div>
                    <div class="detail-item">
                        <div class="detail-label">Buy-in</div>
                        <div class="detail-value">$${table.minimum_buyin} - $${table.maximum_buyin}</div>
                    </div>
                </div>

                <div class="table-actions">
                    ${this.userTables.includes(table.id) ? `
                        <button class="btn btn-success btn-small rejoin-table-btn"
                                data-table-id="${table.id}">
                            Rejoin
                        </button>
                    ` : `
                        <button class="btn btn-primary btn-small join-table-btn"
                                data-table-id="${table.id}"
                                ${isFull ? 'disabled' : ''}>
                            ${isFull ? 'Full' : 'Join'}
                        </button>
                    `}
                    <button class="btn btn-outline btn-small spectate-btn"
                            data-table-id="${table.id}">
                        <i class="icon-eye"></i> Spectate
                    </button>
                    <button class="btn btn-secondary btn-small details-btn"
                            data-table-id="${table.id}">
                        Details
                    </button>
                </div>
            </div>
        `;
    }

    setupTableCardEvents() {
        // Join table buttons
        document.querySelectorAll('.join-table-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const tableId = btn.dataset.tableId;
                this.joinTable(tableId);
            });
        });

        // Rejoin table buttons (for users already at a table)
        document.querySelectorAll('.rejoin-table-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const tableId = btn.dataset.tableId;
                this.rejoinTable(tableId);
            });
        });

        // Spectate buttons
        document.querySelectorAll('.spectate-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const tableId = btn.dataset.tableId;
                this.spectateTable(tableId);
            });
        });

        // Details buttons
        document.querySelectorAll('.details-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const tableId = btn.dataset.tableId;
                this.showTableDetails(tableId);
            });
        });

        // Table card click (show details)
        document.querySelectorAll('.table-card').forEach(card => {
            card.addEventListener('click', () => {
                const tableId = card.dataset.tableId;
                this.showTableDetails(tableId);
            });
        });
    }

    getFilteredTables() {
        return this.tables.filter(table => {
            // Variant filter
            if (this.filters.variant && table.variant !== this.filters.variant) {
                return false;
            }

            // Stakes filter
            if (this.filters.stakes) {
                const stakes = this.getStakesCategory(table.stakes, table.betting_structure);
                if (stakes !== this.filters.stakes) {
                    return false;
                }
            }

            // Structure filter
            if (this.filters.structure && table.betting_structure !== this.filters.structure) {
                return false;
            }

            // Players filter
            if (this.filters.players) {
                switch (this.filters.players) {
                    case 'has-seats':
                        if (table.current_players >= table.max_players) return false;
                        break;
                    case 'heads-up':
                        if (table.max_players !== 2) return false;
                        break;
                    case 'short-handed':
                        if (table.max_players < 3 || table.max_players > 6) return false;
                        break;
                    case 'full-ring':
                        if (table.max_players < 7) return false;
                        break;
                }
            }

            return true;
        });
    }

    getStakesCategory(stakes, structure) {
        let bigBlind = 0;
        const struct = (structure || '').toLowerCase();

        if (struct === 'limit') {
            bigBlind = stakes.big_bet || 0;
        } else {
            bigBlind = stakes.big_blind || 0;
        }

        if (bigBlind <= 0.50) return 'micro';
        if (bigBlind <= 5) return 'low';
        if (bigBlind <= 25) return 'mid';
        return 'high';
    }

    formatStakes(stakes, structure) {
        const struct = (structure || '').toLowerCase();
        if (struct === 'limit') {
            return `$${stakes.small_bet || 0}/$${stakes.big_bet || 0}`;
        } else {
            return `$${stakes.small_blind || 0}/$${stakes.big_blind || 0}`;
        }
    }

    formatVariantName(variant) {
        if (this.variantMap[variant]) {
            return this.variantMap[variant];
        }
        // Fallback: convert underscores to spaces and title-case
        return variant.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
    }

    formatStructure(structure) {
        return structure.replace('-', ' ').replace(/\b\w/g, l => l.toUpperCase());
    }

    async createTable() {
        const form = document.getElementById('create-table-form');
        const formData = new FormData(form);

        // Collect stakes data
        const bettingStructure = formData.get('betting_structure');
        const stakes = {};

        if (bettingStructure === 'limit') {
            stakes.small_bet = parseFloat(formData.get('small_bet') || 10);
            stakes.big_bet = parseFloat(formData.get('big_bet') || 20);
            stakes.ante = parseFloat(formData.get('ante') || 0);
        } else {
            stakes.small_blind = parseFloat(formData.get('small_blind') || 1);
            stakes.big_blind = parseFloat(formData.get('big_blind') || 2);
        }

        const tableData = {
            name: formData.get('name'),
            variant: formData.get('variant'),
            betting_structure: bettingStructure,
            max_players: parseInt(formData.get('max_players')),
            stakes: stakes,
            is_private: formData.get('is_private') === 'on',
            password: formData.get('is_private') === 'on' ? (formData.get('password') || null) : null,
            allow_bots: formData.get('allow_bots') === 'on'
        };

        // Validate required fields
        if (!tableData.name || !tableData.variant || !tableData.betting_structure) {
            this.showNotification('Please fill in all required fields', 'error');
            return;
        }

        // Validate stakes
        if (bettingStructure === 'limit') {
            if (stakes.small_bet <= 0 || stakes.big_bet <= 0 || stakes.big_bet <= stakes.small_bet) {
                this.showNotification('Invalid stakes configuration', 'error');
                return;
            }
        } else {
            if (stakes.small_blind <= 0 || stakes.big_blind <= 0 || stakes.big_blind <= stakes.small_blind) {
                this.showNotification('Invalid blinds configuration', 'error');
                return;
            }
        }

        try {
            const response = await fetch('/api/tables', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(tableData)
            });

            const result = await response.json();

            if (result.success) {
                this.showNotification('Table created successfully!', 'success');
                this.closeModal('create-table-modal');
                this.loadTables();

                // Optionally redirect to the table
                if (result.table_id) {
                    window.location.href = `/table/${result.table_id}`;
                }
            } else {
                this.showNotification(result.error || 'Failed to create table', 'error');
            }
        } catch (error) {
            console.error('Error creating table:', error);
            this.showNotification('Failed to create table', 'error');
        }
    }

    joinTable(tableId) {
        const table = this.tables.find(t => t.id === tableId);
        if (!table) {
            this.showNotification('Table not found', 'error');
            return;
        }

        if (table.current_players >= table.max_players) {
            this.showNotification('Table is full', 'error');
            return;
        }

        // Check if private table
        if (table.is_private) {
            this.showNotification('This is a private table. Use the invite code to join.', 'warning');
            return;
        }

        // Show seat selection modal
        this.showSeatSelectionModal(tableId);
    }

    rejoinTable(tableId) {
        // Navigate directly to the table - user is already seated
        window.location.href = `/table/${tableId}`;
    }

    showSeatSelectionModal(tableId) {
        const table = this.tables.find(t => t.id === tableId);
        if (!table) return;

        // Show loading modal first
        this.showLoadingSeatModal(table);

        // Fetch actual seat data
        fetch(`/api/tables/${tableId}/seats`)
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    this.showSeatSelectionModalWithData(table, data);
                } else {
                    this.showNotification('Failed to load seat information', 'error');
                    closeModal('seat-selection-modal');
                }
            })
            .catch(error => {
                console.error('Error fetching seat data:', error);
                this.showNotification('Failed to load seat information', 'error');
                closeModal('seat-selection-modal');
            });
    }

    showLoadingSeatModal(table) {
        const modalHtml = `
            <div id="seat-selection-modal" class="modal show">
                <div class="modal-content">
                    <div class="modal-header">
                        <h3>Join ${table.name}</h3>
                        <button class="modal-close" onclick="closeModal('seat-selection-modal')">&times;</button>
                    </div>
                    <div class="modal-body">
                        <div class="loading-seats">
                            <div class="loading-spinner"></div>
                            <p>Loading seat information...</p>
                        </div>
                    </div>
                </div>
            </div>
        `;
        document.body.insertAdjacentHTML('beforeend', modalHtml);
    }

    showSeatSelectionModalWithData(table, seatData) {
        // Remove loading modal
        closeModal('seat-selection-modal');

        // Create seat selection modal HTML with real data
        const modalHtml = `
            <div id="seat-selection-modal" class="modal show">
                <div class="modal-content modal-compact">
                    <div class="modal-header">
                        <h3>Join ${table.name}</h3>
                        <button class="modal-close" onclick="closeModal('seat-selection-modal')">&times;</button>
                    </div>
                    <div class="modal-body">
                        <div class="seat-modal-layout">
                            <div class="seat-modal-left">
                                <div class="table-info-compact">
                                    <div class="info-row">
                                        <span class="info-label">Game:</span>
                                        <span class="info-value">${table.variant.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase())}</span>
                                    </div>
                                    <div class="info-row">
                                        <span class="info-label">Stakes:</span>
                                        <span class="info-value">$${table.stakes.small_blind || table.stakes.small_bet}/${table.stakes.big_blind || table.stakes.big_bet}</span>
                                    </div>
                                    <div class="info-row">
                                        <span class="info-label">Players:</span>
                                        <span class="info-value">${seatData.current_players}/${seatData.max_players}</span>
                                    </div>
                                </div>

                                <div class="buy-in-section-compact">
                                    <label for="buy-in-amount">Buy-in Amount:</label>
                                    <input type="number" id="buy-in-amount" min="${seatData.minimum_buyin}" max="${seatData.maximum_buyin}" value="${seatData.minimum_buyin * 2}" step="1">
                                    <div class="buy-in-range">
                                        <small>$${seatData.minimum_buyin} - $${seatData.maximum_buyin}</small>
                                    </div>
                                </div>

                                <div class="seat-options">
                                    <label class="auto-assign-option" onclick="pokerLobby.selectAutoAssign()">
                                        <input type="radio" name="seat-choice" value="auto" checked>
                                        <span class="auto-assign-text">Auto-assign seat</span>
                                    </label>
                                </div>
                            </div>

                            <div class="seat-modal-right">
                                <div class="mini-poker-table">
                                    ${this.generateMiniPokerTable(seatData.seats, seatData.max_players)}
                                </div>
                            </div>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" onclick="closeModal('seat-selection-modal')">Cancel</button>
                        <button type="button" class="btn btn-primary" onclick="pokerLobby.confirmJoinTable('${table.id}')">Join Table</button>
                    </div>
                </div>
            </div>
        `;

        // Add modal to page
        document.body.insertAdjacentHTML('beforeend', modalHtml);
    }

    generateSeatGridWithData(seats) {
        let seatHtml = '';

        seats.forEach(seat => {
            const isOccupied = !seat.is_available;
            const seatClass = isOccupied ? 'seat-occupied' : 'seat-available';
            const disabled = isOccupied ? 'disabled' : '';

            let seatContent;
            if (isOccupied) {
                seatContent = `
                    <div class="seat-number">Seat ${seat.seat_number}</div>
                    <div class="seat-player">${seat.player.username}</div>
                    <div class="seat-stack">$${seat.player.stack}</div>
                `;
            } else {
                seatContent = `
                    <div class="seat-number">Seat ${seat.seat_number}</div>
                    <div class="seat-empty">Available</div>
                `;
            }

            seatHtml += `
                <div class="seat-option ${seatClass}">
                    <label>
                        <input type="radio" name="seat-choice" value="${seat.seat_number}" ${disabled}>
                        <div class="seat-visual">
                            ${seatContent}
                        </div>
                    </label>
                </div>
            `;
        });

        return seatHtml;
    }

    generateMiniPokerTable(seats, maxPlayers) {
        // Create a mini version of the poker table for seat selection
        // Map to nearest supported CSS layout (2, 6, or 9)
        const layoutPlayers = maxPlayers <= 2 ? 2 : maxPlayers <= 6 ? 6 : 9;
        let tableHtml = `
            <div class="mini-table-container" data-max-players="${layoutPlayers}">
                <div class="mini-poker-table-felt">
                    <div class="mini-table-center">
                        <div class="mini-table-label">Select Your Seat</div>
                    </div>
                    <div class="mini-player-seats">
        `;

        seats.forEach(seat => {
            const isOccupied = !seat.is_available;
            const seatClass = isOccupied ? 'mini-seat-occupied' : 'mini-seat-available';

            let seatContent;
            if (isOccupied) {
                seatContent = `
                    <div class="mini-player-info occupied">
                        <div class="mini-player-name">${seat.player.username}</div>
                        <div class="mini-player-chips">$${seat.player.stack}</div>
                    </div>
                `;
            } else {
                seatContent = `
                    <div class="mini-player-info available" onclick="pokerLobby.selectSeat(${seat.seat_number})">
                        <div class="mini-seat-number">Seat ${seat.seat_number}</div>
                        <div class="mini-seat-status">Click to join</div>
                    </div>
                `;
            }

            tableHtml += `
                <div class="mini-player-seat ${seatClass}" data-position="${seat.seat_number - 1}" data-seat="${seat.seat_number}">
                    ${seatContent}
                </div>
            `;
        });

        tableHtml += `
                    </div>
                </div>
            </div>
        `;

        return tableHtml;
    }

    selectSeat(seatNumber) {
        // Uncheck auto-assign
        const autoRadio = document.querySelector('input[name="seat-choice"][value="auto"]');
        if (autoRadio) autoRadio.checked = false;

        // Clear any existing seat selection
        document.querySelectorAll('.mini-player-seat.selected').forEach(seat => {
            seat.classList.remove('selected');
        });

        // Select the clicked seat
        const seatElement = document.querySelector(`[data-seat="${seatNumber}"]`);
        if (seatElement) {
            seatElement.classList.add('selected');
        }

        // Store the selection
        this.selectedSeat = seatNumber;

        // Update the radio button selection (create hidden radio if needed)
        let seatRadio = document.querySelector(`input[name="seat-choice"][value="${seatNumber}"]`);
        if (!seatRadio) {
            seatRadio = document.createElement('input');
            seatRadio.type = 'radio';
            seatRadio.name = 'seat-choice';
            seatRadio.value = seatNumber;
            seatRadio.style.display = 'none';
            document.querySelector('.seat-options').appendChild(seatRadio);
        }
        seatRadio.checked = true;
    }

    selectAutoAssign() {
        // Clear any seat selection
        document.querySelectorAll('.mini-player-seat.selected').forEach(seat => {
            seat.classList.remove('selected');
        });

        // Clear stored selection
        this.selectedSeat = null;

        // Make sure auto-assign is checked
        const autoRadio = document.querySelector('input[name="seat-choice"][value="auto"]');
        if (autoRadio) autoRadio.checked = true;
    }

    // Keep the old method for backward compatibility
    generateSeatGrid(table) {
        let seatHtml = '';
        for (let i = 1; i <= table.max_players; i++) {
            const isOccupied = false; // For demo, assume all seats are available
            const seatClass = isOccupied ? 'seat-occupied' : 'seat-available';
            const disabled = isOccupied ? 'disabled' : '';

            seatHtml += `
                <div class="seat-option ${seatClass}">
                    <label>
                        <input type="radio" name="seat-choice" value="${i}" ${disabled}>
                        <div class="seat-visual">
                            <div class="seat-number">Seat ${i}</div>
                            ${isOccupied ? '<div class="seat-player">Occupied</div>' : '<div class="seat-empty">Available</div>'}
                        </div>
                    </label>
                </div>
            `;
        }
        return seatHtml;
    }

    confirmJoinTable(tableId) {
        const buyInAmount = parseInt(document.getElementById('buy-in-amount').value);
        const seatChoiceElement = document.querySelector('input[name="seat-choice"]:checked');

        if (!seatChoiceElement) {
            this.showNotification('Please select a seat or choose auto-assign', 'error');
            return;
        }

        const seatChoice = seatChoiceElement.value;

        const joinData = {
            table_id: tableId,
            buy_in_amount: buyInAmount
        };

        if (seatChoice !== 'auto') {
            joinData.seat_number = parseInt(seatChoice);
        }

        this.socket.emit('join_table', joinData);
        closeModal('seat-selection-modal');
    }

    spectateTable(tableId) {
        this.socket.emit('spectate_table', { table_id: tableId });
    }

    joinPrivateTable() {
        const form = document.getElementById('join-private-form');
        const formData = new FormData(form);

        const inviteCode = formData.get('invite_code');
        const password = formData.get('password');

        if (!inviteCode) {
            this.showNotification('Please enter an invite code', 'error');
            return;
        }

        this.socket.emit('join_private_table', {
            invite_code: inviteCode,
            password: password
        });
    }

    showTableDetails(tableId) {
        const table = this.tables.find(t => t.id === tableId);
        if (!table) {
            this.showNotification('Table not found', 'error');
            return;
        }

        const modal = document.getElementById('table-details-modal');
        const title = document.getElementById('table-details-title');
        const content = document.getElementById('table-details-content');
        const joinBtn = document.getElementById('join-table-btn');
        const spectateBtn = document.getElementById('spectate-table-btn');

        title.textContent = table.name;

        const stakesDisplay = this.formatStakes(table.stakes, table.betting_structure);
        const isFull = table.current_players >= table.max_players;

        content.innerHTML = `
            <div class="table-detail-grid">
                <div class="detail-row">
                    <strong>Game Variant:</strong>
                    <span>${this.formatVariantName(table.variant)}</span>
                </div>
                <div class="detail-row">
                    <strong>Betting Structure:</strong>
                    <span>${this.formatStructure(table.betting_structure)}</span>
                </div>
                <div class="detail-row">
                    <strong>Stakes:</strong>
                    <span>${stakesDisplay}</span>
                </div>
                <div class="detail-row">
                    <strong>Players:</strong>
                    <span>${table.current_players}/${table.max_players}</span>
                </div>
                <div class="detail-row">
                    <strong>Buy-in Range:</strong>
                    <span>$${table.minimum_buyin} - $${table.maximum_buyin}</span>
                </div>
                <div class="detail-row">
                    <strong>Table Type:</strong>
                    <span>${table.is_private ? 'Private' : 'Public'}</span>
                </div>
                <div class="detail-row">
                    <strong>Bot Players:</strong>
                    <span>${table.allow_bots ? 'Allowed' : 'Not Allowed'}</span>
                </div>
                <div class="detail-row">
                    <strong>Created:</strong>
                    <span>${new Date(table.created_at).toLocaleString()}</span>
                </div>
            </div>
        `;

        // Configure action buttons
        joinBtn.disabled = isFull || table.is_private;
        joinBtn.textContent = isFull ? 'Table Full' : (table.is_private ? 'Private Table' : 'Join Table');

        joinBtn.onclick = () => {
            if (!isFull && !table.is_private) {
                this.joinTable(tableId);
            }
        };

        spectateBtn.onclick = () => {
            this.spectateTable(tableId);
        };

        this.showModal('table-details-modal');
    }

    showModal(modalId) {
        const modal = document.getElementById(modalId);
        modal.classList.add('show');

        // Focus first input if available
        const firstInput = modal.querySelector('input, select');
        if (firstInput) {
            setTimeout(() => firstInput.focus(), 100);
        }
    }

    closeModal(modalId) {
        const modal = document.getElementById(modalId);
        modal.classList.remove('show');

        // Reset form if it exists
        const form = modal.querySelector('form');
        if (form) {
            form.reset();

            // Reset stakes inputs to default
            if (modalId === 'create-table-modal') {
                this.updateStakesInputs('no-limit');
                document.getElementById('private-options').style.display = 'none';
            }
        }
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
            <button class="notification-close" onclick="this.parentElement.remove()">&times;</button>
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

    filterTables() {
        this.renderTables();
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Global functions for modal management (called from HTML)
window.closeModal = function(modalId) {
    if (modalId === 'seat-selection-modal') {
        // Handle dynamically created modal
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.remove();
        }
    } else if (window.lobby) {
        window.lobby.closeModal(modalId);
    }
};

// Show variant rules modal
window.showVariantRules = function() {
    const variantSelect = document.getElementById('game-variant');
    const variantId = variantSelect ? variantSelect.value : '';
    if (!variantId) return;

    const content = document.getElementById('game-rules-content');
    const title = document.getElementById('game-rules-title');
    if (!content) return;

    content.innerHTML = '<div style="text-align:center; padding: 20px;">Loading...</div>';
    if (window.lobby) window.lobby.showModal('game-rules-modal');

    fetch(`/api/tables/variants/${variantId}/rules`)
        .then(r => r.json())
        .then(data => {
            if (!data.success) {
                content.innerHTML = '<div>Could not load rules.</div>';
                return;
            }
            const rules = data.rules;
            if (title) title.textContent = rules.game;
            content.innerHTML = renderGameCard(rules);
        })
        .catch(() => {
            content.innerHTML = '<div>Failed to load rules.</div>';
        });
};

function renderGameCard(rules) {
    // Subtitle tags
    const subtitle = rules.tags.join(' &bull; ');

    // Timeline
    let tlHtml = '';
    for (const elem of rules.timeline) {
        if (elem.type === 'individual') {
            const labelHtml = (elem.label || '').split('\n').join('<br>');
            if (elem.total_cards <= 1 && elem.has_up) {
                tlHtml += `<div class="gc-tl-group"><div class="gc-card-single gc-card-up">I</div><div class="gc-label">${labelHtml}</div></div>`;
            } else if (elem.total_cards <= 1 && elem.has_down) {
                tlHtml += `<div class="gc-tl-group"><div class="gc-card-single gc-card-down">I</div><div class="gc-label">${labelHtml}</div></div>`;
            } else {
                tlHtml += `<div class="gc-tl-group"><div class="gc-card-stack"><div class="gc-back gc-b1"></div><div class="gc-back gc-b2"></div><div class="gc-back gc-b3"></div><div class="gc-front">I</div></div><div class="gc-label">${labelHtml}</div></div>`;
            }
        } else if (elem.type === 'community') {
            let cards = '';
            for (let i = 0; i < Math.min(elem.count, 6); i++) {
                cards += '<div class="gc-comm">C</div>';
            }
            tlHtml += `<div class="gc-tl-group"><div class="gc-comm-row">${cards}</div></div>`;
        } else if (elem.type === 'bet') {
            tlHtml += '<div class="gc-tl-group gc-bet-group"><div class="gc-bet">Bet</div></div>';
        } else {
            const labelHtml = (elem.label || elem.type.toUpperCase()).split('\n').join('<br>');
            const cls = `gc-action gc-action-${elem.type}`;
            tlHtml += `<div class="gc-tl-group"><div class="${cls}">${labelHtml}</div></div>`;
        }
    }

    // Final hand
    let finalHtml = '';
    if (rules.final_hands.length === 1) {
        const desc = rules.final_hands[0].replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
        finalHtml = `<div class="gc-final"><strong>Final Hand:</strong> ${desc}</div>`;
    } else {
        const parts = rules.final_hands.map(d => d.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')).join('<br>');
        finalHtml = `<div class="gc-final"><strong>Final Hands:</strong><br>${parts}</div>`;
    }

    // Split pot
    let splitHtml = '';
    if (rules.split_pot) {
        splitHtml = `<div class="gc-split"><strong>Split Pot:</strong> ${rules.split_pot}</div>`;
    }

    // Wild cards
    let wildHtml = '';
    if (rules.wild_cards && rules.wild_cards.length) {
        for (const w of rules.wild_cards) {
            if (w.includes('Bug')) {
                wildHtml += '<div class="gc-wild">Bug completes straight or flush, otherwise acts as an Ace.</div>';
            } else {
                wildHtml += `<div class="gc-wild">${w}.</div>`;
            }
        }
    }

    return `
        <div class="gc-subtitle">${subtitle}</div>
        <div class="gc-timeline">${tlHtml}</div>
        ${wildHtml}
        ${finalHtml}
        ${splitHtml}
    `;
}

// Global reference for seat selection
window.pokerLobby = null;

// Initialize lobby when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.lobby = new PokerLobby();
    window.pokerLobby = window.lobby; // For seat selection modal
});

// Add some CSS for table detail grid
const style = document.createElement('style');
style.textContent = `
    .table-detail-grid {
        display: grid;
        gap: 1rem;
    }

    .detail-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 0.75rem;
        background: var(--light-color, #f8f9fa);
        border-radius: 4px;
    }

    .detail-row strong {
        color: var(--dark-color, #343a40);
    }

    /* Game Card styles for rules modal */
    .gc-subtitle { text-align: center; color: #666; font-size: 0.85rem; margin-bottom: 14px; font-weight: 500; }
    .gc-timeline { display: flex; flex-wrap: wrap; align-items: flex-end; gap: 6px; justify-content: center; margin-bottom: 14px; min-height: 70px; padding: 8px 0; }
    .gc-tl-group { display: flex; flex-direction: column; align-items: center; gap: 4px; }
    .gc-card-stack { position: relative; width: 44px; height: 60px; }
    .gc-back { position: absolute; width: 40px; height: 56px; border: 2px solid #888; border-radius: 4px; background: repeating-linear-gradient(135deg, #ccc, #ccc 4px, #ddd 4px, #ddd 8px); }
    .gc-b1 { top: 0; left: 0; }
    .gc-b2 { top: 2px; left: 2px; }
    .gc-b3 { top: 4px; left: 4px; }
    .gc-front { position: absolute; top: 4px; left: 4px; width: 40px; height: 56px; border: 2px solid #333; border-radius: 4px; background: #fff; display: flex; align-items: center; justify-content: center; font-weight: 800; font-size: 1.2rem; z-index: 1; }
    .gc-card-single { width: 40px; height: 56px; border: 2px solid #333; border-radius: 4px; display: flex; align-items: center; justify-content: center; font-weight: 800; font-size: 1.2rem; }
    .gc-card-up { background: #fff; }
    .gc-card-down { background: repeating-linear-gradient(135deg, #ccc, #ccc 4px, #ddd 4px, #ddd 8px); border-color: #888; color: #555; }
    .gc-label { font-size: 0.6rem; text-align: center; color: #555; font-weight: 600; line-height: 1.2; max-width: 60px; }
    .gc-comm-row { display: flex; gap: 3px; }
    .gc-comm { width: 34px; height: 48px; border: 2px solid #333; border-radius: 3px; background: #fff; display: flex; align-items: center; justify-content: center; font-weight: 800; font-size: 1rem; }
    .gc-bet-group { align-self: flex-end; margin: 0 2px; }
    .gc-bet { width: 34px; height: 34px; border-radius: 50%; border: 3px solid #333; background: #f5f5f5; display: flex; align-items: center; justify-content: center; font-size: 0.55rem; font-weight: 700; }
    .gc-action { border: 2px solid #555; border-radius: 4px; padding: 5px 7px; font-size: 0.6rem; font-weight: 700; text-align: center; line-height: 1.3; min-width: 48px; background: #f9f9f9; }
    .gc-action-draw { border-color: #2563eb; color: #2563eb; }
    .gc-action-discard { border-color: #dc2626; color: #dc2626; }
    .gc-action-expose { border-color: #059669; color: #059669; }
    .gc-action-pass { border-color: #7c3aed; color: #7c3aed; }
    .gc-action-separate { border-color: #d97706; color: #d97706; }
    .gc-action-declare { border-color: #be185d; color: #be185d; }
    .gc-action-choose { border-color: #0891b2; color: #0891b2; }
    .gc-wild { font-size: 0.82rem; color: #555; margin-bottom: 6px; font-style: italic; }
    .gc-final { font-size: 0.85rem; margin-bottom: 4px; line-height: 1.4; }
    .gc-split { font-size: 0.85rem; margin-bottom: 4px; line-height: 1.4; }
`;
document.head.appendChild(style);
