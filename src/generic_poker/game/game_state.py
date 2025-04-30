from enum import Enum

class GameState(Enum):
    """Possible states of the game."""
    WAITING = "waiting"  # Waiting for players
    DEALING = "dealing"  # Cards being dealt
    BETTING = "betting"  # Betting round in progress
    DRAWING = "drawing"  # Draw/discard (or other non-bet action with player interaction) in progress
    SHOWDOWN = "showdown"  # Final showdown
    COMPLETE = "complete"  # Hand complete

class PlayerAction(Enum):
    """Actions a player can take."""
    FOLD = "fold"
    CHECK = "check"
    CALL = "call"
    BET = "bet"
    RAISE = "raise"
    BRING_IN = "bring_in" 
    COMPLETE = "complete" # complete bring-in
    DISCARD = "discard" # simplified discard only
    DRAW = "draw" # really more general discard and then draw
    SEPARATE  = "separate"  # separate hand into subsets
    EXPOSE  = "expose"  # expose down cards (make face up)
    PASS = "pass"  # New player action
    DECLARE = "declare"  # New action

