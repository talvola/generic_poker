"""Game state view models for different player perspectives."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class GamePhase(Enum):
    """Game phases for poker hands."""

    WAITING = "waiting"
    DEALING = "dealing"
    PREFLOP = "preflop"
    FLOP = "flop"
    TURN = "turn"
    RIVER = "river"
    DRAWING = "drawing"
    DECLARING = "declaring"
    SHOWDOWN = "showdown"
    COMPLETE = "complete"


class ActionType(Enum):
    """Available player actions."""

    FOLD = "fold"
    CHECK = "check"
    CALL = "call"
    BET = "bet"
    RAISE = "raise"
    ALL_IN = "all_in"
    BRING_IN = "bring_in"
    COMPLETE = "complete"
    DRAW = "draw"
    DISCARD = "discard"
    PASS = "pass"
    EXPOSE = "expose"
    SEPARATE = "separate"
    DECLARE = "declare"
    CHOOSE = "choose"


@dataclass
class ActionOption:
    """Represents an available action for a player."""

    action_type: ActionType
    min_amount: int = 0
    max_amount: int = 0
    is_enabled: bool = True
    display_text: str = ""
    metadata: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        result = {
            "action_type": self.action_type.value,
            "min_amount": self.min_amount,
            "max_amount": self.max_amount,
            "is_enabled": self.is_enabled,
            "display_text": self.display_text,
        }
        if self.metadata is not None:
            result["metadata"] = self.metadata
        return result


@dataclass
class PotInfo:
    """Information about the current pot."""

    main_pot: int
    side_pots: list[dict[str, Any]] = field(default_factory=list)
    total_pot: int = 0
    current_bet: int = 0

    def __post_init__(self):
        """Calculate total pot after initialization."""
        self.total_pot = self.main_pot + sum(pot["amount"] for pot in self.side_pots)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "main_pot": self.main_pot,
            "side_pots": self.side_pots,
            "total_pot": self.total_pot,
            "current_bet": self.current_bet,
        }


@dataclass
class PlayerView:
    """Player information from a specific perspective."""

    user_id: str
    username: str
    position: str
    seat_number: int
    chip_stack: int
    current_bet: int
    cards: list[str] = field(default_factory=list)  # Hidden for other players
    card_count: int = 0  # Number of cards player has (for showing card backs)
    is_active: bool = True
    is_current_player: bool = False
    is_bot: bool = False
    is_connected: bool = True
    is_all_in: bool = False
    has_folded: bool = False
    last_action: str | None = None
    time_to_act: int | None = None  # Seconds remaining to act
    card_subsets: dict[str, list[str]] | None = None  # Named card subsets (for separate games)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        result = {
            "user_id": self.user_id,
            "username": self.username,
            "position": self.position,
            "seat_number": self.seat_number,
            "chip_stack": self.chip_stack,
            "current_bet": self.current_bet,
            "cards": self.cards,
            "card_count": self.card_count,
            "is_active": self.is_active,
            "is_current_player": self.is_current_player,
            "is_bot": self.is_bot,
            "is_connected": self.is_connected,
            "is_all_in": self.is_all_in,
            "has_folded": self.has_folded,
            "last_action": self.last_action,
            "time_to_act": self.time_to_act,
        }
        if self.card_subsets is not None:
            result["card_subsets"] = self.card_subsets
        return result


@dataclass
class GameStateView:
    """Game state from a specific player's perspective."""

    table_id: str
    session_id: str
    viewer_id: str  # ID of the player/spectator viewing this state
    players: list[PlayerView]
    community_cards: dict[str, list[str]] = field(default_factory=dict)
    pot_info: PotInfo = field(default_factory=lambda: PotInfo(0))
    current_player: str | None = None
    valid_actions: list[ActionOption] = field(default_factory=list)
    game_phase: GamePhase = GamePhase.WAITING
    hand_number: int = 0
    is_spectator: bool = False
    dealer_position: int = 0
    small_blind_position: int = 0
    big_blind_position: int = 0
    timestamp: datetime = field(default_factory=datetime.utcnow)

    # Additional game information
    table_info: dict[str, Any] = field(default_factory=dict)
    hand_history: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        # Find the viewer's username from players list
        viewer_username = None
        for player in self.players:
            if player.user_id == self.viewer_id:
                viewer_username = player.username
                break

        return {
            "table_id": self.table_id,
            "session_id": self.session_id,
            "viewer_id": self.viewer_id,
            "current_user": {"id": self.viewer_id, "username": viewer_username},
            "players": [player.to_dict() for player in self.players],
            "community_cards": self.community_cards,
            "pot_info": self.pot_info.to_dict(),
            "current_player": self.current_player,
            "valid_actions": [action.to_dict() for action in self.valid_actions],
            "game_phase": self.game_phase.value,
            "hand_number": self.hand_number,
            "is_spectator": self.is_spectator,
            "dealer_position": self.dealer_position,
            "small_blind_position": self.small_blind_position,
            "big_blind_position": self.big_blind_position,
            "timestamp": self.timestamp.isoformat(),
            "table_info": self.table_info,
            "hand_history": self.hand_history,
        }

    def get_player_by_id(self, user_id: str) -> PlayerView | None:
        """Get a player by their user ID."""
        for player in self.players:
            if player.user_id == user_id:
                return player
        return None

    def get_current_player(self) -> PlayerView | None:
        """Get the current player to act."""
        if self.current_player:
            return self.get_player_by_id(self.current_player)
        return None

    def get_active_players(self) -> list[PlayerView]:
        """Get all active players (not folded, not all-in)."""
        return [p for p in self.players if p.is_active and not p.has_folded and not p.is_all_in]

    def get_connected_players(self) -> list[PlayerView]:
        """Get all connected players."""
        return [p for p in self.players if p.is_connected]


@dataclass
class GameStateUpdate:
    """Represents a change in game state."""

    table_id: str
    session_id: str
    update_type: str
    data: dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.utcnow)
    affected_players: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "table_id": self.table_id,
            "session_id": self.session_id,
            "update_type": self.update_type,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
            "affected_players": self.affected_players,
        }


@dataclass
class HandResult:
    """Result of a completed poker hand."""

    hand_number: int
    table_id: str
    session_id: str
    winners: list[dict[str, Any]]  # List of winner info with amounts
    pot_distribution: dict[str, int]  # user_id -> amount won
    final_board: list[str]  # Community cards
    player_hands: dict[str, dict[str, Any]]  # user_id -> hand info
    hand_summary: str
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "hand_number": self.hand_number,
            "table_id": self.table_id,
            "session_id": self.session_id,
            "winners": self.winners,
            "pot_distribution": self.pot_distribution,
            "final_board": self.final_board,
            "player_hands": self.player_hands,
            "hand_summary": self.hand_summary,
            "timestamp": self.timestamp.isoformat(),
        }
