"""Tests for simple straight poker game end-to-end."""
import pytest
from generic_poker.config.loader import GameRules
from generic_poker.game.game import Game, GameState, PlayerAction
from generic_poker.core.card import Card, Rank, Suit, Visibility
from generic_poker.game.betting import BettingStructure
from generic_poker.core.deck import Deck
from generic_poker.evaluation.hand_description import HandDescriber, EvaluationType
from tests.test_helpers import load_rules_from_file

import json 
import logging
import sys
from typing import List

class MockDeck(Deck):
    """A deck with predetermined card sequence for testing, followed by remaining cards."""
    def __init__(self, named_cards):
        super().__init__(include_jokers=False)
        self.cards.clear()
        # Add named cards in reverse order (last dealt first)
        for card in named_cards:
            self.cards.append(card)
        # Add remaining cards from a standard deck in deterministic order
        all_cards = [Card(rank, suit) for suit in [Suit.SPADES, Suit.HEARTS, Suit.DIAMONDS, Suit.CLUBS] for rank in [Rank.TWO, Rank.THREE, Rank.FOUR, Rank.FIVE, Rank.SIX, Rank.SEVEN, Rank.EIGHT, Rank.NINE, Rank.TEN, Rank.JACK, Rank.QUEEN, Rank.KING, Rank.ACE]]
        used_cards = {(c.rank, c.suit) for c in named_cards}
        remaining_cards = [c for c in all_cards if (c.rank, c.suit) not in used_cards]
        for card in reversed(remaining_cards):
            self.cards.append(card)

        # need to reverse self.cards to ensure the first card dealt is the first in the list
        self.cards.reverse()  # Reverse to maintain deal order

def create_predetermined_deck():
    """Create a deck with predetermined cards for testing."""
    # Create cards in the desired deal order (first card will be dealt first)
    # In this three-handed case, button is dealt first, then SB, then BB in order
    cards = [
        Card(Rank.ACE, Suit.HEARTS),    # BTN card 1
        Card(Rank.QUEEN, Suit.DIAMONDS), # SB card 1
        Card(Rank.FIVE, Suit.SPADES),   # BB card 1
        Card(Rank.KING, Suit.HEARTS),   # BTN card 2
        Card(Rank.FOUR, Suit.CLUBS),    # SB card 2
        Card(Rank.SIX, Suit.DIAMONDS),  # BB card 2
        Card(Rank.QUEEN, Suit.HEARTS),  # Community card 1
        Card(Rank.JACK, Suit.DIAMONDS), # Community card 2
        Card(Rank.TWO, Suit.CLUBS),     # SB third hole card
        Card(Rank.EIGHT, Suit.SPADES),  # BB third hole card
        Card(Rank.TEN, Suit.SPADES),    # BTN third hole card
        Card(Rank.TWO, Suit.HEARTS),    # Community card 3
        Card(Rank.FIVE, Suit.DIAMONDS), # Community card 4
        Card(Rank.TEN, Suit.HEARTS),    #
        Card(Rank.NINE, Suit.SPADES),   #
      
        # Rest of the deck in some order (won't be used in 5-card poker)
        # You can add more cards here if needed for other tests
    ]
    
    return MockDeck(cards)

def setup_test_game():
    """Setup a 3-player archie game with a mock deck."""
    rules = load_rules_from_file('texas_reach_around')
    game = Game(
        rules=rules,
        structure=BettingStructure.LIMIT,
        small_bet=10,
        big_bet=20,
        min_buyin=100,
        max_buyin=1000,
        auto_progress=False,
        named_bets={"protection_fee": 5}
    )
    game.add_player('BTN', 'Player1', 500)
    game.add_player('SB', 'Player2', 500)
    game.add_player('BB', 'Player3', 500)
    original_clear_hands = game.table.clear_hands
    def patched_clear_hands():
        for player in game.table.players.values():
            player.hand.clear()
        game.table.community_cards.clear()
    game.table.clear_hands = patched_clear_hands
    game.table.deck = create_predetermined_deck()
    assert len(game.table.deck.cards) >= 52, 'MockDeck should have at least 52 cards'
    return game

@pytest.fixture(autouse=True)
def setup_logging():
    """Set up logging for all tests."""
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ],
        force=True  # Force reconfiguration of logging
    )
    
def check_wild_cards(game, player_id, expected_wild_rank):
    """Helper function to check wild cards for a player."""
    player = game.table.players[player_id]
    actual_wild_rank = game.player_wild_ranks.get(player_id)
    
    print(f"\n=== Wild Card Check for {player.name} ===")
    print(f"Expected wild rank: {expected_wild_rank}")
    print(f"Actual wild rank: {actual_wild_rank}")
    print(f"Player's cards:")
    
    for i, card in enumerate(player.hand.cards):
        wild_status = "WILD" if card.is_wild else "normal"
        print(f"  Card {i+1}: {card} ({wild_status})")
    
    assert actual_wild_rank == expected_wild_rank, f"Expected {expected_wild_rank}, got {actual_wild_rank}"
    
    # Check that all cards of the wild rank are indeed wild
    for card in player.hand.cards:
        if card.rank == expected_wild_rank:
            assert card.is_wild, f"Card {card} should be wild but isn't"
        else:
            assert not card.is_wild, f"Card {card} should not be wild but is"

def test_protection_decision():
    """Test the card protection purchase mechanism."""
    game = setup_test_game()
    
    # Play a full hand
    game.start_hand()
    assert game.current_step == 0           # Should be in post blinds step
    assert game.state == GameState.BETTING  # Forced bets    
    game._next_step()  # Deal hole cards

    # Verify initial hole cards
    assert str(game.table.players['BTN'].hand.cards[0]) == "Ah"  # Player1
    assert str(game.table.players['BTN'].hand.cards[1]) == "Kh"  # Player1
    assert str(game.table.players['SB'].hand.cards[0]) == "Qd"   # Player2
    assert str(game.table.players['SB'].hand.cards[1]) == "4c"   # Player2
    assert str(game.table.players['BB'].hand.cards[0]) == "5s"   # Player3
    assert str(game.table.players['BB'].hand.cards[1]) == "6d"   # Player3

    # Check initial wild cards after first deal
    # BTN: Ah, Kh -> King is lowest -> Kings are wild
    # SB: Qd, 4c -> Four is lowest -> Fours are wild
    # BB: 5s, 6d -> Five is lowest -> Fives are wild
    check_wild_cards(game, 'BTN', Rank.KING)
    check_wild_cards(game, 'SB', Rank.FOUR)
    check_wild_cards(game, 'BB', Rank.FIVE)

    game._next_step()  # Move to pre-flop bet

    # Calculate initial pot from blinds
    blinds_pot = 15  # 5 (SB) + 10 (BB)    
    
    # check the current player
    assert game.current_player.id == 'BTN'

    # BTN acts first and calls
    game.player_action('BTN', PlayerAction.CALL, 10)
    game.player_action('SB', PlayerAction.CALL, 10)
    game.player_action('BB', PlayerAction.CHECK)

    # Calculate final pot: blinds + additional calls
    expected_pot = blinds_pot + 10 + 5  # BTN adds 10, SB adds 5    
    
    # Step 3: Deal First Community Card (Qh)
    game._next_step()
    assert game.current_step == 3
    assert game.state == GameState.DEALING

    # Verify community card
    assert str(game.table.community_cards['default'][0]) == "Qh"    

    # Step 4 Post-Flop Bet
    game._next_step()  
    assert game.current_step == 4
    assert game.state == GameState.BETTING
    assert game.current_player.id == "SB"  # SB acts first in post-flop betting rounds

    # SB checks
    game.player_action('SB', PlayerAction.CHECK)
    # BB checks
    game.player_action('BB', PlayerAction.CHECK)
    # BTN checks
    game.player_action('BTN', PlayerAction.CHECK)

    # Step 5: Deal Second Community Card (Jd)
    game._next_step()  
    assert game.current_step == 5
    assert game.state == GameState.DEALING

    # Verify second community card
    assert str(game.table.community_cards['default'][1]) == "Jd"    

    # Step 6: Turn Bet
    game._next_step()  
    assert game.current_step == 6
    assert game.state == GameState.BETTING    

    # SB checks
    game.player_action('SB', PlayerAction.CHECK)
    # BB checks
    game.player_action('BB', PlayerAction.CHECK)
    # BTN checks
    game.player_action('BTN', PlayerAction.CHECK)

    # Step 7: Deal Third Hole Card to each player - with player decision for protection
    game._next_step()  # Deal third hole card
    assert game.current_step == 7
    assert game.state == GameState.PROTECTION_DECISION        
    
    assert game.current_player.id == "SB"  # SB acts first in post-flop betting rounds
    valid_actions = game.get_valid_actions('SB')   
    assert (PlayerAction.PROTECT_CARD, 5, 5) in valid_actions
    assert (PlayerAction.DECLINE_PROTECTION, None, None) in valid_actions
    
    # Test declining protection
    result = game.player_action('SB', PlayerAction.PROTECT_CARD)
    assert result.success

    expected_pot = expected_pot + 5  # SB adds 5 for protecting hole card  

    assert game.current_player.id == "BB"  
    valid_actions = game.get_valid_actions('BB')   
    assert (PlayerAction.PROTECT_CARD, 5, 5) in valid_actions
    assert (PlayerAction.DECLINE_PROTECTION, None, None) in valid_actions

    # Test protection purchase
    result = game.player_action('BB', PlayerAction.DECLINE_PROTECTION)
    assert result.success

    assert game.current_player.id == "BTN"  
    valid_actions = game.get_valid_actions('BTN')   
    assert (PlayerAction.PROTECT_CARD, 5, 5) in valid_actions
    assert (PlayerAction.DECLINE_PROTECTION, None, None) in valid_actions

    # Test protection purchase
    result = game.player_action('BTN', PlayerAction.DECLINE_PROTECTION)
    assert result.success    

    # Test whether cards are face up or face down
    
    # SB has 3 face down cards, since they declined protection
    assert game.table.players['SB'].hand.cards[0].visibility == Visibility.FACE_DOWN
    assert game.table.players['SB'].hand.cards[1].visibility == Visibility.FACE_DOWN
    assert game.table.players['SB'].hand.cards[2].visibility == Visibility.FACE_UP

    # BB has 2 face down and 1 face up card, since they bought protection for their hole card
    assert game.table.players['BB'].hand.cards[0].visibility == Visibility.FACE_DOWN
    assert game.table.players['BB'].hand.cards[1].visibility == Visibility.FACE_DOWN
    assert game.table.players['BB'].hand.cards[2].visibility == Visibility.FACE_DOWN

    # BTN also protected their hole card, so they have 2 face down and 1 face up
    assert game.table.players['BTN'].hand.cards[0].visibility == Visibility.FACE_DOWN
    assert game.table.players['BTN'].hand.cards[1].visibility == Visibility.FACE_DOWN
    assert game.table.players['BTN'].hand.cards[2].visibility == Visibility.FACE_DOWN

    # Verify third hole cards
    assert str(game.table.players['SB'].hand.cards[2]) == "2c"   # Player2  
    assert str(game.table.players['BB'].hand.cards[2]) == "8s"   # Player3    
    assert str(game.table.players['BTN'].hand.cards[2]) == "Ts"  # Player1

    # Check wild cards after third hole card deal
    # SB: Qd, 4c, 2c -> Two is now lowest but protected the four so four is still wild
    # BB: 5s, 6d, 8s -> Five is still lowest -> Fives still wild
    # BTN: Ah, Kh, Ts -> Ten dealt face up - King is still the wild card

    check_wild_cards(game, 'SB', Rank.FOUR)
    check_wild_cards(game, 'BB', Rank.FIVE)
    check_wild_cards(game, 'BTN', Rank.TEN)

    # Step 8: Player Bet
    game._next_step()  
    assert game.current_step == 8
    assert game.state == GameState.BETTING    

    # SB checks
    game.player_action('SB', PlayerAction.CHECK)
    # BB checks
    game.player_action('BB', PlayerAction.CHECK)
    # BTN checks
    game.player_action('BTN', PlayerAction.CHECK)    

    # Step 9: Deal Third Community Card (2h)
    game._next_step()  # Deal turn
    assert game.current_step == 9
    assert game.state == GameState.DEALING

    # Verify third community card
    assert str(game.table.community_cards['default'][2]) == "2h"    

    # Step 10: River Bet
    game._next_step()  
    assert game.current_step == 10
    assert game.state == GameState.BETTING        

    # SB checks
    game.player_action('SB', PlayerAction.CHECK)
    # BB checks
    game.player_action('BB', PlayerAction.CHECK)
    # BTN checks
    game.player_action('BTN', PlayerAction.CHECK)    

    # Step 11: Deal Final Community Card (5d)
    game._next_step()  
    assert game.current_step == 11
    assert game.state == GameState.DEALING        

    # Verify final community card
    assert str(game.table.community_cards['default'][3]) == "5d"    

    # Step 12: Final Bet
    game._next_step()  
    assert game.current_step == 12
    assert game.state == GameState.BETTING        

    # SB checks
    game.player_action('SB', PlayerAction.CHECK)
    # BB checks
    game.player_action('BB', PlayerAction.CHECK)
    # BTN checks
    game.player_action('BTN', PlayerAction.CHECK)

    # Step 13: Showdown
    game._next_step()  # Move to showdown
    assert game.current_step == 13
    assert game.state == GameState.COMPLETE    

    # Final wild card check before showdown
    print("\n=== Final Wild Card Status Before Showdown ===")
    check_wild_cards(game, 'SB', Rank.FOUR)   # Twos wild  
    check_wild_cards(game, 'BB', Rank.FIVE)  # Fives wild    
    check_wild_cards(game, 'BTN', Rank.TEN)  # Tens wild

    # Print final hands for analysis
    print("\n=== Final Hands ===")
    for player_id, player in game.table.players.items():
        print(f"{player.name} ({player_id}):")
        print(f"  Hole cards: {[str(c) for c in player.hand.cards]}")
        print(f"  Wild rank: {game.player_wild_ranks.get(player_id)}")
        
    print(f"Community cards: {[str(c) for c in game.table.community_cards['default']]}")    

    # Get results
    results = game.get_hand_results()

    print("\nShowdown Results:")
    print(results)

    # Check overall results
    assert results.is_complete
    assert results.total_pot == expected_pot
    assert len(results.pots) == 1  # Just main pot
    assert len(results.hands) == 3  # All players stayed in

    # Check pot details
    main_pot = results.pots[0]
    assert main_pot.amount == expected_pot
    assert main_pot.pot_type == "main"
    assert not main_pot.split  # Only one winner
    assert len(main_pot.winners) == 1

    # Expected winner analysis:
    # BTN: Ah, Kh, Ts + Qh, Jd, 2h, 5d (Tens wild) -> Can make ace high flush with Ah,Kh,Qh,2h with Ts as wild 
    # SB: Qd, 4c, 2c + Qh, Jd, 2h, 5d (Fours wild) -> Can make queens over twos full house Qd, Qh, 4c (wild), 2c, 2h 
    # BB: 5s, 6d, 8s + Qh, Jd, 2h, 5d (Fives wild) -> Can make a queen high straight with Qj,Jd,8s and 5s and 5d as wild cards
    
    # With wild cards, SB should have the best hand (four of a kind with wild twos)

    assert 'SB' in main_pot.winners

    winning_hand = results.hands['SB']
    assert "Full House" in winning_hand[0].hand_name
    assert "Full House, Queens over Twos" in winning_hand[0].hand_description

    # Check winning hands list
    assert len(results.winning_hands) == 1
    assert results.winning_hands[0].player_id == 'SB'    

