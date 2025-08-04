"""Game action logging service for poker games."""

import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)

@dataclass
class GameAction:
    """Represents a single game action for logging."""
    action_type: str  # 'forced_bet', 'player_action', 'deal', 'showdown', etc.
    player_id: Optional[str]
    player_name: Optional[str]
    message: str
    details: Dict[str, Any]
    timestamp: datetime
    step: int
    game_state: str

class GameActionLogger:
    """Logs and formats game actions for display."""
    
    def __init__(self):
        self.actions: Dict[str, List[GameAction]] = {}  # table_id -> actions
        self.last_broadcast_index: Dict[str, int] = {}  # table_id -> last broadcast action index
    
    def log_forced_bets(self, table_id: str, step: int, game_state: str, forced_bets: List[Dict]) -> List[GameAction]:
        """Log forced betting actions (blinds, antes, bring-ins)."""
        actions = []
        
        for bet in forced_bets:
            player_id = bet.get('player_id')
            player_name = bet.get('player_name', 'Unknown')
            bet_type = bet.get('bet_type', 'bet')
            amount = bet.get('amount', 0)
            
            # Format message based on bet type
            if bet_type == 'small_blind':
                message = f"{player_name} posts small blind ${amount}"
            elif bet_type == 'big_blind':
                message = f"{player_name} posts big blind ${amount}"
            elif bet_type == 'ante':
                message = f"{player_name} posts ante ${amount}"
            elif bet_type == 'bring_in':
                message = f"{player_name} brings in for ${amount}"
            else:
                message = f"{player_name} posts {bet_type} ${amount}"
            
            action = GameAction(
                action_type='forced_bet',
                player_id=player_id,
                player_name=player_name,
                message=message,
                details=bet,
                timestamp=datetime.now(),
                step=step,
                game_state=game_state
            )
            
            actions.append(action)
            self._add_action(table_id, action)
            logger.info(f"Logged forced bet: {message}")
        
        return actions
    
    def log_player_action(self, table_id: str, step: int, game_state: str, 
                         player_id: str, player_name: str, action_type: str, 
                         amount: Optional[int] = None, details: Dict = None) -> GameAction:
        """Log a player's voluntary action."""
        details = details or {}
        
        # Format message based on action type
        if action_type == 'fold':
            message = f"{player_name} folds"
        elif action_type == 'check':
            message = f"{player_name} checks"
        elif action_type == 'call':
            if amount:
                # For calls, we want to show the total bet amount, not just the additional amount
                # The amount passed here might be the additional amount, but we want to show the total call amount
                # We'll use the amount as provided, assuming it represents the total call amount
                message = f"{player_name} calls ${amount}"
            else:
                message = f"{player_name} calls"
        elif action_type == 'bet':
            message = f"{player_name} bets ${amount}"
        elif action_type == 'raise':
            message = f"{player_name} raises to ${amount}"
        elif action_type == 'all_in':
            message = f"{player_name} is all-in for ${amount}"
        else:
            message = f"{player_name} {action_type}" + (f" ${amount}" if amount else "")
        
        action = GameAction(
            action_type='player_action',
            player_id=player_id,
            player_name=player_name,
            message=message,
            details={'action': action_type, 'amount': amount, **details},
            timestamp=datetime.now(),
            step=step,
            game_state=game_state
        )
        
        self._add_action(table_id, action)
        logger.info(f"Logged player action: {message}")
        return action
    
    def log_forced_bet_action(self, table_id: str, step: int, game_state: str,
                             player_name: str, bet_type: str, amount: int) -> GameAction:
        """Log a single forced bet action (captured from game engine logs)."""
        
        # Format message based on bet type
        if bet_type == 'small_blind':
            message = f"{player_name} posts small blind ${amount}"
        elif bet_type == 'big_blind':
            message = f"{player_name} posts big blind ${amount}"
        elif bet_type == 'ante':
            message = f"{player_name} posts ante ${amount}"
        elif bet_type == 'dealer_blind':
            message = f"{player_name} posts dealer blind ${amount}"
        else:
            message = f"{player_name} posts {bet_type} ${amount}"
        
        action = GameAction(
            action_type='forced_bet',
            player_id=None,  # We don't have player_id from the log message
            player_name=player_name,
            message=message,
            details={'bet_type': bet_type, 'amount': amount},
            timestamp=datetime.now(),
            step=step,
            game_state=game_state
        )
        
        self._add_action(table_id, action)
        logger.info(f"Logged forced bet action: {message}")
        return action
    
    def log_dealing(self, table_id: str, step: int, game_state: str, 
                   deal_type: str, details: Dict = None) -> GameAction:
        """Log card dealing actions."""
        details = details or {}
        
        # Format message based on deal type
        if deal_type == 'hole_cards':
            num_cards = details.get('cards_per_player', 2)
            message = f"Dealing {num_cards} hole cards to each player"
        elif deal_type == 'flop':
            message = "Dealing the flop"
        elif deal_type == 'turn':
            message = "Dealing the turn"
        elif deal_type == 'river':
            message = "Dealing the river"
        elif deal_type == 'community':
            num_cards = details.get('num_cards', 1)
            message = f"Dealing {num_cards} community card{'s' if num_cards != 1 else ''}"
        else:
            message = f"Dealing {deal_type}"
        
        action = GameAction(
            action_type='deal',
            player_id=None,
            player_name=None,
            message=message,
            details={'deal_type': deal_type, **details},
            timestamp=datetime.now(),
            step=step,
            game_state=game_state
        )
        
        self._add_action(table_id, action)
        logger.info(f"Logged dealing: {message}")
        return action
    
    def log_phase_change(self, table_id: str, step: int, old_state: str, new_state: str, 
                        phase_name: str = None) -> GameAction:
        """Log game phase changes."""
        if phase_name:
            message = f"*** {phase_name.upper()} ***"
        else:
            message = f"*** {new_state.upper()} ***"
        
        action = GameAction(
            action_type='phase_change',
            player_id=None,
            player_name=None,
            message=message,
            details={'old_state': old_state, 'new_state': new_state, 'phase_name': phase_name},
            timestamp=datetime.now(),
            step=step,
            game_state=new_state
        )
        
        self._add_action(table_id, action)
        logger.info(f"Logged phase change: {message}")
        return action
    
    def log_showdown_result(self, table_id: str, step: int, game_state: str,
                           winners: List[Dict], pot_amount: int, details: Dict = None) -> GameAction:
        """Log showdown results."""
        details = details or {}
        
        if len(winners) == 1:
            winner = winners[0]
            message = f"{winner['player_name']} wins ${pot_amount} with {winner.get('hand_description', 'the best hand')}"
        else:
            winner_names = [w['player_name'] for w in winners]
            message = f"{', '.join(winner_names)} split the pot of ${pot_amount}"
        
        action = GameAction(
            action_type='showdown',
            player_id=None,
            player_name=None,
            message=message,
            details={'winners': winners, 'pot_amount': pot_amount, **details},
            timestamp=datetime.now(),
            step=step,
            game_state=game_state
        )
        
        self._add_action(table_id, action)
        logger.info(f"Logged showdown: {message}")
        return action
    
    def get_recent_actions(self, table_id: str, limit: int = 50) -> List[GameAction]:
        """Get recent actions for a table."""
        if table_id not in self.actions:
            return []
        
        return self.actions[table_id][-limit:]
    
    def get_new_actions_for_broadcast(self, table_id: str) -> List[GameAction]:
        """Get actions that haven't been broadcast yet."""
        if table_id not in self.actions:
            return []
        
        last_index = self.last_broadcast_index.get(table_id, -1)
        new_actions = self.actions[table_id][last_index + 1:]
        
        # Update the last broadcast index
        if new_actions:
            self.last_broadcast_index[table_id] = len(self.actions[table_id]) - 1
        
        return new_actions
    
    def clear_table_actions(self, table_id: str):
        """Clear all actions for a table."""
        if table_id in self.actions:
            del self.actions[table_id]
        if table_id in self.last_broadcast_index:
            del self.last_broadcast_index[table_id]
        logger.info(f"Cleared actions for table {table_id}")
    
    def _add_action(self, table_id: str, action: GameAction):
        """Add an action to the table's action log."""
        if table_id not in self.actions:
            self.actions[table_id] = []
        
        self.actions[table_id].append(action)
        
        # Keep only the last 100 actions per table to prevent memory issues
        if len(self.actions[table_id]) > 100:
            self.actions[table_id] = self.actions[table_id][-100:]
    
    def format_actions_for_chat(self, actions: List[GameAction]) -> List[Dict]:
        """Format actions for chat display."""
        formatted = []
        
        for action in actions:
            formatted.append({
                'type': 'game_action',
                'message': action.message,
                'timestamp': action.timestamp.isoformat(),
                'action_type': action.action_type,
                'player_id': action.player_id,
                'player_name': action.player_name,
                'step': action.step,
                'game_state': action.game_state
            })
        
        return formatted

# Global game action logger instance
game_action_logger = GameActionLogger()