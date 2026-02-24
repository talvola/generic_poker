"""Loader for mixed game rotation configs (HORSE, 8-Game Mix, etc.)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class MixedGameVariant:
    """One variant in a rotation sequence."""

    variant: str  # Config filename stem, e.g. "hold_em"
    betting_structure: str  # "Limit", "No Limit", "Pot Limit"
    letter: str = ""  # Display letter, e.g. "H" for HORSE


@dataclass
class MixedGameConfig:
    """Configuration for a mixed game rotation."""

    name: str  # Config filename stem, e.g. "horse"
    display_name: str  # Human-readable, e.g. "HORSE"
    category: str  # Always "Mixed"
    rotation: list[MixedGameVariant]
    rotation_type: str  # "orbit" = rotate after every dealer orbit
    min_players: int
    max_players: int
    betting_structures: list[str] = field(default_factory=lambda: ["Limit"])

    @classmethod
    def from_file(cls, filepath: Path) -> MixedGameConfig:
        """Load a mixed game config from a JSON file."""
        with open(filepath) as f:
            data = json.load(f)
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict) -> MixedGameConfig:
        """Parse a mixed game config from a dict."""
        rotation = [
            MixedGameVariant(
                variant=v["variant"],
                betting_structure=v["bettingStructure"],
                letter=v.get("letter", ""),
            )
            for v in data["rotation"]
        ]

        return cls(
            name=data["name"],
            display_name=data["displayName"],
            category=data.get("category", "Mixed"),
            rotation=rotation,
            rotation_type=data.get("rotationType", "orbit"),
            min_players=data.get("minPlayers", 2),
            max_players=data.get("maxPlayers", 9),
            betting_structures=data.get("bettingStructures", ["Limit"]),
        )
