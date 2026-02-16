"""Tests for simple straight poker game end-to-end."""
import pytest
from generic_poker.config.loader import GameRules
from generic_poker.game.game import Game, GameState, PlayerAction
from generic_poker.core.card import Card, Rank, Suit
from generic_poker.game.betting import BettingStructure
from generic_poker.core.deck import Deck
from generic_poker.evaluation.hand_description import HandDescriber, EvaluationType
from tests.test_helpers import load_rules_from_file

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
        Card(Rank.QUEEN, Suit.HEARTS), #FLOP
        Card(Rank.KING, Suit.DIAMONDS), #FLOP
        Card(Rank.TEN, Suit.SPADES), #FLOP
        Card(Rank.QUEEN, Suit.CLUBS), #TURN
        Card(Rank.QUEEN, Suit.SPADES), #RIVER
        Card(Rank.JACK, Suit.HEARTS), #
        Card(Rank.TEN, Suit.DIAMONDS), #
        Card(Rank.TEN, Suit.HEARTS), #
        Card(Rank.NINE, Suit.SPADES), #
      
        # Rest of the deck in some order (won't be used in 5-card poker)
        # You can add more cards here if needed for other tests
    ]
    
    return MockDeck(cards)

def setup_test_game_with_mock_deck():
    """Create a test game with three players and a predetermined deck."""
    game = Game(
        rules=load_rules_from_file('pineapple'),
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
    
    # Play a full hand
    game.start_hand()
    assert game.current_step == 0           # Should be in post blinds step
    assert game.state == GameState.BETTING  # Forced bets    
    game._next_step()  # Deal hole cards

    assert str(game.table.players['BTN'].hand.cards[0]) == "Ah"  # Alice
    assert str(game.table.players['BTN'].hand.cards[1]) == "Kh"  # Alice
    assert str(game.table.players['BTN'].hand.cards[2]) == "Qh"  # Alice
    assert str(game.table.players['SB'].hand.cards[0]) == "Qd"  # Bob
    assert str(game.table.players['SB'].hand.cards[1]) == "Kc"  # Bob
    assert str(game.table.players['SB'].hand.cards[2]) == "Kd"  # Bob
    assert str(game.table.players['BB'].hand.cards[0]) == "Js"  # Charlie
    assert str(game.table.players['BB'].hand.cards[1]) == "Jd"  # Charlie
    assert str(game.table.players['BB'].hand.cards[2]) == "Ts"  # Charlie

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
    
    # Go to discard step
    game._next_step()    
    assert game.current_step == 3           # Should be in post blinds step
    assert game.state == GameState.DRAWING  # Drawing/Discarding different or same? 

    # check the current player
    assert game.current_player.id == 'SB'

    valid_actions = game.get_valid_actions(game.current_player.id)
    # only action is DISCARD of 1 card (so min and max are 1)
    assert len(valid_actions) == 1
    assert any(action[0] == PlayerAction.DISCARD and action[1] == 1 and action[2] == 1 for action in valid_actions)    

    # validate player's hand before discard
    discarding_player = game.current_player.id
    player_cards = game.table.players[discarding_player].hand.get_cards()
    assert len(player_cards) == 3
    assert any(card.rank == Rank.QUEEN and card.suit == Suit.DIAMONDS for card in player_cards)
    assert any(card.rank == Rank.KING and card.suit == Suit.CLUBS for card in player_cards)
    assert any(card.rank == Rank.KING and card.suit == Suit.DIAMONDS for card in player_cards)

    # actually discard the cards - this will advance current player, so be sure to use our saved discarding_player
    cards_to_discard = [game.table.players[discarding_player].hand.cards[0]]  # discard the first card
    result = game.player_action('SB', PlayerAction.DISCARD, cards=cards_to_discard)
    assert result.success
    assert not result.advance_step  # still more players to act in this step

    player_cards = game.table.players[discarding_player].hand.get_cards()
    assert len(player_cards) == 2
    assert any(card.rank == Rank.KING and card.suit == Suit.CLUBS for card in player_cards)
    assert any(card.rank == Rank.KING and card.suit == Suit.DIAMONDS for card in player_cards)

    # other players similarly discard
    discarding_player = game.current_player.id
    cards_to_discard = [game.table.players[discarding_player].hand.cards[1]]  # discard the second card
    result = game.player_action('BB', PlayerAction.DISCARD, cards=cards_to_discard)
    assert result.success
    assert not result.advance_step  # still more players to act in this step
    player_cards = game.table.players[discarding_player].hand.get_cards()
    assert len(player_cards) == 2    
    discarding_player = game.current_player.id
    cards_to_discard = [game.table.players[discarding_player].hand.cards[2]]  # discard the third card
    result = game.player_action('BTN', PlayerAction.DISCARD, cards=cards_to_discard)
    assert result.success
    assert result.advance_step  # all players have discarded
    player_cards = game.table.players[discarding_player].hand.get_cards()
    assert len(player_cards) == 2    

    # Step 4: Deal Flop
    game._next_step()
    assert game.current_step == 4
    assert game.state == GameState.DEALING

    # Step 5 Post-Flop Bet
    game._next_step()  # Move to post-flop bet
    assert game.current_step == 5
    assert game.state == GameState.BETTING
    assert game.current_player.id == "SB"  # SB acts first in post-flop betting rounds

    # SB checks
    game.player_action('SB', PlayerAction.CHECK)
    # BB checks
    game.player_action('BB', PlayerAction.CHECK)
    # BTN checks
    game.player_action('BTN', PlayerAction.CHECK)

    # Step 6: Deal Turn
    game._next_step()  # Deal turn
    assert game.current_step == 6
    assert game.state == GameState.DEALING

    # Step 7: Turn Bet
    game._next_step()  # Move to turn bet
    assert game.current_step == 7
    assert game.state == GameState.BETTING    

    # SB checks
    game.player_action('SB', PlayerAction.CHECK)
    # BB checks
    game.player_action('BB', PlayerAction.CHECK)
    # BTN checks
    game.player_action('BTN', PlayerAction.CHECK)

    # Step 8: Deal River
    game._next_step()  # Deal river
    assert game.current_step == 8
    assert game.state == GameState.DEALING        

    # Step 9: River Bet
    game._next_step()  # Move to river bet
    assert game.current_step == 9
    assert game.state == GameState.BETTING    

    # Step 10: Showdown
    game._next_step()  # Move to showdown
    assert game.current_step == 10
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
    assert 'BB' in main_pot.winners

    winning_hand = results.hands['BB']
    assert "Full House" in winning_hand[0].hand_name
    assert "Full House, Tens over Queens" in winning_hand[0].hand_description

    # Check winning hands list
    assert len(results.winning_hands) == 1
    assert results.winning_hands[0].player_id == 'BB'    