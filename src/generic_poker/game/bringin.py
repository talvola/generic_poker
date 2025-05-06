"""Module for determining first-to-act in stud poker games."""
from enum import Enum
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple, Any
import logging

from generic_poker.core.card import Card, Visibility
from generic_poker.game.player import Player
from generic_poker.evaluation.evaluator import evaluator, EvaluationType
from generic_poker.evaluation.cardrule import CardRule
from generic_poker.config.loader import GameRules

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
    
    
    # @classmethod
    # def determine_first_to_act(cls, players: List[Player], num_cards: int, card_rule: CardRule, rules: 'GameRules') -> Optional[Player]:
    #     """
    #     Determine the first player to act based on visible cards and rules.
        
    #     Args:
    #         players: List of active players
    #         num_cards: Number of visible cards (1-5 typically)
    #         card_rule: Bring-in rule (e.g., LOW_CARD)
    #         showdown_rules: Showdown configuration to derive evaluation type
        
    #     Returns:
    #         Player who must act first
    #     """
    #     from generic_poker.evaluation.evaluator import evaluator

    #     logger.debug(f"Determining first to act with num_cards={num_cards}, card_rule={card_rule}, players={len(players)}")
    #     # For 1 card, use the predefined evaluation
    #     if num_cards == 1:
    #         eval_type = cls.ONE_CARD_EVALS[card_rule]
    #         player_cards = {p: p.hand.get_cards(visible_only=True)[:1] for p in players}
    #     else:
    #         # Derive evaluation type from showdown
    #         eval_type = cls._get_dynamic_eval_type(num_cards, card_rule, rules)
    #         player_cards = {p: p.hand.get_cards(visible_only=True)[:num_cards] for p in players}

    #     logger.debug(f"Eval type: {eval_type}")
    #     logger.debug(f"Player cards: {[(p.name, [c.__str__() for c in cards]) for p, cards in player_cards.items()]}")

    #     # Compare hands to find the "best" (lowest or highest per eval_type)
    #     best_player = None
    #     best_hand = None
    #     for player, cards in player_cards.items():
    #         if not cards:
    #             logger.debug(f"No visible cards for player {player.name}")
    #             continue
    #         if best_hand is None or evaluator.compare_hands(cards, best_hand, eval_type) > 0:
    #             best_hand = cards
    #             best_player = player
        
    #     logger.debug(f"Best player: {best_player.name if best_player else 'None'}")
    #     return best_player
    
    @classmethod
    def determine_first_to_act(cls, players: List[Player], num_cards: int, card_rule: CardRule, rules: 'GameRules') -> Optional[Player]:
        """Determine the first player to act based on visible cards."""

        if not players or num_cards < 1:
            logger.debug("No players or invalid num_cards, returning None")
            return None

        eval_type = cls._get_dynamic_eval_type(num_cards, card_rule, rules)
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
    def _get_dynamic_eval_type(cls, num_cards: int, card_rule: CardRule, rules: 'GameRules') -> EvaluationType:
        """Construct the evaluation type based on card count and showdown rules."""
        logger.debug(f"Getting dynamic evaluation type for num_cards={num_cards}, card_rule={card_rule}, rules={rules}")

        best_hands = rules.showdown.best_hand
        if not best_hands:
            logger.warning("No bestHand configurations found, falling back to HIGH")
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
            # # For single-hand games, use the first bestHand
            # if len(best_hands) == 1:
            #     base_eval = best_hands[0]["evaluationType"]
            #     logger.debug(f"Single hand game, using base_eval: {base_eval}")
            # else:
            # Multi-hand game: use bringInEval if specified, else default to first
            forced_bets = rules.forced_bets
            try:
                base_eval = forced_bets.bringInEval if forced_bets.bringInEval else best_hands[0]["evaluationType"]
                logger.debug(f"Using bringInEval: {base_eval}")
            except (AttributeError, ValueError):
                logger.debug("bringInEval not specified or invalid, defaulting to first bestHand evaluation type")
                base_eval = best_hands[0]["evaluationType"]

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
    
    # @classmethod
    # def _determine_bring_in(cls, players: List[Player], rule: CardRule) -> Optional[Player]:
    #     """
    #     Determine which player posts the bring-in (first round).
        
    #     In the first round of stud, we evaluate based on a single door card.
    #     """
    #     # Extract visible cards for each player
    #     player_cards = {player: cls._get_visible_cards(player) for player in players}
        
    #     # Filter to players with at least one visible card
    #     eligible_players = [p for p, cards in player_cards.items() if cards]
    #     if not eligible_players:
    #         return players[0] if players else None
        
    #     # Get appropriate evaluation type
    #     eval_type = cls.get_evaluation_type(1, rule)
        
    #     # For bring-in, we're looking for the player with specific card
    #     first_player = None
    #     first_player_score = None
              
    #     for player in eligible_players:
    #         # Just evaluate the first card
    #         card = player_cards[player][0]
            
    #         # Score this single card
    #         score = evaluator.evaluate_hand([card], eval_type)
            
    #         # Initialize first player if not set
    #         if first_player is None:
    #             first_player = player
    #             first_player_score = score
    #             continue
                
    #         # Compare scores based on whether we want lowest or highest
    #         if score and ((score.rank < first_player_score.rank) or (score.rank == first_player_score.rank and score.ordered_rank < first_player_score.ordered_rank)):
    #             first_player = player
    #             first_player_score = score
        
    #     return first_player
    
    # @classmethod
    # def _determine_post_first_round(
    #     cls,
    #     players: List[Player],
    #     rule: CardRule
    # ) -> Optional[Player]:
    #     """
    #     Determine first to act in rounds after the first.
        
    #     In later rounds, the player with the highest/lowest hand showing goes first.
    #     """
            
    #     # Extract visible cards for each player
    #     player_cards = {player: cls._get_visible_cards(player) for player in players}
        
    #     # Filter to players with at least one visible card
    #     eligible_players = [p for p, cards in player_cards.items() if cards]
    #     if not eligible_players:
    #         return players[0] if players else None
                   
    #     # Get the appropriate evaluation type based on number of cards showing
    #     # (We'll use the first player's hand as a reference for count)
    #     num_cards = len(player_cards[eligible_players[0]])
    #     eval_type = cls.get_evaluation_type(num_cards, rule)
        
    #     # Find the player with best/worst hand
    #     first_player = None
    #     first_player_score = None
        
    #     for player in eligible_players:
    #         # Get all visible cards
    #         cards = player_cards[player]
            
    #         # Score this hand
    #         score = evaluator.evaluate_hand(cards, eval_type)
            
    #         logger.info(f"Player {player} has score {score} for their hand of {cards}")

    #         # Initialize first player if not set
    #         if first_player is None:
    #             first_player = player
    #             first_player_score = score
    #             continue
                
    #         if score and ((score.rank < first_player_score.rank) or (score.rank == first_player_score.rank and score.ordered_rank < first_player_score.ordered_rank)):
    #             first_player = player
    #             first_player_score = score
        
    #     return first_player