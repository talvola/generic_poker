"""Game configuration loading and parsing."""
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Dict, Optional, Any, Union
import json
from pathlib import Path

from generic_poker.core.card import Card, Rank, Suit, Visibility
from generic_poker.core.deck import DeckType

import logging 
logger = logging.getLogger(__name__)

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
    DECLARE = auto()
    SHOWDOWN = auto()
    GROUPED = auto()  # New type for grouped actions
    ROLL_DIE = auto()
    CHOOSE = auto()  # New action type for player choices
    REPLACE_COMMUNITY = auto()  # New action type for community card replacement


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
    style: Optional[str] = None
    rule: Optional[str] = None
    bringInEval: Optional[str] = None
    conditionalOrders: Optional[List[Dict[str, Any]]] = None
    default: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        """Validate that we have either a simple config or conditional config."""
        if self.conditionalOrders is not None:
            # Conditional configuration
            if self.default is None:
                raise ValueError("Conditional forced bets must have a default configuration")
            if self.style is not None or self.rule is not None or self.bringInEval is not None:
                raise ValueError("Cannot specify both simple and conditional forced bet configurations")
        else:
            # Simple configuration
            if self.style is None:
                self.style = "blinds"  # Default style

@dataclass
class BettingOrder:
    """Configuration for determining the starting player of betting rounds."""
    initial: str
    subsequent: Union[str, Dict[str, Any]]  # Now supports both string and conditional object

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
    conditional_state: Optional[Dict[str, Any]] = None  # Add conditional_state field with default None

@dataclass
class ProtectionOption:
    cost: str  # Named bet amount (e.g., "protection_fee")
    timing: str  # "pre_deal" or "post_deal"
    benefit: str  # "flip_face_up" or other benefits
    prompt: Optional[str] = None

@dataclass
class ShowdownConfig:
    """Configuration for final showdown."""
    order: str
    starting_from: str
    cards_required: str
    declaration_mode: str
    best_hand: List[Dict[str, Any]]
    conditionalBestHands: List[Dict[str, Any]] = field(default_factory=list)  # Added for conditional hands
    defaultBestHand: List[Dict[str, Any]] = field(default_factory=list)  # Added for fallback
    globalDefaultAction: Dict[str, Any] = field(default_factory=dict)
    defaultActions: List[Dict[str, Any]] = field(default_factory=list)
    classification_priority: List[Dict[str, Any]] = field(default_factory=list)

@dataclass
class GameRules:
    """Complete rules for a poker variant."""
    game: str
    min_players: int
    max_players: int
    deck_type: str
    deck_size: int
    betting_structures: List[BettingStructure]
    forced_bets: ForcedBets
    betting_order: BettingOrder
    gameplay: List[GameStep]
    showdown: ShowdownConfig
    named_bets: Dict[str, int] = field(default_factory=dict)

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
    def load_forced_bets_from_json(cls, data: Dict[str, Any]) -> ForcedBets:
        """Load forced bets configuration from JSON data."""
        forced_bets_data = data.get('forcedBets', {})
        
        if not forced_bets_data:
            # No forced bets specified, use default
            return ForcedBets(style="blinds")
        
        # Check if this is a conditional configuration
        if 'conditionalOrders' in forced_bets_data:
            # Conditional forced bets
            conditional_orders = forced_bets_data.get('conditionalOrders', [])
            default_config = forced_bets_data.get('default', {})
            
            # Validate conditional orders
            for i, cond_order in enumerate(conditional_orders):
                if 'condition' not in cond_order or 'forcedBet' not in cond_order:
                    logger.warning(f"Invalid conditional forced bet order at index {i}, missing condition or forcedBet")
                    continue
                    
                # Validate the forcedBet configuration
                forced_bet = cond_order['forcedBet']
                style = forced_bet.get('style')
                if style not in ["blinds", "bring-in", "antes_only"]:
                    logger.warning(f"Invalid forcedBet style '{style}' in conditional order {i}, should be one of: blinds, bring-in, antes_only")
                    
                # Validate rule is provided for bring-in style
                if style == "bring-in" and not forced_bet.get('rule'):
                    logger.warning(f"Missing 'rule' for bring-in style in conditional order {i}, defaulting to 'low card'")
                    cond_order['forcedBet']['rule'] = "low card"
            
            # Validate default configuration
            default_style = default_config.get('style')
            if default_style not in ["blinds", "bring-in", "antes_only"]:
                logger.warning(f"Invalid default forcedBet style '{default_style}', defaulting to 'blinds'")
                default_config['style'] = "blinds"
                
            if default_style == "bring-in" and not default_config.get('rule'):
                logger.warning("Missing 'rule' for bring-in style in default forced bet, defaulting to 'low card'")
                default_config['rule'] = "low card"
            
            return ForcedBets(
                conditionalOrders=conditional_orders,
                default=default_config
            )
        
        else:
            # Simple forced bets configuration
            style = forced_bets_data.get('style')
            if style not in ["blinds", "bring-in", "antes_only"]:
                logger.warning(f"Invalid forcedBets style '{style}', defaulting to 'blinds'")
                style = "blinds"
                
            forced_bets = ForcedBets(
                style=style,
                rule=forced_bets_data.get('rule'),
                bringInEval=forced_bets_data.get('bringInEval')
            )
            
            # Validate rule is provided for bring-in style
            if style == "bring-in" and not forced_bets.rule:
                logger.warning("Missing 'rule' for bring-in style, defaulting to 'low card'")
                forced_bets.rule = "low card"
                
            return forced_bets    
        
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

        forced_bets = cls.load_forced_bets_from_json(data)
            
        # Parse betting order - infer defaults from forcedBets if not specified
        betting_order_data = data.get('bettingOrder', {})
        if betting_order_data:
            initial = betting_order_data.get('initial')
            subsequent = betting_order_data.get('subsequent')

            # Validate initial
            if initial not in ["after_big_blind", "bring_in", "dealer", "high_hand"]:
                logger.warning(f"Invalid bettingOrder.initial '{initial}', defaulting based on forcedBets")
                initial = None

            # Validate subsequent - now handles both string and conditional object
            if isinstance(subsequent, str):
                if subsequent not in ["high_hand", "dealer", "after_big_blind", "bring_in", "last_actor"]:
                    logger.warning(f"Invalid bettingOrder.subsequent '{subsequent}', defaulting based on forcedBets")
                    subsequent = None
            elif isinstance(subsequent, dict):
                # Validate conditional subsequent structure
                if "conditionalOrders" not in subsequent or "default" not in subsequent:
                    logger.warning("Invalid conditional betting order structure, defaulting based on forcedBets")
                    subsequent = None
                else:
                    # Validate each conditional order
                    valid_orders = ["high_hand", "dealer", "after_big_blind", "bring_in", "last_actor"]
                    for cond_order in subsequent["conditionalOrders"]:
                        if "condition" not in cond_order or "order" not in cond_order:
                            logger.warning("Invalid conditional order structure, defaulting based on forcedBets")
                            subsequent = None
                            break
                        if cond_order["order"] not in valid_orders:
                            logger.warning(f"Invalid conditional order '{cond_order['order']}', defaulting based on forcedBets")
                            subsequent = None
                            break
                    
                    # Validate default order
                    if subsequent and subsequent["default"] not in valid_orders:
                        logger.warning(f"Invalid default order '{subsequent['default']}', defaulting based on forcedBets")
                        subsequent = None
            else:
                logger.warning("Invalid bettingOrder.subsequent type, defaulting based on forcedBets")
                subsequent = None                        
        else:
            initial = None
            subsequent = None

        # Set defaults based on forcedBets - need to handle conditional case
        if forced_bets.conditionalOrders is not None:
            # For conditional forced bets, use the default configuration for inference
            default_style = forced_bets.default.get('style', 'blinds')
        else:
            # Simple forced bets
            default_style = forced_bets.style

        if default_style == "blinds":
            default_initial = "after_big_blind"
            default_subsequent = "dealer"
        elif default_style == "bring-in":
            default_initial = "bring_in"
            default_subsequent = "high_hand"
        elif default_style == "antes_only":
            default_initial = "dealer"
            default_subsequent = "high_hand"
        else:  # Fallback for invalid styles
            default_initial = "after_big_blind"
            default_subsequent = "dealer"

        betting_order = BettingOrder(
            initial=initial or default_initial,
            subsequent=subsequent or default_subsequent
        )

        # Parse gameplay steps
        gameplay = []
        for step in data['gamePlay']:
            # Extract conditional state (might be needed for any action type)
            conditional_state = step.get('conditional_state')
            
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
                    if key in ['name', 'conditional_state']:
                        continue
                    try:
                        # Handle special case for replaceCommunity -> REPLACE_COMMUNITY
                        if key == "replaceCommunity":
                            action_type = GameActionType.REPLACE_COMMUNITY
                        else:
                            action_type = GameActionType[key.upper()]
                        action_config = step[key]
                        break
                    except KeyError:
                        continue
                if action_type is None:
                    raise ValueError(f"Invalid game step: {step}")
            
            # Create the GameStep with the conditional_state if it exists
            game_step = GameStep(
                name=step['name'],
                action_type=action_type,
                action_config=action_config
            )
            
            # Add conditional_state as an attribute if it exists
            if conditional_state:
                game_step.conditional_state = conditional_state
                
            gameplay.append(game_step)

        # Parse showdown config
        showdown_data = data['showdown']
        showdown = ShowdownConfig(
            order=showdown_data['order'],
            starting_from=showdown_data['startingFrom'],
            cards_required=showdown_data['cardsRequired'],
            best_hand=showdown_data.get('bestHand', []),
            conditionalBestHands=showdown_data.get('conditionalBestHands', []),  # Add this line
            defaultBestHand=showdown_data.get('defaultBestHand', []),  # Add this line
            declaration_mode=showdown_data.get('declaration_mode', 'cards_speak'),
            globalDefaultAction=showdown_data.get('globalDefaultAction', {}),
            defaultActions=showdown_data.get('defaultActions', []),
            classification_priority=showdown_data.get('classification_priority', [])
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
            betting_order=betting_order,
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
        if self.deck_type not in DeckType.__members__.values():
            raise ValueError(f"Invalid deck type: {self.deck_type}")
        deck_sizes = {
            DeckType.STANDARD: 52,
            DeckType.SHORT_27_JA: 40,
            DeckType.SHORT_6A: 36,
            DeckType.SHORT_TA: 20
        }
        if self.deck_size != deck_sizes[DeckType(self.deck_type)]:
            raise ValueError(f"Invalid deck size {self.deck_size} for type {self.deck_type}")

        # Validate gameplay sequence
        self._validate_gameplay_sequence()

        # Validate conditional dealing
        for step in self.gameplay:
            if step.action_type == GameActionType.DEAL:
                config = step.action_config
                if "conditional_state" in config:
                    cond_state = config["conditional_state"]
                    if cond_state.get("type") == "flop_color_check":
                        if "color_check" not in cond_state:
                            raise ValueError("Missing 'color_check' in conditional_state")
                        color_check = cond_state["color_check"]
                        if "color" not in color_check or "min_count" not in color_check:
                            raise ValueError("color_check must specify 'color' and 'min_count'")        

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
                f"Game requires {total_dealt + community_dealt} cards but deck only has {self.deck_size}"
            )