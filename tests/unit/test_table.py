"""Unit tests for table positions and betting order."""
import pytest
from generic_poker.game.table import Table, Position

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
    assert positions[0].position.has_position(Position.BUTTON)
    assert positions[0].position.has_position(Position.SMALL_BLIND)
    assert positions[1].position.has_position(Position.BIG_BLIND)
    
    # Move button
    table.move_button()
    positions = table.get_position_order()
    assert [p.id for p in positions] == ["p2", "p1"]
    assert positions[0].position.has_position(Position.BUTTON)
    assert positions[0].position.has_position(Position.SMALL_BLIND)
    assert positions[1].position.has_position(Position.BIG_BLIND)

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
    assert positions[0].position.has_position(Position.BUTTON)
    assert positions[1].position.has_position(Position.SMALL_BLIND)
    assert positions[2].position.has_position(Position.BIG_BLIND)

def test_full_ring_positions():
    """Test position assignment in full ring game."""
    table = Table(max_players=9, min_buyin=100, max_buyin=1000)
    
    # Add six players
    for i in range(6):
        table.add_player(f"p{i+1}", f"Player {i+1}", 500)
    
    # Test initial positions
    positions = table.get_position_order()
    assert len(positions) == 6
    assert positions[0].position.has_position(Position.BUTTON)
    assert positions[1].position.has_position(Position.SMALL_BLIND)
    assert positions[2].position.has_position(Position.BIG_BLIND)
    
    # Other positions should be None
    for player in positions[3:]:
        assert player.position is None
    
    # Test button movement preserves core positions
    table.move_button()
    positions = table.get_position_order()
    assert positions[0].position.has_position(Position.BUTTON)
    assert positions[1].position.has_position(Position.SMALL_BLIND)
    assert positions[2].position.has_position(Position.BIG_BLIND)

def test_button_movement():
    """Test button movement preserves core positions."""
    table = Table(max_players=9, min_buyin=100, max_buyin=1000)
    
    # Add five players
    for i in range(5):
        table.add_player(f"p{i+1}", f"Player {i+1}", 500)
    
    # Test full orbit
    for i in range(5):
        positions = table.get_position_order()
        assert positions[0].position.has_position(Position.BUTTON)
        assert positions[1].position.has_position(Position.SMALL_BLIND)
        assert positions[2].position.has_position(Position.BIG_BLIND)
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
    assert positions[0].position.value == "BTN"
    assert positions[1].position.value == "BB"
    
    # Test 3+ players
    table.add_player("p3", "Charlie", 500)
    positions = table.get_position_order()
    assert positions[0].position.value == "BTN"
    assert positions[1].position.value == "SB"
    assert positions[2].position.value == "BB"

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
    assert positions[0].position.has_position(Position.BUTTON)
    assert positions[1].position.has_position(Position.SMALL_BLIND)
    assert positions[2].position.has_position(Position.BIG_BLIND)
    
    # Remove another player to force heads-up
    sb_player_id = positions[1].id
    table.remove_player(sb_player_id)
    
    # Verify heads-up positions
    positions = table.get_position_order()
    assert len(positions) == 2
    assert positions[0].position.has_position(Position.BUTTON)
    assert positions[0].position.has_position(Position.SMALL_BLIND)
    assert positions[1].position.has_position(Position.BIG_BLIND)

def test_player_addition_positions():
    """Test position assignments when players join the table."""
    table = Table(max_players=9, min_buyin=100, max_buyin=1000)
    
    # Start heads-up
    table.add_player("p1", "Alice", 500)
    table.add_player("p2", "Bob", 500)
    
    positions = table.get_position_order()
    assert len(positions) == 2
    assert positions[0].position.has_position(Position.BUTTON)
    assert positions[0].position.has_position(Position.SMALL_BLIND)
    
    # Add third player
    table.add_player("p3", "Charlie", 500)
    positions = table.get_position_order()
    assert len(positions) == 3
    assert positions[0].position.has_position(Position.BUTTON)
    assert not positions[0].position.has_position(Position.SMALL_BLIND)  # Should no longer be SB
    assert positions[1].position.has_position(Position.SMALL_BLIND)
    assert positions[2].position.has_position(Position.BIG_BLIND)

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
            assert positions[0].position.has_position(Position.BUTTON)
            assert positions[0].position.has_position(Position.SMALL_BLIND)
            assert positions[1].position.has_position(Position.BIG_BLIND)
        else:
            # 3+ players
            assert positions[0].position.has_position(Position.BUTTON)
            assert positions[1].position.has_position(Position.SMALL_BLIND)
            assert positions[2].position.has_position(Position.BIG_BLIND)
        
        # Move button through one complete orbit
        for _ in range(len(positions)):
            table.move_button()
            new_positions = table.get_position_order()
            if len(new_positions) < 3:  # Skip for 1-2 players
                continue
            # Core positions should always be assigned for 3+ players
            assert new_positions[0].position.has_position(Position.BUTTON)
            assert new_positions[1].position.has_position(Position.SMALL_BLIND)
            assert new_positions[2].position.has_position(Position.BIG_BLIND)

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

