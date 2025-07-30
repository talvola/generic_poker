#!/usr/bin/env python3
"""Demonstration of table creation functionality integrated with existing Game class."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from online_poker.models.table_config import TableConfig
from online_poker.services.table_manager import TableManager
from generic_poker.game.betting import BettingStructure
from generic_poker.game.game import Game


def demo_table_creation():
    """Demonstrate table creation and Game integration."""
    print("=== Online Poker Table Creation Demo ===\n")
    
    # Show available variants
    print("1. Available Poker Variants:")
    variants = TableManager.get_available_variants()
    print(f"   Total variants available: {len(variants)}")
    
    # Show some popular variants
    popular_variants = ['hold_em', '7_card_stud', 'omaha', '5_card_draw', 'razz']
    for variant_name in popular_variants:
        variant = next((v for v in variants if v['name'] == variant_name), None)
        if variant:
            print(f"   • {variant['display_name']}: {variant['min_players']}-{variant['max_players']} players")
            print(f"     Betting structures: {', '.join(variant['betting_structures'])}")
    
    print("\n2. Creating Tables with Different Configurations:")
    
    # Demo 1: No-Limit Hold'em
    print("\n   Demo 1: No-Limit Hold'em Table")
    config1 = TableConfig(
        name="High Stakes NL Hold'em",
        variant="hold_em",
        betting_structure=BettingStructure.NO_LIMIT,
        stakes={"small_blind": 100, "big_blind": 200},
        max_players=6,
        is_private=False
    )
    
    rules1 = TableManager.get_variant_rules(config1.variant)
    game1 = Game(rules=rules1, **config1.to_game_params())
    
    print(f"   ✓ Created: {game1.get_game_description()}")
    print(f"     Buy-in range: ${config1.get_minimum_buyin()} - ${config1.get_maximum_buyin()}")
    print(f"     Table info: {game1.get_table_info()}")
    
    # Demo 2: Limit 7-Card Stud
    print("\n   Demo 2: Limit 7-Card Stud Table")
    config2 = TableConfig(
        name="Classic Limit Stud",
        variant="7_card_stud",
        betting_structure=BettingStructure.LIMIT,
        stakes={"small_bet": 10, "big_bet": 20, "ante": 2, "bring_in": 5},
        max_players=8,
        is_private=True
    )
    
    rules2 = TableManager.get_variant_rules(config2.variant)
    game2 = Game(rules=rules2, **config2.to_game_params())
    
    print(f"   ✓ Created: {game2.get_game_description()}")
    print(f"     Buy-in range: ${config2.get_minimum_buyin()} - ${config2.get_maximum_buyin()}")
    print(f"     Private table: {config2.is_private}")
    
    # Demo 3: Pot-Limit Omaha
    print("\n   Demo 3: Pot-Limit Omaha Table")
    config3 = TableConfig(
        name="PLO Action Table",
        variant="omaha",
        betting_structure=BettingStructure.POT_LIMIT,
        stakes={"small_blind": 5, "big_blind": 10},
        max_players=9
    )
    
    rules3 = TableManager.get_variant_rules(config3.variant)
    game3 = Game(rules=rules3, **config3.to_game_params())
    
    print(f"   ✓ Created: {game3.get_game_description()}")
    print(f"     Buy-in range: ${config3.get_minimum_buyin()} - ${config3.get_maximum_buyin()}")
    
    print("\n3. Demonstrating Game Functionality:")
    
    # Add players to the Hold'em game
    print(f"\n   Adding players to {game1.get_game_description()}:")
    game1.add_player("alice", "Alice", 10000)
    game1.add_player("bob", "Bob", 8000)
    game1.add_player("charlie", "Charlie", 12000)
    
    updated_info = game1.get_table_info()
    print(f"   ✓ Players added: {updated_info['player_count']}")
    print(f"   ✓ Average stack: ${updated_info['avg_stack']:.0f}")
    
    # Show player information
    print("   Player details:")
    for player in game1.table.get_position_order():
        print(f"     • {player.name}: ${player.stack}")
    
    print("\n4. Suggested Stakes:")
    for structure in BettingStructure:
        suggestions = TableManager.get_suggested_stakes(structure)
        print(f"\n   {structure.value} suggestions:")
        for suggestion in suggestions[:3]:  # Show first 3
            stakes_str = ", ".join([f"{k}: ${v}" for k, v in suggestion['stakes'].items()])
            print(f"     • {suggestion['name']}: {stakes_str}")
    
    print("\n=== Demo Complete ===")
    print("\nKey Integration Points:")
    print("• TableConfig validates stakes against betting structures")
    print("• TableManager loads and caches GameRules from JSON configs")
    print("• Game class handles all poker logic (betting, dealing, showdown)")
    print("• Full support for all 192+ poker variants")
    print("• Seamless integration between online platform and game engine")


if __name__ == "__main__":
    demo_table_creation()