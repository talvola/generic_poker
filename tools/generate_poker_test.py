import json
from typing import Dict, List, Any
import sys
import os
import subprocess
import json
import re

def update_test_with_json(script_path: str):
    """Run the test script, capture JSON showdown output, and update assertions."""
    result = subprocess.run(
        ["pytest", script_path, "-s"],
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        print(f"Initial test run failed (expected until updated): {result.stderr}")

    output = result.stdout
    # Updated regex to stop at PASSED, FAILED, or end of output
    json_pattern = r"Showdown Results \(JSON\):\n(.*?)\n(?=PASSED|FAILED|\Z)"
    match = re.search(json_pattern, output, re.DOTALL)
    if not match:
        print("Could not find JSON output in test results")
        print("Full output:", output)
        return
    json_str = match.group(1).strip()
    try:
        results = json.loads(json_str)
    except json.JSONDecodeError as e:
        print(f"Failed to parse JSON: {e}")
        print(f"Extracted JSON: {json_str}")
        return

    # Read the original script
    with open(script_path, 'r') as f:
        lines = f.readlines()

    # Update showdown section
    updated_lines = []
    in_showdown = False
    for line in lines:
        if "Step" in line and "Showdown" in line:
            in_showdown = True
        if in_showdown:
            if "assert main_pot.amount == results.total_pot" in line:
                # Replace with per-pot amount check
                line = "    # Check each pot’s amount\n"
                for i, pot in enumerate(results['pots']):
                    updated_lines.append(f"    assert results.pots[{i}].amount == {pot['amount']}  # {pot['hand_type']} pot\n")
                continue  # Skip adding the original line
            elif "assert main_pot.pot_type == 'main'" in line:
                # Keep this as-is for the first pot, but we’ll check others below
                line = f"    assert main_pot.pot_type == '{results['pots'][0]['pot_type']}'  # Updated from run\n"
            elif "assert not main_pot.split" in line:
                is_split = results['pots'][0]['split']
                line = f"    assert main_pot.split == {is_split}  # Updated from run\n"
            elif "assert len(main_pot.winners) == 1" in line:
                num_winners = len(results['pots'][0]['winners'])
                line = f"    assert len(main_pot.winners) == {num_winners}  # Updated from run\n"
            elif "assert main_pot.winners[0] in" in line:
                winners = results['pots'][0]['winners']
                line = f"    assert sorted(main_pot.winners) == {sorted(winners)}  # Updated from run\n"
            elif "assert winning_hand[0].hand_name" in line and "TODO" in line:
                hand_name = results['winning_hands'][0]['hand_name']
                line = f"    assert winning_hand[0].hand_name == '{hand_name}'  # Updated from run\n"
            elif "assert winning_hand[0].hand_description" in line and "TODO" in line:
                hand_desc = results['winning_hands'][0]['hand_description']
                line = f"    assert winning_hand[0].hand_description == '{hand_desc}'  # Updated from run\n"
            elif "assert len(results.winning_hands) == 1" in line:
                num_winning_hands = len(results['winning_hands'])
                line = f"    assert len(results.winning_hands) == {num_winning_hands}  # Updated from run\n"
            elif "assert results.winning_hands[0].player_id == winning_player" in line:
                winner = results['winning_hands'][0]['player_id']
                line = f"    assert results.winning_hands[0].player_id == '{winner}'  # Updated from run\n"
        updated_lines.append(line)

    # Write back updated script
    with open(script_path, 'w') as f:
        f.writelines(updated_lines)
    print(f"Updated {script_path} with JSON results")

def generate_test_script(json_file_path: str, output_file_path: str) -> None:
    """Generate a pytest script for a poker game defined in a JSON file."""
    with open(json_file_path, 'r') as f:
        game_rules = json.load(f)

    file_base_name = os.path.splitext(os.path.basename(json_file_path))[0]
    game_name = game_rules["game"].replace(" ", "_").replace("-","_").replace("'","_").lower()
    uses_blinds = any(step.get("bet", {}).get("type") == "blinds" for step in game_rules["gamePlay"])
    player_ids = ["BTN", "SB", "BB"] if uses_blinds else ["p1", "p2", "p3"]
    action_order = ["SB", "BB", "BTN"] if uses_blinds else player_ids

    script = [
        '"""Minimal end-to-end test for {game_name}."""'.format(game_name=game_name),
        "import pytest",
        "from generic_poker.config.loader import GameRules",
        "from generic_poker.game.game import Game, GameState, PlayerAction",
        "from generic_poker.core.card import Card, Rank, Suit",
        "from generic_poker.game.betting import BettingStructure",
        "from generic_poker.core.deck import Deck",
        "from tests.test_helpers import load_rules_from_file",
        "import logging",
        "import sys",
        "",
        "class MockDeck(Deck):",
        '    """A deck with predetermined card sequence for testing, followed by remaining cards."""',
        "    def __init__(self, named_cards):",
        "        super().__init__(include_jokers=False)",
        "        self.cards.clear()",
        "        for card in named_cards:",
        "            self.cards.append(card)",
        "        # Add remaining cards from a standard deck in deterministic order",
        "        all_cards = [Card(rank, suit) for suit in [Suit.SPADES, Suit.HEARTS, Suit.DIAMONDS, Suit.CLUBS] "
        "                    for rank in [Rank.TWO, Rank.THREE, Rank.FOUR, Rank.FIVE, Rank.SIX, Rank.SEVEN, "
        "                                 Rank.EIGHT, Rank.NINE, Rank.TEN, Rank.JACK, Rank.QUEEN, Rank.KING, Rank.ACE]]",
        "        used_cards = {(c.rank, c.suit) for c in named_cards}",
        "        remaining_cards = [c for c in all_cards if (c.rank, c.suit) not in used_cards]",
        "        for card in remaining_cards:",
        "            self.cards.append(card)",
        "        self.cards.reverse()",
        "",
        "def create_predetermined_deck():",
        '    """Create a deck with predetermined cards followed by the rest of a standard deck."""',
        "    named_cards = [",
        "        Card(Rank.ACE, Suit.HEARTS), Card(Rank.NINE, Suit.DIAMONDS), Card(Rank.JACK, Suit.SPADES),",
        "        Card(Rank.KING, Suit.HEARTS), Card(Rank.KING, Suit.CLUBS), Card(Rank.JACK, Suit.DIAMONDS),",
        "        Card(Rank.QUEEN, Suit.HEARTS), Card(Rank.KING, Suit.DIAMONDS), Card(Rank.TEN, Suit.SPADES),",
        "        Card(Rank.QUEEN, Suit.CLUBS), Card(Rank.QUEEN, Suit.SPADES), Card(Rank.JACK, Suit.HEARTS),",
        "        Card(Rank.TEN, Suit.DIAMONDS), Card(Rank.TEN, Suit.HEARTS), Card(Rank.NINE, Suit.SPADES),",
        "        Card(Rank.TWO, Suit.SPADES), Card(Rank.TWO, Suit.DIAMONDS), Card(Rank.TWO, Suit.HEARTS),",
        "        Card(Rank.SEVEN, Suit.DIAMONDS), Card(Rank.SIX, Suit.CLUBS), Card(Rank.THREE, Suit.SPADES),",
        "    ]",
        "    return MockDeck(named_cards)",
        "",
        "def setup_test_game():",
        f'    """Setup a 3-player {game_name} game with a mock deck."""',
        f"    rules = load_rules_from_file('{file_base_name}')",
        "    game = Game(",
        "        rules=rules,",
        "        structure=BettingStructure.LIMIT,",
        "        small_bet=10,",
        "        big_bet=20,",
        "        min_buyin=100,",
        "        max_buyin=1000,",
        "        auto_progress=False",
        "    )",
    ]

    for i, pid in enumerate(player_ids):
        script.append(f"    game.add_player('{pid}', 'Player{i+1}', 500)")

    script.extend([
        "    original_clear_hands = game.table.clear_hands",
        "    def patched_clear_hands():",
        "        for player in game.table.players.values():",
        "            player.hand.clear()",
        "        game.table.community_cards.clear()",
        "    game.table.clear_hands = patched_clear_hands",
        "    game.table.deck = create_predetermined_deck()",
        "    assert len(game.table.deck.cards) >= 52, 'MockDeck should have at least 52 cards'",
        "    return game",
        "",
        "@pytest.fixture(autouse=True)",
        "def setup_logging():",
        "    root_logger = logging.getLogger()",
        "    for handler in root_logger.handlers[:]:",
        "        root_logger.removeHandler(handler)",
        "    logging.basicConfig(",
        "        level=logging.DEBUG,",
        "        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',",
        "        handlers=[logging.StreamHandler(sys.stdout)],",
        "        force=True",
        "    )",
        "",
        f"def test_{game_name}_minimal_flow():",
        f'    """Test minimal flow for {game_name} from start to showdown."""',
        "    game = setup_test_game()",
        "    game.start_hand()",
    ])

    first_betting_round = True

    # Calculate cumulative community cards per step
    community_card_counts = {}
    total_community_cards = 0
    for step_idx, step in enumerate(game_rules["gamePlay"]):
        if "deal" in step and step["deal"]["location"] == "community":
            total_community_cards += sum(c["number"] for c in step["deal"]["cards"])
            community_card_counts[step_idx] = total_community_cards    

    for step_idx, step in enumerate(game_rules["gamePlay"]):
        step_name = step["name"].replace(" ", "_").lower()
        action_type = list(step.keys())[0]
        if step_idx == 0:
            script.append(f"    # Step {step_idx}: {step['name']}")
            script.append(f"    assert game.current_step == {step_idx}")
        else:
            script.append(f"    # Step {step_idx}: {step['name']}")
            script.append(f"    game._next_step()  # {step_name}")
            script.append(f"    assert game.current_step == {step_idx}")

        if action_type == "bet":
            bet_type = step["bet"]["type"]
            if bet_type == "blinds":
                script.extend([
                    "    assert game.state == GameState.BETTING",
                    f"    assert game.table.players['{player_ids[1]}'].stack == 495  # SB posted 5",
                    f"    assert game.table.players['{player_ids[2]}'].stack == 490  # BB posted 10",
                    f"    assert game.table.players['{player_ids[0]}'].stack == 500  # BTN",
                    "    assert game.betting.get_main_pot_amount() == 15",
                    "    print('Stacks after blinds:', {{pid: game.table.players[pid].stack for pid in {}}})".format(player_ids),
                ])
            elif bet_type in ["small", "big"]:
                bet_amount = 10 if bet_type == "small" else 20
                first_player = "'BTN'" if first_betting_round else "'SB'"
                if first_betting_round:
                    script.extend([
                        "    assert game.state == GameState.BETTING",
                        f"    assert game.current_player.id == {first_player}  # BTN first pre-flop",
                        f"    actions = game.get_valid_actions({first_player})",
                        f"    assert (PlayerAction.CALL, {bet_amount}, {bet_amount}) in actions",
                        f"    game.player_action('BTN', PlayerAction.CALL, {bet_amount})",
                        f"    game.player_action('SB', PlayerAction.CALL, {bet_amount - 5})  # SB completes to {bet_amount}",
                        f"    game.player_action('BB', PlayerAction.CHECK)  # BB already in for {bet_amount}",
                        "    assert game.betting.get_main_pot_amount() == 30",
                        f"    assert game.table.players['BTN'].stack == {500 - bet_amount}  # BTN called {bet_amount}",
                        f"    assert game.table.players['SB'].stack == {495 - (bet_amount - 5)}  # SB completed",
                        f"    assert game.table.players['BB'].stack == 490  # BB unchanged",
                        "    print('Stacks after pre-flop:', {{pid: game.table.players[pid].stack for pid in {}}})".format(player_ids),
                    ])
                else:
                    script.extend([
                        "    assert game.state == GameState.BETTING",
                        f"    assert game.current_player.id == {first_player}  # SB first post-flop",
                        f"    actions = game.get_valid_actions({first_player})",
                        "    assert (PlayerAction.CHECK, None, None) in actions",
                        "    game.player_action('SB', PlayerAction.CHECK)",
                        "    game.player_action('BB', PlayerAction.CHECK)",
                        "    game.player_action('BTN', PlayerAction.CHECK)",
                        "    assert game.betting.get_main_pot_amount() == 30  # No change",
                        "    assert game.table.players['BTN'].stack == 490  # Unchanged from pre-flop",
                        "    assert game.table.players['SB'].stack == 490  # Unchanged from pre-flop",
                        "    assert game.table.players['BB'].stack == 490  # Unchanged",
                        "    print('Stacks after post-flop:', {{pid: game.table.players[pid].stack for pid in {}}})".format(player_ids),
                    ])
                first_betting_round = False
            elif bet_type == "bring-in":
                script.extend([
                    "    assert game.state == GameState.BETTING",
                    f"    assert game.current_player.id == '{player_ids[0]}'  # Temp assumption",
                    "    actions = game.get_valid_actions(game.current_player.id)",
                    "    game.player_action(game.current_player.id, PlayerAction.BET, 10)",
                ])
            else:
                script.extend([
                    "    assert game.state == GameState.BETTING",
                    f"    assert game.current_player.id == '{player_ids[0]}'  # BTN first",
                    "    actions = game.get_valid_actions('BTN')",
                    "    assert (PlayerAction.CALL, 10, 10) in actions",
                    "    game.player_action('BTN', PlayerAction.CALL, 10)",
                    "    game.player_action('SB', PlayerAction.CALL, 5)",
                    "    game.player_action('BB', PlayerAction.CHECK)",
                    "    assert game.betting.get_main_pot_amount() == 30",
                ])
                first_betting_round = False

        elif action_type == "deal":
            location = step["deal"]["location"]
            num_cards = sum(c["number"] for c in step["deal"]["cards"])
            if location == "player":
                script.extend([
                    "    assert game.state == GameState.DEALING",
                    "    for pid in {}:".format(player_ids),
                    f"        assert len(game.table.players[pid].hand.get_cards()) == {num_cards}",
                    f"    print(f'\\nStep {step_idx} - Player Hands:')",
                    "    for pid in {}:".format(player_ids),
                    f"        print(f'{{pid}}: {{[str(c) for c in game.table.players[pid].hand.get_cards()]}}')",
                ])
            elif location == "community":
                total_so_far = community_card_counts.get(step_idx, num_cards)  # Use cumulative total
                script.extend([
                    "    assert game.state == GameState.DEALING",
                    f"    assert len(game.table.community_cards['default']) == {total_so_far}",
                    f"    print(f'\\nStep {step_idx} - Community Cards:')",
                    "    print([str(c) for c in game.table.community_cards['default']])",
                ])

        elif action_type == "separate":
            total_cards = sum(c["number"] for c in step["separate"]["cards"])
            subsets = [c["hole_subset"] for c in step["separate"]["cards"]]
            subset_sizes = {c["hole_subset"]: c["number"] for c in step["separate"]["cards"]}
            script.extend([
                "    assert game.state == GameState.DRAWING",
                f"    assert game.current_player.id == '{action_order[0]}'  # Start with SB",
                "    actions = game.get_valid_actions(game.current_player.id)",
                f"    assert any(a[0] == PlayerAction.SEPARATE and a[1] == {total_cards} for a in actions)",
                "    for pid in {}:".format(action_order),  # Added colon here
                "        hand = game.table.players[pid].hand",
                f"        cards = hand.get_cards()[:{total_cards}]",
                "        game.player_action(pid, PlayerAction.SEPARATE, cards=cards)",
                *[f"        assert len(hand.get_subset('{subset}')) == {subset_sizes[subset]}  # {subset}" for subset in subsets],
                f"    print(f'\\nStep {step_idx} - Post-Separate Hands:')",
                "    for pid in {}:".format(action_order),  # Added colon here
                *[f"        print(f'{{pid}} - {subset}: {{[str(c) for c in game.table.players[pid].hand.get_subset(\"{subset}\")]}}')" for subset in subsets],
            ])

        elif action_type == "draw":
            draw_config = step["draw"]["cards"][0]
            min_num = draw_config.get("min_number", 0)
            max_num = draw_config["number"]
            num_to_discard = max(min_num, min(2, max_num))
            script.extend([
                "    assert game.state == GameState.DRAWING",
                f"    assert game.current_player.id == '{action_order[0]}'  # Start with SB",
                "    actions = game.get_valid_actions(game.current_player.id)",
                f"    assert any(a[0] == PlayerAction.DRAW and a[1] == {min_num} and a[2] == {max_num} for a in actions)",
                f"    for pid in {action_order}:",
                "        hand = game.table.players[pid].hand",
                "        initial_count = len(hand.get_cards())",
                f"        cards_to_discard = hand.get_cards()[:{num_to_discard}]",
                f"        game.player_action(pid, PlayerAction.DRAW, cards=cards_to_discard)",
                "        assert len(hand.get_cards()) == initial_count  # Hand size unchanged",
            ])

        elif action_type == "discard":
            discard_config = step["discard"]["cards"][0]
            num_to_discard = discard_config["number"]
            script.extend([
                "    assert game.state == GameState.DRAWING",
                f"    assert game.current_player.id == '{action_order[0]}'  # Start with SB",
                "    actions = game.get_valid_actions(game.current_player.id)",
                f"    assert any(a[0] == PlayerAction.DISCARD and a[1] == {num_to_discard} for a in actions)",
                f"    for pid in {action_order}:",
                "        hand = game.table.players[pid].hand",
                "        initial_count = len(hand.get_cards())",
                f"        cards_to_discard = hand.get_cards()[:{num_to_discard}]",
                f"        game.player_action(pid, PlayerAction.DISCARD, cards=cards_to_discard)",
                f"        assert len(hand.get_cards()) == initial_count - {num_to_discard}  # Hand size reduced by discards",
                f"    print(f'\\nStep {step_idx} - Post-Discard Hands:')",
                f"    for pid in {action_order}:",
                f"        print(f'{{pid}}: {{[str(c) for c in game.table.players[pid].hand.get_cards()]}}')",
            ])            

        elif action_type == "showdown":
            script.extend([
                "    assert game.state == GameState.COMPLETE",
                "    results = game.get_hand_results()",
                "    assert results.is_complete",
                "    assert results.total_pot > 0",
                "    assert len(results.hands) == 3",
                "    assert len(results.pots) >= 1",
                "    print('\\nShowdown Results (Human):')",
                "    print(results)",
                "    print('\\nShowdown Results (JSON):')",
                "    print(results.to_json())",
                "",
                "    # Check pot details",
                "    main_pot = results.pots[0]",
                "    assert main_pot.amount == results.total_pot  # TODO: Verify expected pot size",
                "    assert main_pot.pot_type == 'main'",
                "    assert not main_pot.split  # TODO: Adjust if split pots expected",
                "    assert len(main_pot.winners) == 1  # TODO: Adjust if multiple winners",
                "    assert main_pot.winners[0] in {}".format(player_ids),
                "    # TODO: Replace with expected winner, e.g., assert 'BTN' in main_pot.winners",
                "",
                "    # Check winning hand",
                "    winning_player = main_pot.winners[0]",
                "    winning_hand = results.hands[winning_player]",
                "    assert winning_hand[0].hand_name  # TODO: e.g., assert 'Pair' in winning_hand[0].hand_name",
                "    assert winning_hand[0].hand_description  # TODO: e.g., assert 'Pair of Sevens' in winning_hand[0].hand_description",
                "",
                "    # Check winning hands list",
                "    assert len(results.winning_hands) == 1  # TODO: Adjust if multiple winners",
                "    assert results.winning_hands[0].player_id == winning_player",
                "    # TODO: Replace with expected winner, e.g., assert results.winning_hands[0].player_id == 'BTN'",
            ])

    with open(output_file_path, 'w') as f:
        f.write("\n".join(script))

# Integrate into main
if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python generate_poker_test.py <input_json> <output_py> [--auto-update]")
        sys.exit(1)
    generate_test_script(sys.argv[1], sys.argv[2])
    if "--auto-update" in sys.argv:
        update_test_with_json(sys.argv[2])
