from .setup import setup_game
from .cli import run_game

if __name__ == "__main__":
    game = setup_game()
    run_game(game)