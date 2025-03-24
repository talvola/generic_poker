"""Module for determining first-to-act in stud poker games."""
from enum import Enum
from typing import List, Dict, Optional, Tuple, Any
import logging

from generic_poker.core.card import Card, Visibility
from generic_poker.game.table import Player
from generic_poker.evaluation.evaluator import evaluator, EvaluationType

logger = logging.getLogger(__name__)

class CardRule(Enum):
    """Types of card rules for bring-in determination."""
    LOW_CARD = 'low card'          # Standard 7-Card Stud (Ace high, 2 low)
    LOW_CARD_AL = 'low card al'    # Unusual - low card bring-in (Ace low)
    LOW_CARD_AL_RH = 'low card al rh'  # Razz High - low card bring-in (Ace low), other rounds use Razz High evaluation
    HIGH_CARD = 'high card'        # For A-5 low games like Razz (King high, Ace low)
    HIGH_CARD_AH = 'high card ah'  # For 2-7 low games (Ace high, 2 low)


class BringInDeterminator:
    """
    Determines which player acts first in stud poker games based on exposed cards.
    
    This class handles the complex rules for first-to-act determination in stud poker,
    which varies based on the game variant, the number of exposed cards, and
    the specific card ranking rules in effect.
    """
    
    # Mapping of number of exposed cards and rules to evaluation types
    # Razz High breaks the pattern.    In the future, probalby want to 
    # explicitly call out in the game rules two sets of bring-in rules
    # instead of trying to derive here
    # EVAL_MAPPINGS = {
    #     1: {  # First round - one card showing
    #         CardRule.LOW_CARD: EvaluationType.ONE_CARD_LOW,          # Lowest card by high ranking
    #         CardRule.LOW_CARD_AL: EvaluationType.ONE_CARD_LOW_AL,     # Lowest card with A low
    #         CardRule.LOW_CARD_AL_RH: EvaluationType.ONE_CARD_LOW_AL,     # Lowest card with A low (Razz High)
    #         CardRule.HIGH_CARD: EvaluationType.ONE_CARD_HIGH,       # Highest card with A low
    #         CardRule.HIGH_CARD_AH: EvaluationType.ONE_CARD_HIGH_AH       # Highest card by high ranking
    #     },
    #     2: {  # Two cards showing
    #         CardRule.LOW_CARD: EvaluationType.TWO_CARD_HIGH,          # Highest hand by high ranking
    #         CardRule.LOW_CARD_AL: EvaluationType.TWO_CARD_HIGH_AL,     # Highest hand by A5 low ranking
    #         CardRule.LOW_CARD_AL_RH: EvaluationType.TWO_CARD_HIGH_AL_RH,     # Highest hand by A5 low ranking (Razz High)
    #         CardRule.HIGH_CARD: EvaluationType.TWO_CARD_LOW,       # Lowest hand by A5 low ranking
    #         CardRule.HIGH_CARD_AH: EvaluationType.TWO_CARD_LOW_AH     # Lowest hand by 2-7 ranking
    #     },
    #     3: {  # Three cards showing
    #         CardRule.LOW_CARD: EvaluationType.THREE_CARD_HIGH,
    #         CardRule.LOW_CARD_AL: EvaluationType.THREE_CARD_HIGH_AL,
    #         CardRule.LOW_CARD_AL_RH: EvaluationType.THREE_CARD_HIGH_AL_RH,
    #         CardRule.HIGH_CARD: EvaluationType.THREE_CARD_LOW,
    #         CardRule.HIGH_CARD_AH: EvaluationType.THREE_CARD_LOW_AH
    #     },
    #     4: {  # Four cards showing
    #         CardRule.LOW_CARD: EvaluationType.FOUR_CARD_HIGH,
    #         CardRule.LOW_CARD_AL: EvaluationType.FOUR_CARD_HIGH_AL,
    #         CardRule.LOW_CARD_AL_RH: EvaluationType.FOUR_CARD_HIGH_AL_RH,
    #         CardRule.HIGH_CARD: EvaluationType.FOUR_CARD_LOW,
    #         CardRule.HIGH_CARD_AH: EvaluationType.FOUR_CARD_LOW_AH
    #     },
    #     5: {  # Five cards showing
    #         CardRule.LOW_CARD: EvaluationType.HIGH,
    #         CardRule.LOW_CARD_AL: EvaluationType.LOW_A5,        # no game uses this currently
    #         CardRule.LOW_CARD_AL_RH: EvaluationType.LOW_A5_HIGH,
    #         CardRule.HIGH_CARD: EvaluationType.LOW_A5,
    #         CardRule.HIGH_CARD_AH: EvaluationType.LOW_27
    #     }
    # }
    
    # Whether high hand or low hand goes first after first round
    # POST_FIRST_ROUND_MAPPING = {
    #     CardRule.LOW_CARD: "high",         # In standard stud, high hand goes first
    #     CardRule.LOW_CARD_AL: "high",      # In stud/8, high hand goes first
    #     CardRule.HIGH_CARD: "low",         # In Razz, low hand goes first
    #     CardRule.HIGH_CARD_AH: "low"       # In 2-7 stud, low hand goes first
    # }

    ONE_CARD_EVALS = {
        CardRule.LOW_CARD: EvaluationType.ONE_CARD_LOW,
        CardRule.LOW_CARD_AL: EvaluationType.ONE_CARD_LOW_AL,
        CardRule.LOW_CARD_AL_RH: EvaluationType.ONE_CARD_LOW_AL,
        CardRule.HIGH_CARD: EvaluationType.ONE_CARD_HIGH,
        CardRule.HIGH_CARD_AH: EvaluationType.ONE_CARD_HIGH_AH
    }    
    
    @classmethod
    def get_evaluation_type(cls, num_cards: int, card_rule: CardRule) -> EvaluationType:
        """
        Get the evaluation type based on number of visible cards and rule.
        
        Args:
            num_cards: Number of visible cards
            card_rule: Rule for evaluating cards
            
        Returns:
            Appropriate evaluation type
        """
        if num_cards not in cls.EVAL_MAPPINGS:
            # Default to using the 5-card evaluation if number not found
            num_cards = 5
            
        return cls.EVAL_MAPPINGS[num_cards][card_rule]
    
    # @classmethod
    # def determine_first_to_act(
    #     cls,
    #     players: List[Player],
    #     round_num: int,
    #     card_rule: str
    # ) -> Optional[Player]:
    #     """
    #     Determine which player acts first based on stud poker rules.
        
    #     Args:
    #         players: List of active players
    #         round_num: Current betting round (1-indexed)
    #         card_rule: Rule for determining first to act
    #         community_cards: Optional community cards (if any)
            
    #     Returns:
    #         Player who should act first or None if no eligible players
    #     """
    #     if not players:
    #         return None
            
    #     # Convert string rule to enum
    #     try:
    #         rule = CardRule(card_rule)
    #     except ValueError:
    #         logger.warning(f"Unknown card rule: {card_rule}, defaulting to 'low card'")
    #         rule = CardRule.LOW_CARD
        
    #     # First round uses special bring-in rules
    #     if round_num == 1:
    #         return cls._determine_bring_in(players, rule)
        
    #     # Later rounds look at the highest/lowest hand showing
    #     return cls._determine_post_first_round(players, rule)
    
    @classmethod
    def determine_first_to_act(cls, players: List[Player], num_cards: int, card_rule: CardRule, rules: 'GameRules') -> Player:
        """
        Determine the first player to act based on visible cards and rules.
        
        Args:
            players: List of active players
            num_cards: Number of visible cards (1-5 typically)
            card_rule: Bring-in rule (e.g., LOW_CARD)
            showdown_rules: Showdown configuration to derive evaluation type
        
        Returns:
            Player who must act first
        """
        from generic_poker.evaluation.evaluator import evaluator

        # For 1 card, use the predefined evaluation
        if num_cards == 1:
            eval_type = cls.ONE_CARD_EVALS[card_rule]
            player_cards = {p: p.hand.get_cards(visible_only=True)[:1] for p in players}
        else:
            # Derive evaluation type from showdown
            eval_type = cls._get_dynamic_eval_type(num_cards, card_rule, rules)
            player_cards = {p: p.hand.get_cards(visible_only=True)[:num_cards] for p in players}

        # Compare hands to find the "best" (lowest or highest per eval_type)
        best_player = None
        best_hand = None
        for player, cards in player_cards.items():
            if not cards:
                continue
            if best_hand is None or evaluator.compare_hands(cards, best_hand, eval_type) > 0:
                best_hand = cards
                best_player = player
        
        return best_player
        
    @classmethod
    def _get_dynamic_eval_type(cls, num_cards: int, card_rule: CardRule, rules: 'GameRules') -> str:
        """Construct the evaluation type based on card count and showdown rules."""
        best_hands = rules.showdown.best_hand  # Access attribute directly
        if not best_hands:
            return "high"  # Fallback

        # For single-hand games, use the first bestHand
        if len(best_hands) == 1:
            base_eval = best_hands[0]["evaluationType"]
        else:
            # Multi-hand game: use bringInEval if specified, else default to first
            forced_bets = showdown_rules.get("forcedBets", {})
            base_eval = forced_bets.get("bringInEval", best_hands[0]["evaluationType"])

        if num_cards >= 5:
            return base_eval
        # Construct e.g., "two_card_high" or "four_card_a5_low"
        card_count_prefix = ["", "one_card", "two_card", "three_card", "four_card"][num_cards]
        return f"{card_count_prefix}_{base_eval}"
            
    @classmethod
    def _get_visible_cards(cls, player: Player) -> List[Card]:
        """Get the visible (face-up) cards from a player's hand."""
        return [card for card in player.hand.cards 
                if card.visibility == Visibility.FACE_UP]
    
    @classmethod
    def _determine_bring_in(cls, players: List[Player], rule: CardRule) -> Optional[Player]:
        """
        Determine which player posts the bring-in (first round).
        
        In the first round of stud, we evaluate based on a single door card.
        """
        # Extract visible cards for each player
        player_cards = {player: cls._get_visible_cards(player) for player in players}
        
        # Filter to players with at least one visible card
        eligible_players = [p for p, cards in player_cards.items() if cards]
        if not eligible_players:
            return players[0] if players else None
        
        # Get appropriate evaluation type
        eval_type = cls.get_evaluation_type(1, rule)
        
        # For bring-in, we're looking for the player with specific card
        first_player = None
        first_player_score = None
              
        for player in eligible_players:
            # Just evaluate the first card
            card = player_cards[player][0]
            
            # Score this single card
            score = evaluator.evaluate_hand([card], eval_type)
            
            # Initialize first player if not set
            if first_player is None:
                first_player = player
                first_player_score = score
                continue
                
            # Compare scores based on whether we want lowest or highest
            if score and ((score.rank < first_player_score.rank) or (score.rank == first_player_score.rank and score.ordered_rank < first_player_score.ordered_rank)):
                first_player = player
                first_player_score = score
        
        return first_player
    
    @classmethod
    def _determine_post_first_round(
        cls,
        players: List[Player],
        rule: CardRule
    ) -> Optional[Player]:
        """
        Determine first to act in rounds after the first.
        
        In later rounds, the player with the highest/lowest hand showing goes first.
        """
            
        # Extract visible cards for each player
        player_cards = {player: cls._get_visible_cards(player) for player in players}
        
        # Filter to players with at least one visible card
        eligible_players = [p for p, cards in player_cards.items() if cards]
        if not eligible_players:
            return players[0] if players else None
                   
        # Get the appropriate evaluation type based on number of cards showing
        # (We'll use the first player's hand as a reference for count)
        num_cards = len(player_cards[eligible_players[0]])
        eval_type = cls.get_evaluation_type(num_cards, rule)
        
        # Find the player with best/worst hand
        first_player = None
        first_player_score = None
        
        for player in eligible_players:
            # Get all visible cards
            cards = player_cards[player]
            
            # Score this hand
            score = evaluator.evaluate_hand(cards, eval_type)
            
            logger.info(f"Player {player} has score {score} for their hand of {cards}")

            # Initialize first player if not set
            if first_player is None:
                first_player = player
                first_player_score = score
                continue
                
            if score and ((score.rank < first_player_score.rank) or (score.rank == first_player_score.rank and score.ordered_rank < first_player_score.ordered_rank)):
                first_player = player
                first_player_score = score
        
        return first_player