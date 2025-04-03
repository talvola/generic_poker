from typing import Tuple, Optional, List
from generic_poker.game.game import Game, PlayerAction, GameActionType
from generic_poker.game.game_state import GameState
from generic_poker.core.card import Card
from .display import display_game_state

def get_player_action(game: Game, player: 'Player') -> Tuple[PlayerAction, int]:
    """Prompt the current player for their action."""
    valid_actions = game.get_valid_actions(player.id)
    print(f"\n{player.name}'s Turn | Stack: ${player.stack}")
    print(f"Cards: {' '.join(str(c) for c in player.hand.get_cards())}")
    print("Options:")
    for i, (action, min_amt, max_amt) in enumerate(valid_actions, 1):
        if min_amt == max_amt:
            print(f"{i}: {action.value} ${min_amt or 0}")
        elif min_amt is None:
            print(f"{i}: {action.value}")
        else:
            print(f"{i}: {action.value} ${min_amt}-${max_amt}")
    
    while True:
        choice = input("Choose action (number): ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(valid_actions):
            action, min_amt, max_amt = valid_actions[int(choice) - 1]
            if min_amt != max_amt and min_amt is not None:
                while True:
                    amt = input(f"Enter amount (${min_amt}-${max_amt}): ").strip()
                    try:
                        amt = int(amt)
                        if min_amt <= amt <= max_amt:
                            return action, amt
                        print("Amount out of range.")
                    except ValueError:
                        print("Invalid amount.")
            return action, min_amt or 0
        print("Invalid choice.")

def get_discard_action(game: Game, player: 'Player') -> Tuple[PlayerAction, int, Optional[List[Card]]]:
    """Prompt the current player to select cards to discard, or handle forced discards."""
    step = game.rules.gameplay[game.current_step]
    discard_config = step.action_config["cards"][0]  # Assume one discard object for now
    
    # Check for forced discard
    if "rule" in discard_config:
        print(f"\n{player.name}'s Turn | Forced discard ({discard_config['rule']})")
        return PlayerAction.DISCARD, 0, []  # Engine handles the rule-based discard
    
    # Optional discard
    hand = player.hand.get_cards()
    if not hand:
        print(f"\n{player.name}'s Turn | No cards to discard")
        return PlayerAction.DISCARD, 0, []

    valid_actions = game.get_valid_actions(player.id)
    discard_action = next((a for a in valid_actions if a[0] == PlayerAction.DISCARD), None)
    if not discard_action:
        print(f"\n{player.name}'s Turn | Discarding not allowed")
        return PlayerAction.DISCARD, 0, []
    
    _, min_discards, max_discards = discard_action  # e.g., (DISCARD, 0, 4)

    print(f"\n{player.name}'s Turn | Stack: ${player.stack}")
    print("Your cards:")
    for i, card in enumerate(hand, 1):
        print(f"{i}: {card}")
    
    prompt = f"Select {min_discards} to {max_discards} cards to discard (e.g., '1 3 5' or press Enter to discard {min_discards}):"
    print(prompt)
    
    while True:
        choice = input("Enter card numbers: ").strip()
        if not choice and min_discards == 0:  # Empty input allowed if min is 0
            return PlayerAction.DISCARD, 0, []
        elif not choice:  # Empty input not allowed if min > 0
            print(f"Must discard at least {min_discards} cards.")
            continue
        
        try:
            indices = [int(x) - 1 for x in choice.split()]
            if not all(0 <= i < len(hand) for i in indices):
                print("Invalid card numbers. Try again.")
                continue
            num_discards = len(indices)
            if num_discards < min_discards or num_discards > max_discards:
                print(f"Must discard between {min_discards} and {max_discards} cards.")
                continue
            if len(indices) != len(set(indices)):  # Check for duplicates
                print("Duplicate card numbers. Try again.")
                continue
            cards_to_discard = [hand[i] for i in indices]
            return PlayerAction.DISCARD, 0, cards_to_discard
        except ValueError:
            print("Invalid input. Use space-separated numbers (e.g., '1 3 5').")

def run_game(game: Game) -> None:
    """Run an interactive poker game."""
    print(f"Starting {game.rules.game} Game")
    game.start_hand()

    while True:
        initial_stacks = {pid: p.stack for pid, p in game.table.players.items()}
        
        while game.state != GameState.COMPLETE:
            display_game_state(game)
            step = game.rules.gameplay[game.current_step]
            
            if step.action_type == GameActionType.DEAL:
                input("\nPress Enter to proceed...")
                game._next_step()
            elif step.action_type == GameActionType.DISCARD and game.current_player:
                action, amount, cards = get_discard_action(game, game.current_player)
                result = game.player_action(game.current_player.id, action, amount, cards)
                print(f"results: {result}")
                if not result.success:
                    print(f"Error: {result.error}")
                elif result.advance_step:
                    game._next_step()
            elif step.action_type == GameActionType.DRAW:
                input("\nPress Enter to proceed...")
                game._next_step()
            elif step.action_type == GameActionType.BET and "type" in step.action_config and step.action_config["type"] in ["antes", "blinds", "bring-in"]:
                input("\nPress Enter to post forced bets...")
                game._next_step()
            elif game.state == GameState.BETTING and game.current_player:
                action, amount = get_player_action(game, game.current_player)
                result = game.player_action(game.current_player.id, action, amount)
                if not result.success:
                    print(f"Error: {result.error}")
                elif result.advance_step:
                    game._next_step()

        # Display final state and results
        display_game_state(game)
        print("\nResults:")
        for pid, player in game.table.players.items():
            change = player.stack - initial_stacks[pid]
            if change > 0:
                print(f"{player.name} won ${change}")
            elif change < 0:
                print(f"{player.name} lost ${-change}")
            else:
                print(f"{player.name} broke even")

        # Move the button after the hand ends
        game.table.move_button()

        # Prompt to continue or exit
        print("\nCurrent Chip Stacks:")
        for player in game.table.get_position_order():
            print(f"{player.name}: ${player.stack}")
        while True:
            choice = input("\nContinue to next hand? (y/n): ").strip().lower()
            if choice in ('y', 'n'):
                break
            print("Please enter 'y' or 'n'.")
        
        if choice == 'n':
            print("Game ended.")
            break
        
        # Start new hand with the updated button position
        game.start_hand()
    
    display_game_state(game)
    print("\nResults:")
    for pid, player in game.table.players.items():
        change = player.stack - initial_stacks[pid]
        if change > 0:
            print(f"{player.name} won ${change}")
        elif change < 0:
            print(f"{player.name} lost ${-change}")
        else:
            print(f"{player.name} broke even")