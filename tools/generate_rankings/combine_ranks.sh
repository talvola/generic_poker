#!/bin/bash

# Combine all rank files, extract the hand (first 7 fields), skip headers, and sort
for i in {1..20}; do
    # Skip the header line, extract the first 7 fields, and join them
    tail -n +2 poker_hands/rank_${i}.csv | cut -d',' -f1-7
done | sort > all_ranked_hands.txt
