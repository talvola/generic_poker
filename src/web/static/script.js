// Initialize socket connection
const socket = io();

// DOM elements
const joinForm = document.getElementById('join-form');
const gameContainer = document.getElementById('game-container');
const playerNameInput = document.getElementById('player-name');
const joinButton = document.getElementById('join-button');
const playersDiv = document.getElementById('players');
const communityCardsDisplay = document.getElementById('community-cards-display');
const potAmount = document.getElementById('pot-amount');
const currentBetAmount = document.getElementById('current-bet-amount');
const actionsDiv = document.getElementById('actions');
const resultsArea = document.getElementById('results-area');
const resultsContent = document.getElementById('results-content');
const gameStepElement = document.getElementById('game-step');
const gameStateElement = document.getElementById('game-state');
const gameTitle = document.getElementById('game-title');

// Game state tracking
let myPlayerId = null;
let currentState = null;
let currentGameStep = null;
let raiseModalActive = false;
let currentPlayerCards = [];

// Enhanced state management
let gameConfig = {
    selectedVariant: null,
    bettingStructure: null,
    stakes: {}
};

let chatVisible = true;
let isSpectator = false;
let disconnectTimer = null;

// Initialize enhanced features
document.addEventListener('DOMContentLoaded', function() {
    initializeEnhancedFeatures();
});

function initializeEnhancedFeatures() {
    // Add game variant selection button
    addGameVariantButton();
    
    // Initialize chat system
    initializeChatSystem();
    
    // Add disconnect detection
    initializeConnectionMonitoring();
    
    // Enhanced notification system
    createNotificationContainer();
    
    addToLog('Enhanced poker client loaded. Choose your game variant to begin.');
}

function addGameVariantButton() {
    const joinForm = document.getElementById('join-form');
    
    const variantButton = document.createElement('button');
    variantButton.type = 'button';
    variantButton.id = 'select-variant';
    variantButton.className = 'btn-secondary';
    variantButton.textContent = 'Select Game Variant';
    variantButton.style.display = 'block';
    variantButton.style.margin = '10px auto';
    
    variantButton.onclick = showGameVariantSelection;
    
    joinForm.insertBefore(variantButton, joinForm.querySelector('button'));
}

function showGameVariantSelection() {
    const modal = document.createElement('div');
    modal.className = 'modal game-selection-modal';
    
    // Common poker variants
    const gameVariants = [
        {
            name: "Texas Hold'em",
            description: "The most popular poker variant. 2 hole cards, 5 community cards.",
            file: "hold_em"
        },
        {
            name: "Omaha",
            description: "4 hole cards, must use exactly 2. 5 community cards.",
            file: "omaha"
        },
        {
            name: "Omaha 8",
            description: "Omaha with high-low split. 8-or-better qualifier for low.",
            file: "omaha_8"
        },
        {
            name: "7-Card Stud",
            description: "Classic stud poker. 7 cards per player, best 5-card hand wins.",
            file: "7_card_stud"
        },
        {
            name: "7-Card Stud 8",
            description: "7-Card Stud with high-low split. 8-or-better qualifier for low.",
            file: "7_card_stud_8"
        },
        {
            name: "Razz",
            description: "Lowball stud poker. Lowest 5-card hand wins.",
            file: "razz"
        },
        {
            name: "Mexican Poker",
            description: "Stud variant with joker and conditional wild cards.",
            file: "mexican_poker"
        }
    ];
    
    let optionsHtml = '';
    gameVariants.forEach(variant => {
        optionsHtml += `
            <div class="game-option" data-variant="${variant.file}">
                <h4>${variant.name}</h4>
                <p>${variant.description}</p>
            </div>
        `;
    });
    
    modal.innerHTML = `
        <div class="modal-content game-selection-content">
            <h3>Select Poker Variant</h3>
            <div class="game-options">
                ${optionsHtml}
            </div>
            <div id="betting-config" style="display: none;">
                <h4>Betting Structure</h4>
                <div class="betting-config">
                    <div class="betting-option">
                        <input type="radio" name="betting" value="limit" id="limit">
                        <label for="limit">Limit - Fixed bet sizes</label>
                    </div>
                    <div class="betting-option">
                        <input type="radio" name="betting" value="no-limit" id="no-limit" checked>
                        <label for="no-limit">No Limit - Bet any amount</label>
                    </div>
                    <div class="betting-option">
                        <input type="radio" name="betting" value="pot-limit" id="pot-limit">
                        <label for="pot-limit">Pot Limit - Bet up to pot size</label>
                    </div>
                    
                    <div id="stakes-config">
                        <div class="stakes-input">
                            <label>Small Blind:</label>
                            <input type="number" id="small-blind" value="1" min="1">
                        </div>
                        <div class="stakes-input">
                            <label>Big Blind:</label>
                            <input type="number" id="big-blind" value="2" min="1">
                        </div>
                    </div>
                </div>
            </div>
            <div class="modal-buttons">
                <button id="cancel-variant" class="btn-secondary">Cancel</button>
                <button id="confirm-variant" class="btn-primary" disabled>Confirm Selection</button>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    
    // Add event listeners
    const gameOptions = modal.querySelectorAll('.game-option');
    const bettingConfig = modal.querySelector('#betting-config');
    const confirmButton = modal.querySelector('#confirm-variant');
    const cancelButton = modal.querySelector('#cancel-variant');
    
    gameOptions.forEach(option => {
        option.addEventListener('click', function() {
            gameOptions.forEach(opt => opt.classList.remove('selected'));
            this.classList.add('selected');
            gameConfig.selectedVariant = this.dataset.variant;
            bettingConfig.style.display = 'block';
            updateConfirmButton();
        });
    });
    
    modal.querySelectorAll('input[name="betting"]').forEach(radio => {
        radio.addEventListener('change', function() {
            gameConfig.bettingStructure = this.value;
            updateStakesConfig(this.value);
            updateConfirmButton();
        });
    });
    
    function updateStakesConfig(structure) {
        const stakesConfig = modal.querySelector('#stakes-config');
        if (structure === 'limit') {
            stakesConfig.innerHTML = `
                <div class="stakes-input">
                    <label>Small Bet:</label>
                    <input type="number" id="small-bet" value="10" min="1">
                </div>
                <div class="stakes-input">
                    <label>Big Bet:</label>
                    <input type="number" id="big-bet" value="20" min="1">
                </div>
                <div class="stakes-input">
                    <label>Ante:</label>
                    <input type="number" id="ante" value="1" min="0">
                </div>
            `;
        } else {
            stakesConfig.innerHTML = `
                <div class="stakes-input">
                    <label>Small Blind:</label>
                    <input type="number" id="small-blind" value="1" min="1">
                </div>
                <div class="stakes-input">
                    <label>Big Blind:</label>
                    <input type="number" id="big-blind" value="2" min="1">
                </div>
            `;
        }
    }
    
    function updateConfirmButton() {
        confirmButton.disabled = !gameConfig.selectedVariant || !gameConfig.bettingStructure;
    }
    
    confirmButton.addEventListener('click', function() {
        // Collect stakes
        if (gameConfig.bettingStructure === 'limit') {
            gameConfig.stakes = {
                small_bet: parseInt(modal.querySelector('#small-bet').value),
                big_bet: parseInt(modal.querySelector('#big-bet').value),
                ante: parseInt(modal.querySelector('#ante').value)
            };
        } else {
            gameConfig.stakes = {
                small_blind: parseInt(modal.querySelector('#small-blind').value),
                big_blind: parseInt(modal.querySelector('#big-blind').value)
            };
        }
        
        // Send configuration to server
        socket.emit('configure_game', {
            variant: gameConfig.selectedVariant,
            betting_structure: gameConfig.bettingStructure,
            stakes: gameConfig.stakes
        });
        
        document.body.removeChild(modal);
        
        // Update UI
        const variantButton = document.getElementById('select-variant');
        variantButton.textContent = `Selected: ${gameVariants.find(v => v.file === gameConfig.selectedVariant).name}`;
        variantButton.classList.add('btn-success');
        
        showNotification('Game variant configured successfully!', 'success');
    });
    
    cancelButton.addEventListener('click', function() {
        document.body.removeChild(modal);
    });
}

function initializeChatSystem() {
    const gameContainer = document.getElementById('game-container');
    
    const chatHtml = `
        <div class="chat-container" id="chat-container">
            <div class="chat-header">
                <span>Table Chat</span>
                <button class="chat-toggle" onclick="toggleChat()">Hide</button>
            </div>
            <div class="chat-messages" id="chat-messages"></div>
            <div class="chat-input-container">
                <input type="text" class="chat-input" id="chat-input" placeholder="Type a message..." maxlength="200">
                <button class="chat-send" onclick="sendChatMessage()">Send</button>
            </div>
        </div>
    `;
    
    gameContainer.insertAdjacentHTML('beforeend', chatHtml);
    
    // Add enter key support for chat
    document.getElementById('chat-input').addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            sendChatMessage();
        }
    });
}

function toggleChat() {
    const chatContainer = document.getElementById('chat-container');
    const chatMessages = document.getElementById('chat-messages');
    const chatInput = document.querySelector('.chat-input-container');
    const toggleButton = document.querySelector('.chat-toggle');
    
    chatVisible = !chatVisible;
    
    if (chatVisible) {
        chatMessages.style.display = 'block';
        chatInput.style.display = 'flex';
        toggleButton.textContent = 'Hide';
    } else {
        chatMessages.style.display = 'none';
        chatInput.style.display = 'none';
        toggleButton.textContent = 'Show';
    }
}

function sendChatMessage() {
    const chatInput = document.getElementById('chat-input');
    const message = chatInput.value.trim();
    
    if (message && myPlayerId) {
        socket.emit('chat_message', {
            message: message,
            player_id: myPlayerId
        });
        chatInput.value = '';
    }
}

function addChatMessage(data) {
    const chatMessages = document.getElementById('chat-messages');
    if (!chatMessages) return;
    
    const messageDiv = document.createElement('div');
    messageDiv.className = `chat-message ${data.type || 'player'}`;
    
    const time = new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
    
    messageDiv.innerHTML = `
        <span class="chat-sender">${data.sender}:</span>
        ${data.message}
        <span class="chat-time">${time}</span>
    `;
    
    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    
    // Limit chat history
    if (chatMessages.children.length > 50) {
        chatMessages.removeChild(chatMessages.firstChild);
    }
}

function initializeConnectionMonitoring() {
    // Monitor connection status
    socket.on('connect', () => {
        clearTimeout(disconnectTimer);
        hideConnectionWarning();
        addToLog('Connected to server');
    });
    
    socket.on('disconnect', () => {
        showConnectionWarning();
        addToLog('Disconnected from server', 'error');
    });
    
    socket.on('reconnect', () => {
        addToLog('Reconnected to server', 'success');
        // Attempt to rejoin with same name
        const playerName = localStorage.getItem('poker_player_name');
        if (playerName) {
            socket.emit('join', { name: playerName, is_reconnect: true });
        }
    });
}

function showConnectionWarning() {
    let warning = document.getElementById('connection-warning');
    if (!warning) {
        warning = document.createElement('div');
        warning.id = 'connection-warning';
        warning.className = 'notification notification-error';
        warning.style.position = 'fixed';
        warning.style.top = '50%';
        warning.style.left = '50%';
        warning.style.transform = 'translate(-50%, -50%)';
        warning.style.zIndex = '10000';
        warning.innerHTML = `
            <h3>Connection Lost</h3>
            <p>Attempting to reconnect...</p>
            <div class="loading-spinner"></div>
        `;
        document.body.appendChild(warning);
    }
}

function hideConnectionWarning() {
    const warning = document.getElementById('connection-warning');
    if (warning) {
        document.body.removeChild(warning);
    }
}

function createNotificationContainer() {
    if (!document.getElementById('notification-container')) {
        const container = document.createElement('div');
        container.id = 'notification-container';
        container.className = 'notification-container';
        document.body.appendChild(container);
    }
}

// Enhanced notification system
function showNotification(message, type = 'info', duration = 4000) {
    const container = document.getElementById('notification-container') || createNotificationContainer();
    
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    
    notification.innerHTML = `
        ${message}
        <button class="notification-close" onclick="closeNotification(this)">&times;</button>
    `;
    
    container.appendChild(notification);
    
    // Animate in
    setTimeout(() => {
        notification.classList.add('show');
    }, 10);
    
    // Auto-remove
    setTimeout(() => {
        closeNotification(notification.querySelector('.notification-close'));
    }, duration);
}

function closeNotification(closeButton) {
    const notification = closeButton.parentElement;
    notification.classList.add('hiding');
    setTimeout(() => {
        if (notification.parentElement) {
            notification.parentElement.removeChild(notification);
        }
    }, 300);
}

// Enhanced socket event handlers
socket.on('chat_message', addChatMessage);

socket.on('player_disconnected', (data) => {
    addChatMessage({
        type: 'system',
        sender: 'System',
        message: `${data.player_name} has disconnected. Auto-fold in ${data.timeout_seconds}s if not reconnected.`
    });
    
    // Mark player as disconnected in UI
    const playerElements = document.querySelectorAll('.player');
    playerElements.forEach(el => {
        if (el.getAttribute('data-player-id') === data.player_id) {
            el.classList.add('disconnected');
        }
    });
});

socket.on('player_reconnected', (data) => {
    addChatMessage({
        type: 'system',
        sender: 'System',
        message: `${data.player_name} has reconnected.`
    });
    
    // Remove disconnected status
    const playerElements = document.querySelectorAll('.player');
    playerElements.forEach(el => {
        if (el.getAttribute('data-player-id') === data.player_id) {
            el.classList.remove('disconnected');
        }
    });
});

socket.on('player_auto_folded', (data) => {
    addChatMessage({
        type: 'system',
        sender: 'Dealer',
        message: `Player auto-folded due to ${data.reason.replace('_', ' ')}.`
    });
});

// Store player name for reconnection
function storePlayerName(name) {
    localStorage.setItem('poker_player_name', name);
}

// Modify existing join button handler to store name
const originalJoinHandler = joinButton.onclick;
joinButton.onclick = function() {
    const name = playerNameInput.value.trim();
    if (name) {
        storePlayerName(name);
    }
    originalJoinHandler();
};

// Add spectator mode toggle
function toggleSpectatorMode() {
    isSpectator = !isSpectator;
    
    if (isSpectator) {
        // Hide action controls
        document.getElementById('actions-container').style.display = 'none';
        
        // Add spectator indicator
        if (!document.getElementById('spectator-indicator')) {
            const indicator = document.createElement('div');
            indicator.id = 'spectator-indicator';
            indicator.className = 'spectator-indicator';
            indicator.textContent = 'SPECTATOR MODE';
            document.body.appendChild(indicator);
        }
        
        showNotification('Spectator mode enabled', 'info');
    } else {
        // Show action controls
        document.getElementById('actions-container').style.display = 'block';
        
        // Remove spectator indicator
        const indicator = document.getElementById('spectator-indicator');
        if (indicator) {
            document.body.removeChild(indicator);
        }
        
        showNotification('Spectator mode disabled', 'info');
    }
}

// Add keyboard shortcuts
document.addEventListener('keydown', function(e) {
    // Only handle shortcuts when game is active and it's player's turn
    if (document.getElementById('actions').style.display === 'flex') {
        switch(e.key.toLowerCase()) {
            case 'f':
                // Quick fold
                handleQuickAction('fold');
                break;
            case 'c':
                // Quick call/check
                handleQuickAction('call') || handleQuickAction('check');
                break;
            case 'r':
                // Quick raise (minimum)
                handleQuickAction('raise');
                break;
        }
    }
    
    // Global shortcuts
    if (e.ctrlKey || e.metaKey) {
        switch(e.key.toLowerCase()) {
            case 'enter':
                // Focus chat input
                e.preventDefault();
                document.getElementById('chat-input').focus();
                break;
        }
    }
});

function handleQuickAction(actionType) {
    const actionButtons = document.querySelectorAll('.action-btn');
    for (let button of actionButtons) {
        if (button.textContent.toLowerCase().includes(actionType)) {
            button.click();
            return true;
        }
    }
    return false;
}

// Playing card display functions
function getCardColor(card) {
    if (!card || card === '**') return 'black';
    const suit = card.slice(-1);
    return (suit === 'h' || suit === 'd') ? 'red' : 'black';
}

function getCardSymbol(card) {
    if (!card || card === '**') return '🂠';
    
    const value = card.slice(0, -1);
    const suit = card.slice(-1);
    
    // Unicode playing card symbols
    const suits = {
        's': '♠',
        'h': '♥',
        'd': '♦',
        'c': '♣'
    };
    
    return `${value}${suits[suit] || ''}`;
}

function formatCard(card, isVisible = true) {
    if (card === '**' || !isVisible) {
        return '<span class="card card-back">🂠</span>';
    }
    
    const color = getCardColor(card);
    const symbol = getCardSymbol(card);
    
    return `<span class="card" style="color: ${color}">${symbol}</span>`;
}

// Socket event handlers
socket.on('connect', () => {
    console.log('Connected to server');
    addToLog('Connected to server');
});

// Keep track of current players for reference
let currentPlayers = [];

// Update currentPlayers when game state updates
socket.on('game_state', (data) => {
    if (data.players) {
        currentPlayers = data.players;
    }
    // Existing updateGameState code...
    updateGameState(data);
});

socket.on('your_turn', (data) => {
    console.log('Received your_turn event:', data);
    showActions(data.actions);
    playSound('your-turn');
    
    // Highlight current player area
    const playerElements = document.querySelectorAll('.player');
    playerElements.forEach(el => {
        if (el.classList.contains('self')) {
            el.classList.add('active-turn');
            el.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
    });
    
    addToLog("It's your turn to act");
});

socket.on('error', (data) => {
    addToLog(`Error: ${data.message}`, 'error');
    showNotification(data.message, 'error');
});

// Join button event listener
joinButton.addEventListener('click', () => {
    const name = playerNameInput.value.trim();
    if (name) {
        addToLog(`Joining game as ${name}...`);
        socket.emit('join', { name: name });
        joinForm.style.display = 'none';
        gameContainer.style.display = 'block';
        
        // Find our player ID once the game state updates
        socket.once('game_state', (data) => {
            const myPlayer = data.players.find(p => p.name === name);
            if (myPlayer) {
                myPlayerId = myPlayer.id;
                addToLog(`Joined as player ID: ${myPlayerId}`);
                showNotification(`Welcome to the table, ${name}!`, 'success');
            }
        });
    } else {
        showNotification('Please enter a name', 'error');
    }
});

// After joining, show the ready button
socket.once('game_state', (data) => {
    const myPlayer = data.players.find(p => p.name === playerNameInput.value);
    if (myPlayer) {
        myPlayerId = myPlayer.id;
        addToLog(`Joined as player ID: ${myPlayerId}`);
        
        // Create and show ready button
        const readyBtn = document.createElement('button');
        readyBtn.id = 'ready-button';
        readyBtn.className = 'action-btn btn-success';
        readyBtn.textContent = 'Ready to Play';
        readyBtn.onclick = () => {
            socket.emit('ready', {});
            readyBtn.disabled = true;
            readyBtn.textContent = 'Waiting for others...';
            addToLog('You are ready to play');
        };
        
        // Insert before the table
        document.getElementById('game-container').insertBefore(
            readyBtn, 
            document.getElementById('table')
        );
    }
});

// Handle ready status updates
socket.on('ready_status', (data) => {
    const readyPlayers = data.ready_players;
    const allPlayers = data.all_players;
    
    // Update the button text with how many players are ready
    const readyBtn = document.getElementById('ready-button');
    if (readyBtn && !readyBtn.disabled) {
        readyBtn.textContent = 'Ready to Play';
    } else if (readyBtn) {
        readyBtn.textContent = `Waiting: ${readyPlayers.length}/${allPlayers.length} ready`;
    }
    
    // Add to log
    const notReadyPlayers = allPlayers.filter(p => !readyPlayers.includes(p));
    if (notReadyPlayers.length > 0) {
        addToLog(`Waiting for ${notReadyPlayers.length} player(s) to be ready`);
    }
    
    // If everyone is ready, hide the button and start the game
    if (data.all_ready) {
        addToLog('All players ready! Game starting...');
        if (readyBtn) {
            readyBtn.style.display = 'none';
        }
    }
});

// Add to the script.js file
socket.on('hand_complete', (results) => {
    console.log('Hand complete results:', results);
    showHandResults(results);
});

socket.on('next_hand_status', (data) => {
    updateNextHandStatus(data);
});

function showHandResults(results) {
    console.log('Showing hand results:', results);

    // Remove any existing results modal
    const existingModal = document.querySelector('.hand-results-modal');
    if (existingModal) {
        document.body.removeChild(existingModal);
    }    

    // Create a modal to display hand results
    const modal = document.createElement('div');
    modal.className = 'modal hand-results-modal';
    
    let winnerNames = results.pots.flatMap(pot => 
        pot.winners.map(winnerId => {
            const player = currentPlayers.find(p => p.id === winnerId);
            return player ? player.name : winnerId;
        })
    );
    
    let handResultsHtml = '<div class="winning-hands">';
    
    // Show the winning hands
    if (results.winning_hands && results.winning_hands.length > 0) {
        results.winning_hands.forEach(hand => {
            const playerName = currentPlayers.find(p => p.id === hand.player_id)?.name || hand.player_id;
            
            handResultsHtml += `
                <div class="winner-hand">
                    <h4>${playerName} wins with ${hand.hand_description}</h4>
                    <div class="cards-display">
                        ${hand.cards.map(card => formatCard(card)).join(' ')}
                    </div>
                </div>
            `;
        });
    }
    
    // Show all players' hands
    handResultsHtml += '<h4>All Hands</h4>';
    Object.entries(results.hands).forEach(([playerId, hands]) => {
        if (hands.length > 0) {
            const playerName = currentPlayers.find(p => p.id === playerId)?.name || playerId;
            const bestHand = hands[0]; // Assuming first hand is the best
            
            handResultsHtml += `
                <div class="player-hand ${results.pots.some(pot => pot.winners.includes(playerId)) ? 'winner' : ''}">
                    <h5>${playerName}: ${bestHand.hand_description}</h5>
                    <div class="cards-display">
                        ${bestHand.cards.map(card => formatCard(card)).join(' ')}
                    </div>
                </div>
            `;
        }
    });
    
    handResultsHtml += '</div>';
    
    // Show pot information
    let potsHtml = '<div class="pots-info">';
    results.pots.forEach((pot, index) => {
        const potWinners = pot.winners.map(winnerId => {
            const player = currentPlayers.find(p => p.id === winnerId);
            return player ? player.name : winnerId;
        }).join(', ');
        
        potsHtml += `
            <div class="pot-result ${index === 0 ? 'main-pot' : 'side-pot'}">
                <h5>${index === 0 ? 'Main Pot' : `Side Pot ${index}`}: $${pot.amount}</h5>
                <div>Winner(s): ${potWinners}</div>
                <div>Amount per winner: $${pot.amount_per_player}</div>
            </div>
        `;
    });
    potsHtml += '</div>';
    
    modal.innerHTML = `
        <div class="modal-content hand-results">
            <h3>Hand Results</h3>
            ${handResultsHtml}
            ${potsHtml}
            <div class="modal-buttons">
                <button id="ready-next-hand" class="btn-primary">Ready for Next Hand</button>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    
    // Add event listener to Ready button
    document.getElementById('ready-next-hand').addEventListener('click', () => {
        socket.emit('ready_for_next_hand', {});
        document.getElementById('ready-next-hand').disabled = true;
        document.getElementById('ready-next-hand').textContent = 'Waiting for others...';
        addToLog('You are ready for the next hand');
    });
}

function updateNextHandStatus(data) {
    const readyBtn = document.getElementById('ready-next-hand');
    if (!readyBtn) return;
    
    const readyCount = data.ready_players.length;
    const totalCount = data.all_players.length;
    
    readyBtn.textContent = `Waiting: ${readyCount}/${totalCount} ready`;
    
    if (data.all_ready) {
        // Close the modal when all players are ready
        const modal = document.querySelector('.hand-results-modal');
        if (modal) {
            modal.classList.add('closing');
            setTimeout(() => {
                document.body.removeChild(modal);
            }, 500);
        }
        
        addToLog('All players ready! Starting next hand...');
    }
}

function updateGameState(data) {
    // Update game info
    if (data.game_info) {
        gameTitle.textContent = data.game_info.name + ' Poker';
        gameStepElement.textContent = data.game_info.step_name || 'Not started';
        gameStateElement.textContent = data.state || 'waiting';
        
        // Log significant state changes
        if (currentState !== data.state || currentGameStep !== data.game_info.step_name) {
            addToLog(`Game phase: ${data.game_info.step_name} (${data.state})`);

            // Community cards changes
            if (data.community_cards && Object.keys(data.community_cards).length > 0) {
                for (const [subset, cards] of Object.entries(data.community_cards)) {
                    if (cards.length > 0) {
                        addToLog(`Community cards: ${cards.join(' ')}`);
                    }
                }
            }
            
            // Pot changes
            if (data.pot > 0) {
                addToLog(`Current pot: $${data.pot}`);
            }            

            if (data.state === 'dealing' && data.game_info.step_name.includes('Deal')) {
                playSound('deal');
                addToLog(`Dealing: ${data.game_info.step_name}`);
            } else if (data.state === 'betting') {
                addToLog(`Betting round: ${data.game_info.step_name}`);
            } else if (data.state === 'complete') {
                playSound('showdown');
                addToLog('Hand complete - Showdown');
            }
            currentState = data.state;
            currentGameStep = data.game_info.step_name;
        }
    }
    
    // Update community cards with animation
    updateCommunityCards(data.community_cards);
    
    // Update pot and betting info
    potAmount.textContent = data.pot || '0';
    
    if (data.betting) {
        currentBetAmount.textContent = data.betting.current_bet;
        // Highlight active betting info
        document.getElementById('current-bet').classList.add('highlight');
        setTimeout(() => {
            document.getElementById('current-bet').classList.remove('highlight');
        }, 1000);
    } else {
        currentBetAmount.textContent = '0';
    }
    
    resultsArea.style.display = 'none';

    // Update players with animation
    updatePlayers(data.players);
    
    // Hide actions if not our turn
    if (!data.players.some(p => p.id === myPlayerId && p.is_current)) {
        actionsDiv.style.display = 'none';
        
        // Remove active-turn class from all players
        document.querySelectorAll('.player').forEach(el => {
            el.classList.remove('active-turn');
        });
    }

    // Check if someone is making a choice (optional visual feedback)
    if (data.game_info && data.game_info.step_name && 
        data.game_info.step_name.toLowerCase().includes('choose')) {
        
        // Find who is making the choice
        const choosingPlayer = data.players.find(p => p.is_current);
        if (choosingPlayer && choosingPlayer.id !== myPlayerId) {
            // Show that another player is making a choice
            showNotification(`${choosingPlayer.name} is making a choice...`, 'info', 2000);
        }
    }    
}

function updateCommunityCards(communityCards) {
    if (!communityCards || Object.keys(communityCards).length === 0) {
        communityCardsDisplay.innerHTML = '<div class="no-cards">No community cards yet</div>';
        return;
    }
    
    let communityCardsHtml = '';
    
    // Process each subset of community cards
    for (const [subset, cards] of Object.entries(communityCards)) {
        if (cards.length > 0) {
            const displayName = subset === 'default' ? 'Board' : subset;
            
            communityCardsHtml += `<div class="card-subset">
                <div class="subset-name">${displayName}:</div> 
                <div class="cards-display">
                    ${cards.map(card => formatCard(card)).join(' ')}
                </div>
            </div>`;
        }
    }
    
    // Only animate if content has changed
    if (communityCardsHtml !== communityCardsDisplay.innerHTML) {
        communityCardsDisplay.classList.add('updating');
        setTimeout(() => {
            communityCardsDisplay.innerHTML = communityCardsHtml;
            communityCardsDisplay.classList.remove('updating');
        }, 300);
    }
}

function updatePlayers(players) {
    if (!players || players.length === 0) return;
    
    // Create a map of current player elements to compare with new state
    const currentPlayerElements = {};
    document.querySelectorAll('.player').forEach(el => {
        const playerId = el.getAttribute('data-player-id');
        if (playerId) {
            currentPlayerElements[playerId] = el;
        }
    });
    
    // Clear and rebuild players area
    playersDiv.innerHTML = '';
    
    players.forEach(player => {
        const playerDiv = document.createElement('div');
        playerDiv.className = 'player';
        playerDiv.setAttribute('data-player-id', player.id);
        
        // Add classes for current player, our player, and active status
        if (player.is_current) playerDiv.classList.add('current');
        if (player.id === myPlayerId) playerDiv.classList.add('self');
        if (!player.is_active) playerDiv.classList.add('inactive');
        
        // If this is a player that previously existed, add a transition class
        if (currentPlayerElements[player.id]) {
            playerDiv.classList.add('updating');
        }
        
        // Position display
        const positionDisplay = player.position && player.position !== 'None' 
            ? `<span class="position">(${player.position})</span>` 
            : '';
        
        // Current bet display with animation if it changed
        let currentBetDisplay = '';
        if (player.current_bet) {
            currentBetDisplay = `<span class="current-bet ${player.is_current ? 'highlight' : ''}">
                Bet: $${player.current_bet}
            </span>`;
        }
        
        // All-in indicator
        const allInDisplay = player.is_all_in 
            ? '<span class="all-in">ALL IN</span>' 
            : '';
        
        // Store current player's cards if this is us
        if (player.id === myPlayerId) {
            currentPlayerCards = [];
            for (const [subset, cards] of Object.entries(player.cards)) {
                currentPlayerCards.push(...cards);
            }
        }
        
        // Format cards - use special formatting for player's own cards
        let cardsHtml = '<div class="player-cards">';
        
        if (Object.keys(player.cards).length === 0) {
            cardsHtml += '<div class="no-cards">No cards</div>';
        } else {
            for (const [subset, cards] of Object.entries(player.cards)) {
                const subsetName = subset === 'unassigned' ? 'Hand' : subset;
                
                cardsHtml += `<div class="card-set">
                    <div class="subset-name">${subsetName}:</div>
                    <div class="cards-display">`;
                
                // If this is the current player, use visibility from card_visibility
                if (player.id === myPlayerId && player.card_visibility) {
                    cardsHtml += cards.map((card, idx) => {
                        const visibility = player.card_visibility[subset][idx];
                        const isFaceUp = visibility === "FACE_UP";
                        return formatCard(card, true) + 
                               `<span class="card-visibility ${isFaceUp ? 'face-up' : 'face-down'}">
                                  ${isFaceUp ? '👁️' : '🙈'}
                                </span>`;
                    }).join(' ');
                } else {
                    // For other players, just use what the server sent (which will already handle visibility)
                    cardsHtml += cards.map(card => formatCard(card)).join(' ');
                }
                
                cardsHtml += `</div>
                    </div>`;
            }
        }
        cardsHtml += '</div>';
        
        // Turn indicator
        const turnIndicator = player.is_current 
            ? `<div class="turn-indicator ${player.id === myPlayerId ? 'your-turn' : 'their-turn'}">
                ${player.id === myPlayerId ? 'YOUR TURN' : 'Their Turn'}
              </div>` 
            : '';
            
        // Assemble player display
        playerDiv.innerHTML = `
            <div class="player-header">
                <div class="player-info">
                    <strong class="player-name">${player.name}</strong> ${positionDisplay}
                    <span class="stack">$${player.stack}</span>
                </div>
                <div class="player-status">
                    ${currentBetDisplay}
                    ${allInDisplay}
                </div>
            </div>
            ${cardsHtml}
            ${turnIndicator}
        `;
        
        playersDiv.appendChild(playerDiv);
        
        // Remove transition class after animation completes
        setTimeout(() => {
            playerDiv.classList.remove('updating');
        }, 500);
    });
}

function showActions(actions) {
    if (!actions || actions.length === 0) return;
    
    actionsDiv.innerHTML = '';
    actionsDiv.style.display = 'flex';

    // Log the possible actions
    const actionNames = actions.map(a => {
        if (a.type === 'call' || a.type === 'bet' || a.type === 'raise') {
            return `${a.type}($${a.min}-$${a.max})`;
        }
        return a.type;
    }).join(', ');
    
    addToLog(`Your turn! Available actions: ${actionNames}`);    
    
    // Create buttons for each possible action
    actions.forEach(action => {
        const btn = document.createElement('button');
        btn.className = `action-btn action-${action.type}`;
        
        // Format button text and appearance based on action type
        if (action.type === 'fold') {
            btn.textContent = 'Fold';
            btn.classList.add('btn-danger');
        } else if (action.type === 'check') {
            btn.textContent = 'Check';
            btn.classList.add('btn-secondary');
        } else if (action.type === 'call') {
            btn.textContent = `Call $${action.min}`;
            btn.classList.add('btn-primary');
        } else if (action.type === 'bet') {
            btn.textContent = `Bet`;
            btn.classList.add('btn-success');
        } else if (action.type === 'raise') {
            btn.textContent = `Raise`;
            btn.classList.add('btn-warning');
        } else if (action.type === 'all-in') {
            btn.textContent = `All-In $${action.min}`;
            btn.classList.add('btn-danger');
        }
        
        btn.onclick = () => handleActionClick(action);
        actionsDiv.appendChild(btn);
    });
}

function handleActionClick(action) {
    // Handle simple actions directly
    if (action.type === 'fold' || action.type === 'check' || 
        (action.type === 'call' && action.min === action.max) ||
        (action.type === 'all-in' && action.min === action.max)) {
        
        // Log the action
        let actionMsg = `You ${action.type}`;
        if (action.min !== null && action.min !== undefined) {
            actionMsg += ` $${action.min}`;
        }
        addToLog(actionMsg);

        // Add this console log to debug
        console.log(`Sending action to server: ${action.type}, amount: ${action.min || 0}`);        
        
        // Send the action to the server
        socket.emit('action', {
            action: action.type,
            amount: action.min || 0
        });
        
        // Hide actions after selection
        actionsDiv.style.display = 'none';
        return;
    }
    
    // For bet/raise actions that need an amount, show slider
    showBetSlider(action);
}

function showBetSlider(action) {
    if (raiseModalActive) return;
    raiseModalActive = true;
    
    // Create modal for bet/raise amount selection
    const modal = document.createElement('div');
    modal.className = 'modal';
    
    const actionType = action.type.charAt(0).toUpperCase() + action.type.slice(1);
    const minAmount = action.min;
    const maxAmount = action.max;
    const defaultAmount = action.type === 'raise' ? minAmount * 2 : minAmount;
    
    modal.innerHTML = `
        <div class="modal-content">
            <h3>${actionType} Amount</h3>
            <div class="slider-container">
                <input type="range" id="bet-slider" min="${minAmount}" max="${maxAmount}" value="${defaultAmount}" step="1">
                <div class="slider-labels">
                    <span>Min: $${minAmount}</span>
                    <span>Max: $${maxAmount}</span>
                </div>
                <div class="amount-display">
                    $<input type="number" id="bet-amount" value="${defaultAmount}" min="${minAmount}" max="${maxAmount}">
                </div>
            </div>
            <div class="modal-buttons">
                <button id="cancel-bet" class="btn-secondary">Cancel</button>
                <button id="confirm-bet" class="btn-primary">Confirm ${actionType}</button>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    
    // Set up event listeners
    const slider = document.getElementById('bet-slider');
    const amountInput = document.getElementById('bet-amount');
    const cancelBtn = document.getElementById('cancel-bet');
    const confirmBtn = document.getElementById('confirm-bet');
    
    // Sync slider and input field
    slider.addEventListener('input', () => {
        amountInput.value = slider.value;
    });
    
    amountInput.addEventListener('input', () => {
        let value = parseInt(amountInput.value);
        if (isNaN(value)) value = minAmount;
        if (value < minAmount) value = minAmount;
        if (value > maxAmount) value = maxAmount;
        
        amountInput.value = value;
        slider.value = value;
    });
    
    // Handle cancel button
    cancelBtn.addEventListener('click', () => {
        document.body.removeChild(modal);
        raiseModalActive = false;
    });
    
    // Handle confirm button
    confirmBtn.addEventListener('click', () => {
        const amount = parseInt(amountInput.value);
        if (amount >= minAmount && amount <= maxAmount) {
            addToLog(`You ${action.type} $${amount}`);
            
            socket.emit('action', {
                action: action.type,
                amount: amount
            });
            
            document.body.removeChild(modal);
            raiseModalActive = false;
            actionsDiv.style.display = 'none';
        } else {
            showNotification(`Amount must be between $${minAmount} and $${maxAmount}`, 'error');
        }
    });
}

// Player Choice Action Handling

socket.on('player_choice', (data) => {
    console.log('Received player_choice event:', data);
    showChoiceModal(data);
    addToLog(`Make your choice: ${data.possible_values.join(' or ')}`);
});

socket.on('choice_made', (data) => {
    console.log('Choice was made:', data);
    addToLog(`${data.player_name} chose: ${data.choice}`);
});

function showChoiceModal(choiceData) {
    // Remove any existing choice modal
    const existingModal = document.querySelector('.choice-modal');
    if (existingModal) {
        document.body.removeChild(existingModal);
    }

    const modal = document.createElement('div');
    modal.className = 'modal choice-modal';
    
    const possibleValues = choiceData.possible_values || [];
    const choiceName = choiceData.value_name || 'choice';
    
    let optionsHtml = '';
    possibleValues.forEach((value, index) => {
        // Make the text more user-friendly
        const displayText = value.replace(/_/g, ' ').toUpperCase();
        optionsHtml += `
            <button class="choice-option btn-primary" data-value="${value}">
                ${displayText}
            </button>
        `;
    });
    
    modal.innerHTML = `
        <div class="modal-content choice-content">
            <h3>Make Your Choice</h3>
            <p>Select the ${choiceName.replace('_', ' ')} for this hand:</p>
            <div class="choice-options">
                ${optionsHtml}
            </div>
            <div class="choice-info">
                <p>Your choice will determine the rules for this hand.</p>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    
    // Add event listeners to choice buttons
    const choiceButtons = modal.querySelectorAll('.choice-option');
    choiceButtons.forEach(button => {
        button.addEventListener('click', () => {
            const selectedValue = button.getAttribute('data-value');
            
            // Log the choice
            addToLog(`You chose: ${selectedValue.replace('_', ' ')}`);
            
            // Send choice to server
            socket.emit('player_choice', {
                value_name: choiceName,
                selected_value: selectedValue
            });
            
            // Remove modal
            document.body.removeChild(modal);
            
            // Show feedback
            showNotification(`Choice made: ${selectedValue.replace('_', ' ')}`, 'success');
        });
    });
    
    // Add escape key to close modal
    const escapeHandler = (e) => {
        if (e.key === 'Escape' && document.body.contains(modal)) {
            // Don't allow escape - force the choice
            showNotification('You must make a choice to continue', 'warning');
        }
    };
    
    document.addEventListener('keydown', escapeHandler);
    
    // Remove escape handler when modal is removed
    const observer = new MutationObserver((mutations) => {
        mutations.forEach((mutation) => {
            if (mutation.type === 'childList') {
                mutation.removedNodes.forEach((node) => {
                    if (node === modal) {
                        document.removeEventListener('keydown', escapeHandler);
                        observer.disconnect();
                    }
                });
            }
        });
    });
    observer.observe(document.body, { childList: true });
}

// Helper function to play sound effects
function playSound(soundType) {
    // This is a placeholder - you would implement actual sounds
    console.log(`Playing sound: ${soundType}`);
    
    // Example implementation:
    /*
    const sounds = {
        'deal': 'sounds/deal.mp3',
        'chip': 'sounds/chip.mp3',
        'your-turn': 'sounds/notification.mp3',
        'showdown': 'sounds/showdown.mp3'
    };
    
    if (sounds[soundType]) {
        const audio = new Audio(sounds[soundType]);
        audio.play().catch(e => console.log('Sound play error:', e));
    }
    */
}

// Add a message to the game log
function addToLog(message, type = 'info') {
    const log = document.getElementById('log');
    if (!log) return; // Safety check
    
    const entry = document.createElement('div');
    entry.className = `log-entry log-${type}`;
    
    // Add timestamp
    const now = new Date();
    const time = now.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit', second:'2-digit'});
    
    entry.innerHTML = `<span class="log-time">${time}</span> ${message}`;
    log.insertBefore(entry, log.firstChild);  // Add at the top
    
    // Flash the log container to draw attention
    log.classList.add('flash');
    setTimeout(() => {
        log.classList.remove('flash');
    }, 300);
    
    // Limit log size
    if (log.children.length > 50) {
        log.removeChild(log.lastChild);
    }
}

// Show notification
function showNotification(message, type = 'info') {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.textContent = message;
    
    // Add to body
    document.body.appendChild(notification);
    
    // Animate in
    setTimeout(() => {
        notification.classList.add('show');
    }, 10);
    
    // Remove after delay
    setTimeout(() => {
        notification.classList.remove('show');
        setTimeout(() => {
            document.body.removeChild(notification);
        }, 300);
    }, 3000);
}

// Add initial log entry
window.addEventListener('DOMContentLoaded', () => {
    addToLog('Welcome to Generic Poker! Enter your name to join the game.');
});