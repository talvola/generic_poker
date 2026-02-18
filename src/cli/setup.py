import json
from pathlib import Path

from generic_poker.config.loader import BettingStructure, GameRules
from generic_poker.game.game import Game

# Project root directory (assuming this file is in src/interactive/)
PROJECT_ROOT = Path(__file__).parents[2]  # Up two levels from src/interactive/ to ~/generic_poker/
CONFIG_DIR = PROJECT_ROOT / "data" / "game_configs"


def get_game_variant() -> GameRules:
    """Prompt user to select a poker variant from all available game configs."""
    # Find all JSON files in data/game_configs/
    game_files = sorted(CONFIG_DIR.glob("*.json"), key=lambda p: p.stem.lower())
    if not game_files:
        raise FileNotFoundError("No game configuration files found in data/game_configs/")

    # Load game rules and use the 'game' field for display
    game_options = {}
    for i, game_file in enumerate(game_files, 1):
        try:
            rules = GameRules.from_file(game_file)
            game_name = rules.game  # Use the 'game' field from GameRules
        except (OSError, json.JSONDecodeError, ValueError) as e:
            # Fallback to filename if loading fails (e.g., invalid JSON or missing required fields)
            game_name = game_file.stem.replace("_", " ").title()
            print(f"Warning: Could not load {game_file.name} ({e}), using fallback name")
        game_options[str(i)] = (game_name, game_file)

    # Display available games
    print("Select a poker variant:")
    for num, (name, _) in game_options.items():
        print(f"{num}: {name}")

    # Get user selection
    while True:
        choice = input(f"Enter number (1-{len(game_files)}): ").strip()
        if choice in game_options:
            _, selected_file = game_options[choice]
            with open(selected_file) as f:
                return GameRules.from_json(f.read())
        print("Invalid choice, try again.")


def get_betting_config(rules: GameRules) -> tuple[BettingStructure, dict]:
    """Prompt user for betting structure and stakes with defaults."""
    if not rules.betting_structures:
        raise ValueError(f"No betting structures defined for {rules.game}")

    structure_options = {str(i + 1): bs for i, bs in enumerate(rules.betting_structures)}
    print("Select betting structure:")
    for num, structure in structure_options.items():
        print(f"{num}: {structure.value}")

    while True:
        choice = input(f"Enter number (1-{len(structure_options)}): ").strip()
        if choice in structure_options:
            structure = structure_options[choice]
            break
        print("Invalid choice, try again.")

    stakes = {}
    if structure == BettingStructure.LIMIT:
        small_bet = input("Enter small bet (e.g., 4 for $4/$8) [default: 10]: ").strip()
        stakes["small_bet"] = int(small_bet) if small_bet else 10
        big_bet = input("Enter big bet (e.g., 8 for $4/$8) [default: 20]: ").strip()
        stakes["big_bet"] = int(big_bet) if big_bet else 20
    else:  # NO_LIMIT or POT_LIMIT
        small_blind = input("Enter small blind (e.g., 1 for $1/$3) [default: 1]: ").strip()
        stakes["small_blind"] = int(small_blind) if small_blind else 1
        big_blind = input("Enter big blind (e.g., 3 for $1/$3) [default: 3]: ").strip()
        stakes["big_blind"] = int(big_blind) if big_blind else 3

    if rules.forced_bets.style == "bring-in":
        ante = input("Enter ante amount [default: 1]: ").strip()
        stakes["ante"] = int(ante) if ante else 1
        bring_in = input("Enter bring-in amount [default: 3]: ").strip()
        stakes["bring_in"] = int(bring_in) if bring_in else 3

    min_buyin = input("Enter minimum buy-in [default: 200]: ").strip()
    stakes["min_buyin"] = int(min_buyin) if min_buyin else 200
    max_buyin = input("Enter maximum buy-in [default: 1000]: ").strip()
    stakes["max_buyin"] = int(max_buyin) if max_buyin else 1000
    return structure, stakes


def setup_players(rules: GameRules) -> list:
    """Prompt user for number of players and their details with defaults."""
    max_players = rules.max_players or 10
    while True:
        num_input = input(f"Enter number of players (2-{max_players}) [default: 3]: ").strip()
        num_players = int(num_input) if num_input else 3
        try:
            if 2 <= num_players <= max_players:
                break
            print(f"Number must be between 2 and {max_players}.")
        except ValueError:
            print("Invalid input, enter a number.")

    players = []
    for i in range(num_players):
        default_name = f"Player {i + 1}"
        name = input(f"Enter name for Player {i + 1} [default: {default_name}]: ").strip() or default_name
        stack_input = input(f"Enter stack for {name} [default: 500]: ").strip()
        stack = int(stack_input) if stack_input else 500
        if stack <= 0:
            print("Stack must be positive, using default 500.")
            stack = 500
        players.append((f"p{i + 1}", name, stack))
    return players


def setup_game() -> Game:
    """Set up a new game based on user input."""
    rules = get_game_variant()
    structure, stakes = get_betting_config(rules)
    players = setup_players(rules)

    game = Game(
        rules=rules,
        structure=structure,
        auto_progress=False,  # Manual control for interactive play
        **stakes,
    )
    for pid, name, stack in players:
        game.add_player(pid, name, stack)
    return game
