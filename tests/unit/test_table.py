"""Unit tests for table positions and betting order."""
import pytest
from generic_poker.game.table import Table, Position
from generic_poker.core.card import Visibility  # ✅ Import Visibility Enum

def has_position(player, pos):
    """Helper to check if a player has a specific position."""
    return player.position is not None and player.position.has_position(pos)

def has_position_value(player, value):
    """Helper to check if a player has a specific position value."""
    return player.position is not None and player.position.value == value

def test_heads_up_positions():
    """Test position assignment in heads-up play."""
    table = Table(max_players=9, min_buyin=100, max_buyin=1000)
    
    # Add two players
    table.add_player("p1", "Alice", 500)
    table.add_player("p2", "Bob", 500)
    
    # Test initial positions
    positions = table.get_position_order()
    assert [p.id for p in positions] == ["p1", "p2"]
    
    # First player should have both BTN and SB positions
    assert has_position(positions[0], Position.BUTTON)
    assert has_position(positions[0], Position.SMALL_BLIND)
    assert has_position(positions[1], Position.BIG_BLIND)

    # Move button
    table.move_button()
    positions = table.get_position_order()
    assert [p.id for p in positions] == ["p2", "p1"]
    assert has_position(positions[0], Position.BUTTON)
    assert has_position(positions[0], Position.SMALL_BLIND)
    assert has_position(positions[1], Position.BIG_BLIND)

def test_three_handed_positions():
    """Test position assignment in 3-handed play."""
    table = Table(max_players=9, min_buyin=100, max_buyin=1000)
    
    # Add three players
    table.add_player("p1", "Alice", 500)
    table.add_player("p2", "Bob", 500)
    table.add_player("p3", "Charlie", 500)
    
    # Test initial positions
    positions = table.get_position_order()
    assert [p.id for p in positions] == ["p1", "p2", "p3"]
    assert has_position(positions[0], Position.BUTTON)
    assert has_position(positions[1], Position.SMALL_BLIND)
    assert has_position(positions[2], Position.BIG_BLIND)

def test_full_ring_positions():
    """Test position assignment in full ring game."""
    table = Table(max_players=9, min_buyin=100, max_buyin=1000)
    
    # Add six players
    for i in range(6):
        table.add_player(f"p{i+1}", f"Player {i+1}", 500)
    
    # Test initial positions
    positions = table.get_position_order()
    assert len(positions) == 6
    assert has_position(positions[0], Position.BUTTON)
    assert has_position(positions[1], Position.SMALL_BLIND)
    assert has_position(positions[2], Position.BIG_BLIND)
    
    # Other positions should be None
    for player in positions[3:]:
        assert player.position is None
    
    # Test button movement preserves core positions
    table.move_button()
    positions = table.get_position_order()
    assert has_position(positions[0], Position.BUTTON)
    assert has_position(positions[1], Position.SMALL_BLIND)
    assert has_position(positions[2], Position.BIG_BLIND)

def test_button_movement():
    """Test button movement preserves core positions."""
    table = Table(max_players=9, min_buyin=100, max_buyin=1000)
    
    # Add five players
    for i in range(5):
        table.add_player(f"p{i+1}", f"Player {i+1}", 500)
    
    # Test full orbit
    for i in range(5):
        positions = table.get_position_order()
        assert has_position(positions[0], Position.BUTTON)
        assert has_position(positions[1], Position.SMALL_BLIND)
        assert has_position(positions[2], Position.BIG_BLIND)
        # Other positions should be None
        for player in positions[3:]:
            assert player.position is None
        table.move_button()

def test_position_value_property():
    """Test position value representation for logging."""
    table = Table(max_players=9, min_buyin=100, max_buyin=1000)
    
    # Test heads-up case
    table.add_player("p1", "Alice", 500)
    table.add_player("p2", "Bob", 500)
    
    positions = table.get_position_order()
    # In heads-up, first player should show as BTN even though they're also SB
    assert has_position_value(positions[0], "BTN")
    assert has_position_value(positions[1], "BB")
    
    # Test 3+ players
    table.add_player("p3", "Charlie", 500)
    positions = table.get_position_order()
    assert has_position_value(positions[0], "BTN")
    assert has_position_value(positions[1], "SB")
    assert has_position_value(positions[2], "BB")    

def test_player_removal_positions():
    """Test position assignments when players leave the table."""
    table = Table(max_players=9, min_buyin=100, max_buyin=1000)
    
    # Start with 4 players
    table.add_player("p1", "Alice", 500)
    table.add_player("p2", "Bob", 500)
    table.add_player("p3", "Charlie", 500)
    table.add_player("p4", "David", 500)
    
    positions = table.get_position_order()
    assert len(positions) == 4
    
    # Remove BB player
    bb_player_id = positions[2].id
    table.remove_player(bb_player_id)
    
    # Check new positions
    positions = table.get_position_order()
    assert len(positions) == 3
    assert has_position(positions[0], Position.BUTTON)
    assert has_position(positions[1], Position.SMALL_BLIND)
    assert has_position(positions[2], Position.BIG_BLIND)
    
    # Remove another player to force heads-up
    sb_player_id = positions[1].id
    table.remove_player(sb_player_id)
    
    # Verify heads-up positions
    positions = table.get_position_order()
    assert len(positions) == 2
    assert has_position(positions[0], Position.BUTTON)
    assert has_position(positions[0], Position.SMALL_BLIND)
    assert has_position(positions[1], Position.BIG_BLIND)

def test_player_addition_positions():
    """Test position assignments when players join the table."""
    table = Table(max_players=9, min_buyin=100, max_buyin=1000)
    
    # Start heads-up
    table.add_player("p1", "Alice", 500)
    table.add_player("p2", "Bob", 500)
    
    positions = table.get_position_order()
    assert len(positions) == 2
    assert has_position(positions[0], Position.BUTTON)
    assert has_position(positions[0], Position.SMALL_BLIND)
    
    # Add third player
    table.add_player("p3", "Charlie", 500)
    positions = table.get_position_order()
    assert len(positions) == 3
    assert has_position(positions[0], Position.BUTTON)
    assert not has_position(positions[0], Position.SMALL_BLIND)  # Should no longer be SB
    assert has_position(positions[1], Position.SMALL_BLIND)
    assert has_position(positions[2], Position.BIG_BLIND)

def test_position_rotation():
    """Test position rotation through all table sizes."""
    table = Table(max_players=9, min_buyin=100, max_buyin=1000)
    
    # Add players one at a time and verify positions
    player_ids = []
    for i in range(6):
        player_id = f"p{i+1}"
        table.add_player(player_id, f"Player {i+1}", 500)
        player_ids.append(player_id)
        
        positions = table.get_position_order()
        # Skip position checks for single player
        if len(positions) == 1:
            assert positions[0].position is None
            continue
            
        if len(positions) == 2:
            # Heads-up
            assert has_position(positions[0], Position.BUTTON)
            assert has_position(positions[0], Position.SMALL_BLIND)
            assert has_position(positions[1], Position.BIG_BLIND)
        else:
            # 3+ players
            assert has_position(positions[0], Position.BUTTON)
            assert has_position(positions[1], Position.SMALL_BLIND)
            assert has_position(positions[2], Position.BIG_BLIND)
        
        # Move button through one complete orbit
        for _ in range(len(positions)):
            table.move_button()
            new_positions = table.get_position_order()
            if len(new_positions) < 3:  # Skip for 1-2 players
                continue
            # Core positions should always be assigned for 3+ players
            assert has_position(positions[0], Position.BUTTON)
            assert has_position(positions[1], Position.SMALL_BLIND)
            assert has_position(positions[2], Position.BIG_BLIND)

def test_invalid_position_cases():
    """Test edge cases and invalid scenarios for positions."""
    table = Table(max_players=9, min_buyin=100, max_buyin=1000)
    
    # Empty table should return empty position list
    positions = table.get_position_order()
    assert len(positions) == 0
    
    # Single player should return that player with no position
    table.add_player("p1", "Alice", 500)
    positions = table.get_position_order()
    assert len(positions) == 1
    assert positions[0].position is None  # No positions assigned with single player
    
    # Test button movement with single player (should not error)
    table.move_button()  # Should not raise exception

def test_deal_hole_cards():
    """Test dealing hole cards to active players."""
    table = Table(max_players=6, min_buyin=100, max_buyin=1000)
    table.add_player("p1", "Alice", 500)
    table.add_player("p2", "Bob", 500)
    table.add_player("p3", "Charlie", 500)
    
    # Deal 2 hole cards
    table.deal_hole_cards(2)
    
    # Assert each player has 2 cards
    for player in table.players.values():
        assert len(player.hand.cards) == 2

def test_deal_community_cards():
    """Test dealing community cards to the table."""
    table = Table(max_players=6, min_buyin=100, max_buyin=1000)
    
    # Deal 3 flop cards
    table.deal_community_cards(3)
    assert len(table.community_cards) == 3
    assert all(card.visibility == Visibility.FACE_UP for card in table.community_cards)
    
    # Deal 1 turn card
    table.deal_community_cards(1)
    assert len(table.community_cards) == 4

def test_clear_hands():
    """Test clearing player hands and community cards."""
    table = Table(max_players=6, min_buyin=100, max_buyin=1000)
    
    # Add players and deal cards
    table.add_player("p1", "Alice", 500)
    table.add_player("p2", "Bob", 500)
    table.deal_hole_cards(2)
    table.deal_community_cards(3)
    
    # Ensure cards are dealt
    assert len(table.players["p1"].hand.cards) == 2
    assert len(table.community_cards) == 3
    
    # Clear hands and verify
    table.clear_hands()
    assert len(table.players["p1"].hand.cards) == 0
    assert len(table.community_cards) == 0

def test_invalid_buyin():
    """Test adding a player with invalid buy-in amounts."""
    table = Table(max_players=6, min_buyin=100, max_buyin=1000)
    
    # Buy-in too low
    with pytest.raises(ValueError, match="Buy-in must be between 100 and 1000"):
        table.add_player("p1", "Alice", 50)
    
    # Buy-in too high
    with pytest.raises(ValueError, match="Buy-in must be between 100 and 1000"):
        table.add_player("p2", "Bob", 1500)

def test_add_player_to_full_table():
    """Test that adding a player to a full table raises an error."""
    table = Table(max_players=2, min_buyin=100, max_buyin=1000)
    
    table.add_player("p1", "Alice", 500)
    table.add_player("p2", "Bob", 500)
    
    # Attempt to add a third player to a full table
    with pytest.raises(ValueError, match="Table is full"):
        table.add_player("p3", "Charlie", 500)

def test_get_player_to_act():
    """Test that the correct player is chosen to act."""
    table = Table(max_players=3, min_buyin=100, max_buyin=1000)
    table.add_player("p1", "Alice", 500)
    table.add_player("p2", "Bob", 500)
    table.add_player("p3", "Charlie", 500)
    
    print([player.id for player in table.get_position_order()])

    # Pre-flop, first player to act after BB is UTG (p3)
    player = table.get_player_to_act(round_start=True)
    assert player is not None and player.id == "p1"
    
    # Move button and check again
    table.move_button()
    player = table.get_player_to_act(round_start=True)
    assert player is not None and player.id == "p2"

def test_remove_nonexistent_player():
    """Test removing a player who isn't at the table."""
    table = Table(max_players=6, min_buyin=100, max_buyin=1000)
    
    # Remove non-existent player (should not raise an error)
    table.remove_player("nonexistent_player")
    assert len(table.players) == 0  # Table remains unchanged

