"""Interactive example of Straight Poker game."""
import logging
import sys

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)
import json
from pathlib import Path
from typing import Dict, List

from generic_poker.config.loader import GameRules, BettingStructure
from generic_poker.game.game import Game, GameState, PlayerAction
from generic_poker.core.card import Card
from generic_poker.game.betting import PlayerBet  # Add this import



def load_straight_poker_rules() -> GameRules:
    """Load Straight Poker game rules."""
    rules_path = Path(__file__).parents[1] / 'data' / 'game_configs' / 'straight.json'
    with open(rules_path) as f:
        return GameRules.from_json(f.read())


def print_game_state(game: Game) -> None:
    """Print current state of the game."""
    print("\n=== Game State ===")
    print(f"State: {game.state.value}")
    
    # Only show step/action if hand has started
    if game.current_step >= 0:
        print(f"Current Step: {game.current_step}")
        if game.current_step < len(game.rules.gameplay):
            print(f"Current Action: {game.rules.gameplay[game.current_step].name}")
            
        if game.current_player:
            print(f"Current Player: {game.table.players[game.current_player].name}")
    
    print("\nPlayers:")
    # Get players in position order
    for player in game.table.get_position_order():
        position = player.position.value if player.position else "NA"
        cards = [
            str(c) if c.visibility.name == 'FACE_UP' else '**'
            for c in player.hand.get_cards()
        ]
        print(
            f"{player.name} ({position}): "
            f"Stack: ${player.stack} "
            f"Active: {player.is_active} "
            f"Cards: {' '.join(cards)}"
        )
    
    if game.table.community_cards:
        print("\nCommunity Cards:")
        print(' '.join(str(c) for c in game.table.community_cards))
    
    if game.state == GameState.BETTING:
        print("\nBetting Status:")
        print(f"Current Bet: ${game.betting.current_bet}")
        print(f"Pot: ${game.betting.pot.main_pot}")
        
        current_action = (
            game.rules.gameplay[game.current_step].name
            if game.current_step < len(game.rules.gameplay)
            else None
        )
        
        if current_action == "Post Blinds":
            print("\nWaiting for blinds to be posted...")
        else:
            # Show current bets for each player
            if game.betting.current_bets:
                print("Current round bets:")
                for pid, bet in game.betting.current_bets.items():
                    player = game.table.players[pid]
                    print(f"  {player.name}: ${bet.amount}")
            if game.betting.pot.side_pots:
                print("Side Pots:", game.betting.pot.side_pots)


def setup_test_game() -> Game:
    """Set up a test game with some players."""
    # Load rules
    rules = load_straight_poker_rules()
    
    # Create game - $10/$20 limit
    game = Game(
        rules=rules,
        structure=BettingStructure.LIMIT,
        small_bet=10,
        big_bet=20,
        min_buyin=200,
        max_buyin=1000
    )
    
    # Add some test players
    game.add_player("p1", "Alice", 500)
    game.add_player("p2", "Bob", 500)
    game.add_player("p3", "Charlie", 500)
    
    return game


def get_player_action(game: Game, player_id: str) -> tuple[PlayerAction, int]:
    """Get action from player (or simulate it for testing)."""
    player = game.table.players[player_id]
    required_bet = game.betting.get_required_bet(player_id)
    current_bet = game.betting.current_bets.get(player_id, PlayerBet()).amount
    
    print(f"\n{player.name}'s turn")
    print(f"Stack: ${player.stack}")
    print(f"Cards: {' '.join(str(c) for c in player.hand.get_cards())}")
    if required_bet > 0:
        print(f"To call: ${required_bet}")
    else:
        print("No bet to call")
    
    # Show available actions
    print("\nAvailable actions:")
    if required_bet == 0:
        print("1: Check")
        print("2: Bet")
    else:
        print("1: Fold")
        print("2: Call")
        if player.stack > required_bet:
            print("3: Raise")
    
    while True:
        choice = input("\nEnter choice number: ")
        if not choice.isdigit():
            print("Invalid choice")
            continue
            
        choice = int(choice)
        if required_bet == 0:
            if choice == 1:
                return PlayerAction.CHECK, 0
            elif choice == 2:
                amount = game.betting.get_min_bet(player_id, None)
                return PlayerAction.BET, amount
        else:
            if choice == 1:
                return PlayerAction.FOLD, 0
            elif choice == 2:
                # For calls, tell betting system we want to bet exactly current_bet
                # It will handle the fact that we might have already contributed some
                return PlayerAction.CALL, game.betting.current_bet
            elif choice == 3 and player.stack > required_bet:
                # For limit, raise is double current bet
                return PlayerAction.RAISE, game.betting.current_bet * 2
                
        print("Invalid choice")

def run_game():
    """Run through a game of Straight Poker."""
    game = setup_test_game()
    print("Starting new game of Straight Poker")
    print_game_state(game)
    
    input("\nPress Enter to start hand...")
    game.start_hand()
    
    while game.state != GameState.COMPLETE:
        print_game_state(game)
        
        # Get current action if there is one
        current_action = (
            game.rules.gameplay[game.current_step].name
            if game.current_step < len(game.rules.gameplay)
            else None
        )
        
        if current_action == "Post Blinds":
            print("\nPosting forced bets...")
            input("Press Enter to continue...")
            game.process_current_step()
        elif game.state == GameState.BETTING and game.current_player:
            action, amount = get_player_action(game, game.current_player)
            result = game.player_action(game.current_player, action, amount)
            
            if not result.success:
                print(f"\nError: {result.error}")
                continue
        else:
            input("\nPress Enter to continue...")
    
    print("\n=== Hand Complete ===")
    print_game_state(game)


if __name__ == "__main__":
    run_game()