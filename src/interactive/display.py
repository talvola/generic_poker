from generic_poker.game.game import Game
from generic_poker.game.game_state import GameState

def display_game_state(game: Game) -> None:
    """Display the current game state in a user-friendly way."""
    print("\n=== Poker Game ===")
    step_name = game.rules.gameplay[game.current_step].name if game.current_step >= 0 else "Pre-Hand"
    print(f"Step: {step_name} | State: {game.state.value}")
    if game.current_player:
        print(f"Current Player: {game.current_player.name}")
    else:
        print("Current Player: None")

    print("\nPlayers:")
    for player in game.table.get_position_order():
        all_cards = player.hand.get_cards()
        subsets = player.hand.subsets  # Access the subsets defaultdict
        subset_display = []

        # Display named subsets
        for subset_name, subset_cards in subsets.items():
            hidden_cards = " ".join("**" for _ in subset_cards) if subset_cards else "None"
            subset_display.append(f"{subset_name}: {hidden_cards}")

        # Display unassigned cards (if any)
        unassigned = [c for c in all_cards if not any(c in sc for sc in subsets.values())]
        if unassigned:
            hidden_unassigned = " ".join("**" for _ in unassigned)
            subset_display.append(f"Unassigned: {hidden_unassigned}")

        cards_str = " / ".join(subset_display) if subset_display else "None"
        print(f"{player.name}: Stack ${player.stack} | Cards: {cards_str} | Active: {player.is_active}")

    if game.table.community_cards:
        print("\nCommunity Cards:")
        for subset_name, cards in game.table.community_cards.items():
            if subset_name == "default":
                print(f"  {' '.join(str(c) for c in cards)}")
            else:
                print(f"  {subset_name}: {' '.join(str(c) for c in cards)}")

    if game.state == GameState.BETTING:
        print(f"\nPot: ${game.betting.get_main_pot_amount()} | Current Bet: ${game.betting.current_bet}")
        print("Current Bets:")
        for pid, bet in game.betting.current_bets.items():
            print(f"  {game.table.players[pid].name}: ${bet.amount}")

    if game.state == GameState.COMPLETE:
        print("\n=== Showdown ===")
        results = game.get_hand_results()
        print(results)  # Use the __str__ method of GameResult