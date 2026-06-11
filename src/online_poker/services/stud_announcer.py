"""Stud street chat announcements (BACKLOG 8.4).

When a new betting street begins in a stud (bring-in) game, players need to
know who is showing what on board and whose action it is. This builds a compact
chat line, e.g.::

    4th street — Alice: K♠ 9♦ | Bob: A♥ 2♣ · action on Bob

The street label is derived from the betting round's position in the config
(stateless), since stud configs name their betting steps inconsistently. The
message builder is a pure function over the engine ``Game`` so it can be
unit-tested without a WebSocket. The announce-once-per-street bookkeeping lives
in the WebSocketManager.
"""

from generic_poker.config.loader import GameActionType
from generic_poker.core.card import Visibility
from generic_poker.game.game_state import GameState

_SUIT_SYMBOLS = {"s": "♠", "h": "♥", "d": "♦", "c": "♣"}

# Betting in stud begins on 3rd street, so the Nth voluntary betting round
# (0-indexed) is street N+3.
_STREET_ORDINALS = {0: "3rd", 1: "4th", 2: "5th", 3: "6th", 4: "7th"}


def format_card(card) -> str:
    """Render a card with a Unicode suit symbol: ``Ah`` -> ``A♥``."""
    s = str(card)
    if len(s) == 2:
        return s[0] + _SUIT_SYMBOLS.get(s[1].lower(), s[1])
    return s


def is_stud_game(game) -> bool:
    """True if this variant uses bring-in (stud-style) forced bets."""
    fb = game.rules.forced_bets
    return bool(fb and fb.style == "bring-in")


def _voluntary_bet_steps(game) -> list[int]:
    """Indexes of the voluntary betting rounds (small/big bets) in gameplay."""
    steps = []
    for i, step in enumerate(game.rules.gameplay):
        if step.action_type == GameActionType.BET and isinstance(step.action_config, dict):
            if step.action_config.get("type") in ("small", "big"):
                steps.append(i)
    return steps


def _street_label(game) -> str | None:
    """Label for the current betting street, or None if not on a betting round."""
    bet_steps = _voluntary_bet_steps(game)
    if game.current_step not in bet_steps:
        return None
    ordinal = bet_steps.index(game.current_step)
    return _STREET_ORDINALS.get(ordinal, f"{ordinal + 3}th") + " street"


def _up_cards(player) -> list[str]:
    return [format_card(c) for c in player.hand.cards if c.visibility == Visibility.FACE_UP]


def build_street_announcement(game) -> str | None:
    """Build the chat line for the current stud betting street, or None.

    Returns None when the game is not a stud game, is not currently waiting for
    a player on a voluntary betting round, or no players are showing up cards
    (nothing useful to announce).
    """
    if not is_stud_game(game):
        return None
    if game.state != GameState.BETTING or game.current_player is None:
        return None

    label = _street_label(game)
    if label is None:
        return None

    shows = []
    for player in game.table.get_position_order(include_inactive=False):
        ups = _up_cards(player)
        if ups:
            shows.append(f"{player.name}: {' '.join(ups)}")

    if not shows:
        return None

    board = " | ".join(shows)
    return f"{label} — {board} · action on {game.current_player.name}"
