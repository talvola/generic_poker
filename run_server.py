#!/usr/bin/env python3
"""Simple server to run the poker lobby for testing."""

import os
import sys
import logging
from flask import Flask, render_template, redirect, url_for, request, jsonify
from flask_socketio import SocketIO, emit
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user

# Add src to path so we can import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

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

# Initialize SocketIO
socketio = SocketIO(app, cors_allowed_origins="*")

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

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
    table = next((t for t in tables if t['id'] == table_id), None)
    
    if not table:
        emit('error', {'message': 'Table not found'})
        return
    
    if table['current_players'] >= table['max_players']:
        emit('error', {'message': 'Table is full'})
        return
    
    # For demo, just show success message
    emit('table_joined', {
        'table_id': table_id,
        'message': 'Joined table successfully! (Demo mode - actual game not implemented yet)'
    })

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
            'maximum_buyin': 500
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
            'allow_bots': False,
            'creator_id': 'demo_user',
            'created_at': '2024-01-01T00:00:00',
            'minimum_buyin': 200,
            'maximum_buyin': 2000
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
            'allow_bots': False,
            'creator_id': 'demo_user',
            'created_at': '2024-01-01T00:00:00',
            'minimum_buyin': 100,
            'maximum_buyin': 1000
        }
    ])
    
    socketio.run(
        app, 
        debug=True, 
        host='0.0.0.0', 
        port=5000,
        allow_unsafe_werkzeug=True
    )