from typing import Tuple, Optional, List, Dict
from generic_poker.game.game import Game, PlayerAction, GameActionType
from generic_poker.game.game_state import GameState
from generic_poker.core.card import Card, Visibility
from generic_poker.game.table import Player
from .display import display_game_state

def get_player_action(game: Game, player: 'Player') -> Tuple[PlayerAction, int]:
    """Prompt the current player for their action."""
    valid_actions = game.get_valid_actions(player.id)
    print(f"\n{player.name}'s Turn | Stack: ${player.stack}")

    # Display cards
    print("Cards:")
    all_cards = player.hand.get_cards()
    subsets = player.hand.subsets  # Access the subsets defaultdict

    # Check if there's a mix of face-down and face-up cards
    has_face_down = any(card.visibility == Visibility.FACE_DOWN for card in all_cards)
    has_face_up = any(card.visibility == Visibility.FACE_UP for card in all_cards)
    use_visibility_grouping = has_face_down and has_face_up

    if use_visibility_grouping:
        # Group by visibility when there's a mix of face-down and face-up cards
        hole_cards = [card for card in all_cards if card.visibility == Visibility.FACE_DOWN]
        upcards = [card for card in all_cards if card.visibility == Visibility.FACE_UP]

        if hole_cards:
            cards_display = " ".join(str(card) for card in hole_cards)
            print(f"  Hole Cards: {cards_display}")
        else:
            print("  Hole Cards: None")

        if upcards:
            cards_display = " ".join(str(card) for card in upcards)
            print(f"  Upcards: {cards_display}")
        else:
            print("  Upcards: None")
    else:
        # Group by subsets when all cards have the same visibility
        for subset_name, subset_cards in subsets.items():
            if subset_cards:
                # Show full card values for the current player
                cards_display = " ".join(str(card) for card in subset_cards)
                print(f"  {subset_name}: {cards_display}")
            else:
                print(f"  {subset_name}: None")

        # Display unassigned cards (if any)
        unassigned = [c for c in all_cards if not any(c in sc for sc in subsets.values())]
        if unassigned:
            unassigned_display = " ".join(str(card) for card in unassigned)
            print(f"  Unassigned: {unassigned_display}")

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

def get_discard_action(game: Game, player: Player) -> Tuple[PlayerAction, int, Optional[List[Card]]]:
    """Prompt the current player to select cards to discard, or handle forced discards."""
    step = game.rules.gameplay[game.current_step]
    if step.action_type == GameActionType.GROUPED:
        discard_config = step.action_config[game.action_handler.current_substep]
    else:
        discard_config = step.action_config["cards"][0]  # Assume one discard object for now
    
    # Check for forced discard
    if "rule" in discard_config:
        print(f"\n{player.name}'s Turn | Forced discard ({discard_config['rule']})")
        return PlayerAction.DISCARD, 0, []  # Engine handles the rule-based discard
    
    hand = player.hand.get_cards()
    if not hand:
        print(f"\n{player.name}'s Turn | No cards to discard")
        return PlayerAction.DISCARD, 0, []
    
    valid_actions = game.get_valid_actions(player.id)
    discard_action = next((a for a in valid_actions if a[0] == PlayerAction.DISCARD), None)
    if not discard_action:
        print(f"\n{player.name}'s Turn | Discarding not allowed")
        return PlayerAction.DISCARD, 0, []
    _, min_discards, max_discards = discard_action    

    print(f"\n{player.name}'s Turn | Stack: ${player.stack}")
    print("Your cards:")
    subsets = player.hand.subsets
    card_list = []
    for subset_name, subset_cards in subsets.items():
        for i, card in enumerate(subset_cards, 1):
            card_list.append((f"{subset_name} {i}", card))
    unassigned = [c for c in hand if not any(c in sc for sc in subsets.values())]
    for i, card in enumerate(unassigned, 1):
        card_list.append((f"Unassigned {i}", card))
    for idx, (label, card) in enumerate(card_list, 1):
        print(f"{idx}: {card}")
    
    prompt = f"Select {min_discards} to {max_discards} cards to discard (e.g., '1 3 5' or press Enter to discard {min_discards}):"
    print(prompt)
    
    while True:
        choice = input("Enter card numbers: ").strip()
        if not choice and min_discards == 0:
            return PlayerAction.DISCARD, 0, []
        elif not choice:
            print(f"Must discard at least {min_discards} cards.")
            continue
        try:
            indices = [int(x) - 1 for x in choice.split()]
            if not all(0 <= i < len(card_list) for i in indices):
                print("Invalid card numbers. Try again.")
                continue
            num_discards = len(indices)
            if num_discards < min_discards or num_discards > max_discards:
                print(f"Must discard between {min_discards} and {max_discards} cards.")
                continue
            if len(indices) != len(set(indices)):
                print("Duplicate card numbers. Try again.")
                continue
            cards_to_discard = [card_list[i][1] for i in indices]
            return PlayerAction.DISCARD, 0, cards_to_discard
        except ValueError:
            print("Invalid input. Use space-separated numbers (e.g., '1 3').")

def get_expose_action(game: Game, player: Player) -> Tuple[PlayerAction, int, Optional[List[Card]]]:
    """
    Prompt the player to select cards to expose based on valid game actions.
    
    Args:
        game: The current Game instance.
        player: The Player instance making the action.
    
    Returns:
        Tuple containing:
        - PlayerAction.EXPOSE: The action type.
        - int: Amount (set to 0, as it's not used for expose).
        - Optional[List[Card]]: List of cards to expose, or empty list if none.
    """
    # Get the player's hand
    hand = player.hand.get_cards()
    if not hand:
        print(f"\n{player.name}'s Turn | No cards to expose")
        return PlayerAction.EXPOSE, 0, []

    valid_actions = game.get_valid_actions(player.id)
    expose_action = next((a for a in valid_actions if a[0] == PlayerAction.EXPOSE), None)
    if not expose_action:
        print(f"\n{player.name}'s Turn | Exposing not allowed")
        return PlayerAction.EXPOSE, 0, []
    _, min_expose, max_expose = expose_action

    print(f"\n{player.name}'s Turn | Stack: ${player.stack}")
    print("Your cards:")
    subsets = player.hand.subsets
    card_list = []
    for subset_name, subset_cards in subsets.items():
        for i, card in enumerate(subset_cards, 1):
            card_list.append((f"{subset_name} {i}", card))
    unassigned = [c for c in hand if not any(c in sc for sc in subsets.values())]
    for i, card in enumerate(unassigned, 1):
        card_list.append((f"Unassigned {i}", card))
    for idx, (label, card) in enumerate(card_list, 1):
        visibility = "face up" if card.visibility == Visibility.FACE_UP else "face down"
        print(f"{idx}: {card} ({visibility})")

    prompt = f"Select {min_expose} to {max_expose} cards to expose (e.g., '1 3'):"
    print(prompt)

    while True:
        choice = input("Enter card numbers: ").strip()
        # Handle empty input (only allowed if min_expose is 0)
        if not choice and min_expose == 0:
            return PlayerAction.EXPOSE, 0, []
        elif not choice:
            print(f"Must expose at least {min_expose} card{'s' if min_expose != 1 else ''}.")
            continue

        try:
            # Convert input to zero-based indices
            indices = [int(x) - 1 for x in choice.split()]
            
            # Validate indices are within range
            if not all(0 <= i < len(hand) for i in indices):
                print("Invalid card numbers. Try again.")
                continue
            
            # Check number of cards selected is within min and max
            num_expose = len(indices)
            if num_expose < min_expose or num_expose > max_expose:
                print(f"Must expose between {min_expose} and {max_expose} cards.")
                continue
            
            # Ensure no duplicate selections
            if len(indices) != len(set(indices)):
                print("Duplicate card numbers. Try again.")
                continue
            
            # Create list of cards to expose
            cards_to_expose = [hand[i] for i in indices]
            return PlayerAction.EXPOSE, 0, cards_to_expose
        
        except ValueError:
            print("Invalid input. Use space-separated numbers (e.g., '1 3').")

def get_separate_action(game: Game, player: Player) -> Tuple[PlayerAction, int, Optional[List[Card]]]:
    """Prompt the player to separate their hand into specified subsets."""
    hand = player.hand.get_cards()
    if not hand:
        print(f"\n{player.name}'s Turn | No cards to separate")
        return PlayerAction.SEPARATE, 0, []

    valid_actions = game.get_valid_actions(player.id)
    separate_action = next((a for a in valid_actions if a[0] == PlayerAction.SEPARATE), None)
    if not separate_action:
        print(f"\n{player.name}'s Turn | Separating not allowed")
        input("Press Enter to continue...")
        return PlayerAction.SEPARATE, 0, []

    # Get subset requirements from the step config
    step = game.rules.gameplay[game.current_step]
    separate_config = step.action_config["cards"]  # List of {"hole_subset": str, "number": int}
    total_cards_required = sum(subset["number"] for subset in separate_config)
    if len(hand) != total_cards_required:
        print(f"\n{player.name}'s Turn | Hand size ({len(hand)}) does not match required total ({total_cards_required})")
        return PlayerAction.SEPARATE, 0, []

    print(f"\n{player.name}'s Turn | Stack: ${player.stack}")
    print("Your cards:")
    for i, card in enumerate(hand, 1):
        print(f"{i}: {card}")

    # Collect cards for each subset
    selected_cards = []
    remaining_hand = hand.copy()

    for subset in separate_config:
        subset_name = subset["hole_subset"]
        num_cards = subset["number"]
        print(f"\nSelect {num_cards} card{'s' if num_cards != 1 else ''} for '{subset_name}' subset (e.g., '1 3'):")
        print("Remaining cards:")
        for i, card in enumerate(remaining_hand, 1):
            print(f"{i}: {card}")

        while True:
            choice = input("Enter card numbers: ").strip()
            if not choice:
                print(f"Must select exactly {num_cards} card{'s' if num_cards != 1 else ''}.")
                continue

            try:
                indices = [int(x) - 1 for x in choice.split()]
                if not all(0 <= i < len(remaining_hand) for i in indices):
                    print("Invalid card numbers. Try again.")
                    continue
                if len(indices) != num_cards:
                    print(f"Must select exactly {num_cards} card{'s' if num_cards != 1 else ''}.")
                    continue
                if len(indices) != len(set(indices)):
                    print("Duplicate card numbers. Try again.")
                    continue

                subset_cards = [remaining_hand[i] for i in indices]
                selected_cards.extend(subset_cards)
                # Remove selected cards from remaining_hand
                remaining_hand = [card for i, card in enumerate(remaining_hand) if i not in indices]
                break
            except ValueError:
                print("Invalid input. Use space-separated numbers (e.g., '1 3').")

    # All cards should be assigned
    if remaining_hand:
        print("Error: Not all cards were assigned to subsets.")
        return PlayerAction.SEPARATE, 0, []

    return PlayerAction.SEPARATE, 0, selected_cards

def get_declare_action(game: Game, player: Player) -> Tuple[PlayerAction, int, Optional[List[Dict]]]:
    """
    Prompt the player to declare their intention (high, low, or high/low) for each eligible pot.

    Args:
        game: The current Game instance.
        player: The Player instance making the action.

    Returns:
        Tuple containing:
        - PlayerAction.DECLARE: The action type.
        - int: Amount (set to 0, as it's not used for declare).
        - Optional[List[Dict]]: List of declarations, each with {"pot_index": int, "declaration": str}.
    """
    step = game.rules.gameplay[game.current_step]
    if step.action_type == GameActionType.GROUPED:
        declare_config = step.action_config[game.action_handler.current_substep]["declare"]
    else:
        declare_config = step.action_config

    allowed_options = declare_config.get("options", ["high", "low", "high_low"])
    per_pot = declare_config.get("per_pot", False)

    valid_actions = game.get_valid_actions(player.id)
    declare_action = next((a for a in valid_actions if a[0] == PlayerAction.DECLARE), None)
    if not declare_action:
        print(f"\n{player.name}'s Turn | Declaring not allowed")
        return PlayerAction.DECLARE, 0, []

    print(f"\n{player.name}'s Turn | Stack: ${player.stack}")
    print("Available declarations:", ", ".join(opt.replace("_", "/") for opt in allowed_options))

    declarations = []
    if per_pot:
        # Get eligible pots (main pot: -1, side pots: 0, 1, ...)
        eligible_pots = [-1]  # Main pot
        for i in range(game.betting.get_side_pot_count()):
            if player.id in game.betting.get_side_pot_eligible_players(i):
                eligible_pots.append(i)

        print("You must declare for each eligible pot:")
        for pot_index in eligible_pots:
            pot_name = "Main Pot" if pot_index == -1 else f"Side Pot {pot_index + 1}"
            print(f"{pot_name}:")
            prompt = f"Choose declaration ({', '.join(opt.replace('_', '/') for opt in allowed_options)}): "
            while True:
                choice = input(prompt).strip().lower().replace("/", "_")
                if choice not in allowed_options:
                    print(f"Invalid declaration. Choose from: {', '.join(opt.replace('_', '/') for opt in allowed_options)}")
                    continue
                declarations.append({"pot_index": pot_index, "declaration": choice})
                break
    else:
        # Single declaration for all pots
        prompt = f"Choose declaration ({', '.join(opt.replace('_', '/') for opt in allowed_options)}): "
        while True:
            choice = input(prompt).strip().lower().replace("/", "_")
            if choice not in allowed_options:
                print(f"Invalid declaration. Choose from: {', '.join(opt.replace('_', '/') for opt in allowed_options)}")
                continue
            declarations.append({"pot_index": -1, "declaration": choice})
            break

    return PlayerAction.DECLARE, 0, declarations

def get_draw_action(game: Game, player: Player) -> Tuple[PlayerAction, int, Optional[List[Card]]]:
    """Prompt the player to select cards from a subset to discard and draw replacements."""
    step = game.rules.gameplay[game.current_step]
    draw_config = step.action_config["cards"][0]  # Assume one draw object for now
    subset_name = draw_config.get("hole_subset", "default")  # e.g., "Badugi"

    # Get cards from the specified subset
    hand = player.hand.get_subset(subset_name) if subset_name != "default" else player.hand.get_cards()
    if not hand:
        print(f"\n{player.name}'s Turn | No cards in '{subset_name}' subset to draw")
        return PlayerAction.DRAW, 0, []
    
    valid_actions = game.get_valid_actions(player.id)
    draw_action = next((a for a in valid_actions if a[0] == PlayerAction.DRAW), None)
    if not draw_action:
        print(f"\n{player.name}'s Turn | Drawing not allowed")
        return PlayerAction.DRAW, 0, []
    _, min_draw, max_draw = draw_action

    print(f"\n{player.name}'s Turn | Stack: ${player.stack}")
    print(f"Cards in '{subset_name}' subset:")
    for i, card in enumerate(hand, 1):
        print(f"{i}: {card}")

    prompt = f"Select {min_draw} to {max_draw} cards to discard and draw replacements (e.g., '1 3' or press Enter to draw {min_draw}):"
    print(prompt)

    while True:
        choice = input("Enter card numbers: ").strip()
        if not choice and min_draw == 0:  # Empty input allowed if min is 0
            return PlayerAction.DRAW, 0, []
        elif not choice:
            print(f"Must discard at least {min_draw} card{'s' if min_draw != 1 else ''}.")
            continue

        try:
            indices = [int(x) - 1 for x in choice.split()]
            if not all(0 <= i < len(hand) for i in indices):
                print("Invalid card numbers. Try again.")
                continue
            num_draw = len(indices)
            if num_draw < min_draw or num_draw > max_draw:
                print(f"Must select between {min_draw} and {max_draw} cards.")
                continue
            if len(indices) != len(set(indices)):
                print("Duplicate card numbers. Try again.")
                continue
            cards_to_discard = [hand[i] for i in indices]
            return PlayerAction.DRAW, 0, cards_to_discard
        except ValueError:
            print("Invalid input. Use space-separated numbers (e.g., '1 3').")

def run_game(game: Game) -> None:
    """Run an interactive poker game."""
    print(f"Starting {game.rules.game} Game")

    initial_stacks = {pid: p.stack for pid, p in game.table.players.items()}
    game.start_hand(shuffle_deck=True)

    while True:
        
        while game.state != GameState.COMPLETE:
            display_game_state(game)
            step = game.rules.gameplay[game.current_step]

            # Handle non-player actions
            if step.action_type == GameActionType.DEAL:
                input("\nPress Enter to proceed...")
                game._next_step()
            elif step.action_type == GameActionType.ROLL_DIE:
                input("\nPress Enter to proceed...")
                game._next_step()                
            elif step.action_type == GameActionType.REMOVE:
                input("\nPress Enter to remove board cards...")
                game._next_step()                
            elif step.action_type == GameActionType.BET and "type" in step.action_config and step.action_config["type"] in ["antes", "blinds"]:
                input("\nPress Enter to post forced bets...")
                game._next_step()
            elif game.current_player:
                # Inner loop to handle all subactions for the current player
                while game.current_player:
                    if step.action_type == GameActionType.GROUPED:
                        action_dict = step.action_config[game.action_handler.current_substep]
                        action_name = list(action_dict.keys())[0]  # This will be 'bet'
                        action_type = GameActionType[action_name.upper()]  # Convert 'bet' -> 'BET'
                    else:
                        action_type = step.action_type

                    if game.state == GameState.BETTING:
                        action, amount = get_player_action(game, game.current_player)
                        result = game.player_action(game.current_player.id, action, amount)
                    elif action_type == GameActionType.DISCARD and game.current_player:
                        action, amount, cards = get_discard_action(game, game.current_player)
                        result = game.player_action(game.current_player.id, action, amount, cards)
                    elif action_type == GameActionType.EXPOSE and game.current_player:
                        action, amount, cards = get_expose_action(game, game.current_player)
                        result = game.player_action(game.current_player.id, action, amount, cards)    
                    elif action_type == GameActionType.DECLARE and game.current_player:
                        action, amount, declaration_data = get_declare_action(game, game.current_player)
                        result = game.player_action(game.current_player.id, action, amount, declaration_data=declaration_data)
                    elif action_type == GameActionType.SEPARATE:
                        action, amount, cards = get_separate_action(game, game.current_player)
                        result = game.player_action(game.current_player.id, action, amount, cards)     
                    elif action_type == GameActionType.DRAW:
                        action, amount, cards = get_draw_action(game, game.current_player)
                        result = game.player_action(game.current_player.id, action, amount, cards)        
                    elif action_type == GameActionType.DEAL:
                        # assume no player input needed - just send the player action
                        result = game.player_action(game.current_player.id, PlayerAction.DEAL)                                                                                                      
                    else:
                        print(f"Unhandled game state: {game.state}")
                        input("\nPress Enter to proceed...")
                        break                        

                    if not result.success:
                        print(f"Error: {result.error}")

                    if result.advance_step:
                        game._next_step()
                        break  # Exit inner loop to re-evaluate the new step in the outer loop

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
        initial_stacks = {pid: p.stack for pid, p in game.table.players.items()}
        game.start_hand(shuffle_deck=True)
    
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