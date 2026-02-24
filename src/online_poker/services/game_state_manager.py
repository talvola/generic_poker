"""Service for managing game state views and synchronization."""

import logging
from typing import Any

from generic_poker.config.loader import GameActionType
from generic_poker.core.card import Visibility
from generic_poker.game.game_state import GameState, PlayerAction

from ..models.game_state_view import (
    ActionOption,
    ActionType,
    GamePhase,
    GameStateUpdate,
    GameStateView,
    HandResult,
    PlayerView,
    PotInfo,
)
from ..services.game_orchestrator import GameSession, game_orchestrator
from ..services.table_access_manager import TableAccessManager

logger = logging.getLogger(__name__)


class GameStateManager:
    """Service for managing game state views and synchronization."""

    @staticmethod
    def generate_game_state_view(table_id: str, viewer_id: str, is_spectator: bool = False) -> GameStateView | None:
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
                # No active game session - return waiting state with player list
                logger.debug(f"No game session found for table {table_id}, returning waiting state")
                return GameStateManager._generate_waiting_state(table_id, viewer_id, is_spectator)

            # Get table players
            table_players = TableAccessManager.get_table_players(table_id)
            if not table_players:
                logger.warning(f"No players found for table {table_id}")
                return None

            # Generate player views
            player_views = []
            human_ids = set()
            for player_info in table_players:
                if player_info["is_spectator"]:
                    continue  # Skip spectators in player list

                human_ids.add(player_info["user_id"])
                player_view = GameStateManager._create_player_view(player_info, session, viewer_id, is_spectator)
                if player_view:
                    player_views.append(player_view)

            # Add bot players from game session (they have no DB records)
            from ..services.simple_bot import SimpleBot

            if session.game:
                for pid, player in session.game.table.players.items():
                    if SimpleBot.is_bot_player(pid) and pid not in human_ids:
                        seat_num = session.game.table.layout.get_player_seat(pid)
                        bot_info = {
                            "user_id": pid,
                            "username": player.name,
                            "seat_number": seat_num,
                            "current_stack": player.stack,
                            "is_spectator": False,
                        }
                        bot_view = GameStateManager._create_player_view(bot_info, session, viewer_id, is_spectator)
                        if bot_view:
                            bot_view.is_bot = True
                            player_views.append(bot_view)

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
                # Import here to avoid circular imports
                from ..services.player_action_manager import player_action_manager

                action_options = player_action_manager.get_available_actions(table_id, viewer_id)
                valid_actions = [GameStateManager._convert_action_option(opt, session) for opt in action_options]

            # Determine game phase
            game_phase = GameStateManager._get_game_phase(session)

            # Get table information
            table_info = GameStateManager._get_table_info(session)

            # Get time_limit from Flask config
            try:
                from flask import current_app

                time_limit = current_app.config.get("ACTION_TIMEOUT_SECONDS", 30)
            except RuntimeError:
                time_limit = 30

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
                time_limit=time_limit,
                table_info=table_info,
            )

            return game_state_view

        except Exception as e:
            logger.error(f"Failed to generate game state view for table {table_id}, viewer {viewer_id}: {e}")
            return None

    @staticmethod
    def _generate_waiting_state(table_id: str, viewer_id: str, is_spectator: bool) -> GameStateView | None:
        """Generate a game state view for when no active game session exists (waiting state).

        Args:
            table_id: ID of the table
            viewer_id: ID of the player/spectator viewing the state
            is_spectator: Whether the viewer is a spectator

        Returns:
            GameStateView with waiting state or None if table/players not found
        """
        try:
            # Get table players from database
            table_players = TableAccessManager.get_table_players(table_id)
            if not table_players:
                logger.debug(f"No players found for table {table_id} in waiting state")
                return None

            # Create simple player views (no game-specific state)
            player_views = []
            for player_info in table_players:
                if player_info["is_spectator"]:
                    continue  # Skip spectators in player list

                player_view = PlayerView(
                    user_id=player_info["user_id"],
                    username=player_info["username"],
                    position=GameStateManager._get_position_name(player_info["seat_number"]),
                    seat_number=player_info["seat_number"],
                    chip_stack=player_info["current_stack"] or 0,
                    current_bet=0,
                    cards=[],  # No cards in waiting state
                    is_active=True,
                    is_current_player=False,
                    is_bot=False,
                    is_connected=True,
                    is_all_in=False,
                    has_folded=False,
                    last_action=None,
                    time_to_act=None,
                )
                player_views.append(player_view)

            # Sort players by seat number
            player_views.sort(key=lambda p: p.seat_number)

            # Get table info from TableManager
            from ..services.table_manager import TableManager

            table = TableManager.get_table_by_id(table_id)
            table_info = {}
            if table:
                table_info = {
                    "table_name": table.name,
                    "variant": table.variant,
                    "betting_structure": table.betting_structure,
                    "max_players": table.max_players,
                    "stakes": table.get_stakes(),
                }

            # Create waiting state game view
            game_state_view = GameStateView(
                table_id=table_id,
                session_id="",  # No session yet
                viewer_id=viewer_id,
                players=player_views,
                community_cards={"layout": {"type": "none"}, "cards": {}},
                pot_info=PotInfo(0),
                current_player=None,
                valid_actions=[],
                game_phase=GamePhase.WAITING,
                hand_number=0,
                is_spectator=is_spectator,
                dealer_position=0,
                small_blind_position=0,
                big_blind_position=0,
                table_info=table_info,
            )

            return game_state_view

        except Exception as e:
            logger.error(f"Failed to generate waiting state for table {table_id}: {e}")
            return None

    @staticmethod
    def _create_player_view(
        player_info: dict[str, Any], session: GameSession, viewer_id: str, is_spectator: bool
    ) -> PlayerView | None:
        """Create a player view from player information."""
        try:
            user_id = player_info["user_id"]

            # Get player cards with per-card visibility
            cards = GameStateManager._get_player_cards_with_visibility(session, user_id, viewer_id, is_spectator)

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

            # Get chip stack from game session if available, otherwise from database
            chip_stack = player_info["current_stack"] or 0
            if session and session.game and hasattr(session.game, "table"):
                game_player = session.game.table.players.get(user_id)
                if game_player and hasattr(game_player, "stack"):
                    chip_stack = game_player.stack

            # Get card count for all players (used to show card backs for opponents)
            card_count = GameStateManager._get_player_card_count(session, user_id)

            # Create player view
            # Get card subsets if the player has separated their cards
            card_subsets = GameStateManager._get_card_subsets(session, user_id, viewer_id, is_spectator)

            player_view = PlayerView(
                user_id=user_id,
                username=player_info["username"],
                position=GameStateManager._get_position_name(player_info["seat_number"]),
                seat_number=player_info["seat_number"],
                chip_stack=chip_stack,
                current_bet=GameStateManager._get_current_bet(session, user_id),
                cards=cards,
                card_count=card_count,
                is_active=GameStateManager._is_player_active(session, user_id),
                is_current_player=is_current_player,
                is_bot=False,  # TODO: Implement bot detection
                is_connected=is_connected,
                is_all_in=GameStateManager._is_all_in(session, user_id),
                has_folded=GameStateManager._has_folded(session, user_id),
                last_action=last_action,
                time_to_act=time_to_act,
                card_subsets=card_subsets,
            )

            return player_view

        except Exception as e:
            logger.error(f"Failed to create player view for {player_info.get('user_id', 'unknown')}: {e}")
            return None

    @staticmethod
    def _infer_community_layout(session: GameSession) -> dict[str, Any]:
        """Infer community card layout from game rules if not explicitly specified."""
        # 1. If config has explicit communityCardLayout, use it
        if hasattr(session, "game_rules") and session.game_rules and session.game_rules.community_card_layout:
            return session.game_rules.community_card_layout

        # 2. Scan gameplay steps for community deals
        game_rules = getattr(session, "game_rules", None)
        if not game_rules:
            return {"type": "linear"}

        has_community = False
        all_subsets = set()
        total_community_cards = 0
        for step in game_rules.gameplay:
            if step.action_type == GameActionType.DEAL:
                config = step.action_config
                if config.get("location") == "community":
                    has_community = True
                    for card_info in config.get("cards", []):
                        total_community_cards += card_info.get("number", 0)
                        subset = card_info.get("community_subset") or card_info.get("subset")
                        if subset:
                            if isinstance(subset, list):
                                all_subsets.update(subset)
                            else:
                                all_subsets.add(subset)
            elif step.action_type == GameActionType.GROUPED:
                for action in step.action_config:
                    if "deal" in action:
                        deal_config = action["deal"]
                        if deal_config.get("location") == "community":
                            has_community = True
                            for card_info in deal_config.get("cards", []):
                                total_community_cards += card_info.get("number", 0)
                                subset = card_info.get("community_subset") or card_info.get("subset")
                                if subset:
                                    if isinstance(subset, list):
                                        all_subsets.update(subset)
                                    else:
                                        all_subsets.add(subset)

        # 3. No community deals -> "none"
        if not has_community:
            return {"type": "none"}

        # 4. All default/no subset -> "linear"
        if not all_subsets or all_subsets == {"default"}:
            return {"type": "linear", "expectedCards": total_community_cards}

        # 5. Has subsets but no explicit layout -> "linear" fallback
        return {"type": "linear", "expectedCards": total_community_cards}

    @staticmethod
    def _get_community_cards(session: GameSession) -> dict[str, Any]:
        """Get community cards from the game session.

        Returns structured format:
        {
            "layout": {"type": "linear"},
            "cards": {
                "default": [
                    {"card": "Ts", "face_up": true},
                    ...
                ]
            }
        }
        """
        try:
            if not session.game or not hasattr(session.game, "table"):
                return {"layout": {"type": "none"}, "cards": {}}

            layout = GameStateManager._infer_community_layout(session)

            cards_by_subset = {}

            if hasattr(session.game.table, "community_cards"):
                cards_dict = session.game.table.community_cards
                if cards_dict:
                    for subset_name, card_list in cards_dict.items():
                        cards_by_subset[subset_name] = [{"card": str(card), "face_up": True} for card in card_list]

            if not cards_by_subset:
                return {"layout": layout, "cards": {}}

            return {"layout": layout, "cards": cards_by_subset}

        except Exception as e:
            logger.error(f"Failed to get community cards: {e}")
            return {"layout": {"type": "none"}, "cards": {}}

    @staticmethod
    def _get_pot_info(session: GameSession) -> PotInfo:
        """Get pot information from the game session."""
        try:
            if not session.game or not hasattr(session.game, "betting"):
                return PotInfo(0)

            # Get pot information from the betting manager
            betting = session.game.betting
            total_pot = 0
            side_pots = []
            current_bet = 0

            # Get total pot from betting manager
            # Note: get_total_pot() returns pot.total which already includes
            # all bets from the current round (blinds, etc.) since pot.add_bet()
            # is called when bets are placed. No need to add current_round_bets.
            if hasattr(betting, "get_total_pot"):
                total_pot = betting.get_total_pot()

            # Get side pots if available
            if hasattr(betting, "pot") and hasattr(betting.pot, "round_pots"):
                round_pots = betting.pot.round_pots
                if round_pots and len(round_pots) > 0:
                    current_round = round_pots[-1]
                    if hasattr(current_round, "side_pots"):
                        side_pots = [
                            {
                                "amount": sp.amount,
                                "eligible_players": list(sp.eligible_players)
                                if hasattr(sp, "eligible_players")
                                else [],
                            }
                            for sp in current_round.side_pots
                        ]

            # Get current bet level from betting manager
            if hasattr(betting, "current_bet"):
                current_bet = betting.current_bet

            return PotInfo(main_pot=total_pot, side_pots=side_pots, total_pot=total_pot, current_bet=current_bet)

        except Exception as e:
            logger.error(f"Failed to get pot info: {e}")
            return PotInfo(0)

    @staticmethod
    def _get_current_player(session: GameSession) -> str | None:
        """Get the current player to act."""
        try:
            if not session.game:
                return None

            # current_player is on the Game object, not on game.table
            current_player = session.game.current_player
            if current_player and hasattr(current_player, "id"):
                return current_player.id

            return None

        except Exception as e:
            logger.error(f"Failed to get current player: {e}")
            return None

    @staticmethod
    def _convert_action_option(action_option, session: GameSession = None) -> ActionOption:
        """Convert PlayerActionOption to ActionOption for the game state view.

        Args:
            action_option: PlayerActionOption from the action manager
            session: Optional game session for metadata extraction

        Returns:
            ActionOption for the game state view
        """
        try:
            # Map PlayerAction to ActionType
            action_type_map = {
                PlayerAction.FOLD: ActionType.FOLD,
                PlayerAction.CHECK: ActionType.CHECK,
                PlayerAction.CALL: ActionType.CALL,
                PlayerAction.BET: ActionType.BET,
                PlayerAction.RAISE: ActionType.RAISE,
                PlayerAction.BRING_IN: ActionType.BRING_IN,
                PlayerAction.COMPLETE: ActionType.COMPLETE,
                PlayerAction.DRAW: ActionType.DRAW,
                PlayerAction.DISCARD: ActionType.DISCARD,
                PlayerAction.PASS: ActionType.PASS,
                PlayerAction.EXPOSE: ActionType.EXPOSE,
                PlayerAction.SEPARATE: ActionType.SEPARATE,
                PlayerAction.DECLARE: ActionType.DECLARE,
                PlayerAction.CHOOSE: ActionType.CHOOSE,
            }

            action_type = action_type_map.get(action_option.action_type, ActionType.FOLD)

            # Attach metadata for special actions
            metadata = None
            if action_option.action_type == PlayerAction.SEPARATE and session and session.game:
                if hasattr(session.game, "current_separate_config"):
                    config = session.game.current_separate_config
                    metadata = {
                        "subsets": [
                            {"name": cfg["hole_subset"], "count": cfg["number"]} for cfg in config.get("cards", [])
                        ]
                    }
            elif action_option.action_type == PlayerAction.DECLARE and session and session.game:
                if hasattr(session.game, "current_declare_config"):
                    config = session.game.current_declare_config
                    metadata = {
                        "options": config.get("options", ["high", "low"]),
                        "per_pot": config.get("per_pot", False),
                    }
            elif action_option.action_type == PlayerAction.CHOOSE and session and session.game:
                step = session.game.rules.gameplay[session.game.current_step]
                if step.action_type == GameActionType.CHOOSE:
                    possible_values = step.action_config.get("possible_values", [])
                    metadata = {"options": possible_values}

            return ActionOption(
                action_type=action_type,
                min_amount=action_option.min_amount,
                max_amount=action_option.max_amount,
                display_text=action_option.display_text,
                metadata=metadata,
            )

        except Exception as e:
            logger.error(f"Failed to convert action option: {e}")
            return ActionOption(ActionType.FOLD, display_text="Fold")

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
                # Determine betting round based on total community card count
                num_cards = GameStateManager._count_community_cards(session)

                if num_cards == 0:
                    return GamePhase.PREFLOP
                elif num_cards <= 3:
                    return GamePhase.FLOP
                elif num_cards == 4:
                    return GamePhase.TURN
                elif num_cards >= 5:
                    return GamePhase.RIVER
                else:
                    return GamePhase.PREFLOP
            elif game_state == GameState.DRAWING:
                # Distinguish declaring from other drawing actions
                if hasattr(session.game, "current_declare_config"):
                    return GamePhase.DECLARING
                return GamePhase.DRAWING
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
    def _count_community_cards(session: GameSession) -> int:
        """Count total community cards directly from game engine (avoids structured format overhead)."""
        try:
            if not session.game or not hasattr(session.game, "table"):
                return 0
            if hasattr(session.game.table, "community_cards"):
                cards_dict = session.game.table.community_cards
                if cards_dict:
                    return sum(len(card_list) for card_list in cards_dict.values())
            return 0
        except Exception:
            return 0

    @staticmethod
    def _get_table_info(session: GameSession) -> dict[str, Any]:
        """Get table information."""
        try:
            table_info = {
                "name": session.table.name,
                "variant": session.table.variant,
                "betting_structure": session.table.betting_structure,
                "stakes": session.table.get_stakes(),
                "max_players": session.table.max_players,
                "is_private": session.table.is_private,
            }
            # Add mixed game rotation info if applicable
            mixed_info = session.get_mixed_game_info()
            if mixed_info:
                table_info["mixed_game"] = mixed_info
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
        except Exception:
            return False

    @staticmethod
    def _get_player_cards(session: GameSession, user_id: str) -> list[str]:
        """Get a player's hole cards."""
        try:
            if not session.game or not hasattr(session.game, "table"):
                return []

            # Get player cards from the game engine
            if hasattr(session.game.table, "players") and user_id in session.game.table.players:
                player = session.game.table.players[user_id]
                # Cards are stored in player.hand.cards, not player.cards
                if hasattr(player, "hand") and hasattr(player.hand, "cards"):
                    return [str(card) for card in player.hand.cards]

            return []

        except Exception as e:
            logger.error(f"Failed to get player cards for {user_id}: {e}")
            return []

    @staticmethod
    def _get_player_card_count(session: GameSession, user_id: str) -> int:
        """Get the number of cards a player has (for showing card backs)."""
        try:
            if not session.game or not hasattr(session.game, "table"):
                return 0

            # Get card count from the game engine
            if hasattr(session.game.table, "players") and user_id in session.game.table.players:
                player = session.game.table.players[user_id]
                # Cards are stored in player.hand.cards
                if hasattr(player, "hand") and hasattr(player.hand, "cards"):
                    return len(player.hand.cards)

            return 0

        except Exception as e:
            logger.error(f"Failed to get player card count for {user_id}: {e}")
            return 0

    @staticmethod
    def _get_player_cards_with_visibility(
        session: GameSession, user_id: str, viewer_id: str, is_spectator: bool
    ) -> list[str | None]:
        """Get a player's cards with per-card visibility for the viewer.

        - Viewer's own cards: all returned as strings (all visible)
        - Showdown/complete: all returned as strings (all visible)
        - Opponent mid-hand: face-up cards as strings, face-down as None.
          If ALL are face-down, returns empty list (let card_count handle backs).
        """
        try:
            if not session.game or not hasattr(session.game, "table"):
                return []

            player = session.game.table.players.get(user_id)
            if not player or not hasattr(player, "hand") or not hasattr(player.hand, "cards"):
                return []

            cards = player.hand.cards
            if not cards:
                return []

            # Viewer's own cards: always fully visible
            if user_id == viewer_id and not is_spectator:
                return [str(card) for card in cards]

            # Showdown/complete: all visible
            if GameStateManager._should_show_cards(session, user_id):
                return [str(card) for card in cards]

            # Opponent mid-hand: check per-card visibility
            result = []
            has_face_up = False
            for card in cards:
                if card.visibility == Visibility.FACE_UP:
                    result.append(str(card))
                    has_face_up = True
                else:
                    result.append(None)

            # If all cards are face-down, return empty list for backward compat
            # (frontend uses card_count to show backs)
            if not has_face_up:
                return []

            return result

        except Exception as e:
            logger.error(f"Failed to get cards with visibility for {user_id}: {e}")
            return []

    @staticmethod
    def _get_card_subsets(
        session: GameSession, user_id: str, viewer_id: str, is_spectator: bool
    ) -> dict[str, list[str]] | None:
        """Get card subsets for a player who has separated their cards.

        Returns subset name -> card strings for viewer's own cards or showdown,
        subset name -> card count for opponents mid-hand.
        Returns None if no subsets exist.
        """
        try:
            if not session.game or not hasattr(session.game, "table"):
                return None

            player = session.game.table.players.get(user_id)
            if not player or not hasattr(player, "hand") or not hasattr(player.hand, "subsets"):
                return None

            subsets = player.hand.subsets
            if not subsets:
                return None

            is_own_cards = user_id == viewer_id and not is_spectator
            is_showdown = GameStateManager._should_show_cards(session, user_id)

            result = {}
            for name, cards in subsets.items():
                if is_own_cards or is_showdown:
                    result[name] = [str(c) for c in cards]
                else:
                    # For opponents, just show count per subset
                    result[name] = [str(c) if c.visibility == Visibility.FACE_UP else None for c in cards]

            return result if result else None

        except Exception as e:
            logger.error(f"Failed to get card subsets for {user_id}: {e}")
            return None

    @staticmethod
    def _is_current_player(session: GameSession, user_id: str) -> bool:
        """Check if a player is the current player to act."""
        current_player = GameStateManager._get_current_player(session)
        return current_player == user_id

    @staticmethod
    def _get_last_action(session: GameSession, user_id: str) -> str | None:
        """Get a player's last action."""
        # This would typically come from the game engine's action history
        # For now, return None - this should be implemented with actual game logic
        return None

    @staticmethod
    def _get_time_to_act(session: GameSession, user_id: str) -> int | None:
        """Get time remaining for a player to act."""
        # This would typically be managed by a timer system
        # For now, return the configured timeout - this should be implemented with actual timing logic
        try:
            from flask import current_app

            return current_app.config.get("ACTION_TIMEOUT_SECONDS", 30)
        except RuntimeError:
            return 30

    @staticmethod
    def _get_current_bet(session: GameSession, user_id: str) -> int:
        """Get a player's current bet amount in this betting round."""
        try:
            if not session.game or not hasattr(session.game, "betting"):
                return 0

            # Bets are tracked in the betting manager, not on the Player object
            current_bets = session.game.betting.current_bets
            if user_id in current_bets:
                return current_bets[user_id].amount

            return 0

        except Exception as e:
            logger.error(f"Failed to get current bet for {user_id}: {e}")
            return 0

    @staticmethod
    def _is_player_active(session: GameSession, user_id: str) -> bool:
        """Check if a player is active in the current hand."""
        try:
            if not session.game or not hasattr(session.game, "table"):
                return False

            # Check if player is active in the game
            if hasattr(session.game.table, "players") and user_id in session.game.table.players:
                player = session.game.table.players[user_id]
                if hasattr(player, "is_active"):
                    return player.is_active

            return user_id in session.connected_players

        except Exception as e:
            logger.error(f"Failed to check if player {user_id} is active: {e}")
            return False

    @staticmethod
    def _is_all_in(session: GameSession, user_id: str) -> bool:
        """Check if a player is all-in."""
        try:
            if not session.game or not hasattr(session.game, "table"):
                return False

            # Check if player is all-in
            if hasattr(session.game.table, "players") and user_id in session.game.table.players:
                player = session.game.table.players[user_id]
                if hasattr(player, "stack"):
                    return player.stack == 0

            return False

        except Exception as e:
            logger.error(f"Failed to check if player {user_id} is all-in: {e}")
            return False

    @staticmethod
    def _has_folded(session: GameSession, user_id: str) -> bool:
        """Check if a player has folded."""
        try:
            if not session.game or not hasattr(session.game, "table"):
                return False

            # Check if player has folded
            if hasattr(session.game.table, "players") and user_id in session.game.table.players:
                player = session.game.table.players[user_id]

                # First check if there's an explicit has_folded attribute
                if hasattr(player, "has_folded"):
                    return player.has_folded

                # If no explicit has_folded, use is_active as proxy
                # A player who is not active during a hand has likely folded
                # (unless they're all-in)
                if hasattr(player, "is_active") and not player.is_active:
                    # If they're not all-in, they must have folded
                    if not GameStateManager._is_all_in(session, user_id):
                        return True

            return False

        except Exception as e:
            logger.error(f"Failed to check if player {user_id} has folded: {e}")
            return False

    @staticmethod
    def _get_position_name(seat_number: int) -> str:
        """Get position name from seat number."""
        # This is a simplified position naming - should be enhanced based on actual game logic
        positions = {1: "UTG", 2: "UTG+1", 3: "MP", 4: "MP+1", 5: "CO", 6: "BTN", 7: "SB", 8: "BB", 9: "UTG"}
        return positions.get(seat_number, f"Seat {seat_number}")

    @staticmethod
    def _get_dealer_position(session: GameSession) -> int:
        """Get dealer button seat number."""
        try:
            if not session.game or not hasattr(session.game, "table"):
                return 0

            # Get dealer position from button_seat
            if hasattr(session.game.table, "button_seat"):
                return session.game.table.button_seat

            return 0

        except Exception as e:
            logger.error(f"Failed to get dealer position: {e}")
            return 0

    @staticmethod
    def _get_small_blind_position(session: GameSession) -> int:
        """Get small blind seat number."""
        try:
            if not session.game or not hasattr(session.game, "table"):
                return 0

            from generic_poker.game.table import Position

            # Find player with small blind position
            for player in session.game.table.players.values():
                if player.position and player.position.has_position(Position.SMALL_BLIND):
                    # Get seat number for this player
                    seat_num = session.game.table.get_player_seat_number(player.id)
                    if seat_num:
                        return seat_num

            return 0

        except Exception as e:
            logger.error(f"Failed to get small blind position: {e}")
            return 0

    @staticmethod
    def _get_big_blind_position(session: GameSession) -> int:
        """Get big blind seat number."""
        try:
            if not session.game or not hasattr(session.game, "table"):
                return 0

            from generic_poker.game.table import Position

            # Find player with big blind position
            for player in session.game.table.players.values():
                if player.position and player.position.has_position(Position.BIG_BLIND):
                    # Get seat number for this player
                    seat_num = session.game.table.get_player_seat_number(player.id)
                    if seat_num:
                        return seat_num

            return 0

        except Exception as e:
            logger.error(f"Failed to get big blind position: {e}")
            return 0

    @staticmethod
    def create_game_state_update(
        table_id: str, update_type: str, data: dict[str, Any], affected_players: list[str] = None
    ) -> GameStateUpdate:
        """Create a game state update."""
        session = game_orchestrator.get_session(table_id)
        session_id = session.session_id if session else ""

        return GameStateUpdate(
            table_id=table_id,
            session_id=session_id,
            update_type=update_type,
            data=data,
            affected_players=affected_players or [],
        )

    @staticmethod
    def process_hand_completion(session: GameSession) -> HandResult | None:
        """Process hand completion and generate results."""
        try:
            if not session.game:
                return None

            # Get hand results from the game engine
            game_result = session.game.get_hand_results()
            if not game_result:
                return None

            # Build winners list from pot results
            winners = []
            pot_distribution = {}
            for pot in game_result.pots:
                for winner_id in pot.winners:
                    amount = pot.amount_per_player
                    winners.append({"user_id": winner_id, "amount": amount, "pot_type": pot.pot_type})
                    pot_distribution[winner_id] = pot_distribution.get(winner_id, 0) + amount

            # Get community cards as flat list
            community_data = GameStateManager._get_community_cards(session)
            final_board = []
            for subset_cards in community_data.get("cards", {}).values():
                for card_info in subset_cards:
                    final_board.append(card_info["card"])

            # Build player hands dict
            player_hands = {}
            for player_id, hands in game_result.hands.items():
                if hands:
                    hand = hands[0] if isinstance(hands, list) else hands
                    player_hands[player_id] = {
                        "cards": [str(c) for c in hand.cards],
                        "hand_name": hand.hand_name,
                        "hand_description": hand.hand_description,
                    }

            # Build summary
            winner_names = ", ".join(pot_distribution.keys())
            hand_summary = f"Won by {winner_names}" if winner_names else "Hand completed"

            hand_result = HandResult(
                hand_number=session.hands_played + 1,
                table_id=session.table.id,
                session_id=session.session_id,
                winners=winners,
                pot_distribution=pot_distribution,
                final_board=final_board,
                player_hands=player_hands,
                hand_summary=hand_summary,
            )

            return hand_result

        except Exception as e:
            logger.error(f"Failed to process hand completion: {e}")
            return None

    @staticmethod
    def detect_state_changes(old_state: GameStateView, new_state: GameStateView) -> list[GameStateUpdate]:
        """Detect changes between two game states."""
        changes = []

        try:
            # Check for phase changes
            if old_state.game_phase != new_state.game_phase:
                changes.append(
                    GameStateManager.create_game_state_update(
                        new_state.table_id,
                        "phase_change",
                        {"old_phase": old_state.game_phase.value, "new_phase": new_state.game_phase.value},
                    )
                )

            # Check for current player changes
            if old_state.current_player != new_state.current_player:
                changes.append(
                    GameStateManager.create_game_state_update(
                        new_state.table_id,
                        "current_player_change",
                        {"old_player": old_state.current_player, "new_player": new_state.current_player},
                        [new_state.current_player] if new_state.current_player else [],
                    )
                )

            # Check for pot changes
            if old_state.pot_info.total_pot != new_state.pot_info.total_pot:
                changes.append(
                    GameStateManager.create_game_state_update(
                        new_state.table_id,
                        "pot_change",
                        {"old_pot": old_state.pot_info.total_pot, "new_pot": new_state.pot_info.total_pot},
                    )
                )

            # Check for community card changes
            old_cards = old_state.community_cards.get("cards", {})
            new_cards = new_state.community_cards.get("cards", {})
            if old_cards != new_cards:
                changes.append(
                    GameStateManager.create_game_state_update(
                        new_state.table_id, "community_cards_change", {"old_cards": old_cards, "new_cards": new_cards}
                    )
                )

            # Check for player changes
            old_players = {p.user_id: p for p in old_state.players}
            new_players = {p.user_id: p for p in new_state.players}

            for user_id, new_player in new_players.items():
                old_player = old_players.get(user_id)
                if not old_player:
                    # New player joined
                    changes.append(
                        GameStateManager.create_game_state_update(
                            new_state.table_id, "player_joined", {"player": new_player.to_dict()}, [user_id]
                        )
                    )
                else:
                    # Check for player state changes
                    if old_player.chip_stack != new_player.chip_stack:
                        changes.append(
                            GameStateManager.create_game_state_update(
                                new_state.table_id,
                                "stack_change",
                                {
                                    "user_id": user_id,
                                    "old_stack": old_player.chip_stack,
                                    "new_stack": new_player.chip_stack,
                                },
                                [user_id],
                            )
                        )

                    if old_player.is_connected != new_player.is_connected:
                        changes.append(
                            GameStateManager.create_game_state_update(
                                new_state.table_id,
                                "connection_change",
                                {"user_id": user_id, "connected": new_player.is_connected},
                                [user_id],
                            )
                        )

            # Check for players who left
            for user_id in old_players:
                if user_id not in new_players:
                    changes.append(
                        GameStateManager.create_game_state_update(
                            new_state.table_id, "player_left", {"user_id": user_id}, [user_id]
                        )
                    )

            return changes

        except Exception as e:
            logger.error(f"Failed to detect state changes: {e}")
            return []
