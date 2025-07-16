"""Tests for 6 card stud end-to-end."""
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
        Card(Rank.QUEEN, Suit.HEARTS), #Alice DOOR CARD
        Card(Rank.KING, Suit.DIAMONDS), #Bob DOOR CARD
        Card(Rank.TWO, Suit.CLUBS), #Charlie DOOR CARD
        Card(Rank.TEN, Suit.SPADES), #Alice 3RD ST
        Card(Rank.QUEEN, Suit.CLUBS), #Bob 3RD ST
        Card(Rank.QUEEN, Suit.SPADES), #Charlie 3RD ST
        Card(Rank.JACK, Suit.HEARTS), #Alice 4TH ST
        Card(Rank.TEN, Suit.DIAMONDS), #Bob 4TH ST
        Card(Rank.TEN, Suit.HEARTS), #Charlie 4TH ST
        Card(Rank.NINE, Suit.SPADES), #Alice 5TH ST
        Card(Rank.SEVEN, Suit.SPADES), #Bob 5TH ST
        Card(Rank.SIX, Suit.SPADES), #Charlie 5TH ST
        Card(Rank.NINE, Suit.DIAMONDS), #Alice 6TH ST (FINAL FACE DOWN)
        Card(Rank.SEVEN, Suit.HEARTS), #Bob 6TH ST (FINAL FACE DOWN)
        Card(Rank.SIX, Suit.CLUBS), #Charlie 6TH ST (FINAL FACE DOWN)

        # Rest of the deck in some order (won't be used in 6-card poker)
        # You can add more cards here if needed for other tests
    ]
    
    return MockDeck(cards)

def setup_test_game_with_mock_deck():
    """Create a test game with three players and a predetermined deck."""
    rules = load_rules_from_file('6_card_stud')

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

    # Antes don't create current_bets entries - they're separate from betting action
    assert game.betting.current_bets == {}  # Should be empty after antes
    assert game.betting.current_bet == 0   # No betting action yet

    # also test total_bets and total_antes from Pot
    assert game.betting.pot.total_bets == {'round_1_p1': 1, 'round_1_p2': 1, 'round_1_p3': 1}
    assert game.betting.pot.total_antes == {'round_1_p1': 1, 'round_1_p2': 1, 'round_1_p3': 1}

    # Step 1: Deal Initial Cards (1 down, 1 up)
    game._next_step()
    assert game.current_step == 1
    assert game.state == GameState.DEALING
    # Verify door cards (exposed)
    assert str(game.table.players['p1'].hand.cards[1]) == "Qh"  # Alice
    assert str(game.table.players['p2'].hand.cards[1]) == "Kd"  # Bob
    assert str(game.table.players['p3'].hand.cards[1]) == "2c"  # Charlie

    # pot unchanged
    assert game.betting.get_main_pot_amount() == 3  # 3 players x $1
    assert game.betting.get_ante_total() == 3  # 3 players x $1

    assert game.betting.current_bets == {}  # Should be empty after antes
    assert game.betting.current_bet == 0   # No betting action yet

    # also test total_bets and total_antes from Pot
    assert game.betting.pot.total_bets == {'round_1_p1': 1, 'round_1_p2': 1, 'round_1_p3': 1}
    assert game.betting.pot.total_antes == {'round_1_p1': 1, 'round_1_p2': 1, 'round_1_p3': 1}

    # Step 2: Post Bring-In
    game._next_step()
    assert game.current_step == 2
    assert game.state == GameState.BETTING
    assert game.current_player.id == "p3"  # Charlie has 2♣, lowest card

    # pot unchanged before actions
    assert game.betting.get_main_pot_amount() == 3  # 3 players x $1
    assert game.betting.get_ante_total() == 3  # 3 players x $1    

    # Check valid actions for bring-in player (Charlie)
    valid_actions = game.get_valid_actions("p3")
    assert len(valid_actions) == 2  # Bring-in or complete
    assert (PlayerAction.BRING_IN, 3, 3) in valid_actions  # Bring-in amount ($3)
    assert (PlayerAction.BET, 10, 10) in valid_actions  # Complete to small bet ($10)
    
    # Charlie posts bring-in ($3)
    result = game.player_action("p3", PlayerAction.BRING_IN, 3)
    assert result.success
    assert result.advance_step  # Done with bring-in step
    # P1 and P2 unchanged
    assert game.table.players['p1'].stack == 499  # Ante deducted
    assert game.table.players['p2'].stack == 499
    # P3 has ante and bring-in
    assert game.table.players["p3"].stack == 496  # 499 - 3
    assert game.betting.current_bet == 3
    assert game.betting.get_main_pot_amount() == 6  # 3 + 3
    assert game.betting.get_ante_total() == 3  # 3 players x $1

    # test current_bets in BettingManager
    assert game.betting.current_bets == {'p3': PlayerBet(amount=3, has_acted=False, posted_blind=True, is_all_in=False)}

    # also test total_bets and total_antes from Pot
    assert game.betting.pot.total_bets == {'round_1_p1': 1, 'round_1_p2': 1, 'round_1_p3': 4}
    assert game.betting.pot.total_antes == {'round_1_p1': 1, 'round_1_p2': 1, 'round_1_p3': 1}    

    # Step 3: First Betting Round (others can act)
    game._next_step()
    assert game.current_step == 3
    assert game.state == GameState.BETTING
    assert game.betting.get_main_pot_amount() == 6  # 3 + 3
    assert game.betting.get_ante_total() == 3  # 3 players x $1

    assert game.current_player.id == "p1"  # Alice next after Charlie
    valid_actions = game.get_valid_actions("p1")
    assert (PlayerAction.FOLD, None, None) in valid_actions
    assert (PlayerAction.CALL, 3, 3) in valid_actions  # Call $3
    assert (PlayerAction.BET, 10, 10) in valid_actions  # Raise to $10 (small bet)  

    # Alice (p1) will complete to $10
    result = game.player_action("p1", PlayerAction.BET, 10)
    assert result.success
    assert game.betting.current_bet == 10  # Passes
    assert game.table.players["p1"].stack == 489
    assert game.betting.get_main_pot_amount() == 16  # 3 ante + 3 bring-in + 10 complete
    assert game.betting.get_ante_total() == 3  # 3 players x $1

    assert game.current_player.id == "p2"  # Bob next after Alice
    valid_actions = game.get_valid_actions("p2")
    assert (PlayerAction.FOLD, None, None) in valid_actions
    assert (PlayerAction.CALL, 10, 10) in valid_actions  # Call $10
    assert (PlayerAction.RAISE, 20, 20) in valid_actions  # Raise to $20 

    # Bob (p2) will raise to $20
    result = game.player_action("p2", PlayerAction.RAISE, 20)
    assert result.success
    assert game.betting.current_bet == 20  # Passes
    assert game.table.players["p2"].stack == 479
    assert game.betting.get_main_pot_amount() == 36  # 3 ante + 3 bring-in + 10 complete + 20 raise
    assert game.betting.get_ante_total() == 3  # 3 players x $1
    
    # Charlie (p3) calls $20 (needs 17 more: 20 - 3)
    result = game.player_action("p3", PlayerAction.CALL, 20)
    assert result.success
    assert game.betting.current_bet == 20
    assert game.table.players["p3"].stack == 479  # 496 - 17
    assert game.betting.get_main_pot_amount() == 53  # 36 + 17

    # Alice (p1) calls $20 (needs 10 more: 20 - 10 already in)
    assert game.current_player.id == "p1"  # Back to Alice
    valid_actions = game.get_valid_actions("p1")
    assert (PlayerAction.FOLD, None, None) in valid_actions
    assert (PlayerAction.CALL, 20, 20) in valid_actions
    assert (PlayerAction.RAISE, 30, 30) in valid_actions  # Next raise is 20 + 10   

    result = game.player_action("p1", PlayerAction.CALL, 20)
    assert result.success
    assert game.betting.current_bet == 20
    assert game.table.players["p1"].stack == 479  # 489 - 10
    assert game.betting.get_main_pot_amount() == 63  # 53 + 10
    assert game.betting.get_ante_total() == 3

    # Step 4: Deal Second Deal (third card, face up)
    game._next_step()
    assert game.current_step == 4
    assert game.state == GameState.DEALING
    # Check cards: Alice: Ah,Qh,10s; Bob: Qd,Kd,Qc; Charlie: Js,2c,Qs
    assert len(game.table.players["p1"].hand.cards) == 3
    assert len(game.table.players["p2"].hand.cards) == 3
    assert len(game.table.players["p3"].hand.cards) == 3
    assert str(game.table.players["p1"].hand.cards[2]) == "Ts"  # Alice's third card
    assert str(game.table.players["p2"].hand.cards[2]) == "Qc"   # Bob's third card
    assert str(game.table.players["p3"].hand.cards[2]) == "Qs"   # Charlie's third card
    assert game.table.players["p1"].hand.cards[2].visibility == Visibility.FACE_UP
    assert game.table.players["p2"].hand.cards[2].visibility == Visibility.FACE_UP
    assert game.table.players["p3"].hand.cards[2].visibility == Visibility.FACE_UP
    assert game.betting.get_main_pot_amount() == 63
    assert game.betting.get_ante_total() == 3

    # Step 5: Second Betting Round (small bet, high hand first, no bring-in)
    game._next_step()
    assert game.current_step == 5
    assert game.state == GameState.BETTING
    assert game.betting.get_main_pot_amount() == 63 # from before
    assert game.betting.get_ante_total() == 0  # antes have been cleared in this round  

    # Upcards: Alice: Qh,10s; Bob: Kd,Qc; Charlie: 2c,Qs
    # Bob has highest (Kd,Qc), starts betting
    assert game.current_player.id == "p2"  # Bob (Kd,Qc)
    valid_actions = game.get_valid_actions("p2")
    assert (PlayerAction.FOLD, None, None) in valid_actions
    assert (PlayerAction.CHECK, None, None) in valid_actions  # No bring-in
    assert (PlayerAction.BET, 10, 10) in valid_actions  # Small bet

    # Bob bets $10
    result = game.player_action("p2", PlayerAction.BET, 10)
    assert result.success
    assert game.betting.current_bet == 10
    assert game.table.players["p2"].stack == 469  # 479 - 10
    assert game.betting.get_main_pot_amount() == 73  # 63 + 10

    # Charlie calls $10
    assert game.current_player.id == "p3"  # Charlie next
    valid_actions = game.get_valid_actions("p3")
    assert (PlayerAction.FOLD, None, None) in valid_actions
    assert (PlayerAction.CALL, 10, 10) in valid_actions
    result = game.player_action("p3", PlayerAction.CALL, 10)
    assert result.success
    assert game.table.players["p3"].stack == 469  # 479 - 10
    assert game.betting.get_main_pot_amount() == 83  # 73 + 10    

    # Alice calls $10
    assert game.current_player.id == "p1"  # Alice next
    valid_actions = game.get_valid_actions("p1")
    assert (PlayerAction.FOLD, None, None) in valid_actions
    assert (PlayerAction.CALL, 10, 10) in valid_actions
    result = game.player_action("p1", PlayerAction.CALL, 10)
    assert result.success
    assert game.table.players["p1"].stack == 469  # 479 - 10
    assert game.betting.get_main_pot_amount() == 93  # 83 + 10    
   
    # Step 6: Deal Third Deal (fourth card, face up)
    game._next_step()
    assert game.current_step == 6
    assert game.state == GameState.DEALING
    assert len(game.table.players["p1"].hand.cards) == 4  # Alice: Ah,Qh,Ts,Jh
    assert len(game.table.players["p2"].hand.cards) == 4  # Bob: Qd,Kd,Qc,Td
    assert len(game.table.players["p3"].hand.cards) == 4  # Charlie: Js,2c,Qs,Th
    assert str(game.table.players["p1"].hand.cards[3]) == "Jh"
    assert str(game.table.players["p2"].hand.cards[3]) == "Td"
    assert str(game.table.players["p3"].hand.cards[3]) == "Th"
    assert game.table.players["p1"].hand.cards[3].visibility == Visibility.FACE_UP    

    # Step 7: Third Betting Round (big bet)
    game._next_step()
    assert game.current_step == 7
    assert game.state == GameState.BETTING
    assert game.current_player.id == "p2"  # Bob (Kd,Qc,Td)
    valid_actions = game.get_valid_actions("p2")
    assert (PlayerAction.FOLD, None, None) in valid_actions
    assert (PlayerAction.CHECK, None, None) in valid_actions
    assert (PlayerAction.BET, 20, 20) in valid_actions  # Big bet
    result = game.player_action("p2", PlayerAction.CHECK, None)
    assert result.success
    
    assert game.current_player.id == "p3"  # Charlie next
    valid_actions = game.get_valid_actions("p3")
    assert (PlayerAction.CHECK, None, None) in valid_actions
    result = game.player_action("p3", PlayerAction.CHECK, None)
    assert result.success
    
    assert game.current_player.id == "p1"  # Alice next
    valid_actions = game.get_valid_actions("p1")
    assert (PlayerAction.CHECK, None, None) in valid_actions
    result = game.player_action("p1", PlayerAction.CHECK, None)
    assert result.success   

    # Step 8: Deal Fourth Deal (fifth card, face up)
    game._next_step()
    assert game.current_step == 8 
    assert game.state == GameState.DEALING
    assert len(game.table.players["p1"].hand.cards) == 5  # Alice: Ah,Qh,Ts,Jh,9s
    assert len(game.table.players["p2"].hand.cards) == 5  # Bob: Qd,Kd,Qc,Td,7s
    assert len(game.table.players["p3"].hand.cards) == 5  # Charlie: Js,2c,Qs,Th,6s    
    assert str(game.table.players["p1"].hand.cards[4]) == "9s"
    assert str(game.table.players["p2"].hand.cards[4]) == "7s"
    assert str(game.table.players["p3"].hand.cards[4]) == "6s"
    
    # Step 9: Fourth Betting Round (big bet)
    game._next_step()
    assert game.current_step == 9
    assert game.state == GameState.BETTING
    assert game.current_player.id == "p2"
    result = game.player_action("p2", PlayerAction.CHECK, None)
    assert result.success
    
    assert game.current_player.id == "p3"
    result = game.player_action("p3", PlayerAction.CHECK, None)
    assert result.success
    
    assert game.current_player.id == "p1"
    result = game.player_action("p1", PlayerAction.CHECK, None)
    assert result.success
    
    # Step 10: Deal Fifth Deal (final card, face down)
    game._next_step()
    assert game.current_step == 10
    assert game.state == GameState.DEALING
    assert str(game.table.players["p1"].hand.cards[5]) == "9d"
    assert str(game.table.players["p2"].hand.cards[5]) == "7h"
    assert str(game.table.players["p3"].hand.cards[5]) == "6c"
    assert game.table.players["p1"].hand.cards[5].visibility == Visibility.FACE_DOWN
    
    # Step 11: Fifth Betting Round (big bet)
    game._next_step()
    assert game.current_step == 11
    assert game.state == GameState.BETTING
    assert game.current_player.id == "p2"
    result = game.player_action("p2", PlayerAction.CHECK, None)
    assert result.success
    
    assert game.current_player.id == "p3"
    result = game.player_action("p3", PlayerAction.CHECK, None)
    assert result.success
    
    assert game.current_player.id == "p1"
    result = game.player_action("p1", PlayerAction.CHECK, None)
    assert result.success
    assert result.advance_step 

    # Step 12: Showdown
    game._next_step()
    assert game.current_step == 12
    assert game.state == GameState.COMPLETE

    # Get results
    results = game.get_hand_results()

    print("\nShowdown Results:")
    print(results)

    # Check overall results
    expected_pot = 93  # 3 antes + 90 (betting rounds)
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
    
    # Let's see who wins and what hand they have
    # Alice: Ah, Qh, Ts, Jh, 9s, 9d - best 5 cards likely A-Q-J-T-9 high or pair of 9s
    # Bob: Qd, Kd, Qc, Td, 7s, 7h - pair of Queens or pair of 7s
    # Charlie: Js, 2c, Qs, Th, 6s, 6c - pair of 6s or Queen high
    
    # Based on the cards, Bob should win with pair of Queens (Qd, Qc)
    # Let's verify this assumption
    assert 'p2' in main_pot.winners  # Bob should win

    winning_hand = results.hands['p2']    
    assert "Pair" in winning_hand[0].hand_name
    print(f"Winning hand: {winning_hand[0].hand_name} - {winning_hand[0].hand_description}")

    # Check winning hands list
    assert len(results.winning_hands) == 1
    assert results.winning_hands[0].player_id == 'p2'    

def test_game_bringin_for_full():
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
    assert game.betting.current_bets == {}  # Should be empty after antes
    assert game.betting.current_bet == 0   # No betting action yet

    # also test total_bets and total_antes from Pot
    assert game.betting.pot.total_bets == {'round_1_p1': 1, 'round_1_p2': 1, 'round_1_p3': 1}
    assert game.betting.pot.total_antes == {'round_1_p1': 1, 'round_1_p2': 1, 'round_1_p3': 1}

    # Step 1: Deal Initial Cards (1 down, 1 up)
    game._next_step()
    assert game.current_step == 1
    assert game.state == GameState.DEALING

    # pot unchanged
    assert game.betting.get_main_pot_amount() == 3  # 3 players x $1
    assert game.betting.get_ante_total() == 3  # 3 players x $1

    # test current_bets in BettingManager
    assert game.betting.current_bets == {}  # Should be empty after antes
    assert game.betting.current_bet == 0   # No betting action yet

    # also test total_bets and total_antes from Pot
    assert game.betting.pot.total_bets == {'round_1_p1': 1, 'round_1_p2': 1, 'round_1_p3': 1}
    assert game.betting.pot.total_antes == {'round_1_p1': 1, 'round_1_p2': 1, 'round_1_p3': 1}

    # Step 2: Post Bring-In
    game._next_step()
    assert game.current_step == 2
    assert game.state == GameState.BETTING
    assert game.current_player.id == "p3"  # Charlie has 2♣, lowest card

    # pot unchanged before actions
    assert game.betting.get_main_pot_amount() == 3  # 3 players x $1
    assert game.betting.get_ante_total() == 3  # 3 players x $1    

    # Check valid actions for bring-in player (Charlie)
    valid_actions = game.get_valid_actions("p3")
    assert len(valid_actions) == 2  # Bring-in or complete
    assert (PlayerAction.BRING_IN, 3, 3) in valid_actions  # Bring-in amount ($3)
    assert (PlayerAction.BET, 10, 10) in valid_actions  # Complete to small bet ($10)
    
    # Charlie posts bring-in ($3)
    result = game.player_action("p3", PlayerAction.BET, 10)
    assert result.success
    assert result.advance_step  # Done with bring-in step
    # P1 and P2 unchanged
    assert game.table.players['p1'].stack == 499  # Ante deducted
    assert game.table.players['p2'].stack == 499
    # P3 has ante and bring-in
    assert game.table.players["p3"].stack == 489  # 499 - 10
    assert game.betting.current_bet == 10
    assert game.betting.get_main_pot_amount() == 13  # 3 + 10
    assert game.betting.get_ante_total() == 3  # 3 players x $1

    # test current_bets in BettingManager
    assert game.betting.current_bets == {'p3': PlayerBet(amount=10, has_acted=False, posted_blind=True, is_all_in=False)}   
    # also test total_bets and total_antes from Pot
    assert game.betting.pot.total_bets == {'round_1_p1': 1, 'round_1_p2': 1, 'round_1_p3': 11}
    assert game.betting.pot.total_antes == {'round_1_p1': 1, 'round_1_p2': 1, 'round_1_p3': 1}    

    # Step 3: First Betting Round (others can act)
    game._next_step()
    assert game.current_step == 3
    assert game.state == GameState.BETTING
    assert game.betting.get_main_pot_amount() == 13  # 3 + 10
    assert game.betting.get_ante_total() == 3  # 3 players x $1

    assert game.current_player.id == "p1"  # Alice next after Charlie
    valid_actions = game.get_valid_actions("p1")
    assert (PlayerAction.FOLD, None, None) in valid_actions
    assert (PlayerAction.CALL, 10, 10) in valid_actions  # Call $10
    assert (PlayerAction.RAISE, 20, 20) in valid_actions  # Raise to $20 (small bet) 

    # Alice (p1) will call $10
    result = game.player_action("p1", PlayerAction.CALL, 10)
    assert result.success
    assert game.betting.current_bet == 10  # Passes
    assert game.table.players["p1"].stack == 489
    assert game.betting.get_main_pot_amount() == 23  # 3 ante + 10 bring-in + 10 call
    assert game.betting.get_ante_total() == 3  # 3 players x $1

    assert game.current_player.id == "p2"  # Bob next after Alice
    valid_actions = game.get_valid_actions("p2")
    assert (PlayerAction.FOLD, None, None) in valid_actions
    assert (PlayerAction.CALL, 10, 10) in valid_actions  # Call $10
    assert (PlayerAction.RAISE, 20, 20) in valid_actions  # Raise to $20 

    # Bob (p2) will raise to $20
    result = game.player_action("p2", PlayerAction.RAISE, 20)
    assert result.success
    assert game.betting.current_bet == 20  # Passes
    assert game.table.players["p2"].stack == 479
    assert game.betting.get_main_pot_amount() == 43  # 3 ante + 10 bring-in + 10 call + 20 raise
    assert game.betting.get_ante_total() == 3  # 3 players x $1
    
    # Charlie (p3) calls $20 (needs 10 more: 20 - 10)
    result = game.player_action("p3", PlayerAction.CALL, 20)
    assert result.success
    assert game.betting.current_bet == 20
    assert game.table.players["p3"].stack == 479  # 489 - 10
    assert game.betting.get_main_pot_amount() == 53  # 43 + 10

    # Alice (p1) calls $20 (needs 10 more: 20 - 10 already in)
    assert game.current_player.id == "p1"  # Back to Alice
    valid_actions = game.get_valid_actions("p1")
    assert (PlayerAction.FOLD, None, None) in valid_actions
    assert (PlayerAction.CALL, 20, 20) in valid_actions
    assert (PlayerAction.RAISE, 30, 30) in valid_actions  # Next raise is 20 + 10   

    result = game.player_action("p1", PlayerAction.CALL, 20)
    assert result.success
    assert game.betting.current_bet == 20
    assert game.table.players["p1"].stack == 479  # 489 - 10
    assert game.betting.get_main_pot_amount() == 63  # 53 + 10
    assert game.betting.get_ante_total() == 3    