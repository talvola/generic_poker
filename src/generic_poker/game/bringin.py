"""Module for determining first-to-act in stud poker games."""
from enum import Enum
from dataclasses import dataclass
from typing import List, Dict, Optional, Union, Any
import logging

from generic_poker.core.card import Card, Visibility
from generic_poker.game.player import Player
from generic_poker.evaluation.evaluator import evaluator, EvaluationType
from generic_poker.evaluation.cardrule import CardRule
from generic_poker.config.loader import GameRules, ForcedBets

logger = logging.getLogger(__name__)
  
class BringInDeterminator:
    """
    Determines which player acts first in stud poker games based on exposed cards.
    
    This class handles the complex rules for first-to-act determination in stud poker,
    which varies based on the game variant, the number of exposed cards, and
    the specific card ranking rules in effect.
    """
    
    ONE_CARD_EVALS = {
        CardRule.LOW_CARD: EvaluationType.ONE_CARD_LOW,
        CardRule.LOW_CARD_AL: EvaluationType.ONE_CARD_LOW_AL,
        CardRule.HIGH_CARD: EvaluationType.ONE_CARD_HIGH,
        CardRule.HIGH_CARD_AH: EvaluationType.ONE_CARD_HIGH_AH,
        CardRule.HIGH_CARD_AH_WILD: EvaluationType.ONE_CARD_HIGH_AH_WILD
    }    
       
    @classmethod
    def determine_first_to_act(cls, players: List[Player], num_cards: int, card_rule: CardRule, rules: 'GameRules') -> Optional[Player]:
        """Determine the first player to act based on visible cards."""

        if not players or num_cards < 1:
            logger.debug("No players or invalid num_cards, returning None")
            return None

        eval_type = cls._get_dynamic_eval_type(num_cards, card_rule, rules=rules)
        from generic_poker.evaluation.evaluator import evaluator

        best_player = None
        best_cards = None
        for player in players:
            visible_cards = [c for c in player.hand.get_cards() if c.visibility == Visibility.FACE_UP][:num_cards]
            if not visible_cards:
                logger.debug(f"Player {player.id} has no visible cards, skipping")
                continue
            if best_cards is None:
                best_cards = visible_cards
                best_player = player
            elif evaluator.compare_hands(visible_cards, best_cards, eval_type) > 0:
                best_cards = visible_cards
                best_player = player

        if best_player is None:
            logger.warning("No players with visible cards found, returning None")
        return best_player
        
    @classmethod
    def _get_dynamic_eval_type(cls, num_cards: int, card_rule: CardRule, forced_bets: Optional[Union[ForcedBets, Dict[str, Any]]] = None, rules: Optional['GameRules'] = None) -> EvaluationType:
        """Construct the evaluation type based on card count and showdown rules."""
        logger.debug(f"Getting dynamic evaluation type for num_cards={num_cards}, card_rule={card_rule}, forced_bets={forced_bets}, rules={rules}")

        # Handle different forced_bets input types
        bring_in_eval = None
        if forced_bets:
            if isinstance(forced_bets, dict):
                # Already resolved forced bets (from get_effective_forced_bets)
                bring_in_eval = forced_bets.get('bringInEval')
            elif hasattr(forced_bets, 'bringInEval'):
                # Simple ForcedBets object
                bring_in_eval = forced_bets.bringInEval
            elif hasattr(forced_bets, 'conditionalOrders') and forced_bets.conditionalOrders and rules:
                # Conditional ForcedBets - need to resolve
                # But since we're in bring-in context, we know we're using bring-in rules
                # Try to get the effective configuration
                try:
                    effective_forced_bets = get_effective_forced_bets(rules, forced_bets)
                    bring_in_eval = effective_forced_bets.get('bringInEval')
                except Exception as e:
                    logger.warning(f"Could not resolve conditional forced bets: {e}")

        # Get best hands for fallback
        best_hands = []
        if rules and hasattr(rules, 'showdown') and hasattr(rules.showdown, 'best_hand'):
            best_hands = rules.showdown.best_hand or []

        if not best_hands and not bring_in_eval:
            logger.warning("No bestHand configurations found and no bringInEval, falling back to HIGH")
            return EvaluationType.HIGH

        if num_cards == 1:
            try:
                eval_type = cls.ONE_CARD_EVALS[card_rule]
                logger.debug(f"One card game, using eval_type: {eval_type}")
                return eval_type
            except KeyError:
                logger.warning(f"Invalid card_rule '{card_rule}' for one card, defaulting to 'high'")
                return EvaluationType.ONE_CARD_HIGH
        else:
            # Multi-hand game: use bringInEval if specified, else default to first bestHand
            try:
                if bring_in_eval:
                    base_eval = bring_in_eval
                    logger.debug(f"Using bringInEval: {base_eval}")
                elif best_hands:
                    base_eval = best_hands[0]["evaluationType"]
                    logger.debug(f"Using first bestHand evaluation: {base_eval}")
                else:
                    # Fallback based on card rule
                    if card_rule == CardRule.LOW_CARD:
                        base_eval = "a5_low"
                    else:
                        base_eval = "high"
                    logger.debug(f"No bringInEval or bestHand, falling back to: {base_eval}")
            except (AttributeError, IndexError, KeyError) as e:
                logger.warning(f"Error getting evaluation type: {e}, defaulting based on card rule")
                if card_rule == CardRule.LOW_CARD:
                    base_eval = "a5_low"
                else:
                    base_eval = "high"

            if num_cards >= 5:
                return EvaluationType(base_eval)
        
            # Construct e.g., "two_card_high" or "four_card_a5_low"
            card_count_prefix = ["", "one_card", "two_card", "three_card", "four_card"][num_cards]
            eval_type_str = f"{card_count_prefix}_{base_eval}"
            
            # Convert to EvaluationType
            try:
                return EvaluationType(eval_type_str)
            except ValueError:
                logger.warning(f"Unknown evaluation type '{eval_type_str}', falling back to '{base_eval}'")
                return EvaluationType(base_eval)
            
    @classmethod
    def _get_visible_cards(cls, player: Player) -> List[Card]:
        """Get the visible (face-up) cards from a player's hand."""
        return [card for card in player.hand.cards 
                if card.visibility == Visibility.FACE_UP]
