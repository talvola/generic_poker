#!/bin/bash

# Create a temp file with header
head -n 1 rank_1.csv > combined_unique.csv

# Process files in order from highest rank (lowest number) to lowest rank
for i in $(seq 1 20); do
  RANK_FILE="rank_$i.csv"
  if [ -f "$RANK_FILE" ]; then
    echo "Processing $RANK_FILE"
    
    if [ $i -eq 1 ]; then
      # First rank file: extract all hands (skip header)
      tail -n +2 "$RANK_FILE" > temp_processed.csv
    else
      # Add new hands that aren't already in our processed set
      # Extract just the hand part (first 7 columns) for comparing
      tail -n +2 "$RANK_FILE" | while IFS=, read -r c1 c2 c3 c4 c5 c6 c7 rank ordered_rank; do
        hand="$c1,$c2,$c3,$c4,$c5,$c6,$c7"
        # Check if this hand is already in our processed file
        if ! grep -q "^$hand," temp_processed.csv; then
          # Hand not found, add it
          echo "$c1,$c2,$c3,$c4,$c5,$c6,$c7,$rank,$ordered_rank" >> temp_processed.csv
        fi
      done
    fi
    
    # Report progress
    CURRENT_COUNT=$(wc -l < temp_processed.csv)
    echo "  Current unique hands: $CURRENT_COUNT"
  else
    echo "Warning: $RANK_FILE not found, skipping"
  fi
done

# Combine header and processed data
cat temp_processed.csv >> combined_unique.csv

# Final count
TOTAL=$(wc -l < combined_unique.csv)
HANDS=$((TOTAL - 1))  # Subtract 1 for the header
echo "Total unique hands: $HANDS (expecting 133,784,560)"

# Cleanup
rm temp_processed.csv
