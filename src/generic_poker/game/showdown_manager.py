"""Showdown manager handling hand evaluation and pot distribution."""
import logging
import json
import itertools
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Tuple, Set

from generic_poker.config.loader import GameRules
from generic_poker.game.game_state import GameState
from generic_poker.game.table import Table, Player, Position
from generic_poker.game.betting import BettingManager
from generic_poker.core.card import Card, Visibility, WildType, Rank, Suit
from generic_poker.evaluation.evaluator import EvaluationType, evaluator
from generic_poker.evaluation.constants import HAND_SIZES, BASE_RANKS
from generic_poker.game.game_result import HandResult, PotResult, GameResult

logger = logging.getLogger(__name__)

class ShowdownManager:
    """
    Manages the showdown process, including hand evaluation and pot distribution.
    
    This class handles all the logic related to determining winners at the end of a poker hand.
    """
    
    def __init__(self, table: Table, betting: BettingManager, rules: GameRules):
        """Initialize the showdown manager."""
        self.table = table
        self.betting = betting
        self.rules = rules
        self.declarations: Dict[str, Dict[int, str]] = {}

    def handle_showdown(self) -> GameResult:
        """
        Handle showdown and determine winners.
        
        Returns:
            GameResult object with complete results of the hand
        """
        active_players = [p for p in self.table.players.values() if p.is_active]
        if not active_players:
            return GameResult(pots=[], hands={}, winning_hands=[], is_complete=True)
        
        # Check if using declarations mode
        if self.rules.showdown.declaration_mode == "declare":
            return self._handle_showdown_with_declare()     
        
        # Check if we have player-specific conditions (like player_hand_size)
        if self._has_player_specific_conditions():
            return self._handle_player_specific_showdown(active_players)
        
        # Standard showdown processing for global conditions
        return self._handle_standard_showdown(active_players)
        
    def _has_player_specific_conditions(self) -> bool:
        """Check if any conditional best hands use player-specific conditions."""
        conditionalBestHands = getattr(self.rules.showdown, 'conditionalBestHands', None)
        if not conditionalBestHands:
            return False
            
        for condition_rule in conditionalBestHands:
            condition_type = condition_rule['condition'].get('type')
            if condition_type == 'player_hand_size':
                return True
        return False
    
    def _handle_player_specific_showdown(self, active_players: List) -> GameResult:
        """
        Handle showdown where different players might use different hand configurations.
        This is used for conditions like player_hand_size where each player's condition
        needs to be evaluated individually.
        """
        # Initialize tracking structures
        hand_results, pot_results, winning_hands = self._initialize_showdown_tracking()
        
        # Get original pot amounts for tracking
        original_main_pot, original_side_pots, total_pot = self._get_original_pot_amounts()
        
        # Group players by their applicable hand configuration
        player_configs, config_lookup = self._group_players_by_config(active_players)
        
        # If no players matched any specific condition, use default
        if not any(player_configs.values()):
            logger.info("No players matched conditional configurations, using default")
            default_configs = self._get_default_config()
            if default_configs:
                # For default config, create a tuple and add all players
                default_config = default_configs[0]  # Use first default config
                default_tuple = self._config_to_tuple(default_config)
                player_configs = {default_tuple: active_players}
                config_lookup = {default_tuple: default_config}
        
        # Process each group of players with their specific configuration
        config_results = {}  # config_tuple -> {player_id: HandResult}
        
        for config_tuple, players in player_configs.items():
            if not players:
                continue
                
            config = config_lookup[config_tuple]
            config_name = config.get('name', 'Hand Configuration')
            eval_type = EvaluationType(config.get('evaluationType', 'high'))
            
            logger.info(f"Evaluating {len(players)} players with config: {config_name}")
            
            # Evaluate hands for this group of players
            group_results = self._evaluate_hands_for_config(players, config, eval_type)
            config_results[config_tuple] = group_results
            
            # Update hand_results
            self._update_hand_results(hand_results, group_results, config_name)
        
        # Now award pots - all players compete together regardless of their config
        # Find the best hands across all configurations
        all_hand_results = {}
        for group_results in config_results.values():
            all_hand_results.update(group_results)
        
        # Award the entire pot to the best hand(s) across all configurations
        if all_hand_results:
            # Since all players are competing for the same pot, we need to compare
            # hands across different evaluation types. For Tapiola Hold'em, they're
            # all "high" evaluation, so we can compare directly.
            
            # Find the best hand(s) among all players
            best_players = self._find_best_across_all_configs(active_players, all_hand_results)
            
            if best_players:
                # Award full pot to winners
                self._award_full_pot_to_winners(
                    best_players, original_main_pot, original_side_pots, pot_results
                )
                
                # Add winning hands
                for player in best_players:
                    if player.id in all_hand_results:
                        winning_hand = all_hand_results[player.id]
                        winning_hands.append(winning_hand)
        
        # Create and validate final result
        return self._create_final_game_result(pot_results, hand_results, winning_hands, total_pot)    
    
    def _handle_standard_showdown(self, active_players: List) -> GameResult:
        """Handle standard showdown with global conditions."""
        # Determine which best hand configuration to use
        best_hand_configs = self._determine_best_hand_configs()
        default_actions = self.rules.showdown.defaultActions
        global_default_action = self.rules.showdown.globalDefaultAction
                
        # Initialize tracking structures
        hand_results, pot_results, winning_hands = self._initialize_showdown_tracking()
        
        # Get original pot amounts for tracking
        original_main_pot, original_side_pots, total_pot = self._get_original_pot_amounts()
        
        # Process each hand configuration
        awarded_portions, had_any_winners = self._process_hand_configurations(
            best_hand_configs, active_players, hand_results, pot_results, winning_hands,
            original_main_pot, original_side_pots, default_actions
        )
        
        # Handle redistribution if some portions weren't awarded
        if awarded_portions > 0 and awarded_portions < len(best_hand_configs):
            self._redistribute_exact_pot(original_main_pot, original_side_pots, pot_results)
        
        # Handle global default action if no winners in any division
        if not had_any_winners and global_default_action:
            self._handle_global_default_action(
                global_default_action, active_players, original_main_pot, original_side_pots,
                pot_results, hand_results, winning_hands
            )
        
        # Create and validate final result
        return self._create_final_game_result(pot_results, hand_results, winning_hands, total_pot)    
        
    def _group_players_by_config(self, active_players: List) -> Dict[tuple, List]:
        """
        Group players by their applicable hand configuration based on player-specific conditions.
        
        Returns:
            Dictionary mapping config tuples to lists of players who match that config
        """
        player_configs = {}
        config_lookup = {}  # tuple -> actual config dict
        conditionalBestHands = getattr(self.rules.showdown, 'conditionalBestHands', [])
        
        # Initialize groups for each conditional config
        for condition_rule in conditionalBestHands:
            for config in condition_rule['bestHand']:
                config_tuple = self._config_to_tuple(config)
                player_configs[config_tuple] = []
                config_lookup[config_tuple] = config
        
        # Assign each player to their matching configuration
        for player in active_players:
            assigned = False
            
            for condition_rule in conditionalBestHands:
                condition = condition_rule['condition']
                
                # Check if this player matches this condition
                if self._check_best_hand_condition(condition, player):
                    # Add player to all configs in this condition rule
                    for config in condition_rule['bestHand']:
                        config_tuple = self._config_to_tuple(config)
                        if config_tuple in player_configs:
                            player_configs[config_tuple].append(player)
                    assigned = True
                    break  # Player matches this condition, don't check others
            
            if not assigned:
                logger.info(f"Player {player.id} didn't match any conditional configuration")
        
        return player_configs, config_lookup
    
    def _config_to_tuple(self, config: dict) -> tuple:
        """Convert a config dictionary to a hashable tuple for use as a dictionary key."""
        # We need to make the config hashable. Since we can't hash dicts directly,
        # we'll use the config's name and key properties as a tuple
        name = config.get('name', 'Unnamed')
        eval_type = config.get('evaluationType', 'high')
        hole_cards = str(config.get('holeCards', 0))  # Convert to string to handle "all"
        
        # Create a hashable tuple from key config properties
        # We'll store the config separately and use this tuple as a key
        return (name, eval_type, hole_cards)
    
    def _get_default_config(self) -> List[dict]:
        """Get the default hand configuration."""
        showdown_rules = self.rules.showdown
        
        if hasattr(showdown_rules, 'defaultBestHand') and showdown_rules.defaultBestHand:
            return showdown_rules.defaultBestHand
        elif hasattr(showdown_rules, 'best_hand') and showdown_rules.best_hand:
            return showdown_rules.best_hand
        else:
            return []    
        
    def _find_best_across_all_configs(self, active_players: List, all_hand_results: Dict) -> List:
        """
        Find the best hand(s) across all configurations.
        
        For player-specific conditions like hand size, all players compete for the same pot
        but may have used different evaluation rules to build their hands.
        """
        if not all_hand_results:
            return []
        
        # Since all configurations in Tapiola Hold'em use "high" evaluation,
        # we can compare hands directly. For games with mixed evaluation types,
        # this would need more sophisticated logic.
        
        best_players = []
        best_hand = None
        eval_type = EvaluationType.HIGH  # Assume high for now
        
        for player in active_players:
            if player.id not in all_hand_results:
                continue
                
            hand_result = all_hand_results[player.id]
            current_hand = hand_result.cards
            
            if not current_hand:
                continue
                
            if best_hand is None:
                best_players = [player]
                best_hand = current_hand
            else:
                comparison = evaluator.compare_hands(current_hand, best_hand, eval_type)
                if comparison > 0:  # Current hand is better
                    best_players = [player]
                    best_hand = current_hand
                elif comparison == 0:  # Tie
                    best_players.append(player)
        
        return best_players       
    
    def _award_full_pot_to_winners(
        self,
        winners: List,
        original_main_pot: int,
        original_side_pots: List[int],
        pot_results: List
    ) -> None:
        """Award the full pot to the winning players."""
        # Award side pots first
        for i, side_pot_amount in enumerate(original_side_pots):
            if side_pot_amount <= 0:
                continue
                
            eligible_ids = self.betting.get_side_pot_eligible_players(i)
            eligible_winners = [p for p in winners if p.id in eligible_ids]
            
            if eligible_winners:
                self.betting.award_pots(eligible_winners, i, side_pot_amount)
                
                pot_result = PotResult(
                    amount=side_pot_amount,
                    winners=[p.id for p in eligible_winners],
                    pot_type="side",
                    hand_type="Best Hand",
                    side_pot_index=i,
                    eligible_players=set(eligible_ids)
                )
                pot_results.append(pot_result)
        
        # Award main pot
        if original_main_pot > 0:
            self.betting.award_pots(winners, None, original_main_pot)
            
            pot_result = PotResult(
                amount=original_main_pot,
                winners=[p.id for p in winners],
                pot_type="main",
                hand_type="Best Hand",
                eligible_players=set(p.id for p in winners)
            )
            pot_results.append(pot_result)    
        
    def _determine_best_hand_configs(self) -> List[dict]:
        """Determine which best hand configuration to use based on conditions."""
        showdown_rules = self.rules.showdown
        
        # Check for conditional best hands
        conditionalBestHands = getattr(showdown_rules, 'conditionalBestHands', None)
        if conditionalBestHands and isinstance(conditionalBestHands, list):
            for condition_rule in conditionalBestHands:
                if self._check_best_hand_condition(condition_rule['condition']):
                    logger.info(f"Using conditional best hand configuration based on matching condition: {condition_rule['condition'].get('type')}")
                    # If the condition is based on player choice, log which game type is being used
                    if condition_rule['condition'].get('type') == 'player_choice':
                        game_choice = condition_rule['condition'].get('value')
                        logger.info(f"Evaluating hands for game type: {game_choice}")
                    return condition_rule['bestHand']
        
        # If no conditional rule matched, use default or standard best hands
        if hasattr(showdown_rules, 'defaultBestHand') and showdown_rules.defaultBestHand:
            logger.info("No condition matched; using default best hand configuration")
            return showdown_rules.defaultBestHand
        else:
            logger.info("Using standard best hand configuration")
            return showdown_rules.best_hand
        
    def _initialize_showdown_tracking(self) -> Tuple[Dict, List, List]:
        """Initialize data structures for tracking showdown results."""
        hand_results = {}  # player_id -> {config_name: HandResult}
        pot_results = []
        winning_hands = []
        return hand_results, pot_results, winning_hands   

    def _get_original_pot_amounts(self) -> Tuple[int, List[int], int]:
        """Get original pot amounts for tracking and redistribution."""
        original_main_pot = self.betting.get_main_pot_amount()
        original_side_pots = [self.betting.get_side_pot_amount(i) for i in range(self.betting.get_side_pot_count())]
        total_pot = self.betting.get_total_pot()
        return original_main_pot, original_side_pots, total_pot         
               
    def _process_hand_configurations(
        self,
        best_hand_configs: List[dict],
        active_players: List,
        hand_results: Dict,
        pot_results: List,
        winning_hands: List,
        original_main_pot: int,
        original_side_pots: List[int],
        default_actions: List
    ) -> Tuple[int, bool]:
        """
        Process each hand configuration and award pots.
        
        Returns:
            Tuple of (awarded_portions, had_any_winners)
        """        
        pot_percentage = 1.0 / len(best_hand_configs)
        awarded_portions = 0
        had_any_winners = False
        
        logger.info(f"Showdown with {len(best_hand_configs)} possible hands to win")

        for config in best_hand_configs:
            config_name = config.get('name', f"Configuration {len(hand_results)+1}")
            eval_type = EvaluationType(config.get('evaluationType', 'high'))
            
            logger.info(f"  Evaluating {config_name} with evaluation type {eval_type}")
            if config.get('qualifier'):
                logger.info(f"    with qualifier {config.get('qualifier')}")
            
            # Evaluate hands for this configuration
            config_results = self._evaluate_config_hands(active_players, config, eval_type, hand_results)
            
            # Update hand_results with config_results
            self._update_hand_results(hand_results, config_results, config_name)
            
            # Award pots for this configuration
            had_winners = self._award_config_pots(
                active_players, config_results, eval_type, config, pot_percentage,
                original_main_pot, original_side_pots, pot_results, winning_hands
            )
            
            # Handle case where no winners due to qualifier
            if not had_winners:
                had_winners = self._handle_no_qualifier_winners(
                    config, config_name, default_actions, active_players,
                    original_main_pot, original_side_pots, pot_percentage,
                    pot_results, hand_results, winning_hands
                )
            
            # Track results
            had_any_winners = had_any_winners or had_winners
            if had_winners:
                awarded_portions += 1
        
        return awarded_portions, had_any_winners
    
    def _evaluate_config_hands(
        self,
        active_players: List,
        config: dict,
        eval_type: EvaluationType,
        hand_results: Dict
    ) -> Dict:
        """Evaluate hands for a specific configuration."""
        if 'usesUnusedFrom' in config:
            return self._evaluate_unused_cards_config(active_players, config, eval_type, hand_results)
        else:
            return self._evaluate_hands_for_config(active_players, config, eval_type)    
        
    def _evaluate_unused_cards_config(
        self,
        active_players: List,
        config: dict,
        eval_type: EvaluationType,
        hand_results: Dict
    ) -> Dict:
        """Handle configurations that use unused cards from other configurations."""
        config_results = {}
        ref_config_name = config['usesUnusedFrom']

        for player in active_players:
            if player.id in hand_results and ref_config_name in hand_results[player.id]:
                ref_result = hand_results[player.id][ref_config_name]
                used_hole = ref_result.used_hole_cards
                all_hole = player.hand.get_cards()
                unused_hole = [c for c in all_hole if c not in used_hole]
                required_hole = config.get("holeCards", 2)
                required_community = config.get("communityCards", 0)

                if len(unused_hole) < required_hole:
                    logger.warning(f"Player {player.id} has insufficient unused hole cards for {config.get('name')}")
                    config_results[player.id] = None
                    continue

                hand = unused_hole[:required_hole]
                if required_community > 0:
                    comm_cards = self.table.community_cards.get('default', [])
                    if len(comm_cards) >= required_community:
                        hand.extend(list(itertools.combinations(comm_cards, required_community))[0])

                from generic_poker.evaluation.hand_description import HandDescriber
                describer = HandDescriber(eval_type)
                result = HandResult(
                    player_id=player.id,     
                    cards=hand,                                                   
                    hand_name=describer.describe_hand(hand),
                    hand_description=describer.describe_hand_detailed(hand),
                    hand_type=config.get('name'),
                    evaluation_type=eval_type.value,
                    used_hole_cards=unused_hole[:required_hole]
                )
                config_results[player.id] = result
            else:
                logger.warning(f"Referenced config '{ref_config_name}' not found for player {player.id}")
                config_results[player.id] = None
        
        return config_results
    
    def _update_hand_results(self, hand_results: Dict, config_results: Dict, config_name: str) -> None:
        """Update hand_results dictionary with new configuration results."""
        for player_id, result in config_results.items():
            if result:  # Only store if there's a valid result
                if player_id not in hand_results:
                    hand_results[player_id] = {}
                hand_results[player_id][config_name] = result
                logger.info(f"  Player {player_id} has {result.hand_description} for {config_name}")    

    def _award_config_pots(
        self,
        active_players: List,
        config_results: Dict,
        eval_type: EvaluationType,
        config: dict,
        pot_percentage: float,
        original_main_pot: int,
        original_side_pots: List[int],
        pot_results: List,
        winning_hands: List
    ) -> bool:
        """Award pots for a specific configuration and return whether there were winners."""
        pot_winners, had_winners = self._award_pots_for_config(
            active_players, config_results, eval_type, config, pot_percentage,
            original_main_pot, original_side_pots
        )
        
        if had_winners:
            logging.debug("Had winners - saving pot results")
            pot_results.extend(pot_winners)
            
            # Add winning hands to the list with proper type
            for pot_result in pot_winners:
                for winner_id in pot_result.winners:
                    if winner_id in config_results and config_results[winner_id]:
                        winning_hand = config_results[winner_id]
                        winning_hand.hand_type = config.get('name')
                        winning_hands.append(winning_hand)
        
        return had_winners           

    def _handle_no_qualifier_winners(
        self,
        config: dict,
        config_name: str,
        default_actions: List,
        active_players: List,
        original_main_pot: int,
        original_side_pots: List[int],
        pot_percentage: float,
        pot_results: List,
        hand_results: Dict,
        winning_hands: List
    ) -> bool:
        """Handle the case where no players qualified for a configuration."""
        applicable_actions = [da for da in default_actions if config_name in da.get('appliesTo', [])]
        
        if not applicable_actions:
            return False
        
        logger.debug(f"No winners for {config_name}; applying default action")
        
        for default_action in applicable_actions:
            action = default_action.get('action', {})
            if action.get('type') == 'evaluate_special':
                return self._handle_special_evaluation_action(
                    action, active_players, original_main_pot, original_side_pots,
                    pot_percentage, config_name, pot_results, hand_results, winning_hands
                )
        
        return False
    
    def _handle_special_evaluation_action(
        self,
        action: dict,
        active_players: List,
        original_main_pot: int,
        original_side_pots: List[int],
        pot_percentage: float,
        config_name: str,
        pot_results: List,
        hand_results: Dict,
        winning_hands: List
    ) -> bool:
        """Handle special evaluation actions (e.g., highest spade in hole)."""
        evaluation = action['evaluation']
        best_players, best_cards_dict = self._find_best_players_for_special(
            active_players=active_players,
            criterion=evaluation.get('criterion'),
            suit=evaluation.get('suit'),
            from_source=evaluation.get('from'),
            subsets=evaluation.get('subsets', ['default'])
        )
        
        if not best_players:
            return False
        
        # Award this configuration's pot portion to the best players
        special_pot_winners = self._award_special_pot(
            best_players=best_players,
            main_pot=original_main_pot,
            side_pots=original_side_pots,
            pot_percentage=pot_percentage,
            config_name=config_name
        )
        pot_results.extend(special_pot_winners)
        
        # Record the winning hands dynamically
        self._record_special_winning_hands(
            best_players, best_cards_dict, action, config_name, hand_results, winning_hands
        )
        
        return True    
    
    def _record_special_winning_hands(
        self,
        best_players: List,
        best_cards_dict: Dict,
        action: dict,
        config_name: str,
        hand_results: Dict,
        winning_hands: List
    ) -> None:
        """Record winning hands for special evaluation actions."""
        evaluation = action['evaluation']
        criterion = evaluation.get('criterion', 'unknown')
        suit = evaluation.get('suit', '')
        
        # Format criterion and suit: replace underscores with spaces and capitalize each word
        criterion_formatted = ' '.join(word.capitalize() for word in criterion.split('_'))
        suit_formatted = ' '.join(word.capitalize() for word in suit.split('_')) if suit else ''
        hand_name = f"{criterion_formatted} {suit_formatted}".strip() if suit else criterion_formatted
        
        for player in best_players:
            qualifying_cards = best_cards_dict.get(player.id, [])
            hand_description = f"{hand_name} ({', '.join(str(c) for c in qualifying_cards)})" if qualifying_cards else hand_name

            special_hand = HandResult(
                player_id=player.id,
                cards=qualifying_cards,
                hand_name=hand_name,
                hand_description=hand_description,
                hand_type=config_name,
                evaluation_type="special",
                used_hole_cards=qualifying_cards,
                community_cards=[]
            )
            
            if player.id not in hand_results:
                hand_results[player.id] = {}
            hand_results[player.id][config_name] = special_hand
            winning_hands.append(special_hand)    

    def _handle_global_default_action(
        self,
        global_default_action: dict,
        active_players: List,
        original_main_pot: int,
        original_side_pots: List[int],
        pot_results: List,
        hand_results: Dict,
        winning_hands: List
    ) -> None:
        """Handle global default action when no players qualified for any hand."""
        if global_default_action.get('condition') != 'no_qualifier_met':
            return
        
        logger.debug("No player qualified for any hand - handling global default action")
        action = global_default_action.get('action')
        action_type = action.get('type', 'split_pot')
        
        if action_type == 'split_pot':
            self._handle_global_split_pot(
                active_players, original_main_pot, original_side_pots,
                pot_results, hand_results, winning_hands
            )
        elif action_type == 'best_hand':
            self._handle_global_best_hand(
                action, active_players, original_main_pot, original_side_pots,
                pot_results, hand_results, winning_hands
            )

    def _handle_global_split_pot(
        self,
        active_players: List,
        original_main_pot: int,
        original_side_pots: List[int],
        pot_results: List,
        hand_results: Dict,
        winning_hands: List
    ) -> None:
        """Handle global split pot action."""
        logger.debug("   split_pot: split the pot among all active players")
        
        self._handle_split_among_active(active_players, original_main_pot, original_side_pots)
        
        # Create pot result entries for the split
        for i in range(len(original_side_pots)):
            eligible_ids = self.betting.get_side_pot_eligible_players(i)
            eligible_players = [p for p in active_players if p.id in eligible_ids]
            
            if eligible_players:
                pot_result = PotResult(
                    amount=original_side_pots[i],
                    winners=[p.id for p in eligible_players],
                    pot_type="side",
                    hand_type="Split (No Qualifier)",
                    side_pot_index=i,
                    eligible_players=set(p.id for p in eligible_players)
                )
                pot_results.append(pot_result)
        
        # Main pot
        pot_result = PotResult(
            amount=original_main_pot,
            winners=[p.id for p in active_players],
            pot_type="main",
            hand_type="Split (No Qualifier)",
            eligible_players=set(p.id for p in active_players)
        )
        pot_results.append(pot_result)
        
        # Mark all hands as "winning" in this case
        for player in active_players:
            if player.id in hand_results:
                for hand in hand_results[player.id].values():
                    hand.hand_type = "Split (No Qualifier)"
                    winning_hands.append(hand)

    def _handle_global_best_hand(
        self,
        action: dict,
        active_players: List,
        original_main_pot: int,
        original_side_pots: List[int],
        pot_results: List,
        hand_results: Dict,
        winning_hands: List
    ) -> None:
        """Handle global best hand action with alternate evaluation."""
        logger.debug("   best_hand: evaluate hands using the alternate evaluation type")
        
        alternate_configs = action.get('bestHand', [])
        if not alternate_configs:
            return
        
        # Process each alternate hand configuration
        alt_pot_results = []
        alt_winning_hands = []
        
        for alt_config in alternate_configs:
            alt_name = alt_config.get('name', 'Alternate Hand')
            alt_eval_type = EvaluationType(alt_config.get('evaluationType', 'high'))
            
            # Find best hands using alternate evaluation
            alt_results = self._evaluate_hands_for_config(active_players, alt_config, alt_eval_type)
            
            # Update the hand results
            for player_id, result in alt_results.items():
                if player_id not in hand_results:
                    hand_results[player_id] = {}
                if result:
                    result.hand_type = alt_name
                    hand_results[player_id][alt_name] = result
            
            # Award pots using the alternate evaluation
            alt_winners, had_alt_winners = self._award_alternate_pots(
                active_players, alt_results, alt_eval_type, alt_config,
                original_main_pot, original_side_pots
            )
            
            alt_pot_results.extend(alt_winners)
            
            # Add winning hands
            for pot_result in alt_winners:
                for winner_id in pot_result.winners:
                    if winner_id in alt_results and alt_results[winner_id]:
                        winning_hand = alt_results[winner_id]
                        winning_hand.hand_type = alt_name
                        alt_winning_hands.append(winning_hand)
        
        # Replace the results with alternate results
        pot_results.clear()
        pot_results.extend(alt_pot_results)
        winning_hands.clear()
        winning_hands.extend(alt_winning_hands)

    def _create_final_game_result(
        self,
        pot_results: List,
        hand_results: Dict,
        winning_hands: List,
        total_pot: int
    ) -> GameResult:
        """Create the final GameResult and perform validation."""
        game_result = GameResult(
            pots=pot_results,
            hands={pid: list(results.values()) for pid, results in hand_results.items()},
            winning_hands=winning_hands,
            is_complete=True
        )
        
        # Sanity check - verify total pot amounts match
        if game_result.total_pot != total_pot:
            logger.warning(f"Pot amount mismatch: {game_result.total_pot} vs {total_pot}")
        
        return game_result

    def _check_best_hand_condition(self, condition: Dict[str, Any], player: Player = None) -> bool:
        """
        Check if a condition for conditional best hands matches.
        
        Args:
            condition: Condition specification from rules
            player: Specific player to check condition for (for player-specific conditions)
            
        Returns:
            True if condition matches, False otherwise
        """
        condition_type = condition.get('type')
        
        if condition_type == "player_choice":
            subset = condition.get('subset')  # The choice variable name (e.g., "Game")
            expected_value = condition.get('value')  # Expected chosen value (e.g., "Hold'em")
            
            # Check if we have game_choices available (should be passed from Game)
            if not hasattr(self.game, 'game_choices'):
                logger.warning("No game choices available for condition check")
                return False
                
            # Get the actual chosen value
            actual_value = self.game.game_choices.get(subset)
            
            # Check if values match
            matches = actual_value == expected_value
            logger.info(f"Checking player choice condition: {subset}={actual_value}, expected {expected_value}, {'match' if matches else 'no match'}")
            
            # Check both single value and list of values
            if not matches and isinstance(expected_value, list):
                matches = actual_value in expected_value
                logger.info(f"Checking player choice condition against list: {subset}={actual_value}, expected one of {expected_value}, {'match' if matches else 'no match'}")
                
            return matches

        elif condition_type == "player_hand_size":
            # NEW: Check player hand size condition
            hand_sizes = condition.get('hand_sizes', [])
            min_hand_size = condition.get('min_hand_size')
            max_hand_size = condition.get('max_hand_size')
            
            # For player_hand_size, we MUST have a specific player
            if not player:
                logger.warning("player_hand_size condition requires a specific player")
                return False
                
            player_hand_size = len(player.hand.get_cards())
            
            # Check against specific hand sizes
            if hand_sizes:
                matches = player_hand_size in hand_sizes
                logger.info(f"Checking hand size condition for player {player.id}: has {player_hand_size} cards, expected one of {hand_sizes}, {'match' if matches else 'no match'}")
                return matches
                
            # Check against min/max range
            if min_hand_size is not None and player_hand_size < min_hand_size:
                logger.info(f"Player {player.id} hand size {player_hand_size} below minimum {min_hand_size}")
                return False
                
            if max_hand_size is not None and player_hand_size > max_hand_size:
                logger.info(f"Player {player.id} hand size {player_hand_size} above maximum {max_hand_size}")
                return False
                
            logger.info(f"Player {player.id} hand size condition met: {player_hand_size} cards")
            return True      
        
        elif condition_type == "community_card_value":
            subset = condition.get('subset')
            values = condition.get('values', [])
            
            # Check if the specified subset exists
            if subset not in self.table.community_cards or not self.table.community_cards[subset]:
                logger.debug(f"Condition check failed: subset '{subset}' not found or empty")
                return False
            
            # Get the first card in the subset (for die rolls, it's a single card)
            card = self.table.community_cards[subset][0]
            
            # Get the card value and check if it's in the specified values
            try:
                # Try to get numeric value first
                card_value = int(card.rank.value)
            except ValueError:
                # If not numeric, use the rank value directly
                card_value = card.rank.value
                
            logger.debug(f"Checking if card value {card_value} is in condition values {values}")
            return card_value in values
        
        elif condition_type == "community_card_suit":
            # Example of another condition type that could be added
            subset = condition.get('subset')
            suits = condition.get('suits', [])
            
            if subset not in self.table.community_cards or not self.table.community_cards[subset]:
                return False
                
            card = self.table.community_cards[subset][0]
            return card.suit.value in suits
        
        elif condition_type == "board_composition":
            subset = condition.get('subset', 'default')
            check_type = condition.get('check')
            
            # Check if the specified subset exists
            if subset not in self.table.community_cards or not self.table.community_cards[subset]:
                logger.debug(f"Condition check failed: subset '{subset}' not found or empty")
                return False
            
            # Handle color checks for board composition
            if check_type == "color":
                color = condition.get('color')
                min_count = condition.get('min_count', 1)
                
                cards = self.table.community_cards[subset]
                color_count = sum(1 for card in cards if card.color == color)
                
                logger.debug(f"Board composition check: {color_count} {color} cards in {subset} (need {min_count})")
                return color_count >= min_count
            
        # Default: condition not recognized or not implemented
        logger.warning(f"Unknown condition type: {condition_type}")
        return False

    # Add this method to handle community subset requirements
    def _find_hand_with_subset_requirements(
        self,
        hole_cards: List[Card],
        community_cards: Dict[str, List[Card]],
        showdown_rules: dict,
        eval_type: EvaluationType
    ) -> Tuple[List[Card], List[Card]]:
        """Find best hand using community subset requirements."""
        required_hole = showdown_rules.get("holeCards", 0)
        subset_requirements = showdown_rules.get("communitySubsetRequirements", [])
        
        if isinstance(required_hole, str) and required_hole == "all":
            required_hole = len(hole_cards)
        else:
            required_hole = int(required_hole)
        
        best_hand = None
        best_used_hole_cards = []
        
        # Generate hole card combinations
        if required_hole == 0:
            hole_combos = [tuple()]
        elif required_hole > len(hole_cards):
            logger.warning(f"Not enough hole cards: need {required_hole}, have {len(hole_cards)}")
            return [], []
        else:
            hole_combos = list(itertools.combinations(hole_cards, required_hole))
        
        # For each hole card combination, try all valid community combinations
        for hole_combo in hole_combos:
            # Generate all valid community card combinations based on subset requirements
            community_combinations = self._generate_subset_combinations(
                community_cards, subset_requirements
            )
            
            for comm_combo in community_combinations:
                hand = list(hole_combo) + list(comm_combo)
                
                if best_hand is None or evaluator.compare_hands(hand, best_hand, eval_type) > 0:
                    best_hand = hand
                    best_used_hole_cards = list(hole_combo)
        
        logger.info(f"Best hand found: {best_hand}")
        return best_hand if best_hand else [], best_used_hole_cards

    def _generate_subset_combinations(
        self,
        community_cards: Dict[str, List[Card]],
        subset_requirements: List[Dict[str, Any]]
    ) -> List[List[Card]]:
        """Generate all valid combinations of community cards based on subset requirements."""
        if not subset_requirements:
            return [[]]
        
        def generate_combinations_recursive(requirements_index: int, current_combination: List[Card]) -> List[List[Card]]:
            if requirements_index >= len(subset_requirements):
                return [current_combination]
            
            requirement = subset_requirements[requirements_index]
            subset_name = requirement["subset"]
            count = requirement["count"]
            required = requirement.get("required", True)
            
            available_cards = community_cards.get(subset_name, [])
            combinations = []
            
            if not available_cards and required:
                logger.warning(f"Required subset '{subset_name}' not available")
                return []  # Required subset not available
            
            if not available_cards and not required:
                # Optional subset not available, skip it
                return generate_combinations_recursive(requirements_index + 1, current_combination)
            
            if len(available_cards) < count and required:
                logger.warning(f"Not enough cards in required subset '{subset_name}': need {count}, have {len(available_cards)}")
                return []  # Not enough cards in required subset
            
            # Generate combinations for this subset
            if count == 0:
                subset_combos = [tuple()]
            elif count > len(available_cards):
                if required:
                    return []  # Not enough cards
                else:
                    subset_combos = [tuple()]  # Use no cards from optional subset
            else:
                subset_combos = list(itertools.combinations(available_cards, count))
            
            logger.debug(f"Generated {len(subset_combos)} combinations for subset '{subset_name}'")

            # For each combination from this subset, recurse to next requirement
            for subset_combo in subset_combos:
                new_combination = current_combination + list(subset_combo)
                combinations.extend(
                    generate_combinations_recursive(requirements_index + 1, new_combination)
                )
            
            return combinations
        
        result = generate_combinations_recursive(0, [])
        logger.debug(f"Generated {len(result)} total community card combinations")
        return result

    def handle_fold_win(self, active_players: List[Player]) -> GameResult:
        """Handle the case when all but one player folds."""
        logger.info("All but one player folded - hand complete")
        
        total_pot = self.betting.get_total_pot()
        
        self.betting.award_pots(active_players)
        
        hand_results = {}
        for player in active_players:
            hand_result = HandResult(
                player_id=player.id,
                cards=[],
                hand_name="Not shown",
                hand_description="Hand not shown - won uncontested",
                evaluation_type="unknown",
                hand_type="Uncontested"
            )
            hand_results[player.id] = [hand_result]
        
        # Include all winning hands
        winning_hands = [hand for player_hands in hand_results.values() for hand in player_hands]
        
        pot_result = PotResult(
            amount=total_pot,
            winners=[p.id for p in active_players],
            pot_type="main",
            hand_type="Entire Pot",
            eligible_players=set(p.id for p in active_players)
        )
        
        return GameResult(
            pots=[pot_result],
            hands=hand_results,
            winning_hands=winning_hands,
            is_complete=True
        )

    def _handle_showdown_with_declare(self) -> GameResult:
        """
        Handle showdown with declarations for Hi-Lo games.
        
        For declaration_mode='declare', uses Variation #2 from Conjelco:
        - Players declare 'high', 'low', or 'high_low' per pot.
        - High portion: Best high hand among 'high' or 'high_low' declarers.
        - Low portion: Best low hand among 'low' or 'high_low' declarers.
        - 'High_low' declarers must win both outright to scoop, but can win a tied portion.
        - Unwon portions go to the other portion's winners; if none eligible, split among all.
        """
        active_players = [p for p in self.table.players.values() if p.is_active]
        if not active_players:
            return GameResult(pots=[], hands={}, winning_hands=[], is_complete=True)
            
        # Get showdown rules
        showdown_rules = self.rules.showdown
        best_hand_configs = showdown_rules.best_hand

        # Validate Hi-Lo with declarations
        if len(best_hand_configs) != 2 or showdown_rules.declaration_mode != "declare":
            logger.error("Declarations only supported for Hi-Lo games with two configurations and declaration_mode='declare'")
            return GameResult(pots=[], hands={}, winning_hands=[], is_complete=True)
        
        # Assume two configurations: high and low
        high_config = best_hand_configs[0]  # e.g., "High Hand"
        low_config = best_hand_configs[1]   # e.g., "Low Hand"
        high_eval_type = EvaluationType(high_config.get('evaluationType', 'high'))
        low_eval_type = EvaluationType(low_config.get('evaluationType', 'low'))

        # Evaluate all hands
        high_results = self._evaluate_hands_for_config(active_players, high_config, high_eval_type)
        low_results = self._evaluate_hands_for_config(active_players, low_config, low_eval_type)

        # Store hand results
        hand_results = {
            p.id: {
                high_config.get('name', 'High'): high_results.get(p.id),
                low_config.get('name', 'Low'): low_results.get(p.id)
            } for p in active_players
        }
        pot_results = []
        winning_hands = []

        # Pot info
        main_pot_eligible = set(p.id for p in active_players)
        side_pots_eligible = [set(self.betting.get_side_pot_eligible_players(i)) 
                              for i in range(self.betting.get_side_pot_count())]
        
        # Process each pot
        for pot_index in [-1] + list(range(self.betting.get_side_pot_count())):
            if pot_index == -1:
                eligible_ids = main_pot_eligible
                pot_amount = self.betting.get_main_pot_amount()
            else:
                eligible_ids = side_pots_eligible[pot_index]
                pot_amount = self.betting.get_side_pot_amount(pot_index)        

            if not eligible_ids or pot_amount <= 0:
                continue

            # Calculate pot division with odd chip handling
            high_amount = pot_amount // 2
            low_amount = pot_amount // 2
            
            # Give odd chip to high portion per the rules
            if pot_amount % 2 == 1:
                high_amount += 1            

            # Get declarations
            declarations = {pid: self.declarations.get(pid, {}).get(pot_index) 
                            for pid in eligible_ids}
            logger.debug(f"Pot {pot_index}: Declarations {declarations}")      

            # Check if all players declared high_low
            all_high_low = all(decl == "high_low" for decl in declarations.values())            
            
            # Eligible players per portion
            high_eligible = [pid for pid in eligible_ids 
                            if declarations.get(pid) in ["high", "high_low"]]
            low_eligible = [pid for pid in eligible_ids 
                            if declarations.get(pid) in ["low", "high_low"]]        

            # Best high hands
            H = []
            best_high_hands = []
            if high_eligible and high_results:
                high_hands = {pid: high_results[pid] for pid in high_eligible 
                            if pid in high_results and high_results[pid]}
                if high_hands:
                    # Find best high hand(s)
                    best_pids = []
                    best_hand = None
                    for pid, result in high_hands.items():
                        hand = result.cards
                        if not best_hand:
                            best_pids = [pid]
                            best_hand = hand
                            best_high_hands = [result]
                        else:
                            comparison = evaluator.compare_hands(hand, best_hand, high_eval_type)
                            if comparison > 0:  # Current hand is better
                                best_pids = [pid]
                                best_hand = hand
                                best_high_hands = [result]
                            elif comparison == 0:  # Tie
                                best_pids.append(pid)
                                best_high_hands.append(result)
                    H = best_pids
            logger.debug(f"Pot {pot_index}: Best high hands {H}")

            # Best low hands
            L = []
            best_low_hands = []
            if low_eligible and low_results:
                low_hands = {pid: low_results[pid] for pid in low_eligible 
                            if pid in low_results and low_results[pid]}
                if low_hands:
                    # Find best low hand(s)
                    best_pids = []
                    best_hand = None
                    for pid, result in low_hands.items():
                        hand = result.cards
                        if not best_hand:
                            best_pids = [pid]
                            best_hand = hand
                            best_low_hands = [result]
                        else:
                            comparison = evaluator.compare_hands(hand, best_hand, low_eval_type)
                            if comparison > 0:  # Current hand is better
                                best_pids = [pid]
                                best_hand = hand
                                best_low_hands = [result]
                            elif comparison == 0:  # Tie
                                best_pids.append(pid)
                                best_low_hands.append(result)
                    L = best_pids
            logger.debug(f"Pot {pot_index}: Best low hands {L}")

            # Determine high_low eligibility
            high_low_eligible = {}
            for pid in eligible_ids:
                if declarations.get(pid) == "high_low":
                    # Must win or tie both high and low
                    in_high = pid in H
                    in_low = pid in L
                    high_low_eligible[pid] = in_high and in_low
                else:
                    high_low_eligible[pid] = True  # Non-high_low players are eligible
            logger.debug(f"Pot {pot_index}: High_low eligibility {high_low_eligible}")            

            # High winners per Variation #2
            high_winners = []
            high_reason = "Best high hand"
            for pid in H:
                decl = declarations.get(pid)
                if high_low_eligible[pid]:
                    if decl == "high":
                        high_winners.append(pid)
                    elif decl == "high_low":
                        high_winners.append(pid)
            # If no winners yet, check high declarers
            if not high_winners:
                high_only = [pid for pid in high_eligible if declarations.get(pid) == "high" and high_low_eligible[pid]]
                if high_only and high_hands:
                    best_high_only_pids = []
                    best_hand = None
                    for pid in high_only:
                        if pid in high_hands:
                            hand = high_hands[pid].cards
                            if not best_hand:
                                best_high_only_pids = [pid]
                                best_hand = hand
                            else:
                                comparison = evaluator.compare_hands(hand, best_hand, high_eval_type)
                                if comparison > 0:
                                    best_high_only_pids = [pid]
                                    best_hand = hand
                                elif comparison == 0:
                                    best_high_only_pids.append(pid)
                    high_winners = best_high_only_pids
                    high_reason = "Best high hand among high declarers"
            logger.debug(f"Pot {pot_index}: High winners {high_winners}")

            # Low winners per Variation #2
            low_winners = []
            low_reason = "Best low hand"
            for pid in L:
                decl = declarations.get(pid)
                if high_low_eligible[pid]:
                    if decl == "low":
                        low_winners.append(pid)
                    elif decl == "high_low":
                        low_winners.append(pid)
            # If no winners yet, check low declarers
            if not low_winners:
                low_only = [pid for pid in low_eligible if declarations.get(pid) == "low" and high_low_eligible[pid]]
                if low_only and low_hands:
                    best_low_only_pids = []
                    best_hand = None
                    for pid in low_only:
                        if pid in low_hands:
                            hand = low_hands[pid].cards
                            if not best_hand:
                                best_low_only_pids = [pid]
                                best_hand = hand
                            else:
                                comparison = evaluator.compare_hands(hand, best_hand, low_eval_type)
                                if comparison > 0:
                                    best_low_only_pids = [pid]
                                    best_hand = hand
                                elif comparison == 0:
                                    best_low_only_pids.append(pid)
                    low_winners = best_low_only_pids
                    low_reason = "Best low hand among low declarers"
            logger.debug(f"Pot {pot_index}: Low winners {low_winners}")

            # Handle no winners
            if not high_winners and low_winners:
                high_winners = low_winners.copy()
                high_reason = "Reallocated to low winners (no qualifying high hand)"
            if not low_winners and high_winners:
                low_winners = high_winners.copy()
                low_reason = "Reallocated to high winners (no qualifying low hand)"
            if not high_winners and not low_winners:
                # Exception: if all high_low and none qualify, split among all
                if all_high_low and not any(high_low_eligible.values()):
                    high_winners = list(eligible_ids)
                    low_winners = list(eligible_ids)
                    high_reason = "Split among all players (no high_low players qualified)"
                    low_reason = "Split among all players (no high_low players qualified)"
                else:
                    high_winners = list(eligible_ids)
                    low_winners = list(eligible_ids)
                    high_reason = "Split among all players (no qualifying hands)"
                    low_reason = "Split among all players (no qualifying hands)"
            logger.debug(f"Pot {pot_index}: Final high winners {high_winners}, low winners {low_winners}")

            # Award high portion (50%)
            if high_winners:
                winners = [self.table.players[pid] for pid in high_winners]
                self.betting.award_pots(winners, pot_index if pot_index >= 0 else None, high_amount)
                pot_result = PotResult(
                    amount=high_amount,
                    winners=high_winners,
                    pot_type="side" if pot_index >= 0 else "main",
                    hand_type=high_config.get('name', 'High'),
                    side_pot_index=pot_index if pot_index >= 0 else None,
                    eligible_players=eligible_ids,
                    reason=high_reason,
                    best_hands=best_high_hands,
                    declarations=declarations                    
                )
                pot_results.append(pot_result)
                logger.debug(f"Pot {pot_index}: Created high pot result: {pot_result}")
                for pid in high_winners:
                    if pid in high_results and high_results[pid]:
                        hand = high_results[pid]
                        hand.hand_type = high_config.get('name', 'High')
                        winning_hands.append(hand)  

            # Award low portion (50%)
            if low_winners:
                winners = [self.table.players[pid] for pid in low_winners]
                self.betting.award_pots(winners, pot_index if pot_index >= 0 else None, low_amount)
                pot_result = PotResult(
                    amount=low_amount,
                    winners=low_winners,
                    pot_type="side" if pot_index >= 0 else "main",
                    hand_type=low_config.get('name', 'Low'),
                    side_pot_index=pot_index if pot_index >= 0 else None,
                    eligible_players=eligible_ids,
                    reason=low_reason,
                    best_hands=best_low_hands,
                    declarations=declarations
                )
                pot_results.append(pot_result)
                logger.debug(f"Pot {pot_index}: Created low pot result: {pot_result}")
                for pid in low_winners:
                    if pid in low_results and low_results[pid]:
                        hand = low_results[pid]
                        hand.hand_type = low_config.get('name', 'Low')
                        winning_hands.append(hand)

        # Store results
        return GameResult(
            pots=pot_results,
            hands={pid: list(results.values()) for pid, results in hand_results.items()},
            winning_hands=winning_hands,
            is_complete=True
        )
    
    def set_declarations(self, declarations: Dict[str, Dict[int, str]]) -> None:
        """Set player declarations for Hi-Lo games."""
        self.declarations = declarations

    def _evaluate_hands_for_config(
        self,
        players: List[Player],
        hand_config: dict,
        eval_type: EvaluationType
    ) -> Dict[str, HandResult]:
        """
        Evaluate all players' best hands for a specific hand configuration.
        
        Args:
            players: List of active players
            hand_config: Configuration for this hand evaluation
            eval_type: Type of evaluation to use
            
        Returns:
            Dictionary mapping player IDs to their best hand results
        """
        from generic_poker.evaluation.hand_description import HandDescriber
        
        hand_type = hand_config.get('name', "Hand")
        describer = HandDescriber(eval_type)
        results = {}

        if "zeroCardsPipValue" in hand_config:
            zero_cards_pip_value = hand_config["zeroCardsPipValue"]     
        else:
            zero_cards_pip_value = None  # Default to None if not specified in the config

        for player in players:
            # Find the player's best hand for this configuration
            best_hand, used_hole_cards = self._find_best_hand_for_player(
                player,
                self.table.community_cards,
                hand_config,
                eval_type
            )
          
            # Allow an empty hand to play if it has value
            if not best_hand and zero_cards_pip_value is not None:
                logger.info(f"Player {player.name} has no valid hand for {hand_type}, but zeroCardsPipValue is set to {zero_cards_pip_value}. Assigning a default hand.")
                # Create results
                results[player.id] = HandResult(
                    player_id=player.id,
                    cards=[],
                    hand_name="No Cards",
                    hand_description="No Cards",
                    hand_type=hand_type,
                    evaluation_type=eval_type.value,
                    community_cards=self.table.community_cards,
                    used_hole_cards=[]  # No hole cards used for an empty hand
                )
                continue

            if not best_hand:
                logger.info(f"Player {player.name} has no valid hand for {hand_type}. Skipping...")
                continue

            # Determine classification (e.g., face/butt)
            classifications = {}
            if "classification" in hand_config:
                classification_config = hand_config["classification"]
                if classification_config["type"] == "face_butt":
                    face_ranks = [Rank[r] for r in classification_config["faceRanks"]]
                    all_cards = player.hand.get_cards()  # All 7 cards
                    has_face = any(card.rank in face_ranks for card in all_cards)
                    classifications[classification_config["fieldName"]] = "face" if has_face else "butt"

            # Evaluate the hand to get rank
            rank_result = evaluator.evaluate_hand(best_hand, eval_type)
            if not rank_result:
                logger.warning(f"Failed to evaluate hand for player {player.id}")
                continue            
            
            # Create hand result with used_hole_cards
            results[player.id] = HandResult(
                player_id=player.id,
                cards=best_hand,
                rank=rank_result.rank,
                ordered_rank=rank_result.ordered_rank,                
                hand_name=describer.describe_hand(best_hand),
                hand_description=describer.describe_hand_detailed(best_hand),
                hand_type=hand_type,
                evaluation_type=eval_type.value,
                community_cards=self.table.community_cards,
                used_hole_cards=used_hole_cards,
                classifications=classifications
            )
        
        return results

    def _award_pots_for_config(
        self,
        players: List[Player],
        hand_results: Dict[str, HandResult],
        eval_type: EvaluationType,
        hand_config: dict,
        pot_percentage: float,
        original_main_pot: int,  
        original_side_pots: List[int]         
    ) -> Tuple[List[PotResult], bool]:
        """
        Award pots for a specific hand configuration.
        
        Args:
            players: List of active players
            hand_results: Dictionary of player hand results
            eval_type: Type of evaluation being used
            hand_config: Hand configuration 
            pot_percentage: Percentage of the pot to award for this config
            original_main_pot: Original main pot amount  
            original_side_pots: Original side pot amounts
            
        Returns:
            Tuple of (pot results, had_winners)
        """

        logger.info(f"_award_pots_for_config for eval_type: {eval_type}, hand_config: {hand_config}")  

        pot_results = []
        player_hands = {
            player_id: result.cards 
            for player_id, result in hand_results.items()
        }
        
        # Convert players to dictionary for easier lookup
        player_dict = {player.id: player for player in players}
        
        # Get main pot and side pot info
        qualifier = hand_config.get('qualifier', None)

        # Get current pot info for logging
        current_main_pot = self.betting.get_main_pot_amount()
        current_side_pot_count = self.betting.get_side_pot_count()
        
        logger.info(f"    Main pot has ${current_main_pot}.   There are {current_side_pot_count} side pot(s)")  
  
        had_winners = False

        # Award side pots first
        for i in range(len(original_side_pots)):
            eligible_ids = self.betting.get_side_pot_eligible_players(i)
            eligible_players = [player_dict[pid] for pid in eligible_ids if pid in player_dict]
            
            # Find players with valid hands for this side pot
            qualified_players = []
            for player in eligible_players:
                if player.id not in player_hands:
                    continue
                    
                # Check qualifier if specified
                if qualifier:
                    hand = player_hands[player.id]
                    result = evaluator.evaluate_hand(hand, eval_type)
                    if not result or (result.rank > qualifier[0]) or (result.rank == qualifier[0] and result.ordered_rank > qualifier[1]):
                        continue
                
                qualified_players.append(player)
            
            if qualified_players:
                # Find best hand among eligible players
                winners = self._find_winners(qualified_players, hand_results, eval_type, self.rules.showdown)
                if winners:
                    had_winners = True
                    # Calculate pot amount based on ORIGINAL side pot
                    pot_amount = int(original_side_pots[i] * pot_percentage)
                    
                    # For high-low games, handle odd chips
                    if len(self.rules.showdown.best_hand) == 2:
                        # Get card counts for the two hand types to determine which gets the odd chip
                        card_counts = {}
                        for idx, eval_hand_config in enumerate(self.rules.showdown.best_hand):
                            if "anyCards" in eval_hand_config:
                                card_counts[idx] = eval_hand_config.get("anyCards", 0)
                            elif eval_hand_config.get("holeCards") == "all":
                                # When "holeCards" is "all", estimate it as 5 for standard poker
                                card_counts[idx] = 5  # Default to 5 cards for "all" hole cards                                
                            else:
                                hole_cards = eval_hand_config.get("holeCards", 0)
                                # Handle list values (e.g., [2, 5] for "2 or 5" games)
                                if isinstance(hole_cards, list):
                                    hole_cards = max(hole_cards)
                                elif not isinstance(hole_cards, int):
                                    hole_cards = 0
                                comm_cards = eval_hand_config.get("communityCards", 0)
                                if isinstance(comm_cards, list):
                                    comm_cards = max(comm_cards)
                                elif not isinstance(comm_cards, int):
                                    comm_cards = 0
                                card_counts[idx] = hole_cards + comm_cards

                        # Find current config index more robustly
                        current_config_name = hand_config.get('name')
                        current_config_idx = None
                        for idx, cfg in enumerate(self.rules.showdown.best_hand):
                            if cfg.get('name') == current_config_name:
                                current_config_idx = idx
                                break
                        if current_config_idx is None:
                            current_config_idx = 0  # Default to first config if not found

                        other_config_idx = 1 if current_config_idx == 0 else 0

                        # Apply the rules for odd chip assignment
                        gets_odd_chip = False

                        # Rule 1: Traditional High-Low games - high hand gets odd chip
                        if (self.rules.showdown.best_hand[0].get("evaluationType") == "high" and 
                            self.rules.showdown.best_hand[1].get("evaluationType").startswith("low")):
                            gets_odd_chip = (current_config_idx == 0)

                        # Rule 2: Five-card hand vs four-card hand - five-card hand gets odd chip
                        elif card_counts.get(current_config_idx, 0) == 5 and card_counts.get(other_config_idx, 0) == 4:
                            gets_odd_chip = True
                        elif card_counts.get(current_config_idx, 0) == 4 and card_counts.get(other_config_idx, 0) == 5:
                            gets_odd_chip = False
                            
                        # Rule 3: Draw hand vs Omaha hand - draw hand gets odd chip
                        elif ("Omaha" in self.rules.showdown.best_hand[other_config_idx].get("name", "") and 
                            "Draw" in self.rules.showdown.best_hand[current_config_idx].get("name", "")):
                            gets_odd_chip = True
                        elif ("Omaha" in self.rules.showdown.best_hand[current_config_idx].get("name", "") and 
                            "Draw" in self.rules.showdown.best_hand[other_config_idx].get("name", "")):
                            gets_odd_chip = False
                            
                        # Rule 4: Sohe - Omaha hand gets odd chip
                        elif ("Omaha" in self.rules.showdown.best_hand[current_config_idx].get("name", "") and 
                            "Hold'em" in self.rules.showdown.best_hand[other_config_idx].get("name", "")):
                            gets_odd_chip = True
                        elif ("Omaha" in self.rules.showdown.best_hand[other_config_idx].get("name", "") and 
                            "Hold'em" in self.rules.showdown.best_hand[current_config_idx].get("name", "")):
                            gets_odd_chip = False                                            

                        # Fallback to card count as a tiebreaker
                        else:
                            gets_odd_chip = card_counts.get(current_config_idx, 0) > card_counts.get(other_config_idx, 0)

                        # Add the odd chip if this hand qualifies and there is an odd chip
                        if gets_odd_chip and original_side_pots[i] % 2 == 1:
                            pot_amount += 1

                        logger.debug(f"Odd chip decision for {hand_config.get('name')} - " +
                                    f"Gets odd chip: {gets_odd_chip}, " +
                                    f"Original pot: {original_main_pot}, " + 
                                    f"Card counts: {card_counts}, " +
                                    f"Final amount: {pot_amount}")                            

                    # Award the pot portion
                    self.betting.award_pots(winners, i, pot_amount)
                    
                    # Track the result
                    pot_result = PotResult(
                        amount=pot_amount,
                        winners=[p.id for p in winners],
                        pot_type="side",
                        hand_type=hand_config.get('name', 'Unspecified'),
                        side_pot_index=i,
                        eligible_players=eligible_ids
                    )
                    pot_results.append(pot_result)
        
        # Award main pot
        eligible_players = [player_dict[pid] for pid in player_dict.keys()]
        
        # Find players with valid hands for main pot
        qualified_players = []
        for player in eligible_players:
            if player.id not in player_hands:
                continue
                
            # Check qualifier if specified
            if qualifier:
                hand = player_hands[player.id]
                result = evaluator.evaluate_hand(hand, eval_type)
                if not result or (result.rank > qualifier[0]) or (result.rank == qualifier[0] and result.ordered_rank > qualifier[1]):
                    continue
            
            qualified_players.append(player)
        
        if qualified_players:
            winners = self._find_winners(qualified_players, hand_results, eval_type, self.rules.showdown)
            if winners:
                had_winners = True
                # Calculate pot amount based on ORIGINAL main pot
                pot_amount = int(original_main_pot * pot_percentage)

                # For high-low games, handle odd chips
                if len(self.rules.showdown.best_hand) == 2:
                    # Get card counts for the two hand types to determine which gets the odd chip
                    card_counts = {}
                    for idx, eval_hand_config in enumerate(self.rules.showdown.best_hand):
                        if "anyCards" in eval_hand_config:
                            card_counts[idx] = eval_hand_config.get("anyCards", 0)
                        elif eval_hand_config.get("holeCards") == "all":
                            # When "holeCards" is "all", estimate it as 5 for standard poker
                            card_counts[idx] = 5  # Default to 5 cards for "all" hole cards
                        else:
                            hole_cards = eval_hand_config.get("holeCards", 0)
                            # Handle list values (e.g., [2, 5] for "2 or 5" games)
                            if isinstance(hole_cards, list):
                                hole_cards = max(hole_cards)
                            elif not isinstance(hole_cards, int):
                                hole_cards = 0
                            comm_cards = eval_hand_config.get("communityCards", 0)
                            if isinstance(comm_cards, list):
                                comm_cards = max(comm_cards)
                            elif not isinstance(comm_cards, int):
                                comm_cards = 0
                            card_counts[idx] = hole_cards + comm_cards

                    # Find current config index more robustly
                    current_config_name = hand_config.get('name')
                    current_config_idx = None
                    for idx, cfg in enumerate(self.rules.showdown.best_hand):
                        if cfg.get('name') == current_config_name:
                            current_config_idx = idx
                            break
                    if current_config_idx is None:
                        current_config_idx = 0  # Default to first config if not found

                    other_config_idx = 1 if current_config_idx == 0 else 0

                    # Apply the rules for odd chip assignment
                    gets_odd_chip = False

                    # Rule 1: Traditional High-Low games - high hand gets odd chip
                    if (self.rules.showdown.best_hand[0].get("evaluationType") == "high" and 
                        self.rules.showdown.best_hand[1].get("evaluationType").startswith("low")):
                        gets_odd_chip = (current_config_idx == 0)

                    # Rule 2: Five-card hand vs four-card hand - five-card hand gets odd chip
                    elif card_counts.get(current_config_idx, 0) == 5 and card_counts.get(other_config_idx, 0) == 4:
                        gets_odd_chip = True
                    elif card_counts.get(current_config_idx, 0) == 4 and card_counts.get(other_config_idx, 0) == 5:
                        gets_odd_chip = False
                        
                    # Rule 3: Draw hand vs Omaha hand - draw hand gets odd chip
                    elif ("Omaha" in self.rules.showdown.best_hand[other_config_idx].get("name", "") and 
                        "Draw" in self.rules.showdown.best_hand[current_config_idx].get("name", "")):
                        gets_odd_chip = True
                    elif ("Omaha" in self.rules.showdown.best_hand[current_config_idx].get("name", "") and 
                        "Draw" in self.rules.showdown.best_hand[other_config_idx].get("name", "")):
                        gets_odd_chip = False
                        
                    # Rule 4: Sohe - Omaha hand gets odd chip
                    elif ("Omaha" in self.rules.showdown.best_hand[current_config_idx].get("name", "") and 
                        "Hold'em" in self.rules.showdown.best_hand[other_config_idx].get("name", "")):
                        gets_odd_chip = True
                    elif ("Omaha" in self.rules.showdown.best_hand[other_config_idx].get("name", "") and 
                        "Hold'em" in self.rules.showdown.best_hand[current_config_idx].get("name", "")):
                        gets_odd_chip = False
                        
                    # Fallback to card count as a tiebreaker
                    else:
                        gets_odd_chip = card_counts.get(current_config_idx, 0) > card_counts.get(other_config_idx, 0)

                    # Add the odd chip if this hand qualifies and there is an odd chip
                    if gets_odd_chip and original_main_pot % 2 == 1:
                        pot_amount += 1

                    logger.debug(f"Odd chip decision for {hand_config.get('name')} - " +
                                f"Gets odd chip: {gets_odd_chip}, " +
                                f"Original pot: {original_main_pot}, " + 
                                f"Card counts: {card_counts}, " +
                                f"Final amount: {pot_amount}")

                logger.info(f"       Awarding ${pot_amount} ({original_main_pot} * {pot_percentage}) to {winners}.")  
                
                # Award the pot portion
                self.betting.award_pots(winners, None, pot_amount)
                
                # Track the result
                pot_result = PotResult(
                    amount=pot_amount,
                    winners=[p.id for p in winners],
                    pot_type="main",
                    hand_type=hand_config.get('name', 'Unspecified'),
                    eligible_players=set(p.id for p in eligible_players)
                )
                logger.debug(f"Created pot result with hand_type: {hand_config.get('name', 'Unspecified')}")
                pot_results.append(pot_result)
        
        return pot_results, had_winners

    def _find_winners(
        self,
        players: List[Player],
        player_hands: Dict[str, HandResult],
        eval_type: EvaluationType,
        showdown_rules: dict
    ) -> List[Player]:
        """Find best hand(s) among players."""
        if not players or not player_hands:
            return []
            
        # Get classification priority from showdown rules
        classification_priority = showdown_rules.classification_priority
        classification_field = "face_butt"  # Default field name from bestHand classification        
        
        # Helper to get classification rank
        def get_classification_rank(hand_result: HandResult) -> int:
            if not classification_priority:
                return 0
            logger.debug(f"Hand Result: {hand_result}")
            classification = hand_result.classifications.get(classification_field, "butt")
            try:
                return classification_priority.index(classification)
            except ValueError:
                return len(classification_priority)  # Unknown classification is worst
                
        # Get first player as initial best
        best_players = [players[0]]
        best_hand_result = player_hands[players[0].id]
        best_classification_rank = get_classification_rank(best_hand_result)
        
        # Compare against other players
        for player in players[1:]:
            if player.id not in player_hands:
                continue
                
            current_hand_result = player_hands[player.id]
            current_classification_rank = get_classification_rank(current_hand_result)
           
            # Compare by classification first
            if current_classification_rank < best_classification_rank:
                # Current hand has a better classification (e.g., "face" vs "butt")
                best_players = [player]
                best_hand_result = current_hand_result
                best_classification_rank = current_classification_rank
            elif current_classification_rank == best_classification_rank:
                # Same classification, compare by rank
                comparison = evaluator.compare_hands(
                    current_hand_result.cards,
                    best_hand_result.cards,
                    eval_type
                )
                if comparison > 0:  # Current hand better
                    best_players = [player]
                    best_hand_result = current_hand_result
                elif comparison == 0:  # Tie
                    best_players.append(player)
                
        return best_players      
    
    def _get_filtered_hole_cards(self, player: Player, showdown_rules: dict) -> List[Card]:
        """Get hole cards based on subset and filter by card state if needed."""
        hole_subset = showdown_rules.get("hole_subset", "default")
        
        # Get hole cards
        if hole_subset and hole_subset != "default":
            # Use specific subset if specified (e.g., SHESHE)
            hole_cards = player.hand.get_subset(hole_subset)
            if not hole_cards:
                logger.warning(f"No cards in hole subset '{hole_subset}' for player {player.id}")
                return []
        else:
            # Use all cards if no subset specified or default (e.g., Hold'em, Stud)
            hole_cards = player.hand.get_cards()
            if not hole_cards:
                logger.warning(f"No cards in hand for player {player.id}")
                return []
        
        # Filter hole cards by cardState if specified
        if "cardState" in showdown_rules:
            card_state = showdown_rules["cardState"]
            if card_state == "face down":
                hole_cards = [card for card in hole_cards if card.visibility == Visibility.FACE_DOWN]
            elif card_state == "face up":
                hole_cards = [card for card in hole_cards if card.visibility == Visibility.FACE_UP]
            else:
                logger.warning(f"Invalid cardState '{card_state}' for player {player.id}")
                return []
            
            logger.debug(f"Filtered hole cards to {card_state}: {len(hole_cards)} cards remaining")
            if not hole_cards and "minimumCards" not in showdown_rules:
                logger.warning(f"No {card_state} cards available for player {player.id}")
                return []
        
        return hole_cards    
    
    def _handle_zero_cards_case(self, showdown_rules: dict, eval_type: EvaluationType) -> bool:
        """Handle the case when a player has zero cards."""
        minimum_cards = showdown_rules["minimumCards"]
        if minimum_cards > 0:
            logger.warning(f"Player has 0 cards, needs {minimum_cards} to qualify")
            return True
        
        # Handle 0-card variants
        if "zeroCardsPipValue" in showdown_rules and eval_type.startswith("low_pip"):
            # For low pip evaluation, return an empty hand with a pip value
            # The evaluator will use zeroCardsPipValue (e.g., 0 for best low)
            return True
        
        return False    
    
    def _find_hand_with_combinations(
        self,
        hole_cards: List[Card],
        community_cards: Dict[str, List[Card]],  # Changed from comm_cards list to full dict
        showdown_rules: dict,
        eval_type: EvaluationType
    ) -> Tuple[List[Card], List[Card]]:
        """Find best hand using 'combinations' configuration."""
        best_hand = None
        best_used_hole_cards = []
        
        for combo in showdown_rules["combinations"]:
            required_hole = combo["holeCards"]
            required_community = combo["communityCards"]
            
            # Get community cards for this combination
            community_subset = combo.get("community_subset", "default")
            comm_cards = community_cards.get(community_subset, [])
            
            # Skip if not enough cards available
            if len(hole_cards) < required_hole or len(comm_cards) < required_community:
                logger.debug(
                    f"Skipping combo with subset '{community_subset}': {required_hole} hole, "
                    f"{required_community} comm (have {len(hole_cards)} hole, {len(comm_cards)} comm)"
                )
                continue

            # Generate all possible combinations for this requirement
            hole_combos = (
                [tuple()] if required_hole == 0 
                else list(itertools.combinations(hole_cards, required_hole))
            )
            comm_combos = (
                [tuple()] if required_community == 0 
                else list(itertools.combinations(comm_cards, required_community))
            )

            # Try each combination
            for hole_combo in hole_combos:
                for comm_combo in comm_combos:
                    hand = list(hole_combo) + list(comm_combo)
                    if best_hand is None or evaluator.compare_hands(hand, best_hand, eval_type) > 0:
                        best_hand = hand
                        best_used_hole_cards = list(hole_combo)

        if best_hand:
            return best_hand, best_used_hole_cards
        else:
            logger.warning(f"No valid hand combinations found")
            return [], []
        
    def _find_hand_with_select_combinations(
        self,
        hole_cards: List[Card],
        community_cards: Dict[str, List[Card]],
        showdown_rules: dict,
        eval_type: EvaluationType
    ) -> Tuple[List[Card], List[Card]]:
        """Find best hand using communityCardSelectCombinations configuration."""
        select_combinations = showdown_rules.get("communityCardSelectCombinations", [])
        required_hole = showdown_rules.get("holeCards", 2)
        best_hand = None
        best_used_hole_cards = []
        
        # Process each select combination (a group of subset selections)
        for combination in select_combinations:
            # Build a list of card options for each subset in this combination
            subset_options = []
            
            # For each subset specification in this combination
            for subset_spec in combination:
                # Parse the specification
                if isinstance(subset_spec, list):
                    subset_name = subset_spec[0]
                    min_count = subset_spec[1]
                    max_count = subset_spec[2] if len(subset_spec) > 2 else min_count
                else:
                    # For backward compatibility, support string-only specs
                    subset_name = subset_spec
                    min_count = 1
                    max_count = 1
                
                # Get cards for this subset
                subset_cards = community_cards.get(subset_name, [])
                if not subset_cards:
                    logger.warning(f"Subset '{subset_name}' not found or empty")
                    continue
                
                # Generate all valid selections from this subset
                subset_selections = []
                for count in range(min_count, max_count + 1):
                    if count == 0:
                        subset_selections.append([])  # Empty selection is valid if min_count is 0
                    else:
                        subset_selections.extend(list(itertools.combinations(subset_cards, count)))
                
                # If no valid selections, this combination is invalid
                if not subset_selections:
                    break
                    
                subset_options.append(subset_selections)
            
            # If we have options for all subsets, generate all combinations
            if len(subset_options) == len(combination):
                # Generate all ways to combine one selection from each subset
                for combo_selections in itertools.product(*subset_options):
                    # Flatten the selections into a single list of cards
                    community_selection = [card for selection in combo_selections for card in selection]
                    
                    # Check if we have the right number of community cards in total
                    required_community = showdown_rules.get("communityCards", 5 - required_hole)
                    if len(community_selection) != required_community:
                        continue
                    
                    # Try all valid hole card combinations
                    for hole_combo in itertools.combinations(hole_cards, required_hole):
                        hand = list(hole_combo) + community_selection
                        
                        # Check if this hand is better than our current best
                        if best_hand is None or evaluator.compare_hands(hand, best_hand, eval_type) > 0:
                            best_hand = hand
                            best_used_hole_cards = list(hole_combo)
        
        return best_hand if best_hand else [], best_used_hole_cards        
        
    def _find_hand_with_any_cards(
        self,
        hole_cards: List[Card],
        comm_cards: List[Card],
        player: Player,
        showdown_rules: dict,
        eval_type: EvaluationType
    ) -> Tuple[List[Card], List[Card]]:
        """Find best hand using 'anyCards' configuration."""
        logger.debug(f"Finding hand with anyCards for player {player.id}")
        logger.debug(f"  Hole cards: {hole_cards}, Community cards: {comm_cards}")

        total_cards = showdown_rules["anyCards"]
        allowed_combinations = showdown_rules.get("holeCardsAllowed", [])
        padding = showdown_rules.get("padding", False)
        best_hand = None
        best_used_hole_cards = []
        
        if allowed_combinations:
            # Evaluate each allowed combination
            for combo in allowed_combinations:
                subset_cards = []
                for subset_name in combo["hole_subsets"]:
                    subset_cards.extend(player.hand.get_subset(subset_name))
                all_cards = subset_cards + comm_cards
                if len(all_cards) >= total_cards:
                    for hand_combo in itertools.combinations(all_cards, total_cards):
                        hand = list(hand_combo)
                        if best_hand is None or evaluator.compare_hands(hand, best_hand, eval_type) > 0:
                            best_hand = hand            
                            best_used_hole_cards = [c for c in hand if c in hole_cards]
        else:
            all_cards = hole_cards + comm_cards
            if len(all_cards) >= total_cards:
                for hand_combo in itertools.combinations(all_cards, total_cards):
                    hand = list(hand_combo)
                    if best_hand is None or evaluator.compare_hands(hand, best_hand, eval_type) > 0:
                        best_hand = hand
                        best_used_hole_cards = [c for c in hand if c in hole_cards]
        
        # If there are no community cards or exactly the right number of hole cards,
        # we can just use the hole cards (straight poker case)
        if not comm_cards and len(hole_cards) == total_cards:
            return hole_cards, hole_cards
        
        # If we are padding or have enough cards, return the best hand
        if len(all_cards) >= total_cards or padding:
            return best_hand or [], best_used_hole_cards
        
        # Not enough cards total and not padding
        logger.warning(
            f"Not enough cards: "
            f"Has {len(hole_cards)} hole cards and {len(comm_cards)} community cards "
            f"(need {total_cards} total)"
        )
        return [], []      

    def _find_hand_with_hole_card_options(
        self,
        hole_cards: List[Card],
        comm_cards: List[Card],
        showdown_rules: dict,
        eval_type: EvaluationType
    ) -> Tuple[List[Card], List[Card]]:
        """Find best hand with multiple hole card options."""
        hole_options = showdown_rules["holeCards"]
        comm_options = showdown_rules.get("communityCards", [])
        best_hand = None
        best_used_hole_cards = []
        
        # If communityCards is a single value, convert it to a list for consistency
        if isinstance(comm_options, int):
            comm_options = [comm_options]
        
        # Try each valid combination of hole and community card counts
        for i, required_hole in enumerate(hole_options):
            # For each hole card option, get the corresponding community card option
            # If comm_options is shorter than hole_options, use the last value
            comm_index = min(i, len(comm_options) - 1) if comm_options else 0
            required_community = comm_options[comm_index] if comm_options else 0
            
            # Skip if we don't have enough cards
            if len(hole_cards) < required_hole or len(comm_cards) < required_community:
                continue
            
            # Generate combinations for this option
            hole_combos = list(itertools.combinations(hole_cards, required_hole))
            community_combos = [tuple()] if required_community == 0 else list(itertools.combinations(comm_cards, required_community))
            
            # Try all combinations for this option
            for hole_combo in hole_combos:
                for comm_combo in community_combos:
                    # Combine the two sets of cards
                    hand = list(hole_combo) + list(comm_combo)
                    
                    # Compare with our best hand so far
                    if best_hand is None or evaluator.compare_hands(hand, best_hand, eval_type) > 0:
                        best_hand = hand
                        best_used_hole_cards = list(hole_combo)

        # If we found a valid hand, return it
        if best_hand:
            return best_hand, best_used_hole_cards
        else:
            logger.warning(f"No valid hand combinations found")
            return [], []      
        
    def _find_hand_with_community_combinations(
        self,
        hole_cards: List[Card],
        community_cards: Dict[str, List[Card]],
        showdown_rules: dict,
        eval_type: EvaluationType
    ) -> Tuple[List[Card], List[Card]]:
        """Find best hand using community card combinations."""
        combinations = showdown_rules["communityCardCombinations"]
        required_hole = showdown_rules.get("holeCards", 0)
        total_cards = showdown_rules.get("totalCards", 5)  # Default to 5 if not specified
        required_community = total_cards - required_hole
        best_hand = None
        best_used_hole_cards = []

        for combo in combinations:
            # Collect cards from all subsets in this combination
            comm_cards = []
            for subset in combo:
                if subset not in community_cards:
                    logger.debug(f"Subset '{subset}' not available for combination {combo}")
                    break
                comm_cards.extend(community_cards[subset])
            else:  # Proceed only if all subsets were found (no break occurred)
                if len(comm_cards) < required_community:
                    logger.warning(f"Combination {combo} has {len(comm_cards)} cards, need {required_community}")
                    continue

                # Generate combinations
                hole_combos = list(itertools.combinations(hole_cards, required_hole))
                community_combos = list(itertools.combinations(comm_cards, required_community))

                # Evaluate all combinations for this combination
                for hole_combo in hole_combos:
                    for comm_combo in community_combos:
                        hand = list(hole_combo) + list(comm_combo)
                        if best_hand is None or evaluator.compare_hands(hand, best_hand, eval_type) > 0:
                            best_hand = hand  
                            best_used_hole_cards = list(hole_combo)                            

        logger.debug(f'Best hand found using showdown rules: {best_hand}')
        return best_hand if best_hand else [], best_used_hole_cards        
    
    def _find_hand_with_hole_and_community(
        self,
        hole_cards: List[Card],
        comm_cards: List[Card],
        player: Player,
        showdown_rules: dict,
        eval_type: EvaluationType
    ) -> Tuple[List[Card], List[Card]]:
        """Find best hand using hole cards and community cards."""
        required_hole = showdown_rules.get("holeCards", 0)
        required_community = showdown_rules.get("communityCards", 0)
        allowed_combinations = showdown_rules.get("holeCardsAllowed", [])
        padding = showdown_rules.get("padding", False)
        best_hand = None
        best_used_hole_cards = []

        # Special case for "all" hole cards
        if required_hole == "all":
            required_hole = len(hole_cards)  # Use all available hole cards
            # Dynamically calculate community cards based on eval_type hand size
            total_cards_needed = HAND_SIZES.get(eval_type, 5)  # Default to 5 if eval_type not found
            # Cap by available community cards
            required_community = min(max(0, total_cards_needed - required_hole), len(comm_cards))
        else:
            required_hole = int(required_hole)  # Ensure numeric for other cases

        logger.debug(
            f"Required hole cards: {required_hole}, Required community cards: {required_community} "
            f"(have {len(hole_cards)} hole and {len(comm_cards)} community)"
        )

        # Filter hole cards based on allowed subsets if specified
        if allowed_combinations:
            usable_hole_cards = []
            for combo in allowed_combinations:
                for subset_name in combo["hole_subsets"]:
                    usable_hole_cards.extend(player.hand.get_subset(subset_name))
            hole_cards = usable_hole_cards  # Restrict to allowed subsets
        
        # Ensure we have enough cards to evaluate (if padding, we will get enough so OK)
        if (len(hole_cards) < required_hole or len(comm_cards) < required_community) and not padding:
            logger.warning(
                f"Not enough cards: "
                f"Has {len(hole_cards)} hole cards (need {required_hole}) and "
                f"{len(comm_cards)} community cards (need {required_community})"
            )
            return [], []
        
        # Generate combinations only for categories with requirements > 0
        # use the minimum of the cards we have and the required list, since padding will take care of the rest
        hole_combos = [tuple()] if required_hole == 0 else list(itertools.combinations(hole_cards, min(len(hole_cards),required_hole)))
        community_combos = [tuple()] if required_community == 0 else list(itertools.combinations(comm_cards, required_community))
        
        # Try all combinations and find the best
        for hole_combo in hole_combos:
            for comm_combo in community_combos:                 
                # Combine the two sets of cards
                hand = list(hole_combo) + list(comm_combo)
                
                # Compare with our best hand so far
                if best_hand is None:
                    best_hand = hand
                    best_used_hole_cards = list(hole_combo)
                else:
                    # Use compare_hands to determine which is better
                    if evaluator.compare_hands(hand, best_hand, eval_type) > 0:
                        best_hand = hand
                        best_used_hole_cards = list(hole_combo)
        
        logger.debug(f'Best hand found using showdown rules: {best_hand}')
        return best_hand if best_hand else [], best_used_hole_cards    
    
    def _find_hand_with_player_hand_size(
        self,
        hole_cards: List[Card],
        community_cards: Dict[str, List[Card]],
        showdown_rules: dict,
        eval_type: EvaluationType
    ) -> Tuple[List[Card], List[Card]]:
        """Find best hand using playerHandSize configuration."""
        player_hand_size_rules = showdown_rules["playerHandSize"]
        current_hand_size = len(hole_cards)
        
        # Look up the rule for the current hand size
        size_key = str(current_hand_size)
        if size_key not in player_hand_size_rules:
            logger.warning(f"No rule found for hand size {current_hand_size}")
            return [], []
        
        rule = player_hand_size_rules[size_key]
        required_hole = rule["holeCards"]
        required_community = rule["communityCards"]
        
        logger.info(f"Player has {current_hand_size} cards, using rule: {required_hole} hole + {required_community} community")
        
        # Get community cards based on the rule
        comm_cards = []
        if required_community > 0:
            # Check for single subset
            if "community_subset" in rule:
                subset_name = rule["community_subset"]
                subset_cards = community_cards.get(subset_name, [])
                if len(subset_cards) < required_community:
                    logger.warning(f"Not enough cards in subset '{subset_name}': need {required_community}, have {len(subset_cards)}")
                    return [], []
                comm_cards = subset_cards[:required_community]
                
            # Check for multiple subsets
            elif "community_subsets" in rule:
                subset_names = rule["community_subsets"]
                for subset_name in subset_names:
                    subset_cards = community_cards.get(subset_name, [])
                    comm_cards.extend(subset_cards)
                
                if len(comm_cards) < required_community:
                    logger.warning(f"Not enough cards in subsets {subset_names}: need {required_community}, have {len(comm_cards)}")
                    return [], []
                comm_cards = comm_cards[:required_community]
                
            # Fallback to default community cards
            else:
                default_cards = community_cards.get("default", [])
                if len(default_cards) < required_community:
                    logger.warning(f"Not enough default community cards: need {required_community}, have {len(default_cards)}")
                    return [], []
                comm_cards = default_cards[:required_community]
        
        # Validate hole cards
        if len(hole_cards) < required_hole:
            logger.warning(f"Not enough hole cards: need {required_hole}, have {len(hole_cards)}")
            return [], []
        
        # Generate combinations
        best_hand = None
        best_used_hole_cards = []
        
        hole_combos = list(itertools.combinations(hole_cards, required_hole))
        community_combos = [tuple()] if required_community == 0 else list(itertools.combinations(comm_cards, required_community))
        
        # Try all combinations and find the best
        for hole_combo in hole_combos:
            for comm_combo in community_combos:
                hand = list(hole_combo) + list(comm_combo)
                
                if best_hand is None or evaluator.compare_hands(hand, best_hand, eval_type) > 0:
                    best_hand = hand
                    best_used_hole_cards = list(hole_combo)
        
        logger.info(f"Best hand found with playerHandSize: {best_hand}")
        return best_hand if best_hand else [], best_used_hole_cards
    
    def _find_best_hand_for_player(
        self,
        player: Player,
        community_cards: Dict[str, List[Card]],
        showdown_rules: dict,
        eval_type: EvaluationType
    ) -> Tuple[List[Card], List[Card]]:
        """
        Find the best possible hand for a player according to the game rules.
        
        Args:
            player: The player
            community_cards: Available community cards
            showdown_rules: Showdown configuration from game rules
            eval_type: Type of hand evaluation to use
            
        Returns:
            Tuple of (best_hand, used_hole_cards) where:
                - best_hand: List of cards representing the player's best hand
                - used_hole_cards: List of hole cards used in the best hand
        """
        logger.info(f"Finding best hand for player {player.id} with eval_type '{eval_type}'")
        
        # Get and filter hole cards
        hole_cards = self._get_filtered_hole_cards(player, showdown_rules)
        if not hole_cards and "minimumCards" in showdown_rules:
            if self._handle_zero_cards_case(showdown_rules, eval_type):
                return [], []
        
        # Get community cards
        comm_cards = self._get_community_cards_for_player(player, community_cards, showdown_rules)
        
        # Apply wild cards if present
        if "wildCards" in showdown_rules:
            self.apply_wild_cards(player, comm_cards=comm_cards, wild_rules=showdown_rules["wildCards"])
        
        # NEW: Handle community subset requirements
        if "communitySubsetRequirements" in showdown_rules:
            return self._find_hand_with_subset_requirements(
                hole_cards, community_cards, showdown_rules, eval_type)
            
        # Handle different hand configuration types
        if "combinations" in showdown_rules:
            # Pass the full community_cards dictionary for combinations lookup
            return self._find_hand_with_combinations(
                hole_cards, community_cards, showdown_rules, eval_type)          
        
        if "communityCardSelectCombinations" in showdown_rules:
            return self._find_hand_with_select_combinations(
                hole_cards, community_cards, showdown_rules, eval_type)
            
        if "anyCards" in showdown_rules:
            return self._find_hand_with_any_cards(
                hole_cards, comm_cards, player, showdown_rules, eval_type)
        
        if "holeCards" in showdown_rules:
            if isinstance(showdown_rules["holeCards"], list):
                return self._find_hand_with_hole_card_options(
                    hole_cards, comm_cards, showdown_rules, eval_type)
            
            if "communityCardCombinations" in showdown_rules:
                return self._find_hand_with_community_combinations(
                    hole_cards, community_cards, showdown_rules, eval_type)
            
            # Standard hole cards + community cards case
            return self._find_hand_with_hole_and_community(
                hole_cards, comm_cards, player, showdown_rules, eval_type)
        
        if "playerHandSize" in showdown_rules:
            return self._find_hand_with_player_hand_size(
                hole_cards, community_cards, showdown_rules, eval_type)
        
        # Default: just use all hole cards
        return hole_cards, hole_cards    
    
    def _get_community_cards(self, community_cards: Dict[str, List[Card]], showdown_rules: dict) -> List[Card]:
        """
        Get community cards based on subset(s).
        
        Args:
            community_cards: Dictionary of community card subsets
            showdown_rules: Showdown rules configuration
            
        Returns:
            Combined list of community cards from specified subset(s)
        """
        community_subset = showdown_rules.get("community_subset", "default")
        result_cards = []
        
        # Handle both string and list formats for community_subset
        if isinstance(community_subset, str):
            subsets = [community_subset]
        else:
            subsets = community_subset
        
        # Collect cards from all specified subsets
        for subset in subsets:
            subset_cards = community_cards.get(subset, []) if community_cards else []
            result_cards.extend(subset_cards)
            
            if not subset_cards and subset != "default":
                logger.warning(f"Community subset '{subset}' not found")
        
        if not result_cards:
            # If no subsets were found but we need to use all available cards
            # (like in Hold'em), collect all cards from all subsets
            if not showdown_rules.get("community_subset"):
                logger.debug("No community subset specified; collecting cards from all subsets")
                for cards in community_cards.values():
                    result_cards.extend(cards)
        
        return result_cards

    def _get_community_cards_for_player(self, player: Player, community_cards: Dict[str, List[Card]], showdown_rules: dict) -> List[Card]:
        """Get community cards with player-specific wild card rules applied."""
        comm_cards = self._get_community_cards(community_cards, showdown_rules)
        
        # Apply player-specific wild ranks if game instance is available
        if hasattr(self, 'game') and hasattr(self.game, 'player_wild_ranks'):
            player_wild_rank = self.game.player_wild_ranks.get(player.id)
            if player_wild_rank:
                # Create copies with wild status for this player
                player_comm_cards = []
                for card in comm_cards:
                    if card.rank == player_wild_rank:
                        card_copy = Card(card.rank, card.suit, card.visibility)
                        card_copy.make_wild(WildType.NAMED)
                        player_comm_cards.append(card_copy)
                    else:
                        player_comm_cards.append(card)
                return player_comm_cards
        
        return comm_cards

    def apply_wild_cards(self, player: Player, comm_cards: List[Card], wild_rules: List[dict]) -> None:
        """Apply wild card rules to the player's hand and community cards."""
        logger.debug(f"Applying wild card rules for player {player.name} with community cards: {comm_cards} and wild rules: {wild_rules}") 
        for rule in wild_rules:
            rule_type = rule["type"]
            role = rule.get("role", "wild")

            # Re-evaluate conditional wild cards at showdown based on current visibility
            # (cards may have been exposed/flipped since deal time)
            if role == "conditional" and "condition" in rule:
                condition = rule["condition"]
                visibility_condition = condition.get("visibility")
                all_cards = player.hand.get_cards() + comm_cards

                for card in all_cards:
                    # Check if card matches the rule type
                    if rule_type == "joker" and card.rank == Rank.JOKER:
                        pass  # matches
                    elif rule_type == "rank" and card.rank == Rank(rule.get("rank", "R")):
                        pass  # matches
                    else:
                        continue

                    # Determine correct wild type based on current visibility
                    is_face_up = card.visibility == Visibility.FACE_UP
                    if (visibility_condition == "face up" and is_face_up) or \
                       (visibility_condition == "face down" and not is_face_up):
                        chosen_role = condition.get("true_role", "wild")
                    else:
                        chosen_role = condition.get("false_role", "wild")

                    chosen_wild_type = WildType.BUG if chosen_role == "bug" else WildType.NAMED
                    card.make_wild(chosen_wild_type)
                    logger.debug(f"Showdown conditional: {card} is {chosen_role} (face_up={is_face_up})")
                continue

            if rule_type == "last_community_card":
                match_type = rule.get("match", "rank")
                
                if match_type == "rank" and hasattr(self.game, 'dynamic_wild_rank') and self.game.dynamic_wild_rank:
                    # Use stored wild rank to make any cards dealt after the rule was set wild
                    target_rank = self.game.dynamic_wild_rank
                    role = rule.get("role", "wild")
                    wild_type = WildType.BUG if role == "bug" else WildType.NAMED
                    
                    for card in player.hand.get_cards() + comm_cards:
                        if card.rank == target_rank and not card.is_wild:
                            card.make_wild(wild_type)
                            logger.debug(f"Made {card} wild due to stored dynamic_wild_rank")
                
                # For match_type == "card", no additional action needed since only the specific card was made wild
                continue             

            # Handle other wild card types normally
            wild_type = WildType.BUG if role == "bug" else WildType.NAMED

            if rule_type == "joker":
                # Jokers are already marked as wild, adjust role if needed
                for card in player.hand.get_cards() + comm_cards:
                    if card.rank == Rank.JOKER:
                        card.make_wild(wild_type)

            elif rule_type == "rank":
                rank = Rank(rule["rank"])
                for card in player.hand.get_cards() + comm_cards:
                    if card.rank == rank:
                        card.make_wild(wild_type)                       

            elif rule_type == "lowest_community":
                subset = rule.get("subset", "default")
                if not comm_cards:
                    continue
                # Sort by rank (A low, K high)
                sorted_cards = sorted(comm_cards, key=lambda c: list(Rank).index(c.rank))
                lowest_rank = sorted_cards[0].rank
                for card in player.hand.get_cards() + comm_cards:
                    if card.rank == lowest_rank:
                        card.make_wild(wild_type)                  

            elif rule_type == "lowest_hole":
                subset = rule.get("subset", "default")
                visibility = Visibility.FACE_DOWN if rule.get("visibility") == "face down" else Visibility.FACE_UP
                hole_cards = player.hand.get_subset(subset) if subset != "default" else player.hand.get_cards()
                eligible_cards = [c for c in hole_cards if c.visibility == visibility]
                if not eligible_cards:
                    continue
                sorted_cards = sorted(eligible_cards, key=lambda c: list(Rank).index(c.rank))
                lowest_rank = sorted_cards[0].rank
                for card in player.hand.get_cards():  # Player-specific
                    if card.rank == lowest_rank:
                        card.make_wild(wild_type)                             

    def _find_best_players_for_special(self, active_players, criterion, suit, from_source, subsets):
        """
        Find the best players and their qualifying cards based on a special evaluation criterion.
        
        Args:
            active_players (list): List of Player objects.
            criterion (str): Evaluation criterion (e.g., "highest_rank").
            suit (str): Suit to evaluate (e.g., "spades").
            from_source (str): Source of cards (e.g., "hole_cards").
            subsets (list): Subsets of cards to consider (e.g., ["default"]).
        
        Returns:
            tuple: (list of Player objects, dict of player_id -> list of Card objects)
        """
        if criterion != "highest_rank" or from_source != "hole_cards":
            logger.warning(f"Unsupported special evaluation: criterion={criterion}, from={from_source}")
            return [], {}
    
        # Suit mapping for static suits
        suit_map = {
            "clubs": Suit.CLUBS,
            "diamonds": Suit.DIAMONDS,
            "hearts": Suit.HEARTS,
            "spades": Suit.SPADES,
            "club": Suit.CLUBS,
            "diamond": Suit.DIAMONDS,
            "heart": Suit.HEARTS,
            "spade": Suit.SPADES,
            "joker": Suit.JOKER,
            "c": Suit.CLUBS,
            "d": Suit.DIAMONDS,
            "h": Suit.HEARTS,
            "s": Suit.SPADES,
            "j": Suit.JOKER
        }
        
        # Determine the suit enum
        if suit == "river_card_suit":
            try:
                community_cards = self.table.community_cards.get('default', [])
                if not community_cards:
                    logger.error("No community cards available to determine river card suit")
                    return [], {}
                river_card = community_cards[-1]  # Last card is the river
                suit_enum = river_card.suit
                suit_name = river_card.suit.name.lower()  # For logging/description
            except IndexError:
                logger.error("Failed to access river card from community cards")
                return [], {}
        elif suit:
            try:
                suit_enum = suit_map[suit.lower()]
                suit_name = suit  # Use the JSON-provided suit name for description
            except KeyError:
                logger.error(f"Invalid suit specified: {suit}")
                return [], {}
        else:
            suit_enum = None
            suit_name = ""
            
        best_rank_index = len(BASE_RANKS)  # Worst possible index (lower index = better rank)
        best_players = []
        best_cards_dict = {}  # player_id -> list of qualifying cards
        
        for player in active_players:
            if from_source == "hole_cards":
                hole_cards = player.hand.get_cards()
                if suit_enum:
                    suit_cards = [card for card in hole_cards if card.suit == suit_enum]
                else:
                    suit_cards = hole_cards  # No suit filter if not specified

                if suit_cards:
                    highest_card = min(suit_cards, key=lambda c: BASE_RANKS.index(c.rank.value))
                    rank_index = BASE_RANKS.index(highest_card.rank.value)
                    if rank_index < best_rank_index:
                        best_rank_index = rank_index
                        best_players = [player]
                        best_cards_dict = {player.id: [highest_card]}
                    elif rank_index == best_rank_index:
                        best_players.append(player)
                        best_cards_dict[player.id] = [highest_card]
        
        logger.debug(f"Best players for {suit} {criterion}: {[p.id for p in best_players]} with cards: {best_cards_dict}")
        return best_players, best_cards_dict
        
    def _award_special_pot(self, best_players, main_pot, side_pots, pot_percentage, config_name):
        """
        Award a pot portion to players based on a special evaluation.
        
        Args:
            best_players (list): List of Player objects who won.
            main_pot (int): Main pot amount.
            side_pots (list): List of side pot amounts.
            pot_percentage (float): Percentage of the pot for this configuration.
            config_name (str): Name of the configuration (e.g., "Low Hand").
        
        Returns:
            list: List of PotResult objects.
        """
        pot_results = []
        winner_ids = [p.id for p in best_players]
        
        # Main pot portion
        main_amount = int(main_pot * pot_percentage)
        if main_amount > 0:
            self.betting.award_pots(best_players, None, main_amount)
            pot_result = PotResult(
                amount=main_amount,
                winners=winner_ids,
                pot_type="main",
                hand_type=config_name,
                eligible_players=set(p.id for p in best_players)
            )
            pot_results.append(pot_result)

        # Side pots portion
        for i, side_amount in enumerate(side_pots):
            portion_amount = int(side_amount * pot_percentage)
            if portion_amount > 0:
                eligible_ids = self.betting.get_side_pot_eligible_players(i)
                eligible_winners = [p.id for p in best_players if p.id in eligible_ids]
                if eligible_winners:
                    winners_for_pot = [p for p in best_players if p.id in eligible_ids]
                    self.betting.award_pots(winners_for_pot, i, portion_amount)
                    pot_result = PotResult(
                        amount=portion_amount,
                        winners=eligible_winners,
                        pot_type="side",
                        hand_type=config_name,
                        side_pot_index=i,
                        eligible_players=set(eligible_ids)
                    )
                    pot_results.append(pot_result)
        
        logger.debug(f"Awarded {config_name} pot portion to {winner_ids}")
        return pot_results     

    def _redistribute_unawarded_pot(
        self,
        original_main_pot: int,
        original_side_pots: List[int],
        remaining_percentage: float,
        awarded_pot_results: List[PotResult]
    ) -> None:
        """
        Redistribute unawarded pot portions to existing winners.
        
        Args:
            original_main_pot: Original main pot amount
            original_side_pots: Original side pot amounts
            remaining_percentage: Percentage of pot remaining to award
            awarded_pot_results: Pot results that have been awarded so far
        """
        # Group awarded pots by type
        main_pots = [p for p in awarded_pot_results if p.pot_type == "main" and p.winners]
        side_pots = {}
        for pot in [p for p in awarded_pot_results if p.pot_type == "side" and p.winners]:
            if pot.side_pot_index not in side_pots:
                side_pots[pot.side_pot_index] = []
            side_pots[pot.side_pot_index].append(pot)
        
        # Redistribute main pot
        if main_pots:
            # Calculate the exact remaining amount instead of using percentage
            total_awarded = sum(pot.amount for pot in main_pots)            
            additional_main = original_main_pot - total_awarded

            if additional_main > 0:
                for pot in main_pots:
                    # Find players who won this pot
                    winners = [self.table.players[pid] for pid in pot.winners]
                    
                    # Award additional amount
                    self.betting.award_pots(winners, None, additional_main)
                    
                    # Update pot amount in result
                    pot.amount += additional_main
                    
                    logger.info(f"Redistributed ${additional_main} to {[p.name for p in winners]} (no qualifying low hand)")
        
        # Redistribute side pots
        for idx, pots in side_pots.items():
            if idx < len(original_side_pots):
                total_awarded = sum(pot.amount for pot in pots)
                additional_side = original_side_pots[idx] - total_awarded
                
                for pot in pots:
                    # Find players who won this pot
                    winners = [self.table.players[pid] for pid in pot.winners]
                    
                    # Award additional amount
                    self.betting.award_pots(winners, idx, additional_side)
                    
                    # Update pot amount in result
                    pot.amount += additional_side
                    
                    logger.info(f"Redistributed ${additional_side} to {[p.name for p in winners]} for side pot {idx} (no qualifying low hand)")

    def _redistribute_exact_pot(
        self,
        original_main_pot: int,
        original_side_pots: List[int],
        awarded_pot_results: List[PotResult]
    ) -> None:
        """
        Redistribute unawarded pot portions to existing winners, using exact amounts.
        
        Args:
            original_main_pot: Original main pot amount
            original_side_pots: Original side pot amounts
            awarded_pot_results: Pot results that have been awarded so far
        """
        # Group awarded pots by type
        main_pots = [p for p in awarded_pot_results if p.pot_type == "main" and p.winners]
        side_pots = {}
        for pot in [p for p in awarded_pot_results if p.pot_type == "side" and p.winners]:
            if pot.side_pot_index not in side_pots:
                side_pots[pot.side_pot_index] = []
            side_pots[pot.side_pot_index].append(pot)
        
        # Redistribute main pot
        if main_pots:
            # Calculate the exact remaining amount
            total_awarded = sum(pot.amount for pot in main_pots)
            additional_main = original_main_pot - total_awarded
            
            if additional_main > 0:
                for pot in main_pots:
                    # Find players who won this pot
                    winners = [self.table.players[pid] for pid in pot.winners]
                    
                    # Award additional amount
                    self.betting.award_pots(winners, None, additional_main)
                    
                    # Update pot amount in result
                    pot.amount += additional_main
                    
                    logger.info(f"Redistributed ${additional_main} to {[p.name for p in winners]} (no qualifying low hand)")
        
        # Redistribute side pots
        for idx, pots in side_pots.items():
            if idx < len(original_side_pots):
                total_awarded = sum(pot.amount for pot in pots)
                additional_side = original_side_pots[idx] - total_awarded
                
                if additional_side > 0:
                    for pot in pots:
                        # Find players who won this pot
                        winners = [self.table.players[pid] for pid in pot.winners]
                        
                        # Award additional amount
                        self.betting.award_pots(winners, idx, additional_side)
                        
                        # Update pot amount in result
                        pot.amount += additional_side
                        
                        logger.info(f"Redistributed ${additional_side} to {[p.name for p in winners]} for side pot {idx} (no qualifying low hand)")

    def _handle_split_among_active(self, players: List[Player], main_pot: int, side_pots: List[int]) -> None:
        """
        Split the pot among all active players when no qualifier is met.
        
        Args:
            players: List of active players
            main_pot: Main pot amount
            side_pots: List of side pot amounts
        """
        # Award side pots first - only to eligible players
        for i, pot_amount in enumerate(side_pots):
            if pot_amount <= 0:
                continue
                
            eligible_ids = self.betting.get_side_pot_eligible_players(i)
            eligible_players = [p for p in players if p.id in eligible_ids]
            
            if eligible_players:
                # Split this pot among eligible players
                amount_per_player = pot_amount // len(eligible_players)
                remainder = pot_amount % len(eligible_players)
                
                for j, player in enumerate(eligible_players):
                    award = amount_per_player + (1 if j < remainder else 0)
                    player.stack += award
                    logger.info(f"Split ${award} to {player.name} from side pot {i} (no qualifier)")
        
        # Award main pot to all active players
        if main_pot > 0:
            amount_per_player = main_pot // len(players)
            remainder = main_pot % len(players)
            
            for i, player in enumerate(players):
                award = amount_per_player + (1 if i < remainder else 0)
                player.stack += award
                logger.info(f"Split ${award} to {player.name} from main pot (no qualifier)")    

    def _award_alternate_pots(
        self,
        players: List[Player],
        hand_results: Dict[str, HandResult],
        eval_type: EvaluationType,
        hand_config: dict,
        original_main_pot: int,
        original_side_pots: List[int]
    ) -> Tuple[List[PotResult], bool]:
        """
        Award pots using an alternate evaluation when no qualifier is met.
        
        Args:
            players: List of active players
            hand_results: Dictionary of player hand results
            eval_type: Type of evaluation being used
            hand_config: Hand configuration
            original_main_pot: Original main pot amount
            original_side_pots: Original side pot amounts
            
        Returns:
            Tuple of (pot results, had_winners)
        """
        # Similar implementation to _award_pots_for_config but without pot_percentage
        # and using the full pot amounts since this is the fallback evaluation
        
        pot_results = []
        player_hands = {
            player_id: result.cards 
            for player_id, result in hand_results.items()
        }
        
        # Convert players to dictionary for easier lookup
        player_dict = {player.id: player for player in players}
        
        # Qualifier for the alternate hand type (if any)
        qualifier = hand_config.get('qualifier', None)
        
        had_winners = False
        
        # Award side pots first
        for i in range(len(original_side_pots)):
            eligible_ids = self.betting.get_side_pot_eligible_players(i)
            eligible_players = [player_dict[pid] for pid in eligible_ids if pid in player_dict]
            
            # Find qualified players
            qualified_players = []
            for player in eligible_players:
                if player.id not in player_hands:
                    continue
                    
                # Check qualifier if specified
                if qualifier:
                    hand = player_hands[player.id]
                    result = evaluator.evaluate_hand(hand, eval_type)
                    if not result or (result.rank > qualifier[0]) or (result.rank == qualifier[0] and result.ordered_rank > qualifier[1]):
                        continue
                
                qualified_players.append(player)
            
            if qualified_players:
                # Find best hand among eligible players
                winners = self._find_winners(qualified_players, hand_results, eval_type, self.rules.showdown)
                if winners:
                    had_winners = True
                    
                    # Award the full side pot
                    pot_amount = original_side_pots[i]
                    self.betting.award_pots(winners, i, pot_amount)
                    
                    # Track the result
                    pot_result = PotResult(
                        amount=pot_amount,
                        winners=[p.id for p in winners],
                        pot_type="side",
                        hand_type=hand_config.get('name', 'Alternate Hand'),
                        side_pot_index=i,
                        eligible_players=eligible_ids
                    )
                    pot_results.append(pot_result)
        
        # Award main pot
        eligible_players = [player_dict[pid] for pid in player_dict.keys()]
        
        # Find qualified players
        qualified_players = []
        for player in eligible_players:
            if player.id not in player_hands:
                continue
                
            # Check qualifier if specified
            if qualifier:
                hand = player_hands[player.id]
                result = evaluator.evaluate_hand(hand, eval_type)
                if not result or (result.rank > qualifier[0]) or (result.rank == qualifier[0] and result.ordered_rank > qualifier[1]):
                    continue
            
            qualified_players.append(player)
        
        if qualified_players:
            winners = self._find_winners(qualified_players, hand_results, eval_type, self.rules.showdown)
            if winners:
                had_winners = True
                
                # Award the full main pot
                pot_amount = original_main_pot
                self.betting.award_pots(winners, None, pot_amount)
                
                # Track the result
                pot_result = PotResult(
                    amount=pot_amount,
                    winners=[p.id for p in winners],
                    pot_type="main",
                    hand_type=hand_config.get('name', 'Alternate Hand'),
                    eligible_players=set(p.id for p in eligible_players)
                )
                pot_results.append(pot_result)
        
        return pot_results, had_winners    