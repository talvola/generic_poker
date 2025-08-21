from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit
from generic_poker.game.game import Game
from generic_poker.config.loader import GameRules, BettingStructure, GameActionType
from generic_poker.game.game_state import GameState, PlayerAction
from generic_poker.core.card import Card, Visibility

import asyncio
import json
import os
import logging 
import sys
from threading import Thread

import time
from threading import Timer

from pathlib import Path
from datetime import datetime
import uuid

# Track disconnected players and reconnection timers
disconnected_players = {}  # {player_id: disconnect_time}
reconnect_timers = {}      # {player_id: Timer object}

# Configuration
DISCONNECT_TIMEOUT = 60    # seconds before auto-fold
RECONNECT_GRACE_PERIOD = 10  # seconds to reconnect without penalty

# Setup logging
def setup_logging():
    """Set up logging for the server."""
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ],
        force=True  # Force reconfiguration of logging
    )
    
    # You can also set specific loggers to different levels if needed
    # For example, to reduce the verbosity of some modules:
    # logging.getLogger('werkzeug').setLevel(logging.WARNING)
    # logging.getLogger('engineio').setLevel(logging.WARNING)
    # logging.getLogger('socketio').setLevel(logging.WARNING)
    
    # Or increase verbosity for your game module:
    logging.getLogger('generic_poker').setLevel(logging.DEBUG)

# Call the setup function before initializing the app
setup_logging()

app = Flask(__name__, template_folder='templates', static_folder='static')
socketio = SocketIO(app, async_mode='threading')

# Global game instance and player mapping
game = None
player_sids = {}  # Maps player_id to session_id

# Store futures for awaiting player actions
action_futures = {}

player_ready = {}  # Track which players are ready

# Enhanced game management
class GameManager:
    """Manages multiple poker game instances."""
    
    def __init__(self):
        self.games = {}  # {game_id: Game instance}
        self.game_configs = {}  # {game_id: configuration}
        self.player_to_game = {}  # {player_id: game_id}
        
    def create_game(self, game_id, variant, betting_structure, stakes):
        """Create a new game instance."""
        try:
            # Load game configuration
            config_path = self._find_config_file(variant)
            if not config_path:
                raise FileNotFoundError(f"Configuration for {variant} not found")
                
            with open(config_path, 'r') as f:
                config_data = f.read()
                rules = GameRules.from_json(config_data)
            
            # Create game with specified parameters
            game_params = {
                'rules': rules,
                'structure': BettingStructure(betting_structure.upper().replace('-', '_')),
                'auto_progress': False
            }
            
            # Add stakes parameters
            if betting_structure == 'limit':
                game_params.update({
                    'small_bet': stakes.get('small_bet', 10),
                    'big_bet': stakes.get('big_bet', 20),
                    'ante': stakes.get('ante', 0),
                    'bring_in': stakes.get('bring_in', 3)
                })
            else:
                game_params.update({
                    'small_blind': stakes.get('small_blind', 1),
                    'big_blind': stakes.get('big_blind', 2)
                })
            
            game = Game(**game_params)
            
            self.games[game_id] = game
            self.game_configs[game_id] = {
                'variant': variant,
                'betting_structure': betting_structure,
                'stakes': stakes,
                'created_at': datetime.now().isoformat(),
                'players': {}
            }
            
            print(f"Created game {game_id}: {variant} ({betting_structure})")
            return game
            
        except Exception as e:
            print(f"Error creating game {game_id}: {e}")
            raise
    
    def get_game(self, game_id):
        """Get game instance by ID."""
        return self.games.get(game_id)
    
    def add_player_to_game(self, game_id, player_id, player_name, stack=500):
        """Add a player to a specific game."""
        game = self.games.get(game_id)
        if game:
            game.add_player(player_id, player_name, stack)
            self.player_to_game[player_id] = game_id
            self.game_configs[game_id]['players'][player_id] = {
                'name': player_name,
                'joined_at': datetime.now().isoformat()
            }
            return True
        return False
    
    def remove_player_from_game(self, player_id):
        """Remove a player from their current game."""
        game_id = self.player_to_game.get(player_id)
        if game_id and game_id in self.games:
            game = self.games[game_id]
            game.remove_player(player_id)
            del self.player_to_game[player_id]
            if player_id in self.game_configs[game_id]['players']:
                del self.game_configs[game_id]['players'][player_id]
            return game_id
        return None
    
    def get_player_game(self, player_id):
        """Get the game a player is currently in."""
        game_id = self.player_to_game.get(player_id)
        return self.games.get(game_id) if game_id else None
    
    def list_games(self):
        """List all active games."""
        return [
            {
                'game_id': game_id,
                'variant': config['variant'],
                'betting_structure': config['betting_structure'],
                'player_count': len(config['players']),
                'max_players': game.rules.max_players,
                'state': game.state.value if game else 'unknown'
            }
            for game_id, config in self.game_configs.items()
            if (game := self.games.get(game_id))
        ]
    
    def _find_config_file(self, variant):
        """Find configuration file for a variant."""
        possible_paths = [
            f'data/game_configs/{variant}.json',
            f'../data/game_configs/{variant}.json',
            f'../../data/game_configs/{variant}.json',
            os.path.join(os.path.dirname(__file__), f'../data/game_configs/{variant}.json')
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                return path
        return None
                                            
# Initialize game manager
game_manager = GameManager()

# Enhanced session management
class SessionManager:
    """Manages player sessions and authentication."""
    
    def __init__(self):
        self.sessions = {}  # {session_id: player_data}
        self.player_sessions = {}  # {player_id: session_id}
    
    def create_session(self, player_id, player_name, socket_id):
        """Create a new player session."""
        session_id = str(uuid.uuid4())
        session_data = {
            'player_id': player_id,
            'player_name': player_name,
            'socket_id': socket_id,
            'created_at': datetime.now().isoformat(),
            'last_activity': datetime.now().isoformat()
        }
        
        self.sessions[session_id] = session_data
        self.player_sessions[player_id] = session_id
        return session_id
    
    def update_session(self, player_id, socket_id=None):
        """Update session with new socket ID or activity."""
        session_id = self.player_sessions.get(player_id)
        if session_id and session_id in self.sessions:
            if socket_id:
                self.sessions[session_id]['socket_id'] = socket_id
            self.sessions[session_id]['last_activity'] = datetime.now().isoformat()
            return True
        return False
    
    def get_session(self, player_id):
        """Get session data for a player."""
        session_id = self.player_sessions.get(player_id)
        return self.sessions.get(session_id) if session_id else None
    
    def remove_session(self, player_id):
        """Remove a player's session."""
        session_id = self.player_sessions.get(player_id)
        if session_id:
            if session_id in self.sessions:
                del self.sessions[session_id]
            del self.player_sessions[player_id]

# Initialize session manager
session_manager = SessionManager()

# Enhanced socket event handlers
@socketio.on('configure_game')
def handle_game_configuration(data):
    """Handle game variant and betting structure configuration."""
    sid = request.sid
    variant = data.get('variant', 'hold_em')
    betting_structure = data.get('betting_structure', 'no-limit')
    stakes = data.get('stakes', {'small_blind': 1, 'big_blind': 2})
    
    try:
        # For now, we'll use a single game ID
        # In a full implementation, this would create separate games
        game_id = 'main_game'
        
        global game
        game = game_manager.create_game(game_id, variant, betting_structure, stakes)
        
        socketio.emit('game_configured', {
            'variant': variant,
            'betting_structure': betting_structure,
            'stakes': stakes,
            'message': f'Game configured: {variant} ({betting_structure})'
        }, room=sid)
        
        print(f"Game configured: {variant} ({betting_structure}) with stakes {stakes}")
        
    except Exception as e:
        print(f"Error configuring game: {e}")
        socketio.emit('error', {'message': f'Failed to configure game: {str(e)}'}, room=sid)

@socketio.on('chat_message')
def handle_chat_message(data):
    """Handle chat messages from players."""
    sid = request.sid
    player_id = next((pid for pid, s in player_sids.items() if s == sid), None)
    
    if not player_id:
        return
    
    message = data.get('message', '').strip()
    if not message or len(message) > 200:
        return
    
    # Get player name
    player_name = 'Unknown'
    if game and player_id in game.table.players:
        player_name = game.table.players[player_id].name
    
    # Broadcast message to all players at the table
    chat_data = {
        'type': 'player',
        'sender': player_name,
        'message': message,
        'player_id': player_id,
        'timestamp': datetime.now().isoformat()
    }
    
    for pid, s in player_sids.items():
        socketio.emit('chat_message', chat_data, room=s)
    
    print(f"Chat - {player_name}: {message}")

@socketio.on('get_game_list')
def handle_get_game_list():
    """Send list of available games."""
    sid = request.sid
    games_list = game_manager.list_games()
    socketio.emit('game_list', {'games': games_list}, room=sid)

@socketio.on('join_game')
def handle_join_game(data):
    """Handle joining a specific game."""
    sid = request.sid
    game_id = data.get('game_id', 'main_game')
    player_name = data.get('name', '')
    
    if not player_name:
        socketio.emit('error', {'message': 'Player name required'}, room=sid)
        return
    
    # Check if game exists
    target_game = game_manager.get_game(game_id)
    if not target_game:
        socketio.emit('error', {'message': 'Game not found'}, room=sid)
        return
    
    # Generate player ID
    player_id = f"p{len(player_sids) + 1}"
    
    # Add player to game
    success = game_manager.add_player_to_game(game_id, player_id, player_name)
    if not success:
        socketio.emit('error', {'message': 'Failed to join game'}, room=sid)
        return
    
    # Update global references (for backward compatibility)
    global game
    game = target_game
    player_sids[player_id] = sid
    
    # Create session
    session_manager.create_session(player_id, player_name, sid)
    
    # Broadcast updated game state
    for pid, s in player_sids.items():
        emit('game_state', get_game_state_for_player(pid), room=s)
    
    print(f"{player_name} joined game {game_id} as {player_id}")

@socketio.on('spectate_game')
def handle_spectate_game(data):
    """Handle spectator joining a game."""
    sid = request.sid
    game_id = data.get('game_id', 'main_game')
    spectator_name = data.get('name', f'Spectator_{sid[:8]}')
    
    target_game = game_manager.get_game(game_id)
    if not target_game:
        socketio.emit('error', {'message': 'Game not found'}, room=sid)
        return
    
    # Add to spectators (we'll need to track these separately)
    spectator_id = f"spec_{sid}"
    
    # Send game state to spectator
    global game
    game = target_game  # Set for get_game_state_for_player
    
    spectator_state = get_game_state_for_player(None)  # Special case for spectators
    spectator_state['is_spectator'] = True
    spectator_state['spectator_name'] = spectator_name
    
    socketio.emit('game_state', spectator_state, room=sid)
    
    # Notify players
    for pid, s in player_sids.items():
        socketio.emit('spectator_joined', {
            'name': spectator_name,
            'message': f'{spectator_name} is now spectating'
        }, room=s)
    
    print(f"Spectator {spectator_name} joined game {game_id}")

# Enhanced game state function for spectators
def get_game_state_for_player(player_id):
    """Enhanced game state that handles spectators."""
    if not game:
        return {'error': 'No active game'}
    
    state = {
        'players': [],
        'community_cards': {name: [str(c) for c in cards] for name, cards in game.table.community_cards.items()},
        'pot': game.betting.get_total_pot() if hasattr(game.betting, 'get_total_pot') else 0,
        'state': game.state.value,
        'game_info': {
            'name': game.rules.game,
            'betting_structure': game.betting_structure.value,
            'current_step': game.current_step,
            'step_name': game.rules.gameplay[game.current_step].name if game.current_step >= 0 and game.current_step < len(game.rules.gameplay) else "Not started"
        },
        'is_spectator': player_id is None
    }
    
    # Add betting info
    if game.state == GameState.BETTING:
        state['betting'] = {
            'current_bet': game.betting.current_bet,
            'last_raise_size': getattr(game.betting, 'last_raise_size', 0),
            'small_blind': getattr(game, 'small_blind', 0),
            'big_blind': getattr(game, 'big_blind', 0)
        }
    
    # Add hand results if available
    if game.state == GameState.COMPLETE and hasattr(game, 'last_hand_result') and game.last_hand_result:
        try:
            results = game.last_hand_result
            state['results'] = {
                'total_pot': results.total_pot,
                'winners': [pot.winners for pot in results.pots] if hasattr(results, 'pots') else []
            }
        except Exception as e:
            print(f"Error adding results to state: {e}")
    
    # Add player information
    for p in game.table.get_position_order():
        position = "None"
        if p.position:
            position = ', '.join([pos.value for pos in p.position.positions]) if p.position.positions else "None"
        
        player_data = {
            'id': p.id,
            'name': p.name,
            'stack': p.stack,
            'position': position,
            'is_current': p.id == (game.current_player.id if game.current_player else None),
            'is_active': p.is_active
        }
        
        # Add betting information
        current_bet = game.betting.current_bets.get(p.id, None)
        if current_bet:
            player_data['current_bet'] = current_bet.amount
            player_data['has_acted'] = current_bet.has_acted
            player_data['is_all_in'] = current_bet.is_all_in
        
        # Card visibility logic
        is_showdown = game.state in [GameState.SHOWDOWN, GameState.COMPLETE]
        can_see_cards = (p.id == player_id or is_showdown or player_id is None)
        
        if can_see_cards:
            # Show all cards with visibility info
            player_data['cards'] = {'default': [str(c) for c in p.hand.cards]}
            player_data['card_visibility'] = {'default': [c.visibility.value for c in p.hand.cards]}
            
            # Add subset information
            for name, cards in p.hand.subsets.items():
                if cards:
                    player_data['cards'][name] = [str(c) for c in cards]
                    player_data['card_visibility'][name] = [c.visibility.value for c in cards]
        else:
            # Hide face-down cards from other players
            player_data['cards'] = {
                'default': [str(c) if c.visibility == Visibility.FACE_UP else '**' for c in p.hand.cards]
            }
            
            for name, cards in p.hand.subsets.items():
                if cards:
                    player_data['cards'][name] = [str(c) if c.visibility == Visibility.FACE_UP else '**' for c in cards]
        
        state['players'].append(player_data)
    
    return state        

# Hand history tracking
class HandHistoryManager:
    """Tracks and stores hand history."""
    
    def __init__(self):
        self.histories = {}  # {game_id: [hand_data]}
    
    def record_hand(self, game_id, hand_data):
        """Record a completed hand."""
        if game_id not in self.histories:
            self.histories[game_id] = []
        
        self.histories[game_id].append({
            'hand_number': len(self.histories[game_id]) + 1,
            'timestamp': datetime.now().isoformat(),
            **hand_data
        })
        
        # Keep only last 50 hands
        if len(self.histories[game_id]) > 50:
            self.histories[game_id] = self.histories[game_id][-50:]
    
    def get_history(self, game_id, limit=10):
        """Get recent hand history."""
        hands = self.histories.get(game_id, [])
        return hands[-limit:] if hands else []

hand_history = HandHistoryManager()

@socketio.on('get_hand_history')
def handle_get_hand_history(data):
    """Send hand history to requesting player."""
    sid = request.sid
    game_id = data.get('game_id', 'main_game')
    limit = min(data.get('limit', 10), 20)  # Max 20 hands
    
    history = hand_history.get_history(game_id, limit)
    socketio.emit('hand_history', {'hands': history}, room=sid)

# Server status and monitoring
@socketio.on('get_server_status')
def handle_get_server_status():
    """Send server status information."""
    sid = request.sid
    
    status = {
        'active_games': len(game_manager.games),
        'total_players': len(player_sids),
        'disconnected_players': len(disconnected_players),
        'server_time': datetime.now().isoformat(),
        'uptime': 'Unknown'  # Would need to track server start time
    }
    
    socketio.emit('server_status', status, room=sid)

# Error handling and logging
def log_error(error_type, error_msg, player_id=None, game_id=None):
    """Enhanced error logging."""
    error_data = {
        'timestamp': datetime.now().isoformat(),
        'type': error_type,
        'message': error_msg,
        'player_id': player_id,
        'game_id': game_id
    }
    
    print(f"ERROR [{error_type}]: {error_msg}")
    if player_id:
        print(f"  Player: {player_id}")
    if game_id:
        print(f"  Game: {game_id}")
    
    # In production, you'd want to log this to a file or database

# Cleanup function for server shutdown
def cleanup_server():
    """Clean up resources on server shutdown."""
    print("Cleaning up server resources...")
    
    # Cancel all timers
    for timer in reconnect_timers.values():
        timer.cancel()
    
    # Save any important state
    # (In production, you'd save game states, player data, etc.)
    
    print("Server cleanup complete")
    
@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('connect')
def handle_connect():
    print(f"Client connected: {request.sid}")
    # Do not emit any events here that would cause a prompt

@socketio.on('disconnect')
def handle_disconnect():
    """Handle player disconnection."""
    sid = request.sid
    player_id = next((pid for pid, s in player_sids.items() if s == sid), None)
    
    if player_id:
        player_name = game.table.players[player_id].name if game and player_id in game.table.players else player_id
        print(f"Player {player_name} ({player_id}) disconnected")
        
        # Mark player as disconnected
        disconnected_players[player_id] = time.time()
        
        # Remove from active session mapping
        if player_id in player_sids:
            del player_sids[player_id]
        
        # Set up auto-fold timer if it's their turn or in a hand
        if game and game.state != GameState.WAITING and game.state != GameState.COMPLETE:
            setup_disconnect_timer(player_id)
        
        # Notify other players
        for pid, s in player_sids.items():
            socketio.emit('player_disconnected', {
                'player_id': player_id,
                'player_name': player_name,
                'timeout_seconds': DISCONNECT_TIMEOUT
            }, room=s)
        
        print(f"Set up disconnect timer for {player_name}")

def setup_disconnect_timer(player_id):
    """Set up timer to auto-fold disconnected player."""
    if player_id in reconnect_timers:
        reconnect_timers[player_id].cancel()
    
    def auto_fold():
        if player_id in disconnected_players and player_id not in player_sids:
            print(f"Auto-folding disconnected player {player_id}")
            
            # Auto-fold if it's their turn
            if (game.current_player and game.current_player.id == player_id and 
                game.state == GameState.BETTING):
                try:
                    result = game.player_action(player_id, PlayerAction.FOLD, 0)
                    if result.success:
                        print(f"Successfully auto-folded {player_id}")
                        # Broadcast updated state
                        for pid, s in player_sids.items():
                            state = get_game_state_for_player(pid)
                            socketio.emit('game_state', state, room=s)
                            socketio.emit('player_auto_folded', {
                                'player_id': player_id,
                                'reason': 'disconnection_timeout'
                            }, room=s)
                except Exception as e:
                    print(f"Error auto-folding player {player_id}: {e}")
            
            # Mark player as inactive for future hands
            if game and player_id in game.table.players:
                game.table.players[player_id].is_active = False
    
    timer = Timer(DISCONNECT_TIMEOUT, auto_fold)
    timer.start()
    reconnect_timers[player_id] = timer

@socketio.on('reconnect_player')
def handle_reconnect(data):
    """Handle player reconnection."""
    sid = request.sid
    player_name = data.get('name', '')
    
    # Find the player by name (simple reconnection method)
    player_id = None
    if game:
        for pid, player in game.table.players.items():
            if player.name == player_name and pid in disconnected_players:
                player_id = pid
                break
    
    if player_id:
        # Cancel auto-fold timer
        if player_id in reconnect_timers:
            reconnect_timers[player_id].cancel()
            del reconnect_timers[player_id]
        
        # Restore session mapping
        player_sids[player_id] = sid
        
        # Remove from disconnected list
        if player_id in disconnected_players:
            disconnect_time = disconnected_players[player_id]
            del disconnected_players[player_id]
            
            # Check if they were gone too long
            disconnect_duration = time.time() - disconnect_time
            if disconnect_duration > RECONNECT_GRACE_PERIOD:
                print(f"Player {player_name} reconnected after {disconnect_duration:.1f}s")
        
        # Reactivate player
        if game and player_id in game.table.players:
            game.table.players[player_id].is_active = True
        
        # Send current game state
        state = get_game_state_for_player(player_id)
        socketio.emit('game_state', state, room=sid)
        socketio.emit('reconnection_success', {
            'message': f'Welcome back, {player_name}!'
        }, room=sid)
        
        # Notify other players
        for pid, s in player_sids.items():
            if pid != player_id:
                socketio.emit('player_reconnected', {
                    'player_id': player_id,
                    'player_name': player_name
                }, room=s)
        
        print(f"Player {player_name} ({player_id}) successfully reconnected")
        return True
    
    else:
        socketio.emit('reconnection_failed', {
            'message': 'Could not find your previous session. Please join as a new player.'
        }, room=sid)
        return False
        
@socketio.on('ready')
def handle_ready(data):
    """Handle a player indicating they're ready to play."""
    sid = request.sid
    player_id = next((pid for pid, s in player_sids.items() if s == sid), None)
    
    if not player_id:
        return
    
    player_ready[player_id] = True
    print(f"Player {player_id} is ready to play")
    
    # Broadcast ready status to all players
    ready_players = list(player_ready.keys())
    all_players = list(player_sids.keys())
    all_ready = all(pid in player_ready for pid in all_players)
    
    for pid, sid in player_sids.items():
        socketio.emit('ready_status', {
            'ready_players': ready_players,
            'all_players': all_players,
            'all_ready': all_ready
        }, room=sid)
    
    # Start game if all players (minimum 2) are ready
    if len(player_sids) >= 2 and all_ready and not hasattr(game, '_game_started'):
        game._game_started = True
        Thread(target=run_game_loop).start()

# Add this before the ready handler
ready_for_next_hand = {}

@socketio.on('ready_for_next_hand')
def handle_ready_for_next_hand(data):
    """Handle a player indicating they're ready for the next hand."""
    sid = request.sid
    player_id = next((pid for pid, s in player_sids.items() if s == sid), None)
    
    if not player_id:
        return
    
    ready_for_next_hand[player_id] = True
    print(f"Player {player_id} is ready for next hand")
    
    # Broadcast ready status to all players
    ready_players = list(ready_for_next_hand.keys())
    all_players = list(player_sids.keys())
    all_ready = len(ready_players) == len(all_players)
    
    for pid, sid in player_sids.items():
        socketio.emit('next_hand_status', {
            'ready_players': ready_players,
            'all_players': all_players,
            'all_ready': all_ready
        }, room=sid)

@socketio.on('join')
def enhanced_join_handler(data):
    """Enhanced join handler with reconnection support."""
    global game
    sid = request.sid
    player_name = data['name']
    is_reconnect = data.get('is_reconnect', False)
    
    # Check for reconnection first
    if is_reconnect:
        success = handle_reconnect(data)
        if success:
            return
    
    # Check if game exists and if the name is already taken
    if game is not None:
        # Check for existing active player with same name
        existing_active = any(p.name == player_name and p.id not in disconnected_players 
                            for p in game.table.players.values())
        if existing_active:
            emit('error', {'message': 'Name already taken by active player'}, room=sid)
            return
        
        # Check for disconnected player with same name (allow reconnection)
        for pid, player in game.table.players.items():
            if player.name == player_name and pid in disconnected_players:
                # This is a reconnection attempt
                handle_reconnect(data)
                return
    
    # Regular join logic continues...
    if game is None:
        start_game()
    
    player_id = f"p{len(player_sids) + 1}"
    starting_stack = 500
    
    game.add_player(player_id, player_name, starting_stack)
    player_sids[player_id] = sid
    
    # Broadcast updated game state to ALL players
    for pid, s in player_sids.items():
        emit('game_state', get_game_state_for_player(pid), room=s)
    
    print(f"{player_name} joined as {player_id}")
    
@socketio.on('action')
def handle_action(data):
    """Handle player actions."""
    sid = request.sid
    player_id = next((pid for pid, s in player_sids.items() if s == sid), None)
    print(f"Received action from {player_id}: {data}")
    
    if player_id and player_id == (game.current_player.id if game.current_player else None):
        try:
            action_str = data['action']
            amount = data.get('amount', 0)
            cards = data.get('cards', [])

            # Convert string action to PlayerAction enum
            try:
                action = PlayerAction(action_str)
                print(f"Converted action string '{action_str}' to enum: {action}")
            except ValueError:
                print(f"Invalid action string: {action_str}")
                socketio.emit('error', {'message': f"Invalid action: {action_str}"}, room=sid)
                return            
            
            print(f"Processing action directly for {player_id}: {action} {amount}")
            result = game.player_action(player_id, action, amount, cards)
            print(f"Action result: {result}")
            
            if not result.success:
                socketio.emit('error', {'message': result.error}, room=sid)
            else:
                # Broadcast updated state to all players after successful action
                for pid, s in player_sids.items():
                    state = get_game_state_for_player(pid)
                    socketio.emit('game_state', state, room=s)
                
                # Check if hand is complete (all but one folded or other completion condition)
                if game.state == GameState.COMPLETE:
                    print(f"Hand completed after {player_id}'s action - not advancing to next step")
                    # Hand is complete, don't advance further
                    # The game state broadcast above will show the complete state
                elif result.advance_step:
                    print(f"Advancing to next step after {player_id}'s action")
                    game._next_step()

                    # Reset last_player_id when moving to a new step
                    if 'last_player_id' in globals():
                        globals()['last_player_id'] = None                    
                    
                    # After advancing, broadcast the new state
                    for pid, s in player_sids.items():
                        state = get_game_state_for_player(pid)
                        socketio.emit('game_state', state, room=s)
        except Exception as e:
            print(f"Exception in handle_action: {e}")
            import traceback
            traceback.print_exc()
            socketio.emit('error', {'message': f"Error processing action: {str(e)}"}, room=sid)
    else:
        print(f"Not current player's turn or player not found: {player_id}")

@socketio.on('player_choice')
def handle_player_choice(data):
    """Handle player choice selection."""
    sid = request.sid
    player_id = next((pid for pid, s in player_sids.items() if s == sid), None)
    print(f"Received player choice from {player_id}: {data}")
    
    if not player_id:
        socketio.emit('error', {'message': 'Player not found'}, room=sid)
        return
        
    if not game.current_player or player_id != game.current_player.id:
        socketio.emit('error', {'message': 'Not your turn to choose'}, room=sid)
        return
    
    try:
        value_name = data.get('value_name')
        selected_value = data.get('selected_value')
        
        if not value_name or not selected_value:
            socketio.emit('error', {'message': 'Invalid choice data'}, room=sid)
            return
        
        # Store the choice in the game
        if not hasattr(game, 'game_choices'):
            game.game_choices = {}
        game.game_choices[value_name] = selected_value
        
        # Get player name for broadcast
        player_name = game.table.players[player_id].name
        
        print(f"Player {player_name} chose {selected_value} for {value_name}")
        
        # Broadcast the choice to all players
        for pid, s in player_sids.items():
            socketio.emit('choice_made', {
                'player_id': player_id,
                'player_name': player_name,
                'choice': selected_value,
                'value_name': value_name
            }, room=s)
        
        # Advance the game step
        game._next_step()
        
        # Broadcast updated state to all players
        for pid, s in player_sids.items():
            state = get_game_state_for_player(pid)
            socketio.emit('game_state', state, room=s)
            
    except Exception as e:
        print(f"Exception in handle_player_choice: {e}")
        import traceback
        traceback.print_exc()
        socketio.emit('error', {'message': f"Error processing choice: {str(e)}"}, room=sid)

def run_game_loop():
    """Run the game loop in a separate thread."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(game_loop())

async def wait_for_action(sid):
    """Wait for an action from a specific player."""
    print(f"Waiting for action from player with sid: {sid}")
    loop = asyncio.get_event_loop()
    future = loop.create_future()
    action_futures[sid] = future
    print(f"Created future for sid: {sid}, key exists: {sid in action_futures}")
    
    try:
        result = await future
        print(f"Future completed with result: {result}")
        del action_futures[sid]  # Clean up the future
        return result
    except Exception as e:
        print(f"Error waiting for action: {e}")
        import traceback
        traceback.print_exc()
        raise

async def game_loop():
    """Asynchronous game loop."""
    print("Starting game loop")
    
    while True:
        try:
            # Start a new hand
            game.start_hand()
            print(f"Starting new hand with state {game.state}")
            
            # Initial broadcast after hand starts
            broadcast_game_state()
            
            # Process post blinds step
            if game.current_step == 0 and game.rules.gameplay[0].name == "Post Blinds":
                await asyncio.sleep(1)  # Brief pause to show blinds
                
                # Log before transition
                print(f"Before advancing from Post Blinds: step={game.current_step}, state={game.state}")
                
                game._next_step()  # Advance to dealing cards
                
                # Log after transition
                print(f"After advancing from Post Blinds: step={game.current_step}, state={game.state}")
                
                broadcast_game_state()
            
            # Process deal hole cards
            if game.current_step == 1 and "Deal" in game.rules.gameplay[1].name:
                await asyncio.sleep(1)  # Brief pause to show cards being dealt
                
                # Log before transition
                print(f"Before advancing from Deal Hole Cards: step={game.current_step}, state={game.state}")
                
                game._next_step()  # Advance to first betting round
                
                # Log after transition
                print(f"After advancing from Deal Hole Cards: step={game.current_step}, state={game.state}")
                
                broadcast_game_state()
            
            last_player_id = None

            # Track state changes to reduce logging spam
            last_logged_state = None
            last_logged_step = None
            last_logged_player = None

            # Now wait for game to complete
            while game.state != GameState.COMPLETE:
                # Only log when something actually changes
                current_state_info = (game.current_step, game.state, game.current_player.id if game.current_player else None)
                
                if current_state_info != (last_logged_step, last_logged_state, last_logged_player):
                    print(f"\n=== Game State Changed ===")
                    print(f"Step: {game.current_step} - {game.rules.gameplay[game.current_step].name}")
                    print(f"State: {game.state}")
                    print(f"Current player: {game.current_player.name if game.current_player else 'None'}")
                    
                    # Update tracking variables
                    last_logged_step = game.current_step
                    last_logged_state = game.state  
                    last_logged_player = game.current_player.id if game.current_player else None                

                # Check game state and act accordingly
                if game.state == GameState.DEALING:
                    step = game.rules.gameplay[game.current_step]
                    
                    # NEW: Check if this is a choice step
                    if step.action_type == GameActionType.CHOOSE:
                        print("Processing choice step")
                        choice_config = step.action_config
                        
                        # Send choice options to the current player
                        if game.current_player:
                            sid = player_sids.get(game.current_player.id)
                            if sid:
                                socketio.emit('player_choice', {
                                    'possible_values': choice_config.get('possible_values', []),
                                    'value_name': choice_config.get('value', 'choice'),
                                    'chooser': choice_config.get('chooser', 'utg')
                                }, room=sid)
                                
                                print(f"Sent choice options to {game.current_player.name}")
                        
                        # Wait for choice to be made - the choice handler will advance the step
                        # So we just wait here and don't call _next_step()
                        await asyncio.sleep(1)
                        continue
                        
                    else:
                        # EXISTING: Regular dealing step (your original code)
                        print(f"Auto-processing dealing step: {game.rules.gameplay[game.current_step].name}")
                        await asyncio.sleep(1)

                        # Log before transition
                        print(f"Before advancing from dealing step: step={game.current_step}, state={game.state}")
                        
                        game._next_step()
                        
                        # Log after transition
                        print(f"After advancing from dealing step: step={game.current_step}, state={game.state}")
                        print(f"Current player after dealing: {game.current_player.name if game.current_player else 'None'}")
                        
                        # Reset last_player_id when transitioning to a new betting round
                        if game.state == GameState.BETTING:
                            print("Resetting last_player_id for new betting round")
                            last_player_id = None

                        broadcast_game_state()
                                        
                        # After dealing, log again to verify
                        print(f"After dealing processing complete: step={game.current_step}, state={game.state}")
                        continue
                
                # If no current player in betting, advance
                elif game.state == GameState.BETTING and not game.current_player:
                    print("No player to act in betting round, advancing...")
                    
                    # Log before transition
                    print(f"Before advancing (no player): step={game.current_step}, state={game.state}")
                    
                    game._next_step()
                    
                    # Log after transition
                    print(f"After advancing (no player): step={game.current_step}, state={game.state}")
                    
                    broadcast_game_state()
                    continue

                # Handle current player's turn
                elif game.state == GameState.BETTING and game.current_player:
                    player_id = game.current_player.id
                    
                    # Only send your_turn event once per player per round
                    if not hasattr(game, '_notified_players'):
                        game._notified_players = set()
                    
                    # Create a unique key for this notification
                    notification_key = f"{game.current_step}_{player_id}"
                    
                    if notification_key not in game._notified_players:
                        sid = player_sids.get(player_id)
                        if sid:
                            valid_actions = game.get_valid_actions(player_id)
                            
                            print(f"Notifying {game.current_player.name} of their turn")
                            print(f"Valid actions: {[a[0].value for a in valid_actions]}")
                            
                            # Format actions for client
                            actions = [
                                {'type': a.value, 'min': min_amt, 'max': max_amt} 
                                for a, min_amt, max_amt in valid_actions
                            ]
                            
                            # Notify player it's their turn
                            socketio.emit('your_turn', {'actions': actions}, room=sid)
                            
                            # Mark this player as notified for this step
                            game._notified_players.add(notification_key)
                            
                            print(f"Sent your_turn event to {player_id}")
                        else:
                            print(f"Warning: No socket ID found for player {player_id}")                        

                # Unknown state - log and advance
                else:
                    print(f"Unhandled game state: {game.state}, step: {game.current_step}")

                    # Special handling for showdown
                    if game.state == GameState.SHOWDOWN:
                        print("Processing showdown")
                        
                        # First make all cards visible
                        for player in game.table.players.values():
                            if player.is_active:
                                for card in player.hand.cards:
                                    card.visibility = Visibility.FACE_UP
                        
                        # Broadcast state with all cards visible
                        broadcast_game_state()
                        
                        # Give the game engine time to evaluate hands
                        # This is the key change - we need to wait longer
                        await asyncio.sleep(6)  # Increase from 2 to 6 seconds based on your logs
                        
                        # Now check if the showdown is complete
                        # Look for specific log messages or attributes that indicate completion
                        logging.info("Checking if showdown evaluation is complete")
                        
                        # Try to advance after waiting
                        print("Advancing from showdown to complete")
                        game._next_step()
                        broadcast_game_state()
                        
                        # Wait again to ensure results are available
                        await asyncio.sleep(3)
                    else:
                        # For other unknown states, advance as before
                        print(f"Before advancing (unhandled state): step={game.current_step}, state={game.state}")
                        game._next_step()
                        print(f"After advancing (unhandled state): step={game.current_step}, state={game.state}")
                        broadcast_game_state()
                    
                    continue                 
                
                # Wait for player actions to be processed through socket events
                await asyncio.sleep(1)
            
            # Handle hand completion
            if game.state == GameState.COMPLETE:
                print("Hand complete, checking for results")

                # Don't immediately show results - wait until we have them
                
                # First, just update the game state without triggering results
                for pid, sid in player_sids.items():
                    state = get_game_state_for_player(pid)
                    # Don't include detailed results yet
                    state['showingResults'] = False
                    socketio.emit('game_state', state, room=sid)                
                
                # Try multiple times to get results with delay between attempts
                max_attempts = 5
                for attempt in range(max_attempts):
                    try:
                        # Try to get results
                        logging.info(f"Attempt {attempt+1}/{max_attempts} to get hand results")
                        results = game.get_hand_results()
                        logging.info("Successfully got hand results")

                        # Convert GameResult to a JSON-serializable dict
                        if hasattr(results, 'to_json'):
                            # If it has a to_json method, use it
                            results_json = results.to_json()
                            # If it's a string, parse it into a dict
                            if isinstance(results_json, str):
                                results_dict = json.loads(results_json)
                            else:
                                # If it's already a dict, use it directly
                                results_dict = results_json
                            logging.info("Converted results using to_json method")
                        else:
                            # Otherwise create a dict manually
                            results_dict = {
                                "is_complete": results.is_complete,
                                "total_pot": results.total_pot,
                                "pots": [
                                    {
                                        "amount": pot.amount,
                                        "winners": pot.winners,
                                        "split": pot.split,
                                        "pot_type": pot.pot_type,
                                        "hand_type": pot.hand_type,
                                        "side_pot_index": pot.side_pot_index,
                                        "eligible_players": pot.eligible_players,
                                        "amount_per_player": pot.amount_per_player
                                    } for pot in results.pots
                                ],
                                "hands": {
                                    player_id: [
                                        {
                                            "player_id": hand.player_id,
                                            "cards": [str(c) for c in hand.cards],
                                            "hand_name": hand.hand_name,
                                            "hand_description": hand.hand_description,
                                            "evaluation_type": hand.evaluation_type,
                                            "hand_type": hand.hand_type,
                                            "community_cards": hand.community_cards,
                                            "used_hole_cards": [str(c) for c in hand.used_hole_cards] if hand.used_hole_cards else [],
                                            "rank": hand.rank
                                        } for hand in hands
                                    ] for player_id, hands in results.hands.items()
                                },
                                "winning_hands": [
                                    {
                                        "player_id": hand.player_id,
                                        "cards": [str(c) for c in hand.cards],
                                        "hand_name": hand.hand_name,
                                        "hand_description": hand.hand_description,
                                        "evaluation_type": hand.evaluation_type,
                                        "hand_type": hand.hand_type,
                                        "community_cards": hand.community_cards,
                                        "used_hole_cards": [str(c) for c in hand.used_hole_cards] if hand.used_hole_cards else [],
                                        "rank": hand.rank
                                    } for hand in results.winning_hands
                                ]
                            }
                            logging.info("Manually created JSON-serializable dict from results")                        
                        
                        # Broadcast results to all players
                        for pid, sid in player_sids.items():
                            state = get_game_state_for_player(pid)
                            socketio.emit('game_state', state, room=sid)
                            socketio.emit('hand_complete', results_dict, room=sid)  # Use results_dict, not results
                        
                        # Successfully got results, break the retry loop
                        break
                    except Exception as e:
                        logging.warning(f"Error getting hand results (attempt {attempt+1}): {e}")
                        import traceback
                        traceback.print_exc()                        
                        if attempt < max_attempts - 1:
                            # Not the last attempt, wait and try again
                            await asyncio.sleep(2)                
                        else:
                            # Create a simplified result if we can't get detailed results
                            # This might happen if all players folded except one
                            winners = []
                            # Try to determine the winner
                            for player in game.table.players.values():
                                if player.is_active:
                                    winners.append(player.id)
                                            
                            # Create a simplified result if we can't get detailed results
                            simplified_results = {
                                "is_complete": True,
                                "total_pot": game.betting.get_total_pot(),
                                "pots": [
                                    {
                                        "amount": game.betting.get_total_pot(),
                                        "winners": winners,
                                        "pot_type": "main"
                                    }
                                ],
                                "hands": {},
                                "winning_hands": []
                            }

                            # Try to add player hands to the results
                            for player_id, player in game.table.players.items():
                                if player.is_active:
                                    # Get player's cards
                                    hole_cards = [str(c) for c in player.hand.cards]
                                    
                                    # Get community cards
                                    community_cards = []
                                    for cards in game.table.community_cards.values():
                                        community_cards.extend([str(c) for c in cards])
                                    
                                    # Combine for a complete hand (up to 5 cards)
                                    complete_hand = hole_cards + community_cards
                                    
                                    simplified_results["hands"][player_id] = [{
                                        "player_id": player_id,
                                        "cards": complete_hand[:5],  # Take just first 5 cards for simplicity
                                        "hand_name": "Unknown",
                                        "hand_description": "Unknown hand",
                                        "evaluation_type": "high",
                                        "hand_type": "Hand"
                                    }]
                                    
                                    # If this player is a winner, add to winning_hands
                                    if player_id in winners:
                                        simplified_results["winning_hands"].append({
                                            "player_id": player_id,
                                            "cards": complete_hand[:5],
                                            "hand_name": "Unknown",
                                            "hand_description": "Unknown hand",
                                            "evaluation_type": "high",
                                            "hand_type": "Hand"
                                        })

                
                # Reset ready for next hand flags
                ready_for_next_hand.clear()
                
                # Wait for all players to be ready for the next hand
                print("Waiting for players to be ready for next hand")
                while len(ready_for_next_hand) < len(player_sids):
                    # Wait for players to indicate readiness
                    await asyncio.sleep(1)
                
                print("All players ready for next hand")
                
                # Move button for next hand
                game.table.move_button()
            
            # Short delay between hands
            await asyncio.sleep(1)
            
        except Exception as e:
            print(f"Error in game loop: {e}")
            import traceback
            traceback.print_exc()
            await asyncio.sleep(5)  # Wait before retrying

def broadcast_game_state():
    """Broadcast the current game state to all players."""
    for pid, sid in player_sids.items():
        state = get_game_state_for_player(pid)
        socketio.emit('game_state', state, room=sid)

def start_game():
    """Initialize and start the game."""
    global game
    
    try:
        # Look for the game config file, trying multiple possible locations
        possible_paths = [
            'data/game_configs/hold_em.json',
            '../data/game_configs/hold_em.json',
            '../../data/game_configs/hold_em.json',
            os.path.join(os.path.dirname(__file__), '../data/game_configs/hold_em.json')
        ]
        
        config_path = None
        for path in possible_paths:
            if os.path.exists(path):
                config_path = path
                break
        
        if not config_path:
            raise FileNotFoundError(f"Could not find game configuration file. Tried: {possible_paths}")
        
        print(f"Loading game configuration from: {config_path}")
        with open(config_path, 'r') as f:
            config_data = f.read()
            rules = GameRules.from_json(config_data)
        
        print(f"Creating new game: {rules.game}")
        # Create a new game instance
        game = Game(
            rules=rules, 
            structure=BettingStructure.NO_LIMIT, 
            small_blind=1, 
            big_blind=2,
            auto_progress=False  # We'll manually control game progression
        )
        print(f"Game created: {game.get_game_description()}")
        
    except Exception as e:
        print(f"Error starting game: {e}")
        # Create a simple Hold'em game as fallback
        
        # Try to load a standard config
        try:
            import json
            hold_em_config = {
                "game": "Hold'em",
                "players": {"min": 2, "max": 9},
                "deck": {"type": "standard", "cards": 52},
                "bettingStructures": ["No Limit", "Limit", "Pot Limit"],
                "forcedBets": {"style": "blinds"},
                "bettingOrder": {"initial": "after_big_blind", "subsequent": "dealer"},
                "gamePlay": [
                    {"name": "Post Blinds", "bet": {"type": "blinds"}},
                    {"name": "Deal Hole Cards", "deal": {"location": "player", "cards": [{"number": 2, "state": "face down"}]}},
                    {"name": "Pre-Flop Bet", "bet": {"type": "small"}},
                    {"name": "Deal Flop", "deal": {"location": "community", "cards": [{"number": 3, "state": "face up"}]}},
                    {"name": "Post-Flop Bet", "bet": {"type": "small"}},
                    {"name": "Deal Turn", "deal": {"location": "community", "cards": [{"number": 1, "state": "face up"}]}},
                    {"name": "Turn Bet", "bet": {"type": "big"}},
                    {"name": "Deal River", "deal": {"location": "community", "cards": [{"number": 1, "state": "face up"}]}},
                    {"name": "River Bet", "bet": {"type": "big"}},
                    {"name": "Showdown", "showdown": {"type": "final"}}
                ],
                "showdown": {
                    "order": "clockwise",
                    "startingFrom": "dealer",
                    "cardsRequired": "any combination of hole and community cards",
                    "bestHand": [{"evaluationType": "high", "anyCards": 5}]
                }
            }
            
            rules = GameRules.from_json(json.dumps(hold_em_config))
            game = Game(
                rules=rules,
                structure=BettingStructure.NO_LIMIT,
                small_blind=1,
                big_blind=2,
                auto_progress=False
            )
            print("Created fallback Hold'em game")
        except Exception as e2:
            print(f"Failed to create fallback game: {e2}")
            raise

# Add cleanup function for completed hands
def cleanup_disconnected_players():
    """Clean up disconnected player tracking after hand completion."""
    global disconnected_players, reconnect_timers
    
    # Cancel any remaining timers
    for timer in reconnect_timers.values():
        timer.cancel()
    
    # Clear tracking dictionaries
    disconnected_players.clear()
    reconnect_timers.clear()
    
    print("Cleaned up disconnection tracking")

if __name__ == '__main__':
    # Create directory structure if needed
    os.makedirs('static', exist_ok=True)
    os.makedirs('templates', exist_ok=True)
    
    # Start the server
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
