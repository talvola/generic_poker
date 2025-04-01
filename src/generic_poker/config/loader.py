"""Game configuration loading and parsing."""
from dataclasses import dataclass
from enum import Enum, auto
from typing import List, Dict, Optional, Any, Union
import json
from pathlib import Path

from generic_poker.core.card import Card, Rank, Suit, Visibility


class BettingStructure(Enum):
    """Supported betting structures."""
    LIMIT = "Limit"
    NO_LIMIT = "No Limit"
    POT_LIMIT = "Pot Limit"


class GameActionType(Enum):
    """Types of actions that can occur in a game."""
    BET = auto()
    DEAL = auto()
    DRAW = auto()
    EXPOSE = auto()
    PASS = auto()
    SEPARATE = auto()
    DISCARD = auto()
    REMOVE = auto()
    SHOWDOWN = auto()
    GROUPED = auto()  # New type for grouped actions

@dataclass
class DealAction:
    """Configuration for dealing cards."""
    location: str  # 'player' or 'community'
    cards: List[Dict[str, Any]]  # number, state, subset(optional)

@dataclass
class BetAction:
    """Configuration for betting rounds."""
    type: str  # 'blinds', 'small', 'big', etc.

@dataclass
class ForcedBets:
    """Configuration for forced bets."""
    style: str
    rule: Optional[str] = None
    variation: Optional[str] = None
    bringInEval: Optional[str] = None

@dataclass
class ShowdownAction:
    """Configuration for showdown."""
    type: str


@dataclass
class GameStep:
    """A single step in the game sequence."""
    name: str
    action_type: GameActionType
    action_config: Union[Dict[str, Any], List[Dict[str, Any]]]  # Supports single or grouped actions

@dataclass
class ShowdownConfig:
    """Configuration for final showdown."""
    order: str
    starting_from: str
    cards_required: str
    best_hand: List[Dict[str, Any]]
    default_action: Dict[str, Any]

@dataclass
class GameRules:
    """Complete rules for a poker variant."""
    game: str
    min_players: int
    max_players: int
    deck_type: str
    deck_size: int
    betting_structures: List[BettingStructure]
    gameplay: List[GameStep]
    forced_bets: ForcedBets
    showdown: ShowdownConfig

    @classmethod
    def from_file(cls, filepath: Path) -> 'GameRules':
        """
        Load GameRules from a JSON file.
        
        Args:
            filepath: Path to JSON configuration file
            
        Returns:
            GameRules instance
        """
        with open(filepath, 'r') as f:
            return cls.from_json(f.read())

    @classmethod
    def from_json(cls, json_str: str) -> 'GameRules':
        """
        Create GameRules from JSON string.
        
        Args:
            json_str: JSON string defining game rules
            
        Returns:
            GameRules instance
            
        Raises:
            ValueError: If JSON is invalid or missing required fields
        """
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {e}")

        # Validate required top-level fields
        required_fields = {'game', 'players', 'deck', 'bettingStructures', 'gamePlay', 'showdown'}
        missing = required_fields - set(data.keys())
        if missing:
            raise ValueError(f"Missing required fields: {missing}")

        # Parse betting structures
        try:
            betting_structures = [BettingStructure(s) for s in data['bettingStructures']]
        except ValueError as e:
            raise ValueError(f"Invalid betting structure: {e}")

        # Parse forced bets - default to Blinds if nothing specified.
        forced_bets_data = data.get('forcedBets', {})
        if forced_bets_data:
            # see if variation exists - only use in Razz High now - for backward compatibility
            # in the future, we'll have two rules - one for the opening round, and one for 
            # subsequent rounds, which can default to the showdown evaluation (if there is only 
            # one specified)
            if 'variation' in forced_bets_data and forced_bets_data.get('rule') == 'low card al':
                rule = 'low card al rh'
            else:
                rule = forced_bets_data.get('rule')
            forced_bets = ForcedBets(
                style=forced_bets_data.get('style'),
                rule=rule,
                variation=forced_bets_data.get('variation'),
                bringInEval=forced_bets_data.get('bringInEval')
            )
        else:
            forced_bets = ForcedBets(
                style='blinds',
                rule=None,
                variation=None,
                bringInEval=None
            )  

        # Parse gameplay steps
        gameplay = []
        for step in data['gamePlay']:
            if "groupedActions" in step:
                # Handle grouped actions
                action_type = GameActionType.GROUPED
                action_config = step["groupedActions"]
                # Optional: Validate each action in the group
                for action in action_config:
                    if not any(key.lower() in action for key in GameActionType.__members__.keys() if key != "GROUPED"):
                        raise ValueError(f"Invalid action in groupedActions: {action}")
            else:
                # Handle single action
                action_type = None
                action_config = {}
                for key in step.keys():
                    if key == 'name':
                        continue
                    try:
                        action_type = GameActionType[key.upper()]
                        action_config = step[key]
                        break
                    except KeyError:
                        continue
                if action_type is None:
                    raise ValueError(f"Invalid game step: {step}")
                
            gameplay.append(GameStep(
                name=step['name'],
                action_type=action_type,
                action_config=action_config
            ))

        # Parse showdown config
        showdown_data = data['showdown']
        showdown = ShowdownConfig(
            order=showdown_data['order'],
            starting_from=showdown_data['startingFrom'],
            cards_required=showdown_data['cardsRequired'],
            best_hand=showdown_data['bestHand'],
            default_action=showdown_data.get('defaultAction', {})
        )

        rules = cls(
            game=data['game'],
            min_players=data['players']['min'],
            max_players=data['players']['max'],
            deck_type=data['deck']['type'],
            deck_size=data['deck']['cards'],
            betting_structures=betting_structures,
            gameplay=gameplay,
            forced_bets=forced_bets,
            showdown=showdown
        )
        
        # Validate the complete rules
        rules.validate()
        return rules

    def validate(self) -> None:
        """
        Validate the game rules are consistent and complete.
        
        Raises:
            ValueError: If rules are invalid
        """
        # Validate player counts
        if self.min_players < 2:
            raise ValueError("Minimum players must be at least 2")
        if self.max_players < self.min_players:
            raise ValueError("Maximum players must be >= minimum players")
            
        # Validate deck
        if self.deck_type not in ['standard', 'short_6a', 'short_ta']:
            raise ValueError(f"Invalid deck type: {self.deck_type}")
            
        # Map deck types to expected sizes
        deck_sizes = {
            'standard': 52,
            'short_6a': 36,
            'short_ta': 20
        }
        if self.deck_size != deck_sizes[self.deck_type]:
            raise ValueError(f"Invalid deck size {self.deck_size} for type {self.deck_type}")

        # Validate gameplay sequence
        self._validate_gameplay_sequence()

    def _validate_gameplay_sequence(self) -> None:
        """
        Validate that the gameplay sequence is valid.
        
        Raises:
            ValueError: If sequence is invalid
        """
        # Track cards dealt for validation
        total_dealt = 0
        community_dealt = 0
        
        for step in self.gameplay:
            if step.action_type == GameActionType.DEAL:
                config = step.action_config
                for card_info in config['cards']:
                    cards_in_step = card_info['number']
                    if config['location'] == 'community':
                        community_dealt += cards_in_step
                    else:
                        total_dealt += cards_in_step * self.max_players
                        
        # Verify we don't deal more cards than in deck
        if total_dealt + community_dealt > self.deck_size:
            raise ValueError(
                f"Game requires {total_dealt} cards but deck only has {self.deck_size}"
            )