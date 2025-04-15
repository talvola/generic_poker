from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit
from generic_poker.game.game import Game
from generic_poker.config.loader import GameRules, BettingStructure
from generic_poker.game.game_state import GameState
from generic_poker.core.card import Card, Visibility

import asyncio
import json
import os
from threading import Thread

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
    
    if sid in action_futures:
        future = action_futures[sid]
        if not future.done():
            print(f"Setting future result for {player_id}: {data}")
            future.set_result(data)
        else:
            print(f"Future for {player_id} was already done")
    else:
        print(f"No future found for {player_id} (sid: {sid})")

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
        if p.id == player_id:
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

            # Log the current step after starting hand
            print(f"Current step: {game.current_step} - {game.rules.gameplay[game.current_step].name}")           
                           
            # Broadcast state after blinds for all players
            for pid, sid in player_sids.items():
                state = get_game_state_for_player(pid)
                socketio.emit('game_state', state, room=sid)
                    
            # Allow UI to update and players to see blinds posted
            await asyncio.sleep(1)
            
            # Auto-progress to dealing hole cards
            print("Progressing to dealing hole cards...")
            game._next_step()
            print(f"Current step: {game.current_step} - {game.rules.gameplay[game.current_step].name}")
            
            # Broadcast state after hole cards are dealt
            for pid, sid in player_sids.items():
                state = get_game_state_for_player(pid)
                socketio.emit('game_state', state, room=sid)
                
            # Allow UI to update and players to see their cards
            await asyncio.sleep(1)

            # Auto-progress to first betting round
            print("Progressing to first betting round...")
            game._next_step()
            print(f"Current step: {game.current_step} - {game.rules.gameplay[game.current_step].name}")
            
            # Broadcast state after transitioning to betting
            for pid, sid in player_sids.items():
                state = get_game_state_for_player(pid)
                socketio.emit('game_state', state, room=sid)            

            # Main loop for a single hand
            while game.state != GameState.COMPLETE:
                # Log current game state at start of each iteration
                print(f"Game state: {game.state}, Step: {game.current_step} - {game.rules.gameplay[game.current_step].name}")           

                # If a player needs to act
                if game.current_player:
                    player_id = game.current_player.id
                    if player_id in player_sids:  # Make sure player is still connected
                        print(f"Current player: {game.current_player.name} ({player_id})")
                        sid = player_sids[player_id]
                        valid_actions = game.get_valid_actions(player_id)

                        print(f"Valid actions for {player_id}: {valid_actions}")
                        
                        # Format actions for client
                        actions = [
                            {'type': a.value, 'min': min_amt, 'max': max_amt} 
                            for a, min_amt, max_amt in valid_actions
                        ]

                        print(f"Sending actions to client: {actions}")
                        
                        # Notify player it's their turn
                        socketio.emit('your_turn', {'actions': actions}, room=sid)
                        
                        # Wait for player's action
                        try:
                            print(f"Waiting for action from {player_id}")
                            action_data = await wait_for_action(sid)
                            print(f"After wait_for_action, received: {action_data}")
                            if not action_data:
                                print("Warning: action_data is empty or None")
                                continue 

                            # Process action
                            action = action_data['action']
                            amount = action_data.get('amount', 0)
                            cards = action_data.get('cards', [])
                            
                            try:
                                print(f"About to call player_action for {player_id}: {action} {amount}")
                                result = game.player_action(player_id, action, amount, cards)
                                print(f"Action result: {result}")
                            except Exception as e:
                                print(f"Exception in player_action: {e}")
                                import traceback
                                traceback.print_exc()
                                socketio.emit('error', {'message': f"Error in game: {str(e)}"}, room=sid)
                                continue

                            if not result.success:
                                socketio.emit('error', {'message': result.error}, room=sid)
                                continue  # Try again with the same player if action failed    

                            # Broadcast updated state to all players after successful action
                            for pid, sid in player_sids.items():
                                state = get_game_state_for_player(pid)
                                socketio.emit('game_state', state, room=sid)                                                    
                                                      
                            # Check if we need to advance to the next step
                            if result.advance_step:
                                print(f"Advancing to next step after {player_id}'s action")
                                game._next_step()
                                
                                # After advancing, broadcast the new state
                                for pid, sid in player_sids.items():
                                    state = get_game_state_for_player(pid)
                                    socketio.emit('game_state', state, room=sid)
                                
                                # If the game state is dealing, handle automatic deal steps
                                if game.state == GameState.DEALING:
                                    print(f"Auto-processing dealing step: {game.rules.gameplay[game.current_step].name}")
                                    # Allow UI to update and players to see the new state
                                    await asyncio.sleep(1)
                                    
                                    # Auto-advance dealing steps
                                    if "Deal" in game.rules.gameplay[game.current_step].name:
                                        game._next_step()
                                        
                                        # Broadcast state after the deal
                                        for pid, sid in player_sids.items():
                                            state = get_game_state_for_player(pid)
                                            socketio.emit('game_state', state, room=sid)
                                
                                # If we're in a betting round, check if a player needs to act
                                # If not, we might need to auto-advance again
                                if game.state == GameState.BETTING and not game.current_player:
                                    print("No player to act in betting round, advancing...")
                                    game._next_step()
                                    
                                    # Broadcast state after auto-advancing
                                    for pid, sid in player_sids.items():
                                        state = get_game_state_for_player(pid)
                                        socketio.emit('game_state', state, room=sid)
                                else:
                                    # Game progresses automatically
                                    game._next_step()
                                
                                # Broadcast updated state to all players
                                for pid, sid in player_sids.items():
                                    state = get_game_state_for_player(pid)
                                    socketio.emit('game_state', state, room=sid)

                        except Exception as e:
                            print(f"Error handling action: {e}")
                            # Continue the game even if there's an error with one action
                            socketio.emit('error', {'message': f"Error processing action: {str(e)}"}, room=sid)                                    
                
                # Small delay to avoid hammering the CPU
                await asyncio.sleep(0.1)
            
            # Handle hand completion
            print("Hand complete, updating all players")
            for pid, sid in player_sids.items():
                socketio.emit('game_state', get_game_state_for_player(pid), room=sid)
            
            # Move button for next hand
            game.table.move_button()
            
            # Short delay between hands
            await asyncio.sleep(3)
            
        except Exception as e:
            print(f"Error in game loop: {e}")
            await asyncio.sleep(5)  # Wait before retrying

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
