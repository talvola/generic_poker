from dataclasses import dataclass
from typing import Optional

@dataclass
class ActionResult:
    """Result of a player action."""
    success: bool
    error: Optional[str] = None
    advance_step: bool = False
