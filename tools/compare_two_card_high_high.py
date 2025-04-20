import pandas as pd
import os
import csv

def debug_print(message):
    """Print debug message with clear separator."""
    print("\n" + "="*50)
    print(message)
    print("="*50)

def load_rankings_manually(file_path):
    """Load hand rankings by manually parsing the CSV file."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    
    debug_print(f"Reading file: {file_path}")
    
    data = []
    with open(file_path, 'r') as f:
        # Read the header
        header = next(f).strip().split(',')
        debug_print(f"Header: {header}")
        
        # Process each line
        line_num = 1
        for line in f:
            line_num += 1
            if line_num <= 5:
                debug_print(f"Line {line_num}: {line.strip()}")
                
            fields = line.strip().split(',')
            
            # In the expected format, the last two elements should be Rank and OrderedRank
            # Everything before that is the card hand
            if len(fields) < 3:
                debug_print(f"Skipping invalid line: {line.strip()}")
                continue
                
            ordered_rank = int(fields[-1])
            rank = int(fields[-2])
            
            # Join the cards to form the hand
            hand = ','.join(fields[:-2])
            
            data.append({'Hand': hand, 'Rank': rank, 'OrderedRank': ordered_rank})
    
    df = pd.DataFrame(data)
    return df

def extract_cards(hand_str):
    """Extract individual cards from a hand string."""
    return [card.strip() for card in hand_str.split(',') if card.strip()]

def extract_card_values(cards):
    """Extract card values from a list of cards."""
    value_map = {'2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, 
                 '8': 8, '9': 9, 'T': 10, 'J': 11, 'Q': 12, 'K': 13, 'A': 14}
    
    # Extract the value (first character) of each card and convert to numeric
    values = []
    for card in cards:
        if card and len(card) >= 2:
            value = card[0]
            if value in value_map:
                values.append(value_map[value])
    
    # Sort in descending order
    values.sort(reverse=True)
    return values

def is_pair(values):
    """Check if the values contain a pair and return the pair value."""
    value_counts = {}
    for val in values:
        value_counts[val] = value_counts.get(val, 0) + 1
    
    pairs = [(val, count) for val, count in value_counts.items() if count >= 2]
    if pairs:
        # Return highest pair
        return True, max([val for val, count in pairs])
    return False, None

def get_top_cards(values, count=2):
    """Get the top N card values from a sorted list."""
    return values[:min(count, len(values))]

def create_mapping():
    """Create mapping between 2-card and 5-card hand rankings."""
    # Load data with manual parsing
    two_card_df = load_rankings_manually("data/hand_rankings/all_card_hands_ranked_two_card_high.csv")
    five_card_df = load_rankings_manually("data/hand_rankings/all_card_hands_ranked_high.csv")
    
    debug_print(f"Loaded two-card file with {len(two_card_df)} entries")
    debug_print(f"Loaded five-card file with {len(five_card_df)} entries")
    
    # Print sample entries from each file
    debug_print("Sample entries from two-card file:")
    for i, row in two_card_df.head(5).iterrows():
        print(f"Hand: {row['Hand']}, Rank: {row['Rank']}, OrderedRank: {row['OrderedRank']}")
    
    debug_print("Sample entries from five-card file:")
    for i, row in five_card_df.head(5).iterrows():
        print(f"Hand: {row['Hand']}, Rank: {row['Rank']}, OrderedRank: {row['OrderedRank']}")
    
    # Process hands to identify pairs and high cards
    two_card_df['cards'] = two_card_df['Hand'].apply(extract_cards)
    two_card_df['values'] = two_card_df['cards'].apply(extract_card_values)
    two_card_df['is_pair'] = two_card_df['values'].apply(lambda x: is_pair(x)[0])
    two_card_df['pair_value'] = two_card_df['values'].apply(lambda x: is_pair(x)[1])
    two_card_df['top_cards'] = two_card_df['values'].apply(get_top_cards)
    
    five_card_df['cards'] = five_card_df['Hand'].apply(extract_cards)
    five_card_df['values'] = five_card_df['cards'].apply(extract_card_values)
    five_card_df['is_pair'] = five_card_df['values'].apply(lambda x: is_pair(x)[0])
    five_card_df['pair_value'] = five_card_df['values'].apply(lambda x: is_pair(x)[1])
    five_card_df['top_cards'] = five_card_df['values'].apply(get_top_cards)
    
    # Extract only the unique rank/orderedrank combinations
    unique_two_card = two_card_df.drop_duplicates(subset=['Rank', 'OrderedRank']).copy()
    
    # Filter five-card hands to just pairs (rank 9) and high cards (rank 10)
    pairs_df = five_card_df[five_card_df['Rank'] == 9].copy()
    high_cards_df = five_card_df[five_card_df['Rank'] == 10].copy()
    
    # Check pair identification
    pair_count = unique_two_card['is_pair'].sum()
    debug_print(f"Found {pair_count} pairs out of {len(unique_two_card)} unique two-card entries")
    
    # Print sample pairs
    debug_print("Sample two-card pairs:")
    for i, row in unique_two_card[unique_two_card['is_pair']].head(5).iterrows():
        print(f"Hand: {row['Hand']}, Cards: {row['cards']}, Is Pair: {row['is_pair']}, Pair Value: {row['pair_value']}")
    
    debug_print("Sample five-card pairs:")
    for i, row in pairs_df[pairs_df['is_pair']].head(5).iterrows():
        print(f"Hand: {row['Hand']}, Cards: {row['cards']}, Is Pair: {row['is_pair']}, Pair Value: {row['pair_value']}")
    
    # Group pairs by their value
    pair_groups = {}
    for _, row in pairs_df[pairs_df['is_pair']].iterrows():
        pair_value = row['pair_value']
        if pair_value not in pair_groups:
            pair_groups[pair_value] = []
        pair_groups[pair_value].append(row)
    
    debug_print(f"Created {len(pair_groups)} groups of five-card pairs")
    
    # Group high cards by their top two cards
    high_card_groups = {}
    for _, row in high_cards_df.iterrows():
        key = tuple(row['top_cards'])
        if key not in high_card_groups:
            high_card_groups[key] = []
        high_card_groups[key].append(row)
    
    debug_print(f"Created {len(high_card_groups)} groups of five-card high cards")
    
    # Create the mapping
    mapping = []
    
    # Process each unique two-card hand
    for _, row in unique_two_card.iterrows():
        if row['is_pair']:
            # This is a pair
            pair_value = row['pair_value']
            debug_print(f"Processing pair with value {pair_value}: {row['Hand']}")
            
            if pair_value in pair_groups:
                # Sort matches by OrderedRank to get the best (lowest) match
                matches = sorted(pair_groups[pair_value], key=lambda x: x['OrderedRank'])
                if matches:
                    best_match = matches[0]
                    debug_print(f"Found match: {best_match['Hand']} (Rank {best_match['Rank']}, OrderedRank {best_match['OrderedRank']})")
                    
                    mapping.append({
                        'two_card_rank': row['Rank'],
                        'two_card_ordered_rank': row['OrderedRank'],
                        'five_card_rank': best_match['Rank'],
                        'five_card_ordered_rank': best_match['OrderedRank']
                    })
                else:
                    debug_print(f"No matches found for pair value {pair_value}")
            else:
                debug_print(f"No pair group found for value {pair_value}")
        else:
            # This is a high card hand
            top_cards = tuple(row['top_cards'])
            debug_print(f"Processing high card with top cards {top_cards}: {row['Hand']}")
            
            if top_cards in high_card_groups:
                # Sort matches by OrderedRank to get the best (lowest) match
                matches = sorted(high_card_groups[top_cards], key=lambda x: x['OrderedRank'])
                if matches:
                    best_match = matches[0]
                    debug_print(f"Found match: {best_match['Hand']} (Rank {best_match['Rank']}, OrderedRank {best_match['OrderedRank']})")
                    
                    mapping.append({
                        'two_card_rank': row['Rank'],
                        'two_card_ordered_rank': row['OrderedRank'],
                        'five_card_rank': best_match['Rank'],
                        'five_card_ordered_rank': best_match['OrderedRank']
                    })
                else:
                    debug_print(f"No matches found for top cards {top_cards}")
            else:
                debug_print(f"No high card group found for top cards {top_cards}")
    
    # Create DataFrame and save to CSV
    mapping_df = pd.DataFrame(mapping)
    
    debug_print(f"Created {len(mapping)} mapping entries")
    
    if not mapping_df.empty:
        mapping_df = mapping_df[['two_card_rank', 'two_card_ordered_rank', 
                                'five_card_rank', 'five_card_ordered_rank']]
        mapping_df.sort_values(['two_card_rank', 'two_card_ordered_rank'], inplace=True)
        mapping_df.to_csv("hand_rank_mapping.csv", index=False)
        
        print("\nFirst 10 mappings:")
        print(mapping_df.head(10))
    else:
        debug_print("WARNING: No mappings were created!")
    
    return mapping_df

if __name__ == "__main__":
    mapping_df = create_mapping()