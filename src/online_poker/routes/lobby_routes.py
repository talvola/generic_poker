"""Routes for the poker lobby interface."""

from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from flask_login import login_required, current_user
from flask_socketio import emit, join_room, leave_room

from ..models.table import PokerTable
from ..models.user import User
from ..models.table_access import TableAccess
from ..services.table_manager import TableManager
from ..services.table_access_manager import TableAccessManager
from ..services.websocket_manager import get_websocket_manager
from ..database import db

lobby_bp = Blueprint('lobby', __name__)
table_manager = TableManager()


@lobby_bp.route('/')
def index():
    """Main lobby page."""
    return render_template('lobby.html')


@lobby_bp.route('/api/tables')
def get_tables():
    """Get list of active tables."""
    try:
        # Get all public tables
        tables = db.session.query(PokerTable).filter(
            PokerTable.is_private == False
        ).all()

        table_list = []
        for table in tables:
            table_data = table.to_dict()
            table_list.append(table_data)

        # Get list of table IDs where current user is seated (for "Rejoin" button)
        user_tables = []
        if current_user.is_authenticated:
            user_access_records = db.session.query(TableAccess).filter(
                TableAccess.user_id == current_user.id,
                TableAccess.is_active == True,
                TableAccess.is_spectator == False
            ).all()
            user_tables = [str(access.table_id) for access in user_access_records]

        return jsonify({
            'success': True,
            'tables': table_list,
            'user_tables': user_tables  # Tables where user is already seated
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@lobby_bp.route('/api/tables', methods=['POST'])
def create_table():
    """Create a new poker table."""
    try:
        # Check authentication for API calls
        if not current_user.is_authenticated:
            return jsonify({
                'success': False,
                'error': 'Authentication required'
            }), 401
        
        print(f"DEBUG: User authenticated: {current_user.is_authenticated}")
        print(f"DEBUG: Current user: {current_user}")
        data = request.get_json()
        print(f"DEBUG: Request data: {data}")
        
        # Validate required fields
        required_fields = ['name', 'variant', 'betting_structure', 'max_players', 'stakes']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    'success': False,
                    'error': f'Missing required field: {field}'
                }), 400
        
        # Validate stakes
        stakes = data['stakes']
        betting_structure = data['betting_structure']
        
        if betting_structure == 'limit':
            if 'small_bet' not in stakes or 'big_bet' not in stakes:
                return jsonify({
                    'success': False,
                    'error': 'Limit games require small_bet and big_bet'
                }), 400
        else:
            if 'small_blind' not in stakes or 'big_blind' not in stakes:
                return jsonify({
                    'success': False,
                    'error': 'Blind games require small_blind and big_blind'
                }), 400
        
        # Create table config object
        from ..models.table_config import TableConfig
        from generic_poker.game.betting import BettingStructure
        
        print(f"DEBUG: About to create table with data: {data}")
        print(f"DEBUG: Current user ID: {current_user.id}")
        
        # Convert betting structure string to enum
        betting_structure_map = {
            'no-limit': BettingStructure.NO_LIMIT,
            'pot-limit': BettingStructure.POT_LIMIT,
            'limit': BettingStructure.LIMIT
        }
        
        betting_structure_enum = betting_structure_map.get(data['betting_structure'])
        if not betting_structure_enum:
            return jsonify({
                'success': False,
                'error': f'Invalid betting structure: {data["betting_structure"]}'
            }), 400
        
        # Create table config
        config = TableConfig(
            name=data['name'],
            variant=data['variant'],
            betting_structure=betting_structure_enum,
            stakes=stakes,
            max_players=data['max_players'],
            is_private=data.get('is_private', False),
            password=data.get('password'),
            allow_bots=data.get('allow_bots', False)
        )
        
        # Create table using table manager
        table = table_manager.create_table(current_user.id, config)
        
        print(f"DEBUG: Table created: {table}")
        
        if table:
            return jsonify({
                'success': True,
                'table_id': table.id,
                'message': 'Table created successfully'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to create table'
            }), 500
            
    except Exception as e:
        print(f"DEBUG: Exception in create_table: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@lobby_bp.route('/api/tables/<table_id>/seats')
def get_table_seats(table_id):
    """Get seat information for a table."""
    try:
        import traceback

        # Get table
        table = db.session.query(PokerTable).filter(
            PokerTable.id == table_id
        ).first()

        if not table:
            return jsonify({
                'success': False,
                'error': 'Table not found'
            }), 404

        # Get all access records for this table (active players)
        access_records = db.session.query(TableAccess).filter(
            TableAccess.table_id == table_id,
            TableAccess.is_active == True,
            TableAccess.is_spectator == False
        ).all()

        # Create a map of seat_number -> access record
        occupied_seats = {}
        for access in access_records:
            if access.seat_number is not None:
                occupied_seats[access.seat_number] = access

        # Build seats array
        seats = []
        for seat_num in range(1, table.max_players + 1):
            if seat_num in occupied_seats:
                access = occupied_seats[seat_num]
                seats.append({
                    'seat_number': seat_num,
                    'is_available': False,
                    'player': {
                        'username': access.user.username,
                        'stack': access.current_stack
                    }
                })
            else:
                seats.append({
                    'seat_number': seat_num,
                    'is_available': True,
                    'player': None
                })

        # Count active players
        current_players = len(access_records)

        return jsonify({
            'success': True,
            'current_players': current_players,
            'max_players': table.max_players,
            'minimum_buyin': table.get_minimum_buyin(),
            'maximum_buyin': table.get_maximum_buyin(),
            'seats': seats
        })

    except Exception as e:
        import traceback
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error in get_table_seats: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@lobby_bp.route('/api/tables/<table_id>/join', methods=['POST'])
@login_required
def join_table(table_id):
    """Join a poker table."""
    try:
        # Get request data
        data = request.get_json() or {}

        # Get table
        table = db.session.query(PokerTable).filter(
            PokerTable.id == table_id
        ).first()

        if not table:
            return jsonify({
                'success': False,
                'error': 'Table not found'
            }), 404

        # Check if table is private
        if table.is_private:
            return jsonify({
                'success': False,
                'error': 'Cannot join private table without invite code'
            }), 403

        # Check if table is full
        active_players = sum(1 for access in table.access_records
                           if access.is_active and not access.is_spectator)

        if active_players >= table.max_players:
            return jsonify({
                'success': False,
                'error': 'Table is full'
            }), 400

        # Get buy-in amount (default to minimum if not specified)
        buy_in_amount = data.get('buy_in_amount', table.get_minimum_buyin())

        # Get seat number if specified (None for auto-assign)
        seat_number = data.get('seat_number')

        # Validate buy-in amount
        if buy_in_amount < table.get_minimum_buyin():
            return jsonify({
                'success': False,
                'error': f'Buy-in must be at least ${table.get_minimum_buyin()}'
            }), 400

        if buy_in_amount > table.get_maximum_buyin():
            return jsonify({
                'success': False,
                'error': f'Buy-in cannot exceed ${table.get_maximum_buyin()}'
            }), 400

        # Check if user has sufficient bankroll
        if current_user.bankroll < buy_in_amount:
            return jsonify({
                'success': False,
                'error': f'Insufficient bankroll. You have ${current_user.bankroll}'
            }), 400

        # Join table using table access manager
        success, message, access = TableAccessManager.join_table(
            user_id=current_user.id,
            table_id=table_id,
            buy_in_amount=buy_in_amount,
            seat_number=seat_number
        )

        if success:
            return jsonify({
                'success': True,
                'table_id': table_id,
                'message': 'Joined table successfully'
            })
        else:
            return jsonify({
                'success': False,
                'error': message
            }), 400
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@lobby_bp.route('/api/tables/private/join', methods=['POST'])
@login_required
def join_private_table():
    """Join a private table using invite code."""
    try:
        data = request.get_json()
        invite_code = data.get('invite_code')
        password = data.get('password')
        
        if not invite_code:
            return jsonify({
                'success': False,
                'error': 'Invite code required'
            }), 400
        
        # Find table by invite code
        table = db.session.query(PokerTable).filter(
            PokerTable.invite_code == invite_code.upper(),
            PokerTable.is_private == True
        ).first()
        
        if not table:
            return jsonify({
                'success': False,
                'error': 'Invalid invite code'
            }), 404
        
        # Check password if required
        if table.password_hash and not table.check_password(password or ''):
            return jsonify({
                'success': False,
                'error': 'Incorrect password'
            }), 403
        
        # Check if table is full
        active_players = sum(1 for access in table.access_records 
                           if access.is_active and not access.is_spectator)
        
        if active_players >= table.max_players:
            return jsonify({
                'success': False,
                'error': 'Table is full'
            }), 400
        
        # Get buy-in amount (default to minimum if not specified)
        buy_in_amount = data.get('buy_in_amount', table.get_minimum_buyin())

        # Get seat number if specified (None for auto-assign)
        seat_number = data.get('seat_number')

        # Validate buy-in amount
        if buy_in_amount < table.get_minimum_buyin():
            return jsonify({
                'success': False,
                'error': f'Buy-in must be at least ${table.get_minimum_buyin()}'
            }), 400

        if buy_in_amount > table.get_maximum_buyin():
            return jsonify({
                'success': False,
                'error': f'Buy-in cannot exceed ${table.get_maximum_buyin()}'
            }), 400

        # Check if user has sufficient bankroll
        if current_user.bankroll < buy_in_amount:
            return jsonify({
                'success': False,
                'error': f'Insufficient bankroll. You have ${current_user.bankroll}'
            }), 400

        # Join table using table access manager
        success, message, access = TableAccessManager.join_table(
            user_id=current_user.id,
            table_id=table.id,
            buy_in_amount=buy_in_amount,
            invite_code=invite_code,
            password=password,
            seat_number=seat_number
        )

        if success:
            return jsonify({
                'success': True,
                'table_id': table.id,
                'message': 'Joined private table successfully'
            })
        else:
            return jsonify({
                'success': False,
                'error': message
            }), 400
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@lobby_bp.route('/api/tables/<table_id>/spectate', methods=['POST'])
@login_required
def spectate_table(table_id):
    """Join a table as spectator."""
    try:
        # Get table
        table = db.session.query(PokerTable).filter(
            PokerTable.id == table_id
        ).first()
        
        if not table:
            return jsonify({
                'success': False,
                'error': 'Table not found'
            }), 404
        
        # Private tables require invite code for spectating too
        if table.is_private:
            return jsonify({
                'success': False,
                'error': 'Cannot spectate private table without invite code'
            }), 403
        
        # Join as spectator using table access manager
        success, message, access = TableAccessManager.join_table(
            user_id=current_user.id,
            table_id=table_id,
            buy_in_amount=0,
            as_spectator=True
        )
        
        if success:
            return jsonify({
                'success': True,
                'table_id': table_id,
                'message': 'Joined as spectator successfully'
            })
        else:
            return jsonify({
                'success': False,
                'error': message
            }), 400
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@lobby_bp.route('/table/<table_id>')
@login_required
def table_view(table_id):
    """View a specific table (game interface)."""
    # Get table
    table = db.session.query(PokerTable).filter(
        PokerTable.id == table_id
    ).first()
    
    if not table:
        return redirect(url_for('lobby.index'))
    
    # Check if user has access to this table
    user_access = None
    for access in table.access_records:
        if access.user_id == current_user.id and access.is_active:
            user_access = access
            break
    
    if not user_access:
        # User doesn't have access, redirect to lobby
        return redirect(url_for('lobby.index'))
    
    # Build table data dict for template
    # Count active players
    active_players = sum(1 for access in table.access_records
                        if access.is_active and not access.is_spectator)

    # Build players dict keyed by seat number
    players = {}
    for access in table.access_records:
        if access.is_active and not access.is_spectator and access.seat_number:
            players[access.seat_number] = {
                'user_id': access.user_id,
                'username': access.user.username,
                'stack': access.current_stack,
                'seat_number': access.seat_number
            }

    table_data = {
        'id': table.id,
        'name': table.name,
        'variant': table.variant,
        'betting_structure': table.betting_structure,
        'max_players': table.max_players,
        'current_players': active_players,
        'players': players,
        'get_stakes': table.get_stakes  # Pass the method for template to call
    }

    # Render the game interface
    return render_template('table.html', table=table_data, user_access=user_access)


# WebSocket events for lobby
def register_lobby_socket_events(socketio):
    """Register WebSocket events for lobby functionality."""
    
    @socketio.on('get_table_list')
    def handle_get_table_list(data=None):
        """Send list of active tables."""
        try:
            # Get all public tables
            tables = db.session.query(PokerTable).filter(
                PokerTable.is_private == False
            ).all()

            table_list = []
            for table in tables:
                table_data = table.to_dict()
                table_list.append(table_data)

            # Get list of table IDs where current user is seated (for "Rejoin" button)
            user_tables = []
            if current_user.is_authenticated:
                user_access_records = db.session.query(TableAccess).filter(
                    TableAccess.user_id == current_user.id,
                    TableAccess.is_active == True,
                    TableAccess.is_spectator == False
                ).all()
                user_tables = [str(access.table_id) for access in user_access_records]

            emit('table_list', {'tables': table_list, 'user_tables': user_tables})

        except Exception as e:
            emit('error', {'message': f'Failed to get table list: {str(e)}'})
    
    @socketio.on('create_table')
    def handle_create_table(data):
        """Handle table creation via WebSocket."""
        try:
            if not current_user.is_authenticated:
                emit('error', {'message': 'Authentication required'})
                return
            
            # Validate required fields
            required_fields = ['name', 'variant', 'betting_structure', 'max_players', 'stakes']
            for field in required_fields:
                if field not in data:
                    emit('error', {'message': f'Missing required field: {field}'})
                    return
            
            # Create table using table manager
            table = table_manager.create_table(
                name=data['name'],
                variant=data['variant'],
                betting_structure=data['betting_structure'],
                stakes=data['stakes'],
                max_players=data['max_players'],
                creator_id=current_user.id,
                is_private=data.get('is_private', False),
                password=data.get('password'),
                allow_bots=data.get('allow_bots', False)
            )
            
            if table:
                emit('table_created', {
                    'table_id': table.id,
                    'message': 'Table created successfully'
                })
                
                # Broadcast table list update to all lobby users
                socketio.emit('table_list_updated', {
                    'action': 'created',
                    'table': table.to_dict()
                })
            else:
                emit('error', {'message': 'Failed to create table'})
                
        except Exception as e:
            emit('error', {'message': f'Failed to create table: {str(e)}'})
    
    @socketio.on('join_table')
    def handle_join_table(data):
        """Handle joining a table via WebSocket."""
        try:
            if not current_user.is_authenticated:
                emit('error', {'message': 'Authentication required'})
                return
            
            table_id = data.get('table_id')
            if not table_id:
                emit('error', {'message': 'Table ID required'})
                return
            
            # Get table
            table = db.session.query(PokerTable).filter(
                PokerTable.id == table_id
            ).first()
            
            if not table:
                emit('error', {'message': 'Table not found'})
                return
            
            # Check if table is private
            if table.is_private:
                emit('error', {'message': 'Cannot join private table without invite code'})
                return
            
            # Get buy-in amount (default to minimum if not specified)
            buy_in_amount = data.get('buy_in_amount', table.get_minimum_buyin())
            seat_number = data.get('seat_number')

            # Validate buy-in amount
            if buy_in_amount < table.get_minimum_buyin():
                emit('error', {'message': f'Buy-in must be at least ${table.get_minimum_buyin()}'})
                return
            if buy_in_amount > table.get_maximum_buyin():
                emit('error', {'message': f'Buy-in cannot exceed ${table.get_maximum_buyin()}'})
                return
            if current_user.bankroll < buy_in_amount:
                emit('error', {'message': f'Insufficient bankroll. You have ${current_user.bankroll}'})
                return

            # Join table using table access manager
            success, message, access = TableAccessManager.join_table(
                user_id=current_user.id,
                table_id=table_id,
                buy_in_amount=buy_in_amount,
                seat_number=seat_number
            )

            if success:
                emit('table_joined', {
                    'table_id': table_id,
                    'message': 'Joined table successfully'
                })

                # Broadcast table update to all lobby users so they see updated player count
                table = db.session.query(PokerTable).filter(
                    PokerTable.id == table_id
                ).first()
                if table:
                    socketio.emit('table_updated', {
                        'table': table.to_dict(),
                        'action': 'player_joined'
                    })
            else:
                emit('error', {'message': message})

        except Exception as e:
            emit('error', {'message': f'Failed to join table: {str(e)}'})
    
    @socketio.on('join_private_table')
    def handle_join_private_table(data):
        """Handle joining a private table via WebSocket."""
        try:
            if not current_user.is_authenticated:
                emit('error', {'message': 'Authentication required'})
                return
            
            invite_code = data.get('invite_code')
            password = data.get('password')
            
            if not invite_code:
                emit('error', {'message': 'Invite code required'})
                return
            
            # Find table by invite code
            table = db.session.query(PokerTable).filter(
                PokerTable.invite_code == invite_code.upper(),
                PokerTable.is_private == True
            ).first()
            
            if not table:
                emit('error', {'message': 'Invalid invite code'})
                return
            
            # Check password if required
            if table.password_hash and not table.check_password(password or ''):
                emit('error', {'message': 'Incorrect password'})
                return
            
            # Get buy-in amount (default to minimum if not specified)
            buy_in_amount = data.get('buy_in_amount', table.get_minimum_buyin())
            seat_number = data.get('seat_number')

            # Validate buy-in amount
            if buy_in_amount < table.get_minimum_buyin():
                emit('error', {'message': f'Buy-in must be at least ${table.get_minimum_buyin()}'})
                return
            if buy_in_amount > table.get_maximum_buyin():
                emit('error', {'message': f'Buy-in cannot exceed ${table.get_maximum_buyin()}'})
                return
            if current_user.bankroll < buy_in_amount:
                emit('error', {'message': f'Insufficient bankroll. You have ${current_user.bankroll}'})
                return

            # Join table using table access manager
            success, message, access = TableAccessManager.join_table(
                user_id=current_user.id,
                table_id=table.id,
                buy_in_amount=buy_in_amount,
                seat_number=seat_number
            )

            if success:
                emit('table_joined', {
                    'table_id': table.id,
                    'message': 'Joined private table successfully'
                })
            else:
                emit('error', {'message': message})
                
        except Exception as e:
            emit('error', {'message': f'Failed to join private table: {str(e)}'})
    
    @socketio.on('spectate_table')
    def handle_spectate_table(data):
        """Handle spectating a table via WebSocket."""
        try:
            if not current_user.is_authenticated:
                emit('error', {'message': 'Authentication required'})
                return
            
            table_id = data.get('table_id')
            if not table_id:
                emit('error', {'message': 'Table ID required'})
                return
            
            # Get table
            table = db.session.query(PokerTable).filter(
                PokerTable.id == table_id
            ).first()
            
            if not table:
                emit('error', {'message': 'Table not found'})
                return
            
            # Join as spectator using table access manager
            success, message, access = TableAccessManager.join_table(
                user_id=current_user.id,
                table_id=table_id,
                buy_in_amount=0,
                as_spectator=True
            )
            
            if success:
                emit('table_joined', {
                    'table_id': table_id,
                    'message': 'Joined as spectator successfully'
                })
            else:
                emit('error', {'message': message})
                
        except Exception as e:
            emit('error', {'message': f'Failed to spectate table: {str(e)}'})