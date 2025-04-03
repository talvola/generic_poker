"""Tests for 7 card stud end-to-end."""
import pytest
from generic_poker.config.loader import GameRules
from generic_poker.game.game import Game, GameState, PlayerAction
from generic_poker.core.card import Card, Rank, Suit, Visibility
from generic_poker.game.betting import BettingStructure, PlayerBet
from generic_poker.core.deck import Deck
from generic_poker.evaluation.hand_description import HandDescriber, EvaluationType

from tests.test_helpers import load_rules_from_file

import json 
import logging
import sys
from typing import List

class MockDeck(Deck):
    """A deck with predetermined card sequence for testing."""
    
    def __init__(self, cards: List[Card]):
        """
        Initialize a mock deck with specific cards.
        
        Args:
            cards: The cards to use, in reverse order of dealing 
                  (last card in list will be dealt first)
        """
        super().__init__(include_jokers=False)  # Initialize parent
        self.cards.clear()  # Clear the automatically generated cards
        
        # Add the provided cards in reverse order so the first card in the list
        # will be the last card dealt
        for card in reversed(cards):
            self.cards.append(card)

def create_predetermined_deck():
    """Create a deck with predetermined cards for testing."""
    # Create cards in the desired deal order (first card will be dealt first)
    # In this three-handed case, button is dealt first, then SB, then BB in order
    cards = [
        Card(Rank.ACE, Suit.HEARTS), #Alice FD HOLE
        Card(Rank.QUEEN, Suit.DIAMONDS), #Bob FD HOLE
        Card(Rank.JACK, Suit.SPADES), #Charlie FD HOLE
        Card(Rank.KING, Suit.HEARTS), #Alice FD HOLE2
        Card(Rank.KING, Suit.CLUBS), #Bob FD HOLE2
        Card(Rank.JACK, Suit.DIAMONDS), #Charlie FD HOLE2
        Card(Rank.QUEEN, Suit.HEARTS), #Alice DOOR CARD
        Card(Rank.KING, Suit.DIAMONDS), #Bob DOOR CARD
        Card(Rank.TWO, Suit.CLUBS), #Charlie DOOR CARD
        Card(Rank.TEN, Suit.SPADES), #Alice 4TH ST
        Card(Rank.QUEEN, Suit.CLUBS), #Bob 4TH ST
        Card(Rank.QUEEN, Suit.SPADES), #Charlie 4TH ST
        Card(Rank.JACK, Suit.HEARTS), #Alice 5TH ST
        Card(Rank.TEN, Suit.DIAMONDS), #Bob 5TH ST
        Card(Rank.TEN, Suit.HEARTS), #Charlie 5TH ST
        Card(Rank.NINE, Suit.SPADES), #Alice 6TH ST
        Card(Rank.SEVEN, Suit.SPADES), #Bob 6TH ST
        Card(Rank.SIX, Suit.SPADES), #Charlie 6TH ST
        Card(Rank.NINE, Suit.DIAMONDS), #Alice 7TH ST
        Card(Rank.SEVEN, Suit.HEARTS), #Bob 7TH ST
        Card(Rank.SIX, Suit.CLUBS), #Charlie 7TH ST

        # Rest of the deck in some order (won't be used in 5-card poker)
        # You can add more cards here if needed for other tests
    ]
    
    return MockDeck(cards)

def setup_test_game_with_mock_deck():
    """Create a test game with three players and a predetermined deck."""
    rules = load_rules_from_file('razz')

    game = Game(
        rules=rules,
        structure=BettingStructure.LIMIT,
        small_bet=10,
        big_bet=20,
        bring_in=3,
        ante=1,
        min_buyin=100,
        max_buyin=1000,
        auto_progress=False        
    )
  
    # Add players
    game.add_player("p1", "Alice", 500)
    game.add_player("p2", "Bob", 500)
    game.add_player("p3", "Charlie", 500)
    
    # Monkey patch the Table.clear_hands method to preserve our mock deck
    original_clear_hands = game.table.clear_hands
    
    def patched_clear_hands():
        """Clear hands but keep our mock deck."""
        for player in game.table.players.values():
            player.hand.clear()
        game.table.community_cards.clear()
        # Note: We don't reset the deck here
    
    # Replace the method
    game.table.clear_hands = patched_clear_hands
    
    # Set our mock deck
    game.table.deck = create_predetermined_deck()
    
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
    
def test_game_deal():
    """Test that the game results API provides correct information."""
    game = setup_test_game_with_mock_deck()
    
    # Play a full hand
    game.start_hand()
    assert game.current_step == 0           # Should be in post antes step
    assert game.state == GameState.BETTING  # Forced bets    
    game._next_step()  # Deal hole cards

    # check each player's face up card (door card)
    #Card(Rank.QUEEN, Suit.HEARTS), #Alice DOOR CARD
    #Card(Rank.KING, Suit.DIAMONDS), #Bob DOOR CARD
    #Card(Rank.TWO, Suit.CLUBS), #Charlie DOOR CARD    
    print (game.table.players['p1'].hand.get_cards())

    assert game.table.players['p1'].hand.get_cards(visible_only=True) == [Card(Rank.QUEEN, Suit.HEARTS)]
    assert game.table.players['p2'].hand.get_cards(visible_only=True) == [Card(Rank.KING, Suit.DIAMONDS)]
    assert game.table.players['p3'].hand.get_cards(visible_only=True) == [Card(Rank.TWO, Suit.CLUBS)]

def test_game_ante():
    """Test that the game results API provides correct information."""
    game = setup_test_game_with_mock_deck()
    
    # Play a full hand
    game.start_hand()
    assert game.current_step == 0           # Should be in post antes step
    assert game.state == GameState.BETTING  # Forced bets    

    # check each player's ante
    assert game.table.players['p1'].stack == 499
    assert game.table.players['p2'].stack == 499
    assert game.table.players['p3'].stack == 499

    # check the pot
    assert game.betting.get_main_pot_amount() == 3

def test_game_bringin():
    """Test that the game results API provides correct information."""
    game = setup_test_game_with_mock_deck()
    
    # Initial stacks (assume 500 each)
    initial_stacks = {pid: player.stack for pid, player in game.table.players.items()}
    assert all(stack == 500 for stack in initial_stacks.values())

    # Step 0: Post Antes
    game.start_hand()
    assert game.current_step == 0  # Post Antes
    assert game.state == GameState.BETTING
    assert game.table.players['p1'].stack == 499  # Ante deducted
    assert game.table.players['p2'].stack == 499
    assert game.table.players['p3'].stack == 499
    assert game.betting.get_main_pot_amount() == 3  # 3 players x $1
    assert game.betting.get_ante_total() == 3  # 3 players x $1

    # test current_bets in BettingManager
    assert game.betting.current_bets == {'p1': PlayerBet(amount=1, has_acted=False, posted_blind=False, is_all_in=False),
                                         'p2': PlayerBet(amount=1, has_acted=False, posted_blind=False, is_all_in=False),
                                         'p3': PlayerBet(amount=1, has_acted=False, posted_blind=False, is_all_in=False)}
    # also test total_bets and total_antes from Pot
    assert game.betting.pot.total_bets == {'round_2_p1': 1, 'round_2_p2': 1, 'round_2_p3': 1}
    assert game.betting.pot.total_antes == {'round_2_p1': 1, 'round_2_p2': 1, 'round_2_p3': 1}

    # Step 1: Deal Hole Cards (2 down, 1 up)
    game._next_step()
    assert game.current_step == 1
    assert game.state == GameState.DEALING
    # Verify door cards (exposed)
    assert str(game.table.players['p1'].hand.cards[2]) == "Qh"  # Alice
    assert str(game.table.players['p2'].hand.cards[2]) == "Kd"  # Bob
    assert str(game.table.players['p3'].hand.cards[2]) == "2c"  # Charlie

    # pot unchanged
    assert game.betting.get_main_pot_amount() == 3  # 3 players x $1
    assert game.betting.get_ante_total() == 3  # 3 players x $1

    # test current_bets in BettingManager
    assert game.betting.current_bets == {'p1': PlayerBet(amount=1, has_acted=False, posted_blind=False, is_all_in=False),
                                         'p2': PlayerBet(amount=1, has_acted=False, posted_blind=False, is_all_in=False),
                                         'p3': PlayerBet(amount=1, has_acted=False, posted_blind=False, is_all_in=False)}
    # also test total_bets and total_antes from Pot
    assert game.betting.pot.total_bets == {'round_2_p1': 1, 'round_2_p2': 1, 'round_2_p3': 1}
    assert game.betting.pot.total_antes == {'round_2_p1': 1, 'round_2_p2': 1, 'round_2_p3': 1}

    # Step 2: Post Bring-In
    game._next_step()
    assert game.current_step == 2
    assert game.state == GameState.BETTING
    assert game.current_player.id == "p2"  # Charlie has 2♣, lowest card

    # pot unchanged before actions
    assert game.betting.get_main_pot_amount() == 3  # 3 players x $1
    assert game.betting.get_ante_total() == 3  # 3 players x $1    

    # Check valid actions for bring-in player (Charlie)
    valid_actions = game.get_valid_actions("p2")
    assert len(valid_actions) == 2  # Bring-in or complete
    assert (PlayerAction.BRING_IN, 3, 3) in valid_actions  # Bring-in amount ($3)
    assert (PlayerAction.BET, 10, 10) in valid_actions  # Complete to small bet ($10)
    
    # Bob posts bring-in ($3)
    result = game.player_action("p2", PlayerAction.BRING_IN, 3)
    assert result.success
    assert result.advance_step  # Done with bring-in step
    # P1 and P3 unchanged
    assert game.table.players['p1'].stack == 499  # Ante deducted
    assert game.table.players['p3'].stack == 499
    # P2 has ante and bring-in
    assert game.table.players["p2"].stack == 496  # 499 - 3
    assert game.betting.current_bet == 3
    assert game.betting.get_main_pot_amount() == 6  # 3 + 3
    assert game.betting.get_ante_total() == 3  # 3 players x $1

    # test current_bets in BettingManager
    assert game.betting.current_bets == {'p1': PlayerBet(amount=1, has_acted=False, posted_blind=False, is_all_in=False),
                                         'p3': PlayerBet(amount=1, has_acted=False, posted_blind=False, is_all_in=False),
                                         'p2': PlayerBet(amount=4, has_acted=False, posted_blind=True, is_all_in=False)}
    # also test total_bets and total_antes from Pot
    assert game.betting.pot.total_bets == {'round_2_p1': 1, 'round_2_p2': 4, 'round_2_p3': 1}
    assert game.betting.pot.total_antes == {'round_2_p1': 1, 'round_2_p2': 1, 'round_2_p3': 1}    

    # Step 3: Third Street Bet (others can act)
    game._next_step()
    assert game.current_step == 3
    assert game.state == GameState.BETTING
    assert game.betting.get_main_pot_amount() == 6  # 3 + 3
    assert game.betting.get_ante_total() == 3  # 3 players x $1

    assert game.current_player.id == "p3" 
    valid_actions = game.get_valid_actions("p3")
    assert (PlayerAction.FOLD, None, None) in valid_actions
    assert (PlayerAction.CALL, 3, 3) in valid_actions  # Call $3
    assert (PlayerAction.BET, 10, 10) in valid_actions  # Raise to $10 (small bet)  

    # complete to $10
    result = game.player_action("p3", PlayerAction.BET, 10)
    assert result.success
    assert game.betting.current_bet == 10  # Passes
    assert game.table.players["p3"].stack == 489
    assert game.betting.get_main_pot_amount() == 16  # 3 ante + 3 bring-in + 10 complete
    assert game.betting.get_ante_total() == 3  # 3 players x $1

    assert game.current_player.id == "p1"  # 
    valid_actions = game.get_valid_actions("p1")
    assert (PlayerAction.FOLD, None, None) in valid_actions
    assert (PlayerAction.CALL, 10, 10) in valid_actions  # Call $10
    assert (PlayerAction.RAISE, 20, 20) in valid_actions  # Raise to $20 

    # raise to $20
    result = game.player_action("p1", PlayerAction.RAISE, 20)
    assert result.success
    assert game.betting.current_bet == 20  # Passes
    assert game.table.players["p1"].stack == 479
    assert game.betting.get_main_pot_amount() == 36  # 3 ante + 3 bring-in + 10 complete + 20 raise
    assert game.betting.get_ante_total() == 3  # 3 players x $1
    
    # calls $20 (needs 17 more: 20 - 3)
    result = game.player_action("p2", PlayerAction.CALL, 20)
    assert result.success
    assert game.betting.current_bet == 20
    assert game.table.players["p2"].stack == 479  # 496 - 17
    assert game.betting.get_main_pot_amount() == 53  # 36 + 17

    # calls $20 (needs 10 more: 20 - 10 already in)
    assert game.current_player.id == "p3"  # Back to Alice
    valid_actions = game.get_valid_actions("p3")
    assert (PlayerAction.FOLD, None, None) in valid_actions
    assert (PlayerAction.CALL, 20, 20) in valid_actions
    assert (PlayerAction.RAISE, 30, 30) in valid_actions  # Next raise is 20 + 10   

    result = game.player_action("p3", PlayerAction.CALL, 20)
    assert result.success
    assert game.betting.current_bet == 20
    assert game.table.players["p3"].stack == 479  # 489 - 10
    assert game.betting.get_main_pot_amount() == 63  # 53 + 10
    assert game.betting.get_ante_total() == 3

    # Step 4: Deal Fourth Street (fourth card, face up)
    game._next_step()
    assert game.current_step == 4
    assert game.state == GameState.DEALING
    # Check cards: Alice: Ah,Kh,Qh,10s; Bob: Qd,Kc,Kd,Qc; Charlie: Js,Jd,2c,Qs
    assert len(game.table.players["p1"].hand.cards) == 4
    assert len(game.table.players["p2"].hand.cards) == 4
    assert len(game.table.players["p3"].hand.cards) == 4
    assert str(game.table.players["p1"].hand.cards[3]) == "Ts"  # Alice’s fourth card
    assert str(game.table.players["p2"].hand.cards[3]) == "Qc"   # Bob’s fourth card
    assert str(game.table.players["p3"].hand.cards[3]) == "Qs"   # Charlie’s fourth card
    assert game.table.players["p1"].hand.cards[3].visibility == Visibility.FACE_UP
    assert game.table.players["p2"].hand.cards[3].visibility == Visibility.FACE_UP
    assert game.table.players["p3"].hand.cards[3].visibility == Visibility.FACE_UP
    assert game.betting.get_main_pot_amount() == 63
    assert game.betting.get_ante_total() == 3

    # Step 5: Fourth Street Bet (small bet, high hand first, no bring-in)
    game._next_step()
    assert game.current_step == 5
    assert game.state == GameState.BETTING
    assert game.betting.get_main_pot_amount() == 63 # from before
    assert game.betting.get_ante_total() == 0  # antes have been cleared in this round  

    # Upcards: Alice: Qh,10s; Bob: Kd,Qc; Charlie: 2c,Qs
    # Charlie has lowest (2c,Qs), starts betting
    assert game.current_player.id == "p3"  # 
    valid_actions = game.get_valid_actions("p3")
    assert (PlayerAction.FOLD, None, None) in valid_actions
    assert (PlayerAction.CHECK, None, None) in valid_actions  # No bring-in
    assert (PlayerAction.BET, 10, 10) in valid_actions  # Small bet

    # Charlie bets $10
    result = game.player_action("p3", PlayerAction.BET, 10)
    assert result.success
    assert game.betting.current_bet == 10
    assert game.table.players["p3"].stack == 469  # 479 - 10
    assert game.betting.get_main_pot_amount() == 73  # 63 + 10

    # Alice calls $10
    assert game.current_player.id == "p1"  # Charlie next
    valid_actions = game.get_valid_actions("p1")
    assert (PlayerAction.FOLD, None, None) in valid_actions
    assert (PlayerAction.CALL, 10, 10) in valid_actions
    result = game.player_action("p1", PlayerAction.CALL, 10)
    assert result.success
    assert game.table.players["p1"].stack == 469  # 479 - 10
    assert game.betting.get_main_pot_amount() == 83  # 73 + 10    

    # Bob calls $10
    assert game.current_player.id == "p2"  # Alice next
    valid_actions = game.get_valid_actions("p2")
    assert (PlayerAction.FOLD, None, None) in valid_actions
    assert (PlayerAction.CALL, 10, 10) in valid_actions
    result = game.player_action("p2", PlayerAction.CALL, 10)
    assert result.success
    assert game.table.players["p2"].stack == 469  # 479 - 10
    assert game.betting.get_main_pot_amount() == 93  # 83 + 10    
   
    # Step 6: Deal Fifth Street
    game._next_step()
    assert game.current_step == 6
    assert game.state == GameState.DEALING
    assert len(game.table.players["p1"].hand.cards) == 5  # Alice: Ah,Kh,Qh,Ts,Jh
    assert len(game.table.players["p2"].hand.cards) == 5  # Bob: Qd,Kc,Kd,Qc,Td
    assert len(game.table.players["p3"].hand.cards) == 5  # Charlie: Js,Jd,2c,Qs,Th
    assert str(game.table.players["p1"].hand.cards[4]) == "Jh"
    assert str(game.table.players["p2"].hand.cards[4]) == "Td"
    assert str(game.table.players["p3"].hand.cards[4]) == "Th"
    assert game.table.players["p1"].hand.cards[4].visibility == Visibility.FACE_UP    

    # Step 7: Fifth Street Bet (big bet)
    game._next_step()
    assert game.current_step == 7
    assert game.state == GameState.BETTING
    assert game.current_player.id == "p3"  # 
    valid_actions = game.get_valid_actions("p3")
    assert (PlayerAction.FOLD, None, None) in valid_actions
    assert (PlayerAction.CHECK, None, None) in valid_actions
    assert (PlayerAction.BET, 20, 20) in valid_actions  # Big bet
    result = game.player_action("p3", PlayerAction.CHECK, None)
    assert result.success
    
    assert game.current_player.id == "p1"  # next
    valid_actions = game.get_valid_actions("p1")
    assert (PlayerAction.CHECK, None, None) in valid_actions
    result = game.player_action("p1", PlayerAction.CHECK, None)
    assert result.success
    
    assert game.current_player.id == "p2"  # next
    valid_actions = game.get_valid_actions("p2")
    assert (PlayerAction.CHECK, None, None) in valid_actions
    result = game.player_action("p2", PlayerAction.CHECK, None)
    assert result.success   

    # Step 8: Deal Sixth Street
    game._next_step()
    assert game.current_step == 8 
    assert game.state == GameState.DEALING
    assert len(game.table.players["p1"].hand.cards) == 6  # Alice: Ah,Kh   Qh,Ts,Jh,9s
    assert len(game.table.players["p2"].hand.cards) == 6  # Bob: Qd,Kc     Kd,Qc,Td,7s
    assert len(game.table.players["p3"].hand.cards) == 6  # Charlie: Js,Jd 2c,Qs,Th,6s    
    assert str(game.table.players["p1"].hand.cards[5]) == "9s"
    assert str(game.table.players["p2"].hand.cards[5]) == "7s"
    assert str(game.table.players["p3"].hand.cards[5]) == "6s"
    
    # Step 9: Sixth Street Bet (big bet)
    game._next_step()
    assert game.current_step == 9
    assert game.state == GameState.BETTING
    assert game.current_player.id == "p3"
    result = game.player_action("p3", PlayerAction.CHECK, None)
    assert result.success
    
    assert game.current_player.id == "p1"
    result = game.player_action("p1", PlayerAction.CHECK, None)
    assert result.success
    
    assert game.current_player.id == "p2"
    result = game.player_action("p2", PlayerAction.CHECK, None)
    assert result.success
    
    # Step 10: Deal Seventh Street (down card)
    game._next_step()
    assert game.current_step == 10
    assert game.state == GameState.DEALING
    assert str(game.table.players["p1"].hand.cards[6]) == "9d"
    assert str(game.table.players["p2"].hand.cards[6]) == "7h"
    assert str(game.table.players["p3"].hand.cards[6]) == "6c"
    assert game.table.players["p1"].hand.cards[6].visibility == Visibility.FACE_DOWN
    
    # Step 11: Seventh Street Bet (big bet)
    game._next_step()
    assert game.current_step == 11
    assert game.state == GameState.BETTING
    assert game.current_player.id == "p3"
    result = game.player_action("p3", PlayerAction.CHECK, None)
    assert result.success
    
    assert game.current_player.id == "p1"
    result = game.player_action("p1", PlayerAction.CHECK, None)
    assert result.success
    
    assert game.current_player.id == "p2"
    result = game.player_action("p2", PlayerAction.CHECK, None)
    assert result.success
    
    # Step 12: Showdown
    game._next_step()
    assert game.current_step == 12
    assert game.state == GameState.COMPLETE

    # Get results
    results = game.get_hand_results()

    print("\nShowdown Results:")
    print(results)

    # Check overall results
    expected_pot = 93  # 3 antes + 60 (third/fourth street)
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
    assert 'p3' in main_pot.winners

    winning_hand = results.hands['p3']    
    assert "High Card" in winning_hand[0].hand_name
    assert "Queen High" in winning_hand[0].hand_description    

    # Check winning hands list
    assert len(results.winning_hands) == 1
    assert results.winning_hands[0].player_id == 'p3'    

# more tests to follow to check the bring-in, the options for betting for that 
# player and other players, and subsequent rounds of betting.

