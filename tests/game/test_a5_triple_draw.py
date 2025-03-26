"""Tests for simple straight poker game end-to-end."""
import pytest
from generic_poker.config.loader import GameRules
from generic_poker.game.game import Game, GameState, PlayerAction
from generic_poker.core.card import Card, Rank, Suit
from generic_poker.game.betting import BettingStructure
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
        Card(Rank.ACE, Suit.HEARTS), #BTN
        Card(Rank.QUEEN, Suit.DIAMONDS), #SB
        Card(Rank.JACK, Suit.SPADES), #BB
        Card(Rank.KING, Suit.HEARTS), #BTN
        Card(Rank.KING, Suit.CLUBS), #SB
        Card(Rank.JACK, Suit.DIAMONDS), #BB
        Card(Rank.QUEEN, Suit.HEARTS), #BTN
        Card(Rank.KING, Suit.DIAMONDS), #SB
        Card(Rank.TEN, Suit.SPADES), #BB
        Card(Rank.QUEEN, Suit.CLUBS), #BTN
        Card(Rank.QUEEN, Suit.SPADES), #SB
        Card(Rank.JACK, Suit.HEARTS), #BB
        Card(Rank.TEN, Suit.DIAMONDS), #BTN
        Card(Rank.TEN, Suit.HEARTS), #SB
        Card(Rank.NINE, Suit.SPADES), #BB
        Card(Rank.TWO, Suit.SPADES), #draw
        Card(Rank.ACE, Suit.SPADES), #draw
        Card(Rank.EIGHT, Suit.SPADES), #draw                
        Card(Rank.EIGHT, Suit.DIAMONDS), #draw                
        Card(Rank.SEVEN, Suit.HEARTS), #draw                
      
        # Rest of the deck in some order (won't be used in 5-card poker)
        # You can add more cards here if needed for other tests
    ]
    
    return MockDeck(cards)

def setup_test_game_with_mock_deck():
    """Create a test game with three players and a predetermined deck."""
    rules = load_rules_from_file('a5_triple_draw')

    game = Game(
        rules=rules,
        structure=BettingStructure.LIMIT,
        small_bet=10,
        big_bet=20,
        min_buyin=100,
        max_buyin=1000,
        auto_progress=False        
    )
  
    # Add players
    game.add_player("BTN", "Alice", 500)
    game.add_player("SB", "Bob", 500)
    game.add_player("BB", "Charlie", 500)
    
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
    
def test_game_results_showdown():
    """Test that the game results API provides correct information."""
    game = setup_test_game_with_mock_deck()
    
    # Step 0: Post Blinds
    game.start_hand()
    assert game.current_step == 0           # Should be in post blinds step
    assert game.state == GameState.BETTING  # Forced bets    
    assert game.table.players['SB'].stack == 495  # SB deducted
    assert game.table.players['BB'].stack == 490  # BB deducted
    assert game.table.players['BTN'].stack == 500 # has not acted yet
    
    # Step 1: Deal Hole Cards (5 down)
    game._next_step()  # Deal hole cards
    assert game.current_step == 1
    assert game.state == GameState.DEALING
    # Verify hole cards
    assert len(game.table.players['BTN'].hand.cards) == 5  # Alice (BTN)
    assert len(game.table.players['SB'].hand.cards) == 5  # Bob (SB)
    assert len(game.table.players['BB'].hand.cards) == 5  # Charlie (BB)
    assert str(game.table.players['BTN'].hand.cards[0]) == "Ah"  # Alice
    assert str(game.table.players['BTN'].hand.cards[1]) == "Kh"  # Alice
    assert str(game.table.players['BTN'].hand.cards[2]) == "Qh"  # Alice
    assert str(game.table.players['BTN'].hand.cards[3]) == "Qc"  # Alice
    assert str(game.table.players['BTN'].hand.cards[4]) == "Td"  # Alice
    assert str(game.table.players['SB'].hand.cards[0]) == "Qd"  # Bob
    assert str(game.table.players['SB'].hand.cards[1]) == "Kc"  # 
    assert str(game.table.players['SB'].hand.cards[2]) == "Kd"  # 
    assert str(game.table.players['SB'].hand.cards[3]) == "Qs"  # 
    assert str(game.table.players['SB'].hand.cards[4]) == "Th"  # 
    assert str(game.table.players['BB'].hand.cards[0]) == "Js"  # Charlie
    assert str(game.table.players['BB'].hand.cards[1]) == "Jd"  # 
    assert str(game.table.players['BB'].hand.cards[2]) == "Ts"  # 
    assert str(game.table.players['BB'].hand.cards[3]) == "Jh"  # 
    assert str(game.table.players['BB'].hand.cards[4]) == "9s"  # 

    # Step 2: Pre-Flop Bet
    game._next_step()  # Move to pre-flop bet
    assert game.current_step == 2
    assert game.state == GameState.BETTING

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
    assert game.betting.get_main_pot_amount() == expected_pot  
        
    # Step 3: First Draw
    game._next_step()    
    assert game.current_step == 3           # Should be in post blinds step
    assert game.state == GameState.DRAWING  # Drawing/Discarding different or same? 

    # check the current player
    assert game.current_player.id == 'SB'

    valid_actions = game.get_valid_actions(game.current_player.id)
    print(f"Valid actions: {valid_actions}")
    # only action is DRAW of 0-5 cards
    assert len(valid_actions) == 1
    assert any(action[0] == PlayerAction.DRAW and action[1] == 0 and action[2] == 5 for action in valid_actions)    

    # validate player's hand before discard
    discarding_player = game.current_player.id
    player_cards = game.table.players[discarding_player].hand.get_cards()
    assert len(player_cards) == 5
    assert str(game.table.players[discarding_player].hand.cards[0]) == "Qd"  # Bob
    assert str(game.table.players[discarding_player].hand.cards[1]) == "Kc"  # 
    assert str(game.table.players[discarding_player].hand.cards[2]) == "Kd"  # 
    assert str(game.table.players[discarding_player].hand.cards[3]) == "Qs"  # 
    assert str(game.table.players[discarding_player].hand.cards[4]) == "Th"  # 

    # actually discard the cards - this will advance current player, so be sure to use our saved discarding_player
    cards_to_discard = [game.table.players[discarding_player].hand.cards[0]]  # discard the first card
    game.player_action('SB', PlayerAction.DISCARD, cards=cards_to_discard)

    # don't worry about hand order, just check the cards are in the hand
    # want to see the Queen of Diamonds discarded and replaced with the 2 of Spades
    player_cards = game.table.players[discarding_player].hand.get_cards()
    assert len(player_cards) == 5
    assert any(card.rank == Rank.TWO and card.suit == Suit.SPADES for card in player_cards)
    assert any(card.rank == Rank.KING and card.suit == Suit.CLUBS for card in player_cards)
    assert any(card.rank == Rank.KING and card.suit == Suit.DIAMONDS for card in player_cards)
    assert any(card.rank == Rank.QUEEN and card.suit == Suit.SPADES for card in player_cards)
    assert any(card.rank == Rank.TEN and card.suit == Suit.HEARTS for card in player_cards)

    # Step 4: Post-Draw Bet #1
    game._next_step()  # Move to river bet
    assert game.current_step == 4
    assert game.state == GameState.BETTING

    # SB checks
    game.player_action('SB', PlayerAction.CHECK)
    # BB checks
    game.player_action('BB', PlayerAction.CHECK)
    # BTN checks
    game.player_action('BTN', PlayerAction.CHECK)

    assert game.betting.get_main_pot_amount() == expected_pot  

    # Step 5: Second Draw
    game._next_step()    
    assert game.current_step == 5           # Should be in post blinds step
    assert game.state == GameState.DRAWING  # Drawing/Discarding different or same? 

    # check the current player
    assert game.current_player.id == 'SB'

    valid_actions = game.get_valid_actions(game.current_player.id)
    print(f"Valid actions: {valid_actions}")
    # only action is DRAW of 0-5 cards
    assert len(valid_actions) == 1
    assert any(action[0] == PlayerAction.DRAW and action[1] == 0 and action[2] == 5 for action in valid_actions)    

    # validate player's hand before discard
    discarding_player = game.current_player.id
    player_cards = game.table.players[discarding_player].hand.get_cards()
    assert len(player_cards) == 5
    assert any(card.rank == Rank.KING and card.suit == Suit.CLUBS for card in player_cards)
    assert any(card.rank == Rank.KING and card.suit == Suit.DIAMONDS for card in player_cards)
    assert any(card.rank == Rank.QUEEN and card.suit == Suit.SPADES for card in player_cards)
    assert any(card.rank == Rank.TEN and card.suit == Suit.HEARTS for card in player_cards)
    assert any(card.rank == Rank.TWO and card.suit == Suit.SPADES for card in player_cards)

    # actually discard the cards - this will advance current player, so be sure to use our saved discarding_player
    cards_to_discard = [game.table.players[discarding_player].hand.cards[0]]  # discard the first card
    game.player_action('SB', PlayerAction.DISCARD, cards=cards_to_discard)

    # don't worry about hand order, just check the cards are in the hand
    # want to see the Queen of Diamonds discarded and replaced with the 2 of Spades
    player_cards = game.table.players[discarding_player].hand.get_cards()
    assert len(player_cards) == 5
    assert any(card.rank == Rank.KING and card.suit == Suit.DIAMONDS for card in player_cards)
    assert any(card.rank == Rank.QUEEN and card.suit == Suit.SPADES for card in player_cards)
    assert any(card.rank == Rank.TEN and card.suit == Suit.HEARTS for card in player_cards)    
    assert any(card.rank == Rank.TWO and card.suit == Suit.SPADES for card in player_cards)
    assert any(card.rank == Rank.ACE and card.suit == Suit.SPADES for card in player_cards)

    # Step 6: Post-Draw Bet #2
    game._next_step()  # Move to river bet
    assert game.current_step == 6
    assert game.state == GameState.BETTING

    # SB checks
    game.player_action('SB', PlayerAction.CHECK)
    # BB checks
    game.player_action('BB', PlayerAction.CHECK)
    # BTN checks
    game.player_action('BTN', PlayerAction.CHECK)

    assert game.betting.get_main_pot_amount() == expected_pot  

    # Step 7: Third Draw
    game._next_step()    
    assert game.current_step == 7           # Should be in post blinds step
    assert game.state == GameState.DRAWING  # Drawing/Discarding different or same? 

    # check the current player
    assert game.current_player.id == 'SB'

    valid_actions = game.get_valid_actions(game.current_player.id)
    print(f"Valid actions: {valid_actions}")
    # only action is DRAW of 0-5 cards
    assert len(valid_actions) == 1
    assert any(action[0] == PlayerAction.DRAW and action[1] == 0 and action[2] == 5 for action in valid_actions)    

    # validate player's hand before discard
    discarding_player = game.current_player.id
    player_cards = game.table.players[discarding_player].hand.get_cards()
    assert len(player_cards) == 5
    assert any(card.rank == Rank.KING and card.suit == Suit.DIAMONDS for card in player_cards)
    assert any(card.rank == Rank.QUEEN and card.suit == Suit.SPADES for card in player_cards)
    assert any(card.rank == Rank.TEN and card.suit == Suit.HEARTS for card in player_cards)    
    assert any(card.rank == Rank.TWO and card.suit == Suit.SPADES for card in player_cards)
    assert any(card.rank == Rank.ACE and card.suit == Suit.SPADES for card in player_cards)   

    # actually discard the cards - this will advance current player, so be sure to use our saved discarding_player
    cards_to_discard = [game.table.players[discarding_player].hand.cards[0]]  # discard the first card
    game.player_action('SB', PlayerAction.DISCARD, cards=cards_to_discard)

    # don't worry about hand order, just check the cards are in the hand
    # want to see the Queen of Diamonds discarded and replaced with the 2 of Spades
    player_cards = game.table.players[discarding_player].hand.get_cards()
    assert len(player_cards) == 5
    assert any(card.rank == Rank.QUEEN and card.suit == Suit.SPADES for card in player_cards)
    assert any(card.rank == Rank.TEN and card.suit == Suit.HEARTS for card in player_cards)    
    assert any(card.rank == Rank.TWO and card.suit == Suit.SPADES for card in player_cards)
    assert any(card.rank == Rank.ACE and card.suit == Suit.SPADES for card in player_cards)    
    assert any(card.rank == Rank.EIGHT and card.suit == Suit.SPADES for card in player_cards)    

    # Step 8: Post-Draw Bet #3
    game._next_step()  # Move to river bet
    assert game.current_step == 8
    assert game.state == GameState.BETTING

    # SB checks
    game.player_action('SB', PlayerAction.CHECK)
    # BB checks
    game.player_action('BB', PlayerAction.CHECK)
    # BTN checks
    game.player_action('BTN', PlayerAction.CHECK)

    assert game.betting.get_main_pot_amount() == expected_pot  

    # Step 9: Showdown
    game._next_step()  # Move to showdown
    assert game.current_step == 9
    assert game.state == GameState.COMPLETE    

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
    assert 'SB' in main_pot.winners

    winning_hand = results.hands['SB']
    assert "High Card" in winning_hand[0].hand_name
    assert "Queen High" in winning_hand[0].hand_description

    # Check winning hands list
    assert len(results.winning_hands) == 1
    assert results.winning_hands[0].player_id == 'SB'
