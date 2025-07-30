// Lobby JavaScript - Enhanced Poker Platform
class PokerLobby {
    constructor() {
        this.socket = io();
        this.tables = [];
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
        });
        
        this.socket.on('disconnect', () => {
            console.log('Disconnected from server');
            this.showNotification('Disconnected from server', 'error');
        });
        
        this.socket.on('table_list', (data) => {
            this.tables = data.tables || [];
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
    }
    
    setupStakesConfiguration() {
        // Initialize with no-limit structure
        this.updateStakesInputs('no-limit');
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
        const noTables = document.getElementById('no-tables');
        const tableCount = document.getElementById('table-count');
        
        // Filter tables based on current filters
        const filteredTables = this.getFilteredTables();
        
        tableCount.textContent = filteredTables.length;
        
        if (filteredTables.length === 0) {
            tableGrid.innerHTML = '';
            tableGrid.appendChild(noTables);
            return;
        }
        
        // Remove no-tables message
        if (noTables.parentNode) {
            noTables.remove();
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
                        <div class="table-variant">${this.formatVariantName(table.variant)}</div>
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
                    <button class="btn btn-primary btn-small join-table-btn" 
                            data-table-id="${table.id}" 
                            ${isFull ? 'disabled' : ''}>
                        ${isFull ? 'Full' : 'Join'}
                    </button>
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
        
        if (structure === 'limit') {
            bigBlind = stakes.big_bet || 0;
        } else {
            bigBlind = stakes.big_blind || 0;
        }
        
        if (bigBlind <= 0.10) return 'micro';
        if (bigBlind <= 2) return 'low';
        if (bigBlind <= 10) return 'mid';
        return 'high';
    }
    
    formatStakes(stakes, structure) {
        if (structure === 'limit') {
            return `$${stakes.small_bet || 0}/$${stakes.big_bet || 0}`;
        } else {
            return `$${stakes.small_blind || 0}/$${stakes.big_blind || 0}`;
        }
    }
    
    formatVariantName(variant) {
        const variants = {
            'hold_em': "Texas Hold'em",
            'omaha': 'Omaha',
            'omaha_8': 'Omaha Hi-Lo',
            '7_card_stud': '7-Card Stud',
            '7_card_stud_8': '7-Card Stud Hi-Lo',
            'razz': 'Razz',
            'mexican_poker': 'Mexican Poker'
        };
        return variants[variant] || variant.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase());
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
            password: formData.get('password') || null,
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
        
        this.socket.emit('join_table', { table_id: tableId });
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
    if (window.lobby) {
        window.lobby.closeModal(modalId);
    }
};

// Initialize lobby when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.lobby = new PokerLobby();
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
`;
document.head.appendChild(style);