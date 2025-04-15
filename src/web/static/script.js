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

socket.on('game_state', (data) => {
    updateGameState(data);
});

socket.on('your_turn', (data) => {
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
    
    // Update results if available
    if (data.results) {
        resultsArea.style.display = 'block';
        
        // Format winners list
        const winners = data.results.winners || [];
        let winnersText = winners.length > 0 
            ? winners.join(', ') 
            : 'Hand complete without showdown';
        
        // Find the winning player objects to show their hands
        const winningPlayers = data.players.filter(p => winners.includes(p.id));
        let winningHandsHtml = '';
        
        if (winningPlayers.length > 0) {
            winningHandsHtml = '<div class="winning-hands"><h4>Winning Hand(s):</h4>';
            winningPlayers.forEach(player => {
                winningHandsHtml += `<div class="winner-info">
                    <span class="winner-name">${player.name}</span>: `;
                
                // Display the player's cards
                for (const [subset, cards] of Object.entries(player.cards)) {
                    winningHandsHtml += `<span class="cards-display">
                        ${cards.map(card => formatCard(card)).join(' ')}
                    </span>`;
                }
                winningHandsHtml += '</div>';
            });
            winningHandsHtml += '</div>';
        }
        
        resultsContent.innerHTML = `
            <div class="result-header">Winner(s): ${winnersText}</div>
            <div class="pot-result">Pot: $${data.results.total_pot}</div>
            ${winningHandsHtml}
            <button id="next-hand-btn" class="btn-primary">Next Hand</button>
        `;
        
        // Add event listener to the Next Hand button
        document.getElementById('next-hand-btn').addEventListener('click', () => {
            resultsArea.style.display = 'none';
            addToLog('Waiting for next hand...');
        });
        
        addToLog(`Hand complete. Winners: ${winnersText}. Total pot: $${data.results.total_pot}`);
    } else {
        resultsArea.style.display = 'none';
    }
    
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