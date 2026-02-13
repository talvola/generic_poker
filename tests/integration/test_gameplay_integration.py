"""Integration tests for gameplay functionality.

These tests verify the full gameplay flow including:
- Two players joining and getting ready
- Hand starting automatically when players are ready
- Player betting actions (fold, call, check, bet, raise)
- Game state progression through dealing and betting rounds
- Hand completion and pot distribution
"""

import pytest
import json
import uuid
from flask import Flask
from flask_login import LoginManager

from online_poker.database import db, init_database
from online_poker.auth import init_login_manager
from online_poker.routes.auth_routes import auth_bp
from online_poker.routes.lobby_routes import lobby_bp
from online_poker.services.user_manager import UserManager
from online_poker.services.table_manager import TableManager
from online_poker.services.table_access_manager import TableAccessManager
from online_poker.services.game_orchestrator import game_orchestrator, GameSession
from online_poker.models.table_config import TableConfig
from generic_poker.game.betting import BettingStructure
from generic_poker.game.game import GameState, PlayerAction


@pytest.fixture
def app():
    """Create test Flask app with full setup."""
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test-secret-key'
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['WTF_CSRF_ENABLED'] = False

    # Initialize database
    init_database(app)

    # Initialize Flask-Login
    init_login_manager(app)

    # Register blueprints
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(lobby_bp)

    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


@pytest.fixture
def player1(app):
    """Create first test player with bankroll."""
    with app.app_context():
        # Use unique username to avoid conflicts
        unique_id = str(uuid.uuid4())[:8]
        user = UserManager.create_user(f"player1_{unique_id}", f"player1_{unique_id}@test.com", "password123")
        UserManager.update_user_bankroll(user.id, 1000)
        # Store the username for login
        user._test_username = f"player1_{unique_id}"
        return user


@pytest.fixture
def player2(app):
    """Create second test player with bankroll."""
    with app.app_context():
        unique_id = str(uuid.uuid4())[:8]
        user = UserManager.create_user(f"player2_{unique_id}", f"player2_{unique_id}@test.com", "password123")
        UserManager.update_user_bankroll(user.id, 1000)
        user._test_username = f"player2_{unique_id}"
        return user


@pytest.fixture
def holdem_table(app, player1):
    """Create a Texas Hold'em table."""
    with app.app_context():
        table_manager = TableManager()
        config = TableConfig(
            name="Test Hold'em Table",
            variant="hold_em",
            betting_structure=BettingStructure.NO_LIMIT,
            stakes={'small_blind': 1, 'big_blind': 2},
            max_players=6,
            is_private=False,
            allow_bots=False
        )
        table = table_manager.create_table(player1.id, config)
        return table


@pytest.fixture
def logged_in_player1(client, player1):
    """Return a client logged in as player1."""
    client.post('/auth/api/login', json={
        'username': 'player1',
        'password': 'password123'
    })
    return client


@pytest.fixture
def logged_in_player2(app, player2):
    """Return a client logged in as player2."""
    client = app.test_client()
    client.post('/auth/api/login', json={
        'username': 'player2',
        'password': 'password123'
    })
    return client


class TestGameplayFlow:
    """Test complete gameplay flow."""

    def test_two_players_join_table(self, app, holdem_table, player1, player2):
        """Test that two players can join a table."""
        with app.app_context():
            # Player 1 joins
            client1 = app.test_client()
            client1.post('/auth/api/login', json={'username': player1._test_username, 'password': 'password123'})
            response1 = client1.post(
                f'/api/tables/{holdem_table.id}/join',
                json={'buy_in_amount': 100, 'seat_number': 1}
            )
            assert response1.status_code == 200, f"Player 1 join failed: {response1.get_json()}"

            # Player 2 joins
            client2 = app.test_client()
            client2.post('/auth/api/login', json={'username': player2._test_username, 'password': 'password123'})
            response2 = client2.post(
                f'/api/tables/{holdem_table.id}/join',
                json={'buy_in_amount': 100, 'seat_number': 2}
            )
            assert response2.status_code == 200, f"Player 2 join failed: {response2.get_json()}"

            # Verify both are seated
            db.session.expire_all()
            players = TableAccessManager.get_table_players(holdem_table.id)
            active_players = [p for p in players if not p.get('is_spectator', False) and p.get('is_active', True)]
            assert len(active_players) == 2

    def test_ready_status_tracking(self, app, holdem_table, player1, player2):
        """Test that ready status is correctly tracked for players."""
        with app.app_context():
            # Both players join
            client1 = app.test_client()
            client1.post('/auth/api/login', json={'username': player1._test_username, 'password': 'password123'})
            client1.post(f'/api/tables/{holdem_table.id}/join', json={'buy_in_amount': 100})

            client2 = app.test_client()
            client2.post('/auth/api/login', json={'username': player2._test_username, 'password': 'password123'})
            client2.post(f'/api/tables/{holdem_table.id}/join', json={'buy_in_amount': 100})

            # Check initial ready status
            ready_status = TableAccessManager.get_ready_status(holdem_table.id)
            assert ready_status['player_count'] == 2
            assert ready_status['ready_count'] == 0
            assert ready_status['all_ready'] == False

            # Player 1 marks ready
            TableAccessManager.set_player_ready(player1.id, holdem_table.id, True)
            ready_status = TableAccessManager.get_ready_status(holdem_table.id)
            assert ready_status['ready_count'] == 1
            assert ready_status['all_ready'] == False

            # Player 2 marks ready
            TableAccessManager.set_player_ready(player2.id, holdem_table.id, True)
            ready_status = TableAccessManager.get_ready_status(holdem_table.id)
            assert ready_status['ready_count'] == 2
            assert ready_status['all_ready'] == True


class TestGameSessionLifecycle:
    """Test game session creation and lifecycle."""

    def test_create_game_session(self, app, holdem_table, player1, player2):
        """Test that a game session can be created for a table."""
        with app.app_context():
            # Create session
            success, message, session = game_orchestrator.create_session(holdem_table.id)

            assert success, f"Failed to create session: {message}"
            assert session is not None
            assert session.table.id == holdem_table.id
            assert session.game is not None

    def test_add_players_to_session(self, app, holdem_table, player1, player2):
        """Test that players can be added to a game session."""
        with app.app_context():
            # Create session
            success, message, session = game_orchestrator.create_session(holdem_table.id)
            assert success

            # Add players
            success1, msg1 = session.add_player(player1.id, "player1", 100)
            assert success1, f"Failed to add player1: {msg1}"

            success2, msg2 = session.add_player(player2.id, "player2", 100)
            assert success2, f"Failed to add player2: {msg2}"

            # Verify players are in the game
            assert len(session.game.table.players) == 2
            assert player1.id in session.connected_players
            assert player2.id in session.connected_players


class TestHandFlow:
    """Test complete hand flow from start to finish."""

    def test_start_hand(self, app, holdem_table, player1, player2):
        """Test that a hand can be started when enough players are present."""
        with app.app_context():
            # Create session and add players
            success, message, session = game_orchestrator.create_session(holdem_table.id)
            assert success

            session.add_player(player1.id, "player1", 100)
            session.add_player(player2.id, "player2", 100)

            # Start the hand
            game = session.game
            game.start_hand()

            # Verify blinds were posted
            assert game.state == GameState.BETTING
            assert game.betting.get_main_pot_amount() == 3  # SB (1) + BB (2)

    def test_deal_hole_cards(self, app, holdem_table, player1, player2):
        """Test that hole cards are dealt to players."""
        with app.app_context():
            success, message, session = game_orchestrator.create_session(holdem_table.id)
            assert success

            session.add_player(player1.id, "player1", 100)
            session.add_player(player2.id, "player2", 100)

            game = session.game
            game.start_hand()

            # Advance through dealing step
            game._next_step()

            # Each player should have 2 hole cards
            for player in game.table.players.values():
                assert len(player.hand.cards) == 2

    def test_preflop_betting_actions(self, app, holdem_table, player1, player2):
        """Test preflop betting round actions."""
        with app.app_context():
            success, message, session = game_orchestrator.create_session(holdem_table.id)
            assert success

            session.add_player(player1.id, "player1", 100)
            session.add_player(player2.id, "player2", 100)

            game = session.game
            game.start_hand()
            game._next_step()  # Deal hole cards
            game._next_step()  # Move to preflop betting

            assert game.state == GameState.BETTING
            assert game.current_player is not None

            # First player to act (SB/Button in heads-up)
            current_player = game.current_player.id
            valid_actions = game.get_valid_actions(current_player)

            # Should have fold, call, raise options
            action_types = [a[0] for a in valid_actions]
            assert PlayerAction.FOLD in action_types
            assert PlayerAction.CALL in action_types
            assert PlayerAction.RAISE in action_types

    def test_complete_hand_via_fold(self, app, holdem_table, player1, player2):
        """Test that a hand completes when one player folds."""
        with app.app_context():
            success, message, session = game_orchestrator.create_session(holdem_table.id)
            assert success

            session.add_player(player1.id, "player1", 100)
            session.add_player(player2.id, "player2", 100)

            game = session.game
            game.start_hand()
            game._next_step()  # Deal hole cards
            game._next_step()  # Move to preflop betting

            # Get current player
            current_player = game.current_player.id

            # Current player folds
            result = game.player_action(current_player, PlayerAction.FOLD)
            assert result.success

            # Game should be complete
            assert game.state == GameState.COMPLETE

            # Winner should have won the pot
            winner_id = [pid for pid in game.table.players.keys() if pid != current_player][0]
            # The winner gets the pot (blinds)
            assert game.table.players[winner_id].stack > 100

    def test_complete_hand_to_showdown(self, app, holdem_table, player1, player2):
        """Test a hand that goes to showdown."""
        with app.app_context():
            success, message, session = game_orchestrator.create_session(holdem_table.id)
            assert success

            session.add_player(player1.id, "player1", 100)
            session.add_player(player2.id, "player2", 100)

            game = session.game
            game.start_hand()

            # Safety counter to prevent infinite loops
            max_iterations = 100
            iteration = 0

            # Progress through the entire hand with check/call actions
            while game.state != GameState.COMPLETE and iteration < max_iterations:
                iteration += 1

                if game.state == GameState.DEALING:
                    game._next_step()
                elif game.state == GameState.BETTING:
                    if game.current_player:
                        current_id = game.current_player.id
                        actions = game.get_valid_actions(current_id)
                        action_types = {a[0]: a for a in actions}

                        if PlayerAction.CHECK in action_types:
                            result = game.player_action(current_id, PlayerAction.CHECK)
                        elif PlayerAction.CALL in action_types:
                            call_amount = action_types[PlayerAction.CALL][1]
                            result = game.player_action(current_id, PlayerAction.CALL, call_amount)
                        else:
                            # Fold if no other options (shouldn't happen in check/call game)
                            result = game.player_action(current_id, PlayerAction.FOLD)

                        # Advance step if action result indicates betting round complete
                        if result.success and result.advance_step and game.state != GameState.COMPLETE:
                            game._next_step()
                    else:
                        # No current player means betting round is done
                        game._next_step()
                elif game.state == GameState.SHOWDOWN:
                    # Showdown state - advance to complete
                    game._next_step()
                else:
                    # Handle any other states (WAITING, DRAWING, etc.)
                    game._next_step()

            assert iteration < max_iterations, f"Game stuck after {iteration} iterations, state: {game.state}"

            # Hand should be complete
            assert game.state == GameState.COMPLETE

            # Get hand results
            results = game.get_hand_results()
            assert results.is_complete
            assert results.total_pot > 0
            assert len(results.winning_hands) > 0


class TestBettingActions:
    """Test individual betting actions."""

    def test_fold_action(self, app, holdem_table, player1, player2):
        """Test fold action."""
        with app.app_context():
            success, _, session = game_orchestrator.create_session(holdem_table.id)
            session.add_player(player1.id, "player1", 100)
            session.add_player(player2.id, "player2", 100)

            game = session.game
            game.start_hand()
            game._next_step()  # Deal
            game._next_step()  # Betting

            current = game.current_player.id
            result = game.player_action(current, PlayerAction.FOLD)

            assert result.success
            assert game.state == GameState.COMPLETE

    def test_call_action(self, app, holdem_table, player1, player2):
        """Test call action."""
        with app.app_context():
            success, _, session = game_orchestrator.create_session(holdem_table.id)
            session.add_player(player1.id, "player1", 100)
            session.add_player(player2.id, "player2", 100)

            game = session.game
            game.start_hand()
            game._next_step()  # Deal
            game._next_step()  # Betting

            current = game.current_player.id
            actions = game.get_valid_actions(current)
            call_action = next((a for a in actions if a[0] == PlayerAction.CALL), None)

            assert call_action is not None
            call_amount = call_action[1]

            result = game.player_action(current, PlayerAction.CALL, call_amount)
            assert result.success

    def test_raise_action(self, app, holdem_table, player1, player2):
        """Test raise action."""
        with app.app_context():
            success, _, session = game_orchestrator.create_session(holdem_table.id)
            session.add_player(player1.id, "player1", 100)
            session.add_player(player2.id, "player2", 100)

            game = session.game
            game.start_hand()
            game._next_step()  # Deal
            game._next_step()  # Betting

            current = game.current_player.id
            actions = game.get_valid_actions(current)
            raise_action = next((a for a in actions if a[0] == PlayerAction.RAISE), None)

            assert raise_action is not None
            min_raise = raise_action[1]

            result = game.player_action(current, PlayerAction.RAISE, min_raise)
            assert result.success

            # Pot should have increased
            assert game.betting.get_main_pot_amount() > 3

    def test_check_action(self, app, holdem_table, player1, player2):
        """Test check action when available."""
        with app.app_context():
            success, _, session = game_orchestrator.create_session(holdem_table.id)
            session.add_player(player1.id, "player1", 100)
            session.add_player(player2.id, "player2", 100)

            game = session.game
            game.start_hand()
            game._next_step()  # Deal
            game._next_step()  # Preflop betting

            # Call with first player
            p1 = game.current_player.id
            game.player_action(p1, PlayerAction.CALL, 2)

            # Now BB can check
            if game.current_player:
                p2 = game.current_player.id
                actions = game.get_valid_actions(p2)
                check_action = next((a for a in actions if a[0] == PlayerAction.CHECK), None)

                assert check_action is not None, f"Check not available. Actions: {[a[0] for a in actions]}"
                result = game.player_action(p2, PlayerAction.CHECK)
                assert result.success


class TestChipStackManagement:
    """Test chip stack updates during play."""

    def test_blinds_deducted_from_stack(self, app, holdem_table, player1, player2):
        """Test that posting blinds deducts from player stacks."""
        with app.app_context():
            success, _, session = game_orchestrator.create_session(holdem_table.id)
            session.add_player(player1.id, "player1", 100)
            session.add_player(player2.id, "player2", 100)

            game = session.game
            game.start_hand()

            # Check that blinds were deducted
            total_chips = sum(p.stack for p in game.table.players.values())
            assert total_chips == 200 - 3  # 100 + 100 - 3 (SB + BB)

    def test_winner_receives_pot(self, app, holdem_table, player1, player2):
        """Test that winner receives the pot after hand completion."""
        with app.app_context():
            success, _, session = game_orchestrator.create_session(holdem_table.id)
            session.add_player(player1.id, "player1", 100)
            session.add_player(player2.id, "player2", 100)

            game = session.game
            game.start_hand()
            game._next_step()  # Deal
            game._next_step()  # Betting

            # Record stacks before fold
            stacks_before = {pid: p.stack for pid, p in game.table.players.items()}

            # One player folds
            folder = game.current_player.id
            game.player_action(folder, PlayerAction.FOLD)

            # Winner should have gained the pot
            winner = [pid for pid in game.table.players.keys() if pid != folder][0]
            assert game.table.players[winner].stack > stacks_before[winner]


class TestGameStateProgression:
    """Test game state progression through all phases."""

    def test_state_progression_through_hand(self, app, holdem_table, player1, player2):
        """Test that game progresses through all expected states."""
        with app.app_context():
            success, _, session = game_orchestrator.create_session(holdem_table.id)
            session.add_player(player1.id, "player1", 100)
            session.add_player(player2.id, "player2", 100)

            game = session.game

            # Track states visited
            states_visited = []
            community_card_counts = []
            max_iterations = 100
            iteration = 0

            game.start_hand()
            states_visited.append(game.state)

            while game.state != GameState.COMPLETE and iteration < max_iterations:
                iteration += 1
                if game.state == GameState.DEALING:
                    game._next_step()
                    states_visited.append(game.state)
                    community_card_counts.append(
                        len(game.table.community_cards.get('default', []))
                    )
                elif game.state == GameState.BETTING:
                    if game.current_player:
                        current_id = game.current_player.id
                        actions = game.get_valid_actions(current_id)
                        action_types = {a[0]: a for a in actions}

                        if PlayerAction.CHECK in action_types:
                            result = game.player_action(current_id, PlayerAction.CHECK)
                        elif PlayerAction.CALL in action_types:
                            result = game.player_action(current_id, PlayerAction.CALL, action_types[PlayerAction.CALL][1])
                        else:
                            result = game.player_action(current_id, PlayerAction.FOLD)

                        # Advance if betting round complete
                        if result.success and result.advance_step and game.state != GameState.COMPLETE:
                            game._next_step()
                            states_visited.append(game.state)
                    else:
                        game._next_step()
                        states_visited.append(game.state)
                elif game.state == GameState.SHOWDOWN:
                    game._next_step()
                    states_visited.append(game.state)
                else:
                    game._next_step()
                    states_visited.append(game.state)

            assert iteration < max_iterations, f"Game stuck after {iteration} iterations"

            # Should have visited BETTING and DEALING states multiple times
            assert GameState.BETTING in states_visited
            assert GameState.DEALING in states_visited
            assert GameState.COMPLETE in states_visited

            # Community cards should have progressed: 0 -> 3 (flop) -> 4 (turn) -> 5 (river)
            if len(community_card_counts) > 0:
                final_count = game.table.community_cards.get('default', [])
                # In a full hand going to showdown, should have 5 community cards
                assert len(final_count) == 5, f"Expected 5 community cards, got {len(final_count)}"


class TestPreflopBettingAndProgression:
    """Test preflop betting flow with game progression - validates fix for bug #G008."""

    def test_preflop_sb_calls_bb_checks_advances_to_flop(self, app, holdem_table, player1, player2):
        """
        Test that when SB calls and BB checks preflop, the game advances to deal the flop.

        This is the core scenario from bug #G008:
        1. Both players start the game
        2. Blinds are posted, chip stacks decrease, pot increases
        3. SB (button in heads-up) calls the big blind
        4. BB checks
        5. Betting round completes and flop is dealt
        """
        with app.app_context():
            success, _, session = game_orchestrator.create_session(holdem_table.id)
            assert success

            session.add_player(player1.id, "player1", 100)
            session.add_player(player2.id, "player2", 100)

            game = session.game

            # Start the hand - this posts blinds
            game.start_hand()

            # Verify blinds are posted: $1 SB + $2 BB = $3
            assert game.betting.get_main_pot_amount() == 3, f"Expected pot of $3, got {game.betting.get_main_pot_amount()}"

            # Verify chip stacks decreased
            player_stacks = {p.name: p.stack for p in game.table.players.values()}
            total_chips = sum(p.stack for p in game.table.players.values())
            assert total_chips == 200 - 3, f"Expected 197 chips total, got {total_chips}"

            # Advance to deal hole cards
            game._next_step()

            # Verify hole cards dealt
            for player in game.table.players.values():
                assert len(player.hand.cards) == 2, f"Player {player.name} should have 2 hole cards"

            # Advance to preflop betting
            game._next_step()
            assert game.state == GameState.BETTING
            assert game.current_player is not None

            # In heads-up, SB/Button acts first preflop
            sb_player_id = game.current_player.id
            sb_player_name = game.current_player.name

            # SB calls the big blind ($2 total, $1 more since SB already posted $1)
            actions = game.get_valid_actions(sb_player_id)
            call_action = next((a for a in actions if a[0] == PlayerAction.CALL), None)
            assert call_action is not None, f"Call action should be available. Actions: {[a[0] for a in actions]}"

            call_amount = call_action[1]
            result = game.player_action(sb_player_id, PlayerAction.CALL, call_amount)
            assert result.success, f"SB call failed: {result.error if hasattr(result, 'error') else 'unknown'}"

            # Pot should now be $4 ($1 SB + $1 call + $2 BB)
            assert game.betting.get_main_pot_amount() == 4, f"Expected pot of $4, got {game.betting.get_main_pot_amount()}"

            # Current player should now be BB
            assert game.current_player is not None, "BB should be current player"
            bb_player_id = game.current_player.id
            assert bb_player_id != sb_player_id, "BB should be different from SB"

            # BB checks
            actions = game.get_valid_actions(bb_player_id)
            check_action = next((a for a in actions if a[0] == PlayerAction.CHECK), None)
            assert check_action is not None, f"Check action should be available for BB. Actions: {[a[0] for a in actions]}"

            result = game.player_action(bb_player_id, PlayerAction.CHECK)
            assert result.success, f"BB check failed: {result.error if hasattr(result, 'error') else 'unknown'}"

            # The betting round should be complete (result.advance_step = True)
            assert result.advance_step, "Betting round should be complete after BB checks"

            # For games with auto_progress=False, we need to manually advance
            # This simulates what the websocket/api handler should do
            if game.state != GameState.COMPLETE:
                game._next_step()

            # Continue advancing through dealing/non-player-input steps
            while game.state != GameState.COMPLETE:
                if game.current_step >= len(game.rules.gameplay):
                    break
                # DEALING state doesn't require player input - auto advance
                if game.state == GameState.DEALING:
                    game._next_step()
                # BETTING state with no current player - round complete, advance
                elif game.state == GameState.BETTING and game.current_player is None:
                    game._next_step()
                else:
                    # Player input required
                    break

            # Flop should be dealt (3 community cards)
            flop_cards = game.table.community_cards.get('default', [])
            assert len(flop_cards) == 3, f"Expected 3 flop cards, got {len(flop_cards)}"

            # Game should be in BETTING state for post-flop betting
            assert game.state == GameState.BETTING, f"Expected BETTING state for post-flop, got {game.state}"
            assert game.current_player is not None, "There should be a current player for post-flop betting"

    def test_preflop_pot_and_stack_tracking(self, app, holdem_table, player1, player2):
        """
        Test that pot and stack amounts are correctly tracked through preflop betting.
        """
        with app.app_context():
            success, _, session = game_orchestrator.create_session(holdem_table.id)
            assert success

            session.add_player(player1.id, "player1", 100)
            session.add_player(player2.id, "player2", 100)

            game = session.game
            initial_total = 200

            # Start hand
            game.start_hand()

            # After blinds: SB = $1, BB = $2, pot = $3
            pot_after_blinds = game.betting.get_main_pot_amount()
            stacks_after_blinds = sum(p.stack for p in game.table.players.values())

            assert pot_after_blinds == 3, f"Pot should be $3 after blinds, got {pot_after_blinds}"
            assert stacks_after_blinds == initial_total - pot_after_blinds, \
                f"Stacks should total {initial_total - pot_after_blinds}, got {stacks_after_blinds}"

            # Deal hole cards and move to betting
            game._next_step()  # Deal
            game._next_step()  # Betting

            # SB calls
            sb_id = game.current_player.id
            sb_stack_before = game.table.players[sb_id].stack

            result = game.player_action(sb_id, PlayerAction.CALL, 2)
            assert result.success

            pot_after_sb_call = game.betting.get_main_pot_amount()
            sb_stack_after = game.table.players[sb_id].stack

            # SB should have contributed $1 more (already posted $1 SB)
            assert pot_after_sb_call == 4, f"Pot should be $4 after SB call, got {pot_after_sb_call}"
            assert sb_stack_after == sb_stack_before - 1, \
                f"SB stack should decrease by $1, was {sb_stack_before}, now {sb_stack_after}"

            # BB checks
            bb_id = game.current_player.id
            bb_stack_before = game.table.players[bb_id].stack

            result = game.player_action(bb_id, PlayerAction.CHECK)
            assert result.success

            pot_after_bb_check = game.betting.get_main_pot_amount()
            bb_stack_after = game.table.players[bb_id].stack

            # Pot unchanged, BB stack unchanged
            assert pot_after_bb_check == pot_after_sb_call, "Pot should be unchanged after check"
            assert bb_stack_after == bb_stack_before, "BB stack should be unchanged after check"

            # Total chips should still add up
            total_now = sum(p.stack for p in game.table.players.values())
            assert total_now + pot_after_bb_check == initial_total, \
                f"Total chips should be {initial_total}, got {total_now} + {pot_after_bb_check}"

    def test_advance_step_returned_when_betting_round_complete(self, app, holdem_table, player1, player2):
        """
        Test that advance_step is True when the betting round completes.
        This is critical for the online poker platform to know when to advance the game.
        """
        with app.app_context():
            success, _, session = game_orchestrator.create_session(holdem_table.id)
            assert success

            session.add_player(player1.id, "player1", 100)
            session.add_player(player2.id, "player2", 100)

            game = session.game
            game.start_hand()
            game._next_step()  # Deal
            game._next_step()  # Betting

            # SB calls - betting not complete yet
            sb_id = game.current_player.id
            result = game.player_action(sb_id, PlayerAction.CALL, 2)
            assert result.success
            # advance_step should be False because BB still needs to act
            assert not result.advance_step, "advance_step should be False - BB still needs to act"

            # BB checks - betting round complete
            bb_id = game.current_player.id
            result = game.player_action(bb_id, PlayerAction.CHECK)
            assert result.success
            # advance_step should be True because betting round is complete
            assert result.advance_step, "advance_step should be True - betting round is complete"
