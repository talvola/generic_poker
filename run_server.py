#!/usr/bin/env python3
"""Simple server to run the poker lobby for testing."""

import os
import sys
import logging
from flask import Flask, render_template, redirect, url_for, request, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user

# Add src to path so we can import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from online_poker.services.game_manager import game_manager, GameConfig
from online_poker.services.simple_bot import bot_manager
from online_poker.services.game_action_logger import game_action_logger
# from online_poker.routes.game_routes import game_bp  # Disabled for demo
from online_poker.services.websocket_manager import init_websocket_manager
from online_poker.database import db
from generic_poker.game.game import GameState

# Simple in-memory storage for demo
users = {}
tables = []

class User(UserMixin):
    def __init__(self, id, username, email, bankroll=1000):
        self.id = id
        self.username = username
        self.email = email
        self.bankroll = bankroll
    
    def get_id(self):
        return str(self.id)
    
    @property
    def is_authenticated(self):
        return True
    
    @property
    def is_active(self):
        return True
    
    @property
    def is_anonymous(self):
        return False

# Create Flask app
app = Flask(__name__, 
           template_folder='templates',
           static_folder='static')
app.config['SECRET_KEY'] = 'dev-secret-key-for-testing'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///demo_poker.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize SocketIO
socketio = SocketIO(app, cors_allowed_origins="*")

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Register blueprints
# app.register_blueprint(game_bp)  # Disabled for demo - using custom endpoints instead

# Initialize WebSocket manager
init_websocket_manager(socketio)

# Initialize database
db.init_app(app)

# Template filters
@app.template_filter('format_variant')
def format_variant(variant):
    """Format poker variant name for display."""
    variants = {
        'hold_em': "Texas Hold'em",
        'omaha': 'Omaha',
        'omaha_8': 'Omaha Hi-Lo',
        '7_card_stud': '7-Card Stud',
        '7_card_stud_8': '7-Card Stud Hi-Lo',
        'razz': 'Razz',
        'mexican_poker': 'Mexican Poker'
    }
    return variants.get(variant, variant.replace('_', ' ').title())

@app.template_filter('format_structure')
def format_structure(structure):
    """Format betting structure for display."""
    return structure.replace('-', ' ').replace('_', ' ').title()

@login_manager.user_loader
def load_user(user_id):
    return users.get(user_id)

# Routes
@app.route('/')
def index():
    """Main lobby page."""
    if current_user.is_authenticated:
        return render_template('lobby.html')
    else:
        return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Simple login page."""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        if username:
            # Create or get user
            user_id = f"user_{len(users) + 1}"
            if username not in [u.username for u in users.values()]:
                user = User(user_id, username, f"{username}@example.com")
                users[user_id] = user
            else:
                user = next(u for u in users.values() if u.username == username)
            
            login_user(user)
            return redirect(url_for('index'))
    
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Poker Platform - Login</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 400px; margin: 100px auto; padding: 20px; }
            input, button { width: 100%; padding: 10px; margin: 10px 0; font-size: 16px; }
            button { background: #007bff; color: white; border: none; cursor: pointer; }
            button:hover { background: #0056b3; }
        </style>
    </head>
    <body>
        <h2>🎲 Poker Platform Login</h2>
        <form method="post">
            <input type="text" name="username" placeholder="Enter your username" required>
            <button type="submit">Join Lobby</button>
        </form>
        <p><small>Just enter any username to join the demo lobby!</small></p>
    </body>
    </html>
    '''

@app.route('/logout')
@login_required
def logout():
    """Logout user."""
    logout_user()
    return redirect(url_for('login'))

@app.route('/table/<table_id>')
@login_required
def table_view(table_id):
    """View a specific poker table."""
    table = next((t for t in tables if t['id'] == table_id), None)
    
    if not table:
        return redirect(url_for('index'))
    
    # Demo: Ensure current user is counted as a player
    if table['current_players'] == 0:
        table['current_players'] = 1
    
    return render_template('table.html', table=table)

@app.route('/lobby')
@login_required
def lobby():
    """Lobby page."""
    return render_template('lobby.html')

# API Routes for lobby
@app.route('/api/tables')
def get_tables():
    """Get list of active tables."""
    return jsonify({
        'success': True,
        'tables': tables
    })

@app.route('/api/tables/<table_id>/seats')
def get_table_seats(table_id):
    """Get seat information for a table."""
    table = next((t for t in tables if t['id'] == table_id), None)
    
    if not table:
        return jsonify({
            'success': False,
            'error': 'Table not found'
        }), 404
    
    # Initialize players dict if it doesn't exist
    if 'players' not in table:
        table['players'] = {}
    
    # Build seat information
    seats = []
    for seat_num in range(1, table['max_players'] + 1):
        if seat_num in table['players']:
            player = table['players'][seat_num]
            seat_info = {
                'seat_number': seat_num,
                'is_available': False,
                'player': {
                    'username': player['username'],
                    'stack': player['stack']
                }
            }
        else:
            seat_info = {
                'seat_number': seat_num,
                'is_available': True,
                'player': None
            }
        seats.append(seat_info)
    
    return jsonify({
        'success': True,
        'table_id': table_id,
        'table_name': table['name'],
        'max_players': table['max_players'],
        'current_players': len(table['players']),
        'seats': seats,
        'minimum_buyin': table.get('minimum_buyin', 50),
        'maximum_buyin': table.get('maximum_buyin', 500)
    })

@app.route('/api/tables', methods=['POST'])
@login_required
def create_table():
    """Create a new table."""
    try:
        data = request.get_json()
        
        table = {
            'id': f"table_{len(tables) + 1}",
            'name': data.get('name', 'New Table'),
            'variant': data.get('variant', 'hold_em'),
            'betting_structure': data.get('betting_structure', 'no-limit'),
            'stakes': data.get('stakes', {'small_blind': 1, 'big_blind': 2}),
            'max_players': data.get('max_players', 6),
            'current_players': 0,
            'is_private': data.get('is_private', False),
            'allow_bots': data.get('allow_bots', False),
            'creator_id': current_user.id,
            'created_at': '2024-01-01T00:00:00',
            'minimum_buyin': 50,
            'maximum_buyin': 500
        }
        
        if table['is_private']:
            table['invite_code'] = f"DEMO{len(tables):04d}"
        
        tables.append(table)
        
        # Broadcast table update
        socketio.emit('table_list', {'tables': tables})
        
        return jsonify({
            'success': True,
            'table_id': table['id'],
            'message': 'Table created successfully'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# WebSocket events
@socketio.on('connect')
def handle_connect():
    print(f"Client connected: {request.sid}")

@socketio.on('disconnect')
def handle_disconnect():
    print(f"Client disconnected: {request.sid}")

@socketio.on('get_table_list')
def handle_get_table_list(data=None):
    """Send table list to client."""
    emit('table_list', {'tables': tables})

@socketio.on('create_table')
def handle_create_table(data):
    """Handle table creation via WebSocket."""
    if not current_user.is_authenticated:
        emit('error', {'message': 'Authentication required'})
        return
    
    try:
        table = {
            'id': f"table_{len(tables) + 1}",
            'name': data.get('name', 'New Table'),
            'variant': data.get('variant', 'hold_em'),
            'betting_structure': data.get('betting_structure', 'no-limit'),
            'stakes': data.get('stakes', {'small_blind': 1, 'big_blind': 2}),
            'max_players': data.get('max_players', 6),
            'current_players': 0,
            'is_private': data.get('is_private', False),
            'allow_bots': data.get('allow_bots', False),
            'creator_id': current_user.id,
            'created_at': '2024-01-01T00:00:00',
            'minimum_buyin': 50,
            'maximum_buyin': 500
        }
        
        if table['is_private']:
            table['invite_code'] = f"DEMO{len(tables):04d}"
        
        tables.append(table)
        
        emit('table_created', {
            'table_id': table['id'],
            'message': 'Table created successfully'
        })
        
        # Broadcast to all clients
        socketio.emit('table_list', {'tables': tables})
        
    except Exception as e:
        emit('error', {'message': f'Failed to create table: {str(e)}'})

@socketio.on('join_table')
def handle_join_table(data):
    """Handle joining a table."""
    if not current_user.is_authenticated:
        emit('error', {'message': 'Authentication required'})
        return
    
    table_id = data.get('table_id')
    buy_in_amount = data.get('buy_in_amount', 100)  # Default buy-in
    seat_number = data.get('seat_number')  # Optional seat preference
    
    table = next((t for t in tables if t['id'] == table_id), None)
    
    if not table:
        emit('error', {'message': 'Table not found'})
        return
    
    if table['current_players'] >= table['max_players']:
        emit('error', {'message': 'Table is full'})
        return
    
    # Check if user has sufficient bankroll
    if current_user.bankroll < buy_in_amount:
        emit('error', {'message': 'Insufficient bankroll'})
        return
    
    # For demo, simulate joining with seat assignment
    if 'players' not in table:
        table['players'] = {}
    
    # Check if user is already seated at this table
    for seat_num, player in table['players'].items():
        if player['user_id'] == current_user.id:
            emit('error', {'message': f'You are already seated at this table in seat {seat_num}'})
            return
    
    # Find available seat
    occupied_seats = set(table['players'].keys())
    assigned_seat = None
    
    if seat_number and seat_number not in occupied_seats and 1 <= seat_number <= table['max_players']:
        assigned_seat = seat_number
    else:
        # Auto-assign first available seat
        for seat in range(1, table['max_players'] + 1):
            if seat not in occupied_seats:
                assigned_seat = seat
                break
    
    if assigned_seat is None:
        emit('error', {'message': 'No available seats'})
        return
    
    # Add player to table
    table['players'][assigned_seat] = {
        'user_id': current_user.id,
        'username': current_user.username,
        'buy_in': buy_in_amount,
        'stack': buy_in_amount,
        'seat_number': assigned_seat
    }
    
    # Update player count
    table['current_players'] = len(table['players'])
    
    # Create or get game instance
    game = game_manager.get_game(table_id)
    if not game:
        # Create game configuration from table
        config = GameConfig(
            variant=table['variant'],
            betting_structure=table['betting_structure'],
            small_blind=table['stakes']['small_blind'],
            big_blind=table['stakes']['big_blind'],
            min_buyin=table['minimum_buyin'],
            max_buyin=table['maximum_buyin'],
            max_players=table['max_players']
        )
        print(f"DEBUG: Creating game with max_players: {config.max_players}")
        game = game_manager.create_game(table_id, config)
        
        # Add existing demo players to the game
        for seat_num, player in table['players'].items():
            if player['user_id'] != current_user.id:  # Don't add current user twice
                game_manager.add_player_to_game(table_id, player['user_id'], player['username'], player['stack'], int(seat_num))
                print(f"DEBUG: Added existing player {player['username']} to game in seat {seat_num}")
    
    # Add current player to game
    game_manager.add_player_to_game(table_id, current_user.id, current_user.username, buy_in_amount, assigned_seat)
    
    # Check if we can start a hand
    if game_manager.can_start_hand(table_id):
        current_state = game.state.value if game.state else 'None'
        print(f"DEBUG: Game state for table {table_id}: {current_state}")
        if game.state is None or game.state == GameState.WAITING:
            print(f"DEBUG: Starting hand for table {table_id}")
            success = game_manager.start_hand_with_progression(table_id, process_game_progression)
            print(f"DEBUG: Hand start with progression result: {success}")
            if success:
                new_state = game.state.value if game.state else 'None'
                print(f"DEBUG: New game state: {new_state}")
                
                # Broadcast all actions that occurred during hand start and progression
                broadcast_game_actions(table_id)
        else:
            print(f"DEBUG: Cannot start hand - game state is {current_state}")
            # If the hand is already in progress, we might have missed the forced bets
            # Let's try to reconstruct them from the current game state
            if current_state in ['betting', 'dealing']:
                print(f"DEBUG: Hand already started, trying to log missed forced bets")
                game_manager.log_missed_forced_bets(table_id)
                broadcast_game_actions(table_id)
    else:
        print(f"DEBUG: Cannot start hand for table {table_id} - insufficient players")
    
    # Debug: Print table state after joining
    print(f"DEBUG: After {current_user.username} joined table {table_id}:")
    for seat_num, player in table['players'].items():
        print(f"  Seat {seat_num}: {player['username']} (user_id: {player['user_id']})")
    
    # Deduct buy-in from user bankroll (demo)
    current_user.bankroll -= buy_in_amount
    
    # Success response
    emit('table_joined', {
        'table_id': table_id,
        'seat_number': assigned_seat,
        'buy_in_amount': buy_in_amount,
        'message': f'Joined table in seat {assigned_seat} with ${buy_in_amount} buy-in'
    })
    
    # Broadcast to all clients that table state changed
    socketio.emit('table_list', {'tables': tables})

@socketio.on('connect_to_table')
def handle_connect_to_table(data):
    """Handle connecting to a table for gameplay (different from joining)."""
    if not current_user.is_authenticated:
        emit('error', {'message': 'Authentication required'})
        return
    
    table_id = data.get('table_id')
    table = next((t for t in tables if t['id'] == table_id), None)
    
    if not table:
        emit('error', {'message': 'Table not found'})
        return
    
    # Initialize players dict if it doesn't exist
    if 'players' not in table:
        table['players'] = {}
    
    # Debug: Print current table state
    print(f"DEBUG: Table {table_id} players before sending game_state:")
    for seat_num, player in table['players'].items():
        print(f"  Seat {seat_num}: {player['username']} (user_id: {player['user_id']})")
    
    # Get game state from game manager
    game_state = game_manager.get_game_state(table_id, table, current_user.id)
    
    if game_state:
        # Debug: Print game state players
        print(f"DEBUG: Game state players: {game_state.get('players', {})}")
        
        # Use actual game state
        emit('game_state', {
            **game_state,
            'table_name': table['name'],
            'variant': table['variant'],
            'betting_structure': table['betting_structure'],
            'stakes': table['stakes'],
            'max_players': table['max_players'],
            'current_players': len(table['players']),
            'current_user': {'id': current_user.id, 'username': current_user.username}
        })
    else:
        # Fallback to basic state if no game exists yet
        emit('game_state', {
            'table_id': table_id,
            'table_name': table['name'],
            'variant': table['variant'],
            'betting_structure': table['betting_structure'],
            'stakes': table['stakes'],
            'max_players': table['max_players'],
            'current_players': len(table['players']),
            'players': table['players'],
            'pot_amount': 0,
            'community_cards': {},
            'hand_number': 1,
            'game_state': 'waiting',
            'current_player': None,
            'is_hand_active': False,
            'dealer_position': None,
            'valid_actions': {},
            'current_user': {'id': current_user.id, 'username': current_user.username}
        })
    
    # Join the table room for real-time updates
    join_room(table_id)
    print(f"DEBUG: User {current_user.username} joined room {table_id}")
    
    # Send recent game actions to the newly connected player
    recent_actions = game_manager.get_recent_game_actions(table_id, limit=10)
    print(f"DEBUG: Sending {len(recent_actions)} recent actions to {current_user.username}")
    for action in recent_actions:
        emit('chat_message', action)
        print(f"DEBUG: Sent action: {action.get('message', 'No message')}")
    

    
    print(f"User {current_user.username} connected to table {table_id}")

@socketio.on('spectate_table')
def handle_spectate_table(data):
    """Handle spectating a table."""
    if not current_user.is_authenticated:
        emit('error', {'message': 'Authentication required'})
        return
    
    table_id = data.get('table_id')
    table = next((t for t in tables if t['id'] == table_id), None)
    
    if not table:
        emit('error', {'message': 'Table not found'})
        return
    
    # For demo, just show success message
    emit('table_joined', {
        'table_id': table_id,
        'message': 'Spectating table! (Demo mode - actual game not implemented yet)'
    })

@socketio.on('leave_table')
def handle_leave_table(data):
    """Handle leaving a table."""
    if not current_user.is_authenticated:
        emit('error', {'message': 'Authentication required'})
        return
    
    table_id = data.get('table_id')
    table = next((t for t in tables if t['id'] == table_id), None)
    
    if not table:
        emit('error', {'message': 'Table not found'})
        return
    
    # Initialize players dict if it doesn't exist
    if 'players' not in table:
        table['players'] = {}
    
    # Find and remove the player
    player_seat = None
    for seat_num, player in table['players'].items():
        if player['user_id'] == current_user.id:
            player_seat = seat_num
            break
    
    if player_seat is None:
        emit('error', {'message': 'You are not seated at this table'})
        return
    
    # Remove player from table
    removed_player = table['players'].pop(player_seat)
    
    # Update player count
    table['current_players'] = len(table['players'])
    
    # Return buy-in to user bankroll (demo)
    current_user.bankroll += removed_player['stack']
    
    # Debug: Print table state after leaving
    print(f"DEBUG: After {current_user.username} left table {table_id}:")
    for seat_num, player in table['players'].items():
        print(f"  Seat {seat_num}: {player['username']} (user_id: {player['user_id']})")
    
    # Leave the table room
    leave_room(table_id)
    
    # Success response
    emit('table_left', {
        'table_id': table_id,
        'message': f'Left table and returned ${removed_player["stack"]} to bankroll'
    })
    
    # Broadcast to all clients that table state changed
    socketio.emit('table_list', {'tables': tables})
    
    print(f"User {current_user.username} left table {table_id}")

def broadcast_game_actions(table_id):
    """Broadcast new game actions to all players at the table."""
    try:
        # Get only new actions that haven't been broadcast yet
        actions = game_manager.get_new_game_actions_for_broadcast(table_id)
        
        # Broadcast each action as a chat message
        for action in actions:
            socketio.emit('chat_message', action, room=table_id)
            print(f"DEBUG: Broadcasting game action: {action['message']}")
            
    except Exception as e:
        print(f"Error broadcasting game actions for {table_id}: {e}")

def process_game_progression(table_id):
    """Process automatic game progression for bots and game state advancement."""
    try:
        game = game_manager.get_game(table_id)
        if not game:
            return
        
        # Process up to 10 automatic actions to prevent infinite loops
        for _ in range(10):
            # Check if we need to advance game state (dealing, etc.)
            if game_manager.advance_game_state(table_id):
                # Broadcast updated game state
                game_state = game_manager.get_game_state(table_id)
                if game_state:
                    socketio.emit('game_state', game_state, room=table_id)
                
                # Broadcast any new game actions
                broadcast_game_actions(table_id)
                continue
            
            # Check if current player is a bot that needs to act
            if game_manager.needs_bot_action(table_id):
                if game_manager.process_bot_action(table_id):
                    # Broadcast updated game state after bot action
                    game_state = game_manager.get_game_state(table_id)
                    if game_state:
                        socketio.emit('game_state', game_state, room=table_id)
                    
                    # Broadcast any new game actions
                    broadcast_game_actions(table_id)
                    continue
            
            # No more automatic actions needed
            break
            
    except Exception as e:
        print(f"Error in game progression for {table_id}: {e}")

@app.route('/api/games/sessions/<table_id>/action', methods=['POST'])
@login_required
def process_player_action_demo(table_id: str):
    """Process a player action using the old game_manager (demo version)."""
    try:
        data = request.get_json()
        if not data or 'action' not in data:
            return jsonify({
                'success': False,
                'error': 'Action required'
            }), 400
        
        # Parse action
        try:
            from generic_poker.game.game_state import PlayerAction
            action = PlayerAction(data['action'])
        except ValueError:
            return jsonify({
                'success': False,
                'error': f'Invalid action: {data["action"]}'
            }), 400
        
        amount = data.get('amount', 0)
        
        # Get the game
        game = game_manager.get_game(table_id)
        if not game:
            return jsonify({
                'success': False,
                'error': 'Game not found'
            }), 404
        
        # Check if it's the player's turn
        if not game.current_player or game.current_player.id != current_user.id:
            return jsonify({
                'success': False,
                'error': 'Not your turn to act'
            }), 400
        
        # Process the action
        try:
            print(f"DEBUG: Processing action {action.value} with amount {amount} for player {current_user.id}")
            result = game.player_action(current_user.id, action, amount)
            print(f"DEBUG: Action result: success={result.success}, error={result.error}, advance_step={result.advance_step}")
            if result.success:
                # For call actions, use the amount that was validated by the game engine
                # The amount parameter already represents the total call amount
                log_amount = amount
                
                # Log the player action
                game_action_logger.log_player_action(
                    table_id=table_id,
                    step=game.current_step,
                    game_state=game.state.name,
                    player_id=current_user.id,
                    player_name=current_user.username,
                    action_type=action.value.lower(),
                    amount=log_amount if log_amount and log_amount > 0 else None
                )
                
                # Check if we need to advance to the next step
                if result.advance_step:
                    old_step = game.current_step
                    old_state = game.state.name
                    
                    # Advance to the next step
                    game._next_step()
                    
                    # Log the step transition for important phases only
                    step_name = "Unknown Step"
                    if hasattr(game.rules, 'gameplay') and game.current_step < len(game.rules.gameplay):
                        step_name = game.rules.gameplay[game.current_step].name
                    
                    # Only log betting and showdown phases, not dealing phases
                    if 'bet' in step_name.lower() or 'showdown' in step_name.lower():
                        game_action_logger.log_phase_change(
                            table_id=table_id,
                            step=game.current_step,
                            old_state=old_state,
                            new_state=game.state.name,
                            phase_name=step_name
                        )
                
                # Broadcast updated game state
                game_state = game_manager.get_game_state(table_id)
                if game_state:
                    socketio.emit('game_state', game_state, room=table_id)
                
                # Broadcast the player action
                broadcast_game_actions(table_id)
                
                # Process any automatic progression
                process_game_progression(table_id)
                
                return jsonify({
                    'success': True,
                    'message': 'Action processed successfully'
                })
            else:
                return jsonify({
                    'success': False,
                    'error': result.error or 'Action failed'
                }), 400
                
        except Exception as e:
            return jsonify({
                'success': False,
                'error': f'Action processing error: {str(e)}'
            }), 400
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Server error: {str(e)}'
        }), 500

@app.route('/api/games/sessions/<table_id>/test', methods=['GET'])
def test_demo_endpoint(table_id: str):
    """Test endpoint to verify demo endpoints are working."""
    return jsonify({
        'success': True,
        'message': f'Demo endpoint working for table {table_id}',
        'endpoint': 'demo'
    })

@app.route('/api/games/sessions/<table_id>/actions', methods=['GET'])
@login_required
def get_available_actions_demo(table_id: str):
    """Get available actions using the old game_manager (demo version)."""
    try:
        game = game_manager.get_game(table_id)
        if not game:
            return jsonify({
                'success': True,
                'actions': [],
                'timeout_info': {'user_id': current_user.id, 'has_active_timeout': False, 'remaining_seconds': 0},
                'count': 0
            })
        
        # Check if it's the player's turn
        if not game.current_player or game.current_player.id != current_user.id:
            return jsonify({
                'success': True,
                'actions': [],
                'timeout_info': {'user_id': current_user.id, 'has_active_timeout': False, 'remaining_seconds': 0},
                'count': 0
            })
        
        # Get valid actions
        try:
            actions = game.get_valid_actions(current_user.id)
            formatted_actions = game_manager._format_valid_actions_for_ui(actions)
            
            print(f"DEBUG: Found {len(actions)} valid actions for {current_user.username}: {[a[0].value for a in actions]}")
            print(f"DEBUG: Formatted actions: {formatted_actions}")
            
            return jsonify({
                'success': True,
                'actions': formatted_actions,
                'timeout_info': {'user_id': current_user.id, 'has_active_timeout': False, 'remaining_seconds': 0},
                'count': len(formatted_actions)
            })
            
        except Exception as e:
            print(f"DEBUG: Error getting valid actions: {e}")
            return jsonify({
                'success': True,
                'actions': [],
                'timeout_info': {'user_id': current_user.id, 'has_active_timeout': False, 'remaining_seconds': 0},
                'count': 0
            })
        
    except Exception as e:
        print(f"DEBUG: Server error in get_available_actions_demo: {e}")
        return jsonify({
            'success': True,
            'actions': [],
            'timeout_info': {'user_id': current_user.id, 'has_active_timeout': False, 'remaining_seconds': 0},
            'count': 0
        })

@socketio.on('request_game_update')
def handle_request_game_update(data):
    """Handle request for game state update and process any pending bot actions."""
    if not current_user.is_authenticated:
        emit('error', {'message': 'Authentication required'})
        return
    
    table_id = data.get('table_id')
    if not table_id:
        emit('error', {'message': 'Table ID required'})
        return
    
    # Process any pending game progression
    process_game_progression(table_id)
    
    # Send updated game state
    game_state = game_manager.get_game_state(table_id, current_user_id=current_user.id)
    if game_state:
        emit('game_state', game_state)

if __name__ == '__main__':
    # Setup logging
    logging.basicConfig(level=logging.INFO)
    
    print("🎲 Starting Poker Platform Demo Server...")
    print("📍 Access the lobby at: http://localhost:5000")
    print("🔧 Demo mode: Simple in-memory storage")
    print("👤 Login with any username to test the lobby")
    print()
    
    # Add some demo tables
    tables.extend([
        {
            'id': 'demo_table_1',
            'name': 'Beginner Hold\'em',
            'variant': 'hold_em',
            'betting_structure': 'no-limit',
            'stakes': {'small_blind': 1, 'big_blind': 2},
            'max_players': 6,
            'current_players': 2,
            'is_private': False,
            'allow_bots': True,
            'creator_id': 'demo_user',
            'created_at': '2024-01-01T00:00:00',
            'minimum_buyin': 50,
            'maximum_buyin': 500,
            'players': {
                2: {
                    'user_id': 'demo_player_1',
                    'username': 'Alice',
                    'buy_in': 200,
                    'stack': 180,
                    'seat_number': 2
                },
                5: {
                    'user_id': 'demo_player_2',
                    'username': 'Bob',
                    'buy_in': 150,
                    'stack': 220,
                    'seat_number': 5
                }
            }
        },
        {
            'id': 'demo_table_2',
            'name': 'High Stakes Omaha',
            'variant': 'omaha',
            'betting_structure': 'pot-limit',
            'stakes': {'small_blind': 5, 'big_blind': 10},
            'max_players': 9,
            'current_players': 7,
            'is_private': False,
            'allow_bots': True,
            'creator_id': 'demo_user',
            'created_at': '2024-01-01T00:00:00',
            'minimum_buyin': 200,
            'maximum_buyin': 2000,
            'players': {
                1: {'user_id': 'demo_player_3', 'username': 'Charlie', 'buy_in': 500, 'stack': 450, 'seat_number': 1},
                3: {'user_id': 'demo_player_4', 'username': 'Diana', 'buy_in': 400, 'stack': 600, 'seat_number': 3},
                4: {'user_id': 'demo_player_5', 'username': 'Eve', 'buy_in': 300, 'stack': 280, 'seat_number': 4},
                6: {'user_id': 'demo_player_6', 'username': 'Frank', 'buy_in': 600, 'stack': 750, 'seat_number': 6},
                7: {'user_id': 'demo_player_7', 'username': 'Grace', 'buy_in': 350, 'stack': 320, 'seat_number': 7},
                8: {'user_id': 'demo_player_8', 'username': 'Henry', 'buy_in': 500, 'stack': 480, 'seat_number': 8},
                9: {'user_id': 'demo_player_9', 'username': 'Ivy', 'buy_in': 400, 'stack': 520, 'seat_number': 9}
            }
        },
        {
            'id': 'demo_table_3',
            'name': 'Private Game',
            'variant': 'hold_em',
            'betting_structure': 'limit',
            'stakes': {'small_bet': 10, 'big_bet': 20},
            'max_players': 4,
            'current_players': 1,
            'is_private': True,
            'invite_code': 'DEMO0001',
            'allow_bots': True,
            'creator_id': 'demo_user',
            'created_at': '2024-01-01T00:00:00',
            'minimum_buyin': 100,
            'maximum_buyin': 1000,
            'players': {
                3: {
                    'user_id': 'demo_player_10',
                    'username': 'Jack',
                    'buy_in': 300,
                    'stack': 280,
                    'seat_number': 3
                }
            }
        }
    ])
    
    socketio.run(
        app, 
        debug=True, 
        host='0.0.0.0', 
        port=5000,
        allow_unsafe_werkzeug=True
    )