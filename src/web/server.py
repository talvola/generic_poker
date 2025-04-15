from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit
from generic_poker.game.game import Game
from generic_poker.config.loader import GameRules, BettingStructure
from generic_poker.game.game_state import GameState, PlayerAction
from generic_poker.core.card import Card, Visibility

import asyncio
import json
import os
import logging 
import sys
from threading import Thread

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

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('connect')
def handle_connect():
    print(f"Client connected: {request.sid}")
    # Do not emit any events here that would cause a prompt

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
def handle_join(data):
    """Handle a player joining the game."""
    global game
    sid = request.sid
    player_name = data['name']
    
    # Check if game exists and if the name is already taken
    if game is not None and any(p.name == player_name for p in game.table.players.values()):
        emit('error', {'message': 'Name already taken'}, room=sid)
        return
    
    # Initialize game if it doesn't exist
    if game is None:
        start_game()
    
    player_id = f"p{len(player_sids) + 1}"
    starting_stack = 500  # Starting stack size
    
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
                
                # Check if we need to advance to the next step
                if result.advance_step:
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

def run_game_loop():
    """Run the game loop in a separate thread."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(game_loop())

def get_game_state_for_player(player_id):
    """Generate a personalized game state for a player."""
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
        }
    }
    
    # Add betting info
    if game.state == GameState.BETTING:
        state['betting'] = {
            'current_bet': game.betting.current_bet,
            'last_raise_size': game.betting.last_raise_size,
            'small_blind': game.small_blind,
            'big_blind': game.big_blind
        }
    
    # Add last hand result if available
    if game.state == GameState.COMPLETE and game.last_hand_result:
        winners = game.last_hand_result.winners
        state['results'] = {
            'winners': winners,
            'total_pot': game.last_hand_result.total_pot
        }
    
    # Get all players in position order
    for p in game.table.get_position_order():
        # Determine player position
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
        
        # Add current bet info if available
        current_bet = game.betting.current_bets.get(p.id, None)
        if current_bet:
            player_data['current_bet'] = current_bet.amount
            player_data['has_acted'] = current_bet.has_acted
            player_data['is_all_in'] = current_bet.is_all_in
        
        # Show card info based on visibility
        if p.id == player_id or game.state == GameState.SHOWDOWN or game.state == GameState.COMPLETE:
            # Player sees their own cards fully
            player_data['cards'] = {
                'default': [str(c) for c in p.hand.cards]  # Use main cards list
            }
            # Also include card visibility for the frontend to display properly
            player_data['card_visibility'] = {
                'default': [c.visibility.value for c in p.hand.cards]
            }
            
            # Add subset info if any exists
            for name, cards in p.hand.subsets.items():
                if cards:  # Only add non-empty subsets
                    player_data['cards'][name] = [str(c) for c in cards]
                    player_data['card_visibility'][name] = [c.visibility.value for c in cards]
                    
        else:
            # For other players' cards, only send face-up cards
            player_data['cards'] = {
                'default': [str(c) if c.visibility == Visibility.FACE_UP else '**' for c in p.hand.cards]
            }
            
            # Add subset info if any exists
            for name, cards in p.hand.subsets.items():
                if cards:  # Only add non-empty subsets
                    player_data['cards'][name] = [str(c) if c.visibility == Visibility.FACE_UP else '**' for c in cards]

        print(f"Player {p.name} ({p.id}) - Cards: {player_data['cards']}")

        state['players'].append(player_data)
    
    return state

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

            # Now wait for game to complete
            while game.state != GameState.COMPLETE:
                # Print current game state at the start of each iteration
                print(f"\n=== Current game state ===")
                print(f"Step: {game.current_step} - {game.rules.gameplay[game.current_step].name}")
                print(f"State: {game.state}")
                print(f"Current player: {game.current_player.name if game.current_player else 'None'}")

                # Check game state and act accordingly
                if game.state == GameState.DEALING:
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
                    if player_id != last_player_id:
                        sid = player_sids[player_id]
                        valid_actions = game.get_valid_actions(player_id)
                        
                        print(f"Current player: {game.current_player.name} ({player_id})")
                        print(f"Valid actions: {valid_actions}")
                        
                        # Format actions for client
                        actions = [
                            {'type': a.value, 'min': min_amt, 'max': max_amt} 
                            for a, min_amt, max_amt in valid_actions
                        ]
                        
                        print(f"Sending your_turn event to {player_id} with actions: {actions}")
                        
                        # Notify player it's their turn
                        socketio.emit('your_turn', {'actions': actions}, room=sid)
                        print(f"Emitted your_turn event to {player_id}, sid: {sid}")
                        
                        # Update last player ID
                        last_player_id = player_id

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
        from generic_poker.config.loader import GameRules, BettingStructure
        
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

if __name__ == '__main__':
    # Create directory structure if needed
    os.makedirs('static', exist_ok=True)
    os.makedirs('templates', exist_ok=True)
    
    # Start the server
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
