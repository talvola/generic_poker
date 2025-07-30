"""Main Flask application for the Online Poker Platform."""

import os
import logging
from flask import Flask, render_template, redirect, url_for
from flask_socketio import SocketIO
from flask_login import LoginManager, login_required

# Import our modules
from src.online_poker.database import db, init_database, create_tables
from src.online_poker.config import Config
from src.online_poker.auth import init_login_manager
from src.online_poker.routes.auth_routes import auth_bp
from src.online_poker.routes.lobby_routes import lobby_bp, register_lobby_socket_events
from src.online_poker.routes.table_routes import table_bp
from src.online_poker.routes.game_routes import game_bp
from src.online_poker.services.websocket_manager import init_websocket_manager

def create_app(config_class=Config):
    """Create and configure the Flask application."""
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Initialize extensions
    db.init_app(app)
    
    # Initialize SocketIO
    socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')
    
    # Initialize authentication
    login_manager = init_login_manager(app)
    
    # Register blueprints
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(lobby_bp, url_prefix='/')
    app.register_blueprint(table_bp, url_prefix='/table')
    app.register_blueprint(game_bp, url_prefix='/game')
    
    # Initialize WebSocket manager
    websocket_manager = init_websocket_manager(socketio)
    
    # Register WebSocket events
    register_lobby_socket_events(socketio)
    
    # Initialize database
    init_database(app)
    
    # Create database tables
    with app.app_context():
        create_tables()
    
    # Root route
    @app.route('/')
    def index():
        """Redirect to lobby."""
        return redirect(url_for('lobby.index'))
    
    return app, socketio

def setup_logging():
    """Set up logging for the application."""
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('poker_platform.log')
        ]
    )

if __name__ == '__main__':
    setup_logging()
    
    app, socketio = create_app()
    
    print("🎲 Starting Online Poker Platform...")
    print("📍 Access the lobby at: http://localhost:5000")
    print("🔧 Debug mode: ON")
    
    socketio.run(
        app, 
        debug=True, 
        host='0.0.0.0', 
        port=5000,
        allow_unsafe_werkzeug=True
    )