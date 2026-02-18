from dataclasses import dataclass


@dataclass
class ActionResult:
    """Result of a player action."""

    success: bool
    error: str | None = None
    advance_step: bool = False
