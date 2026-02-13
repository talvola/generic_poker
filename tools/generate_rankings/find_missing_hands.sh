#!/bin/bash

# Find hands in all_7_card_hands.txt that are not in all_ranked_hands.txt
comm -23 all_7_card_hands.srt all_ranked_hands.srt > missing_hands.txt
