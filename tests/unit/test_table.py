"""Unit tests for enhanced table with seat-based functionality."""
import pytest
from generic_poker.game.table import Table, TableLayout, Seat, SeatStatus
from generic_poker.game.player import Position
from generic_poker.core.card import Visibility

def has_position(player, pos):
    """Helper to check if a player has a specific position."""
    return player.position is not None and player.position.has_position(pos)

def has_position_value(player, value):
    """Helper to check if a player has a specific position value."""
    return player.position is not None and player.position.value == value

# === NEW SEAT FUNCTIONALITY TESTS ===

def test_seat_creation():
    """Test basic seat creation and status management."""
    seat = Seat(number=1)
    assert seat.number == 1
    assert seat.status == SeatStatus.EMPTY
    assert seat.player is None
    assert seat.is_available() is True

def test_seat_occupation():
    """Test occupying and vacating seats."""
    from generic_poker.game.player import Player
    
    seat = Seat(number=1)
    player = Player(id="p1", name="Alice", stack=1000)
    
    # Occupy seat
    seat.occupy(player)
    assert seat.status == SeatStatus.OCCUPIED
    assert seat.player == player
    assert seat.is_available() is False
    
    # Try to occupy again (should raise error)
    player2 = Player(id="p2", name="Bob", stack=1000)
    with pytest.raises(ValueError, match="Seat 1 is not available"):
        seat.occupy(player2)
    
    # Vacate seat
    returned_player = seat.vacate()
    assert returned_player == player
    assert seat.status == SeatStatus.EMPTY
    assert seat.player is None
    assert seat.is_available() is True

def test_seat_reservation():
    """Test seat reservation functionality."""
    seat = Seat(number=1)
    
    # Reserve seat
    seat.reserve("p1")
    assert seat.status == SeatStatus.RESERVED
    assert seat.reserved_for == "p1"
    assert seat.is_available() is False
    
    # Try to reserve again (should raise error)
    with pytest.raises(ValueError, match="Seat 1 is not available"):
        seat.reserve("p2")

def test_table_layout():
    """Test TableLayout functionality."""
    layout = TableLayout(max_seats=6)
    
    # Test initialization
    assert layout.max_seats == 6
    assert len(layout.seats) == 6
    assert all(seat.is_available() for seat in layout.seats.values())
    
    # Test available seats
    assert layout.get_available_seats() == [1, 2, 3, 4, 5, 6]
    assert layout.get_occupied_seats() == []

def test_table_layout_player_assignment():
    """Test assigning players to specific seats."""
    from generic_poker.game.player import Player
    
    layout = TableLayout(max_seats=4)
    player1 = Player(id="p1", name="Alice", stack=1000)
    player2 = Player(id="p2", name="Bob", stack=1000)
    
    # Assign to specific seats
    layout.assign_player_to_seat(player1, 2)
    layout.assign_player_to_seat(player2, 4)
    
    assert layout.get_occupied_seats() == [2, 4]
    assert layout.get_available_seats() == [1, 3]
    assert layout.get_player_seat("p1") == 2
    assert layout.get_player_seat("p2") == 4
    
    # Try to assign same player again
    with pytest.raises(ValueError, match="Player Alice is already seated"):
        layout.assign_player_to_seat(player1, 1)
    
    # Try to assign to occupied seat
    player3 = Player(id="p3", name="Charlie", stack=1000)
    with pytest.raises(ValueError, match="Seat 2 is not available"):
        layout.assign_player_to_seat(player3, 2)

def test_table_layout_random_assignment():
    """Test random seat assignment."""
    from generic_poker.game.player import Player
    
    layout = TableLayout(max_seats=3)
    player = Player(id="p1", name="Alice", stack=1000)
    
    # Random assignment should work
    seat_num = layout.assign_random_seat(player)
    assert seat_num in [1, 2, 3]
    assert layout.get_player_seat("p1") == seat_num
    
    # Fill remaining seats
    player2 = Player(id="p2", name="Bob", stack=1000)
    player3 = Player(id="p3", name="Charlie", stack=1000)
    layout.assign_random_seat(player2)
    layout.assign_random_seat(player3)
    
    # No more seats available
    player4 = Player(id="p4", name="David", stack=1000)
    with pytest.raises(ValueError, match="No available seats"):
        layout.assign_random_seat(player4)

def test_enhanced_table_initialization():
    """Test enhanced table initialization."""
    table = Table(max_seats=6, min_buyin=100, max_buyin=1000)
    
    assert table.max_players == 6
    assert table.layout.max_seats == 6
    assert table.button_seat == 1
    assert len(table.get_available_seats()) == 6
    assert len(table.get_occupied_seats()) == 0

def test_add_player_with_preferred_seat():
    """Test adding players with preferred seat selection."""
    table = Table(max_seats=4, min_buyin=100, max_buyin=1000)
    
    # Add player to specific seat
    seat_num = table.add_player("p1", "Alice", 500, preferred_seat=3)
    assert seat_num == 3
    assert table.get_player_seat_number("p1") == 3
    assert table.get_player_in_seat(3).name == "Alice"
    
    # Try to add to same seat (should fail)
    with pytest.raises(ValueError, match="Seat 3 is not available"):
        table.add_player("p2", "Bob", 500, preferred_seat=3)
    
    # Invalid seat number
    with pytest.raises(ValueError, match="Invalid seat number: 10"):
        table.add_player("p2", "Bob", 500, preferred_seat=10)

def test_add_player_random_seat():
    """Test adding players to random seats."""
    table = Table(max_seats=3, min_buyin=100, max_buyin=1000)
    
    # Add without preferred seat (should get sequential for backward compatibility)
    seat1 = table.add_player("p1", "Alice", 500)
    assert seat1 == 1  # Should get seat 1 (first available)
    
    # Add another (should get next sequential seat)
    seat2 = table.add_player("p2", "Bob", 500)
    assert seat2 == 2  # Should get seat 2 (next available)
    
    # Use convenience method for truly random assignment
    seat3 = table.add_player_to_random_seat("p3", "Charlie", 500)
    assert seat3 == 3  # Only seat left

def test_seat_reservations():
    """Test seat reservation functionality."""
    table = Table(max_seats=4, min_buyin=100, max_buyin=1000)
    
    # Reserve a seat
    table.reserve_seat(2, "future_player")
    assert 2 not in table.get_available_seats()
    
    # Can't add player to reserved seat
    with pytest.raises(ValueError, match="Seat 2 is not available"):
        table.add_player("p1", "Alice", 500, preferred_seat=2)

def test_enhanced_button_movement():
    """Test button movement with seat-based system."""
    table = Table(max_seats=5, min_buyin=100, max_buyin=1000)
    
    # Add players to non-consecutive seats
    table.add_player("p1", "Alice", 500, preferred_seat=2)
    table.add_player("p2", "Bob", 500, preferred_seat=4)
    table.add_player("p3", "Charlie", 500, preferred_seat=1)
    
    # Button should start at seat 1 by default
    assert table.button_seat == 1
    
    # Move button - should go to next occupied seat (seat 2)
    table.move_button()
    assert table.button_seat == 2
    
    # Move again - should go to seat 4
    table.move_button()
    assert table.button_seat == 4
    
    # Move again - should wrap to seat 1
    table.move_button()
    assert table.button_seat == 1

def test_position_order_with_seats():
    """Test position ordering based on seat numbers."""
    table = Table(max_seats=6, min_buyin=100, max_buyin=1000)
    
    # Add players in non-sequential order
    table.add_player("p3", "Charlie", 500, preferred_seat=3)
    table.add_player("p1", "Alice", 500, preferred_seat=1)
    table.add_player("p5", "Eve", 500, preferred_seat=5)
    
    # Set button to seat 3
    table.button_seat = 3
    
    # Position order should be: seat 3, seat 5, seat 1 (clockwise from button)
    positions = table.get_position_order()
    expected_order = ["p3", "p5", "p1"]  # Charlie, Eve, Alice
    assert [p.id for p in positions] == expected_order
    
    # Check position assignments
    assert has_position(positions[0], Position.BUTTON)      # Charlie
    assert has_position(positions[1], Position.SMALL_BLIND) # Eve
    assert has_position(positions[2], Position.BIG_BLIND)   # Alice

# === UPDATED EXISTING TESTS ===

def test_heads_up_positions():
    """Test position assignment in heads-up play."""
    table = Table(max_seats=9, min_buyin=100, max_buyin=1000)
    
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
    table = Table(max_seats=9, min_buyin=100, max_buyin=1000)
    
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
    table = Table(max_seats=9, min_buyin=100, max_buyin=1000)
    
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
    table = Table(max_seats=9, min_buyin=100, max_buyin=1000)
    
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
    table = Table(max_seats=9, min_buyin=100, max_buyin=1000)
    
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
    table = Table(max_seats=9, min_buyin=100, max_buyin=1000)
    
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
    table = Table(max_seats=9, min_buyin=100, max_buyin=1000)
    
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

def test_invalid_position_cases():
    """Test edge cases and invalid scenarios for positions."""
    table = Table(max_seats=9, min_buyin=100, max_buyin=1000)
    
    # Empty table should return empty position list
    positions = table.get_position_order()
    assert len(positions) == 0
    
    # Single player should have BTN position now (changed from original)
    table.add_player("p1", "Alice", 500)
    positions = table.get_position_order()
    assert len(positions) == 1
    assert has_position(positions[0], Position.BUTTON)  # Single player gets button
    
    # Test button movement with single player (should not error)
    table.move_button()  # Should not raise exception

def test_deal_hole_cards():
    """Test dealing hole cards to active players."""
    table = Table(max_seats=6, min_buyin=100, max_buyin=1000)
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
    table = Table(max_seats=6, min_buyin=100, max_buyin=1000)
    
    # Deal 3 flop cards
    table.deal_community_cards(3)
    assert table.get_community_card_count() == 3 
    assert all(card.visibility == Visibility.FACE_UP for card in table.community_cards["default"])
    
    # Deal 1 turn card
    table.deal_community_cards(1)
    assert table.get_community_card_count() == 4

def test_clear_hands():
    """Test clearing player hands and community cards."""
    table = Table(max_seats=6, min_buyin=100, max_buyin=1000)
    
    # Add players and deal cards
    table.add_player("p1", "Alice", 500)
    table.add_player("p2", "Bob", 500)
    table.deal_hole_cards(2)
    table.deal_community_cards(3)
    
    # Ensure cards are dealt
    assert len(table.players["p1"].hand.cards) == 2
    assert table.get_community_card_count() == 3 
    
    # Clear hands and verify
    table.clear_hands()
    assert len(table.players["p1"].hand.cards) == 0
    assert table.get_community_card_count() == 0

def test_invalid_buyin():
    """Test adding a player with invalid buy-in amounts."""
    table = Table(max_seats=6, min_buyin=100, max_buyin=1000)
    
    # Buy-in too low
    with pytest.raises(ValueError, match="Buy-in must be between 100 and 1000"):
        table.add_player("p1", "Alice", 50)
    
    # Buy-in too high
    with pytest.raises(ValueError, match="Buy-in must be between 100 and 1000"):
        table.add_player("p2", "Bob", 1500)

def test_add_player_to_full_table():
    """Test that adding a player to a full table raises an error."""
    table = Table(max_seats=2, min_buyin=100, max_buyin=1000)
    
    table.add_player("p1", "Alice", 500)
    table.add_player("p2", "Bob", 500)
    
    # Attempt to add a third player to a full table
    with pytest.raises(ValueError, match="Table is full"):
        table.add_player("p3", "Charlie", 500)

def test_get_player_to_act():
    """Test that the correct player is chosen to act."""
    table = Table(max_seats=3, min_buyin=100, max_buyin=1000)
    table.add_player("p1", "Alice", 500)
    table.add_player("p2", "Bob", 500)
    table.add_player("p3", "Charlie", 500)
    
    positions = table.get_position_order()

    # Pre-flop with 3 players, first player is BTN (p1)
    player = table.get_player_to_act(round_start=True)
    assert player is not None and player.id == "p1"
    
    # Post-flop, first player should be SB (p2)
    player = table.get_player_to_act(round_start=False)
    assert player is not None and player.id == "p2"

def test_remove_nonexistent_player():
    """Test removing a player who isn't at the table."""
    table = Table(max_seats=6, min_buyin=100, max_buyin=1000)
    
    # Remove non-existent player (should not raise an error)
    table.remove_player("nonexistent_player")
    assert len(table.players) == 0  # Table remains unchanged

# === BACKWARD COMPATIBILITY TESTS ===

def test_max_players_backward_compatibility():
    """Test that max_players parameter still works for backward compatibility."""
    # Old way should still work
    table = Table(max_players=6, min_buyin=100, max_buyin=1000)
    assert table.max_players == 6
    assert table.layout.max_seats == 6
    
    # New way should work
    table2 = Table(max_seats=8, min_buyin=100, max_buyin=1000)
    assert table2.max_players == 8
    assert table2.layout.max_seats == 8
    
    # Can't specify both with different values
    with pytest.raises(ValueError, match="Cannot specify both max_seats and max_players"):
        Table(max_seats=6, max_players=8, min_buyin=100, max_buyin=1000)
    
    # Must specify at least one
    with pytest.raises(ValueError, match="Either max_seats or max_players must be specified"):
        Table(min_buyin=100, max_buyin=1000)

def test_backward_compatibility_methods():
    """Test that old methods still work for existing code."""
    table = Table(max_players=5, min_buyin=100, max_buyin=1000)
    
    # Add some players
    table.add_player("p1", "Alice", 500)
    table.add_player("p2", "Bob", 500)
    table.add_player("p3", "Charlie", 500)
    
    # Test button_pos property (0-based index)
    button_pos = table.button_pos
    assert isinstance(button_pos, int)
    assert 0 <= button_pos < 3
    
    # Test get_next_active_player
    next_player = table.get_next_active_player(button_pos)
    assert next_player is not None
    assert next_player.is_active
    
    # Test with inactive player
    table.players["p2"].is_active = False
    next_player = table.get_next_active_player(0)
    assert next_player is not None
    assert next_player.is_active
    assert next_player.id != "p2"  # Should skip inactive player
    
    # Test get_player_after_big_blind
    bb_player = table.get_player_after_big_blind()
    # Should return a player or None (depending on positions)
    if bb_player:
        assert bb_player.is_active

# === ADDITIONAL EDGE CASE TESTS ===

def test_invalid_table_sizes():
    """Test invalid table size configurations."""
    # Too few seats
    with pytest.raises(ValueError, match="Table must have between 2 and 10 seats"):
        TableLayout(max_seats=1)
    
    # Too many seats
    with pytest.raises(ValueError, match="Table must have between 2 and 10 seats"):
        TableLayout(max_seats=11)

def test_button_position_edge_cases():
    """Test button position with various player configurations."""
    table = Table(max_seats=5, min_buyin=100, max_buyin=1000)
    
    # Add players to seats 1, 3, 5
    table.add_player("p1", "Alice", 500, preferred_seat=1)
    table.add_player("p3", "Charlie", 500, preferred_seat=3)
    table.add_player("p5", "Eve", 500, preferred_seat=5)
    
    # Set button to seat 2 (unoccupied)
    table.button_seat = 2
    
    # Move button should go to next occupied seat (seat 3)
    table.move_button()
    assert table.button_seat == 3
    
    # Remove player in button seat
    table.remove_player("p3")
    
    # Position order should still work
    positions = table.get_position_order()
    assert len(positions) == 2

def test_mixed_seat_operations():
    """Test complex seat operation scenarios."""
    table = Table(max_seats=4, min_buyin=100, max_buyin=1000)
    
    # Reserve seat 2
    table.reserve_seat(2, "future_player")
    
    # Add players to other seats
    table.add_player("p1", "Alice", 500, preferred_seat=1)
    table.add_player("p3", "Charlie", 500, preferred_seat=3)
    
    # Available seats should exclude occupied and reserved
    available = table.get_available_seats()
    assert available == [4]
    
    # Add last player
    table.add_player("p4", "David", 500)  # Should get seat 4
    assert table.get_player_seat_number("p4") == 4
    
    # Now table should be full
    with pytest.raises(ValueError, match="Table is full"):
        table.add_player("p5", "Eve", 500)

def test_button_with_inactive_players():
    """Test button movement when some players are inactive."""
    table = Table(max_seats=4, min_buyin=100, max_buyin=1000)
    
    # Add players
    table.add_player("p1", "Alice", 500)
    table.add_player("p2", "Bob", 500)
    table.add_player("p3", "Charlie", 500)
    
    # Make one player inactive
    table.players["p2"].is_active = False
    
    # Position order should only include active players when we specifically want that
    positions = table.get_active_players_in_order()
    assert len(positions) == 2
    assert all(p.is_active for p in positions)
    
    # Button movement should work with inactive players
    table.move_button()
    positions = table.get_active_players_in_order()
    assert len(positions) == 2