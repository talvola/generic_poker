"""Table configuration dataclass for poker tables."""

from dataclasses import dataclass
from typing import Any

# Import the existing BettingStructure from the generic poker module
from generic_poker.game.betting import BettingStructure


@dataclass
class TableConfig:
    """Configuration for creating a poker table."""

    # Basic table information
    name: str
    variant: str
    betting_structure: BettingStructure
    stakes: dict[str, int]
    max_players: int

    # Privacy and access settings
    is_private: bool = False
    password: str | None = None
    allow_bots: bool = False

    # Optional settings with defaults
    auto_start: bool = True
    timeout_minutes: int = 30

    def __post_init__(self):
        """Validate configuration after initialization."""
        self.validate()

    def validate(self) -> None:
        """Validate the table configuration.

        Raises:
            ValueError: If configuration is invalid
        """
        # Validate name
        if not self.name or not self.name.strip():
            raise ValueError("Table name cannot be empty")

        if len(self.name.strip()) > 100:
            raise ValueError("Table name cannot exceed 100 characters")

        # Validate variant
        if not self.variant or not self.variant.strip():
            raise ValueError("Poker variant must be specified")

        # Validate betting structure
        if not isinstance(self.betting_structure, BettingStructure):
            raise ValueError(f"Invalid betting structure: {self.betting_structure}")

        # Validate max players
        if not isinstance(self.max_players, int) or self.max_players < 2 or self.max_players > 9:
            raise ValueError("Maximum players must be between 2 and 9")

        # Validate stakes
        if not isinstance(self.stakes, dict) or not self.stakes:
            raise ValueError("Stakes must be a non-empty dictionary")

        # Validate stakes values are non-negative integers
        for key, value in self.stakes.items():
            if not isinstance(value, int) or value < 0:
                raise ValueError(f"Stake '{key}' must be a non-negative integer, got {value}")

            # Special validation for key stakes that must be positive
            if key in ["small_blind", "big_blind", "small_bet", "big_bet"] and value <= 0:
                raise ValueError(f"Stake '{key}' must be positive, got {value}")

        # Validate stakes structure based on betting structure
        self._validate_stakes_structure()

        # Validate timeout
        if not isinstance(self.timeout_minutes, int) or self.timeout_minutes < 1:
            raise ValueError("Timeout must be a positive integer (minutes)")

    def _validate_stakes_structure(self) -> None:
        """Validate stakes structure based on betting structure."""
        if self.betting_structure in [BettingStructure.NO_LIMIT, BettingStructure.POT_LIMIT]:
            # No-Limit and Pot-Limit require blinds
            required_keys = {"small_blind", "big_blind"}
            if not required_keys.issubset(self.stakes.keys()):
                raise ValueError(f"No-Limit and Pot-Limit games require stakes: {required_keys}")

            # Validate blind relationship
            if self.stakes["big_blind"] <= self.stakes["small_blind"]:
                raise ValueError("Big blind must be greater than small blind")

        elif self.betting_structure == BettingStructure.LIMIT:
            # Limit games require small_bet and big_bet
            required_keys = {"small_bet", "big_bet"}
            if not required_keys.issubset(self.stakes.keys()):
                raise ValueError(f"Limit games require stakes: {required_keys}")

            # Validate bet relationship
            if self.stakes["big_bet"] <= self.stakes["small_bet"]:
                raise ValueError("Big bet must be greater than small bet")

    def get_minimum_buyin(self) -> int:
        """Calculate minimum buy-in based on stakes and betting structure."""
        if self.betting_structure in [BettingStructure.NO_LIMIT, BettingStructure.POT_LIMIT]:
            # 20 big blinds minimum for NL/PL
            return self.stakes.get("big_blind", 2) * 20
        else:
            # 10 big bets for limit games
            return self.stakes.get("big_bet", 4) * 10

    def get_maximum_buyin(self) -> int:
        """Calculate maximum buy-in based on stakes and betting structure."""
        if self.betting_structure in [BettingStructure.NO_LIMIT, BettingStructure.POT_LIMIT]:
            # 200 big blinds maximum for NL/PL
            return self.stakes.get("big_blind", 2) * 200
        else:
            # 50 big bets for limit games
            return self.stakes.get("big_bet", 4) * 50

    def to_game_params(self) -> dict[str, Any]:
        """Convert table config to parameters for Game class constructor.

        Returns:
            Dictionary of parameters that can be passed to Game constructor
        """
        params = {
            "structure": self.betting_structure,
            "min_buyin": self.get_minimum_buyin(),
            "max_buyin": self.get_maximum_buyin(),
            "auto_progress": self.auto_start,
        }

        # Add betting structure specific parameters
        if self.betting_structure == BettingStructure.LIMIT:
            params.update(
                {
                    "small_bet": self.stakes.get("small_bet"),
                    "big_bet": self.stakes.get("big_bet"),
                    "ante": self.stakes.get("ante", 0),
                    "bring_in": self.stakes.get("bring_in"),
                }
            )
        else:  # NO_LIMIT or POT_LIMIT
            params.update(
                {
                    "small_blind": self.stakes.get("small_blind"),
                    "big_blind": self.stakes.get("big_blind"),
                    "ante": self.stakes.get("ante", 0),
                }
            )

        return params

    def to_dict(self) -> dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            "name": self.name,
            "variant": self.variant,
            "betting_structure": self.betting_structure.value,
            "stakes": self.stakes,
            "max_players": self.max_players,
            "is_private": self.is_private,
            "allow_bots": self.allow_bots,
            "auto_start": self.auto_start,
            "timeout_minutes": self.timeout_minutes,
            "minimum_buyin": self.get_minimum_buyin(),
            "maximum_buyin": self.get_maximum_buyin(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TableConfig":
        """Create TableConfig from dictionary."""
        # Convert betting structure string back to enum
        betting_structure = BettingStructure(data["betting_structure"])

        return cls(
            name=data["name"],
            variant=data["variant"],
            betting_structure=betting_structure,
            stakes=data["stakes"],
            max_players=data["max_players"],
            is_private=data.get("is_private", False),
            password=data.get("password"),
            allow_bots=data.get("allow_bots", False),
            auto_start=data.get("auto_start", True),
            timeout_minutes=data.get("timeout_minutes", 30),
        )

    def __str__(self) -> str:
        """String representation of table configuration."""
        return f"TableConfig(name='{self.name}', variant='{self.variant}', structure={self.betting_structure.value})"
