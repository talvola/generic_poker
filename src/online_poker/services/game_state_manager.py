"""Service for managing game state views and synchronization."""

import logging
from typing import Dict, List, Optional, Set, Any, Tuple
from datetime import datetime
from flask import current_app

from ..models.game_state_view import (
    GameStateView, PlayerView, PotInfo, ActionOption, GamePhase, 
    ActionType, GameStateUpdate, HandResult
)
from ..models.table_access import TableAccess
from ..services.game_orchestrator import game_orchestrator, GameSession
from ..services.table_access_manager import TableAccessManager
from ..services.user_manager import UserManager
from ..database import db
from generic_poker.game.game_state import GameState, PlayerAction
from generic_poker.game.game import Game


logger = logging.getLogger(__name__)


class GameStateManager:
    """Service for managing game state views and synchronization."""
    
    @staticmethod
    def generate_game_state_view(table_id: str, viewer_id: str, is_spectator: bool = False) -> Optional[GameStateView]:
        """Generate a game state view for a specific player/spectator.
        
        Args:
            table_id: ID of the table
            viewer_id: ID of the player/spectator viewing the state
            is_spectator: Whether the viewer is a spectator
            
        Returns:
            GameStateView for the viewer or None if not found
        """
        try:
            # Get game session
            session = game_orchestrator.get_session(table_id)
            if not session:
                logger.warning(f"No game session found for table {table_id}")
                return None
            
            # Get table players
            table_players = TableAccessManager.get_table_players(table_id)
            if not table_players:
                logger.warning(f"No players found for table {table_id}")
                return None
            
            # Generate player views
            player_views = []
            for player_info in table_players:
                if player_info['is_spectator']:
                    continue  # Skip spectators in player list
                
                player_view = GameStateManager._create_player_view(
                    player_info, session, viewer_id, is_spectator
                )
                if player_view:
                    player_views.append(player_view)
            
            # Sort players by seat number
            player_views.sort(key=lambda p: p.seat_number)
            
            # Get community cards (visible to all)
            community_cards = GameStateManager._get_community_cards(session)
            
            # Get pot information
            pot_info = GameStateManager._get_pot_info(session)
            
            # Get current player
            current_player = GameStateManager._get_current_player(session)
            
            # Get valid actions for the viewer (if they're a player and it's their turn)
            valid_actions = []
            if not is_spectator and current_player == viewer_id:
                valid_actions = GameStateManager._get_valid_actions(session, viewer_id)
            
            # Determine game phase
            game_phase = GameStateManager._get_game_phase(session)
            
            # Get table information
            table_info = GameStateManager._get_table_info(session)
            
            # Create game state view
            game_state_view = GameStateView(
                table_id=table_id,
                session_id=session.session_id,
                viewer_id=viewer_id,
                players=player_views,
                community_cards=community_cards,
                pot_info=pot_info,
                current_player=current_player,
                valid_actions=valid_actions,
                game_phase=game_phase,
                hand_number=session.hands_played + 1,  # Current hand number
                is_spectator=is_spectator,
                dealer_position=GameStateManager._get_dealer_position(session),
                small_blind_position=GameStateManager._get_small_blind_position(session),
                big_blind_position=GameStateManager._get_big_blind_position(session),
                table_info=table_info
            )
            
            return game_state_view
            
        except Exception as e:
            logger.error(f"Failed to generate game state view for table {table_id}, viewer {viewer_id}: {e}")
            return None
    
    @staticmethod
    def _create_player_view(player_info: Dict[str, Any], session: GameSession, 
                           viewer_id: str, is_spectator: bool) -> Optional[PlayerView]:
        """Create a player view from player information."""
        try:
            user_id = player_info['user_id']
            
            # Determine if this player's cards should be visible
            show_cards = (user_id == viewer_id and not is_spectator) or GameStateManager._should_show_cards(session, user_id)
            
            # Get player cards
            cards = []
            if show_cards:
                cards = GameStateManager._get_player_cards(session, user_id)
            
            # Check if player is connected
            is_connected = user_id in session.connected_players
            
            # Get current player status from game
            is_current_player = GameStateManager._is_current_player(session, user_id)
            
            # Get player's last action
            last_action = GameStateManager._get_last_action(session, user_id)
            
            # Get time to act (if current player)
            time_to_act = None
            if is_current_player:
                time_to_act = GameStateManager._get_time_to_act(session, user_id)
            
            # Create player view
            player_view = PlayerView(
                user_id=user_id,
                username=player_info['username'],
                position=GameStateManager._get_position_name(player_info['seat_number']),
                seat_number=player_info['seat_number'],
                chip_stack=player_info['current_stack'] or 0,
                current_bet=GameStateManager._get_current_bet(session, user_id),
                cards=cards,
                is_active=GameStateManager._is_player_active(session, user_id),
                is_current_player=is_current_player,
                is_bot=False,  # TODO: Implement bot detection
                is_connected=is_connected,
                is_all_in=GameStateManager._is_all_in(session, user_id),
                has_folded=GameStateManager._has_folded(session, user_id),
                last_action=last_action,
                time_to_act=time_to_act
            )
            
            return player_view
            
        except Exception as e:
            logger.error(f"Failed to create player view for {player_info.get('user_id', 'unknown')}: {e}")
            return None
    
    @staticmethod
    def _get_community_cards(session: GameSession) -> Dict[str, List[str]]:
        """Get community cards from the game session."""
        try:
            if not session.game or not hasattr(session.game, 'table'):
                return {}
            
            # Get community cards from the game engine
            community_cards = {}
            
            # Try to get community cards from the game table
            if hasattr(session.game.table, 'community_cards'):
                cards = session.game.table.community_cards
                if cards:
                    community_cards['board'] = [str(card) for card in cards]
            
            return community_cards
            
        except Exception as e:
            logger.error(f"Failed to get community cards: {e}")
            return {}
    
    @staticmethod
    def _get_pot_info(session: GameSession) -> PotInfo:
        """Get pot information from the game session."""
        try:
            if not session.game or not hasattr(session.game, 'table'):
                return PotInfo(0)
            
            # Get pot information from the game engine
            main_pot = 0
            side_pots = []
            current_bet = 0
            
            # Try to get pot information from the game
            if hasattr(session.game.table, 'pot'):
                pot = session.game.table.pot
                if hasattr(pot, 'total'):
                    main_pot = pot.total
                if hasattr(pot, 'side_pots'):
                    side_pots = [{'amount': sp.total, 'eligible_players': list(sp.eligible_players)} 
                               for sp in pot.side_pots]
            
            # Get current bet level
            if hasattr(session.game.table, 'current_bet'):
                current_bet = session.game.table.current_bet
            
            return PotInfo(
                main_pot=main_pot,
                side_pots=side_pots,
                current_bet=current_bet
            )
            
        except Exception as e:
            logger.error(f"Failed to get pot info: {e}")
            return PotInfo(0)
    
    @staticmethod
    def _get_current_player(session: GameSession) -> Optional[str]:
        """Get the current player to act."""
        try:
            if not session.game or not hasattr(session.game, 'table'):
                return None
            
            # Get current player from the game engine
            if hasattr(session.game.table, 'current_player'):
                current_player = session.game.table.current_player
                if current_player and hasattr(current_player, 'id'):
                    return current_player.id
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get current player: {e}")
            return None
    
    @staticmethod
    def _get_valid_actions(session: GameSession, user_id: str) -> List[ActionOption]:
        """Get valid actions for a player."""
        try:
            if not session.game:
                return []
            
            # Get valid actions from the game engine
            valid_actions = []
            
            # This would typically come from the game engine's action validation
            # For now, provide basic actions based on game state
            if GameStateManager._is_current_player(session, user_id):
                # Basic actions - this should be enhanced with actual game logic
                valid_actions = [
                    ActionOption(ActionType.FOLD, display_text="Fold"),
                    ActionOption(ActionType.CHECK, display_text="Check"),
                    ActionOption(ActionType.CALL, min_amount=0, max_amount=1000, display_text="Call"),
                    ActionOption(ActionType.BET, min_amount=1, max_amount=1000, display_text="Bet"),
                    ActionOption(ActionType.RAISE, min_amount=1, max_amount=1000, display_text="Raise")
                ]
            
            return valid_actions
            
        except Exception as e:
            logger.error(f"Failed to get valid actions for {user_id}: {e}")
            return []
    
    @staticmethod
    def _get_game_phase(session: GameSession) -> GamePhase:
        """Get the current game phase."""
        try:
            if not session.game:
                return GamePhase.WAITING
            
            # Map game engine state to our game phase
            game_state = session.game.state
            
            if game_state == GameState.WAITING:
                return GamePhase.WAITING
            elif game_state == GameState.DEALING:
                return GamePhase.DEALING
            elif game_state == GameState.BETTING:
                # Determine betting round based on community cards
                community_cards = GameStateManager._get_community_cards(session)
                board_cards = community_cards.get('board', [])
                
                if len(board_cards) == 0:
                    return GamePhase.PREFLOP
                elif len(board_cards) == 3:
                    return GamePhase.FLOP
                elif len(board_cards) == 4:
                    return GamePhase.TURN
                elif len(board_cards) == 5:
                    return GamePhase.RIVER
                else:
                    return GamePhase.PREFLOP
            elif game_state == GameState.SHOWDOWN:
                return GamePhase.SHOWDOWN
            elif game_state == GameState.COMPLETE:
                return GamePhase.COMPLETE
            else:
                return GamePhase.WAITING
                
        except Exception as e:
            logger.error(f"Failed to get game phase: {e}")
            return GamePhase.WAITING
    
    @staticmethod
    def _get_table_info(session: GameSession) -> Dict[str, Any]:
        """Get table information."""
        try:
            table_info = {
                'name': session.table.name,
                'variant': session.table.variant,
                'betting_structure': session.table.betting_structure,
                'stakes': session.table.get_stakes(),
                'max_players': session.table.max_players,
                'is_private': session.table.is_private
            }
            return table_info
            
        except Exception as e:
            logger.error(f"Failed to get table info: {e}")
            return {}
    
    # Helper methods for player status
    @staticmethod
    def _should_show_cards(session: GameSession, user_id: str) -> bool:
        """Determine if a player's cards should be shown (e.g., at showdown)."""
        try:
            # Show cards at showdown or if game is complete
            game_phase = GameStateManager._get_game_phase(session)
            return game_phase in [GamePhase.SHOWDOWN, GamePhase.COMPLETE]
        except:
            return False
    
    @staticmethod
    def _get_player_cards(session: GameSession, user_id: str) -> List[str]:
        """Get a player's hole cards."""
        try:
            if not session.game or not hasattr(session.game, 'table'):
                return []
            
            # Get player cards from the game engine
            if hasattr(session.game.table, 'players') and user_id in session.game.table.players:
                player = session.game.table.players[user_id]
                if hasattr(player, 'cards'):
                    return [str(card) for card in player.cards]
            
            return []
            
        except Exception as e:
            logger.error(f"Failed to get player cards for {user_id}: {e}")
            return []
    
    @staticmethod
    def _is_current_player(session: GameSession, user_id: str) -> bool:
        """Check if a player is the current player to act."""
        current_player = GameStateManager._get_current_player(session)
        return current_player == user_id
    
    @staticmethod
    def _get_last_action(session: GameSession, user_id: str) -> Optional[str]:
        """Get a player's last action."""
        # This would typically come from the game engine's action history
        # For now, return None - this should be implemented with actual game logic
        return None
    
    @staticmethod
    def _get_time_to_act(session: GameSession, user_id: str) -> Optional[int]:
        """Get time remaining for a player to act."""
        # This would typically be managed by a timer system
        # For now, return a default timeout - this should be implemented with actual timing logic
        return 30  # 30 seconds default
    
    @staticmethod
    def _get_current_bet(session: GameSession, user_id: str) -> int:
        """Get a player's current bet amount."""
        try:
            if not session.game or not hasattr(session.game, 'table'):
                return 0
            
            # Get current bet from the game engine
            if hasattr(session.game.table, 'players') and user_id in session.game.table.players:
                player = session.game.table.players[user_id]
                if hasattr(player, 'current_bet'):
                    return player.current_bet
            
            return 0
            
        except Exception as e:
            logger.error(f"Failed to get current bet for {user_id}: {e}")
            return 0
    
    @staticmethod
    def _is_player_active(session: GameSession, user_id: str) -> bool:
        """Check if a player is active in the current hand."""
        try:
            if not session.game or not hasattr(session.game, 'table'):
                return False
            
            # Check if player is active in the game
            if hasattr(session.game.table, 'players') and user_id in session.game.table.players:
                player = session.game.table.players[user_id]
                if hasattr(player, 'is_active'):
                    return player.is_active
            
            return user_id in session.connected_players
            
        except Exception as e:
            logger.error(f"Failed to check if player {user_id} is active: {e}")
            return False
    
    @staticmethod
    def _is_all_in(session: GameSession, user_id: str) -> bool:
        """Check if a player is all-in."""
        try:
            if not session.game or not hasattr(session.game, 'table'):
                return False
            
            # Check if player is all-in
            if hasattr(session.game.table, 'players') and user_id in session.game.table.players:
                player = session.game.table.players[user_id]
                if hasattr(player, 'stack'):
                    return player.stack == 0
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to check if player {user_id} is all-in: {e}")
            return False
    
    @staticmethod
    def _has_folded(session: GameSession, user_id: str) -> bool:
        """Check if a player has folded."""
        try:
            if not session.game or not hasattr(session.game, 'table'):
                return False
            
            # Check if player has folded
            if hasattr(session.game.table, 'players') and user_id in session.game.table.players:
                player = session.game.table.players[user_id]
                if hasattr(player, 'has_folded'):
                    return player.has_folded
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to check if player {user_id} has folded: {e}")
            return False
    
    @staticmethod
    def _get_position_name(seat_number: int) -> str:
        """Get position name from seat number."""
        # This is a simplified position naming - should be enhanced based on actual game logic
        positions = {
            1: "UTG",
            2: "UTG+1", 
            3: "MP",
            4: "MP+1",
            5: "CO",
            6: "BTN",
            7: "SB",
            8: "BB",
            9: "UTG"
        }
        return positions.get(seat_number, f"Seat {seat_number}")
    
    @staticmethod
    def _get_dealer_position(session: GameSession) -> int:
        """Get dealer button position."""
        try:
            if not session.game or not hasattr(session.game, 'table'):
                return 0
            
            # Get dealer position from the game engine
            if hasattr(session.game.table, 'dealer_position'):
                return session.game.table.dealer_position
            
            return 0
            
        except Exception as e:
            logger.error(f"Failed to get dealer position: {e}")
            return 0
    
    @staticmethod
    def _get_small_blind_position(session: GameSession) -> int:
        """Get small blind position."""
        try:
            if not session.game or not hasattr(session.game, 'table'):
                return 0
            
            # Get small blind position from the game engine
            if hasattr(session.game.table, 'small_blind_position'):
                return session.game.table.small_blind_position
            
            return 0
            
        except Exception as e:
            logger.error(f"Failed to get small blind position: {e}")
            return 0
    
    @staticmethod
    def _get_big_blind_position(session: GameSession) -> int:
        """Get big blind position."""
        try:
            if not session.game or not hasattr(session.game, 'table'):
                return 0
            
            # Get big blind position from the game engine
            if hasattr(session.game.table, 'big_blind_position'):
                return session.game.table.big_blind_position
            
            return 0
            
        except Exception as e:
            logger.error(f"Failed to get big blind position: {e}")
            return 0
    
    @staticmethod
    def create_game_state_update(table_id: str, update_type: str, data: Dict[str, Any], 
                               affected_players: List[str] = None) -> GameStateUpdate:
        """Create a game state update."""
        session = game_orchestrator.get_session(table_id)
        session_id = session.session_id if session else ""
        
        return GameStateUpdate(
            table_id=table_id,
            session_id=session_id,
            update_type=update_type,
            data=data,
            affected_players=affected_players or []
        )
    
    @staticmethod
    def process_hand_completion(session: GameSession) -> Optional[HandResult]:
        """Process hand completion and generate results."""
        try:
            if not session.game:
                return None
            
            # Get hand results from the game engine
            # This would typically come from the game's showdown manager
            winners = []
            pot_distribution = {}
            final_board = []
            player_hands = {}
            
            # Get community cards
            community_cards = GameStateManager._get_community_cards(session)
            final_board = community_cards.get('board', [])
            
            # Get pot information
            pot_info = GameStateManager._get_pot_info(session)
            
            # This is a simplified implementation - should be enhanced with actual game results
            hand_result = HandResult(
                hand_number=session.hands_played + 1,
                table_id=session.table.id,
                session_id=session.session_id,
                winners=winners,
                pot_distribution=pot_distribution,
                final_board=final_board,
                player_hands=player_hands,
                hand_summary="Hand completed"
            )
            
            return hand_result
            
        except Exception as e:
            logger.error(f"Failed to process hand completion: {e}")
            return None
    
    @staticmethod
    def detect_state_changes(old_state: GameStateView, new_state: GameStateView) -> List[GameStateUpdate]:
        """Detect changes between two game states."""
        changes = []
        
        try:
            # Check for phase changes
            if old_state.game_phase != new_state.game_phase:
                changes.append(GameStateManager.create_game_state_update(
                    new_state.table_id,
                    "phase_change",
                    {
                        "old_phase": old_state.game_phase.value,
                        "new_phase": new_state.game_phase.value
                    }
                ))
            
            # Check for current player changes
            if old_state.current_player != new_state.current_player:
                changes.append(GameStateManager.create_game_state_update(
                    new_state.table_id,
                    "current_player_change",
                    {
                        "old_player": old_state.current_player,
                        "new_player": new_state.current_player
                    },
                    [new_state.current_player] if new_state.current_player else []
                ))
            
            # Check for pot changes
            if old_state.pot_info.total_pot != new_state.pot_info.total_pot:
                changes.append(GameStateManager.create_game_state_update(
                    new_state.table_id,
                    "pot_change",
                    {
                        "old_pot": old_state.pot_info.total_pot,
                        "new_pot": new_state.pot_info.total_pot
                    }
                ))
            
            # Check for community card changes
            old_board = old_state.community_cards.get('board', [])
            new_board = new_state.community_cards.get('board', [])
            if old_board != new_board:
                changes.append(GameStateManager.create_game_state_update(
                    new_state.table_id,
                    "community_cards_change",
                    {
                        "old_cards": old_board,
                        "new_cards": new_board
                    }
                ))
            
            # Check for player changes
            old_players = {p.user_id: p for p in old_state.players}
            new_players = {p.user_id: p for p in new_state.players}
            
            for user_id, new_player in new_players.items():
                old_player = old_players.get(user_id)
                if not old_player:
                    # New player joined
                    changes.append(GameStateManager.create_game_state_update(
                        new_state.table_id,
                        "player_joined",
                        {"player": new_player.to_dict()},
                        [user_id]
                    ))
                else:
                    # Check for player state changes
                    if old_player.chip_stack != new_player.chip_stack:
                        changes.append(GameStateManager.create_game_state_update(
                            new_state.table_id,
                            "stack_change",
                            {
                                "user_id": user_id,
                                "old_stack": old_player.chip_stack,
                                "new_stack": new_player.chip_stack
                            },
                            [user_id]
                        ))
                    
                    if old_player.is_connected != new_player.is_connected:
                        changes.append(GameStateManager.create_game_state_update(
                            new_state.table_id,
                            "connection_change",
                            {
                                "user_id": user_id,
                                "connected": new_player.is_connected
                            },
                            [user_id]
                        ))
            
            # Check for players who left
            for user_id in old_players:
                if user_id not in new_players:
                    changes.append(GameStateManager.create_game_state_update(
                        new_state.table_id,
                        "player_left",
                        {"user_id": user_id},
                        [user_id]
                    ))
            
            return changes
            
        except Exception as e:
            logger.error(f"Failed to detect state changes: {e}")
            return []