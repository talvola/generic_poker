"""Debug-only API routes for reproducing specific deal scenarios (BACKLOG T009).

These endpoints let an admin stack a table's deck (force an exact deal order) or
seed its shuffle RNG so a scenario — e.g. an open pair on 4th street — can be
reproduced on demand during tester sessions. They are gated behind the
``DEBUG_ALLOW_STACKED_DECK`` config flag (off in production) AND admin auth.

Workflow:
    1. Create a table and navigate to it so its game session exists.
    2. POST the desired card order (or seed) below.
    3. Click Ready — the next hand is dealt from the stacked/seeded deck.

Cards use the engine's two-char notation: rank (2-9, T, J, Q, K, A) + suit
(s/h/d/c), e.g. ``"As"`` = ace of spades. The card list is in deal order: in
Hold'em the first card goes to seat-order player 1, the second to player 2, etc.
"""

import functools

from flask import Blueprint, current_app, jsonify, request
from flask_login import current_user

from generic_poker.core.card import Card

from ..services.game_orchestrator import game_orchestrator

debug_bp = Blueprint("debug", __name__, url_prefix="/api/debug")


def _debug_enabled(f):
    """Return 404 when the stacked-deck debug feature is disabled.

    A 404 (rather than 403) keeps the feature invisible in production.
    """

    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        if not current_app.config.get("DEBUG_ALLOW_STACKED_DECK", False):
            return jsonify({"success": False, "message": "Not found"}), 404
        return f(*args, **kwargs)

    return wrapper


def admin_required(f):
    """Admin gate returning JSON (these are API endpoints, not page routes)."""

    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({"success": False, "message": "Authentication required"}), 401
        if not current_user.is_admin:
            return jsonify({"success": False, "message": "Admin access required"}), 403
        return f(*args, **kwargs)

    return wrapper


def _get_table(table_id: str):
    """Return the engine Table for a table_id, or None if no live session."""
    session = game_orchestrator.get_session(table_id)
    if not session or not session.game:
        return None
    return session.game.table


@debug_bp.route("/tables/<table_id>/stacked-deck", methods=["POST"])
@_debug_enabled
@admin_required
def set_stacked_deck(table_id: str):
    """Stack a table's deck so the next hand is dealt from a fixed card order.

    Body: ``{"cards": ["As", "Ks", "Ah", "Kh", ...], "repeat": false}``
    """
    table = _get_table(table_id)
    if table is None:
        return jsonify({"success": False, "message": "No active game session for this table"}), 404

    data = request.get_json(silent=True) or {}
    raw_cards = data.get("cards")
    if not isinstance(raw_cards, list) or not raw_cards:
        return jsonify({"success": False, "message": "Provide a non-empty 'cards' list"}), 400

    try:
        cards = [Card.from_string(str(c)) for c in raw_cards]
    except ValueError as e:
        return jsonify({"success": False, "message": f"Invalid card: {e}"}), 400

    repeat = bool(data.get("repeat", False))
    table.set_stacked_deck(cards, repeat=repeat)
    current_app.logger.info(
        f"[debug] Stacked deck set for table {table_id}: {[str(c) for c in cards]} (repeat={repeat})"
    )
    return jsonify(
        {
            "success": True,
            "table_id": table_id,
            "cards": [str(c) for c in cards],
            "repeat": repeat,
            "message": f"Stacked {len(cards)} cards for the next hand" + (" (repeating every hand)" if repeat else ""),
        }
    )


@debug_bp.route("/tables/<table_id>/stacked-deck", methods=["DELETE"])
@_debug_enabled
@admin_required
def clear_stacked_deck(table_id: str):
    """Clear any pending stacked deck so hands revert to random deals."""
    table = _get_table(table_id)
    if table is None:
        return jsonify({"success": False, "message": "No active game session for this table"}), 404
    table.clear_stacked_deck()
    return jsonify({"success": True, "table_id": table_id, "message": "Stacked deck cleared"})


@debug_bp.route("/tables/<table_id>/seed", methods=["POST"])
@_debug_enabled
@admin_required
def set_deck_seed(table_id: str):
    """Seed (or unseed) the table's shuffle RNG for reproducible shuffles.

    Body: ``{"seed": 42}`` to seed, or ``{"seed": null}`` to revert to random.
    """
    table = _get_table(table_id)
    if table is None:
        return jsonify({"success": False, "message": "No active game session for this table"}), 404

    data = request.get_json(silent=True) or {}
    seed = data.get("seed")
    if seed is not None:
        try:
            seed = int(seed)
        except (TypeError, ValueError):
            return jsonify({"success": False, "message": "'seed' must be an integer or null"}), 400

    table.set_deck_seed(seed)
    return jsonify(
        {
            "success": True,
            "table_id": table_id,
            "seed": seed,
            "message": f"Deck seed set to {seed}" if seed is not None else "Deck seed cleared",
        }
    )


@debug_bp.route("/tables/<table_id>/deck-status", methods=["GET"])
@_debug_enabled
@admin_required
def deck_status(table_id: str):
    """Report the table's current stacked-deck / seed debug state."""
    table = _get_table(table_id)
    if table is None:
        return jsonify({"success": False, "message": "No active game session for this table"}), 404
    return jsonify(
        {
            "success": True,
            "table_id": table_id,
            "deck_seed": table.deck_seed,
            "pending_stack": [str(c) for c in table.stacked_deck] if table.stacked_deck else None,
            "stacked_deck_repeat": table.stacked_deck_repeat,
            "current_deck_is_stacked": table.deck_is_stacked,
        }
    )
