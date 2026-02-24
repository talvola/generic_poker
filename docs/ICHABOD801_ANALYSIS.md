# New Poker Variants Analysis

**Sources:**
- https://www.ichabod801.com/poker_db/
- https://patents.google.com/patent/US20060125180A1 (3-card hybrid patent)
- https://patents.google.com/patent/WO2007011781A2 (60-card deck - not supportable)
- https://211poker.com/ (2-11 Poker)
- https://www.inag11.com/flatline-holdem-poker (Flatline Hold'em)
- https://www.nobochamp.de/pokerdeluxe2.html (Poker Deluxe - not a poker variant)
- https://www.stardeck.com/ (5-suit deck - not supportable)
- https://www.compatiblepoker.com/ (Americana, Telesina)
- https://www.pokerstrategy.com/ Brunson vs Antonius (Poppyha, Greek Hold'em)
- https://www.pokerchipforum.com/ circus games threads (Scrotum, Route 66, Sassy, Cincinnati)
- https://www.cardplayer.com/ Position Poker (table mechanic, not game variant)
- https://www.pagat.com/poker/variants/telesina.html (Telesina rules)
- https://forumserver.twoplustwo.com/ - TwoPlusTwo forum threads (403 - used web search for rules)
  - New England Hold'em, Reverse Hold'em, Oklahoma, Swingo, 9-Card Omaha, Drawmaha/Sviten Special
  - Crazy Candiru, Goodugi, Badaraha (rules not found)
  - PCA Players Choice nominations, mixed games discussion
- https://www.pagat.com/poker/variants/swingo.html (Swingo rules)
- https://noiq.com/ (via web.archive.org) - Online poker site offering Soko, 32-Card Draw, Americana, Telesina
- https://homepokeredge.com/ (via web.archive.org) - 175+ dealer's choice games (site down, partial via search)
  - King Tut (pyramid community + wild), Bummer (no-check draw)
- https://onlinepoker.org/dealers-choice/ - 56 dealer's choice games (many from HomePokerEdge.com)
  - New: Double Omaha, Criss Cross Wild, Pineapple Stud, Rock-Leigh, Forty-Two Draw, Follow the Queen, Slot Machine, etc.
- https://pages.prodigy.net/sixball/ (via web.archive.org) - inaccessible, dead site
- https://thejokerking.com/ (via web.archive.org) - inaccessible, no search results
- https://pokermike.com/poker/ - ~115 variants across 6 categories (7-stud, 5-stud, draw, community, match-pot, other)
  - New JSON: Spit in the Ocean, Hurricane, Death Wheel, Kings & Low-Men, Six Back To Five
  - Reinforces: Follow the Queen family, Guts family, Anaconda family, Baseball family, Chicago
- https://pokertips.org/en/rules/variants/ - 83 variants across community, draw, stud, mixed categories
  - New JSON: Alabama Hold'em, River Poker, Houston Hold'em, Pass the Pineapple, Long Crazy Pineapple, Texas League Baseball, Kings (stud)
  - Reinforces: Follow the Queen (Partridge, She Swings Both Ways), Chicago/San Francisco, Guts, take-it-or-leave-it
- https://pages.prodigy.net/sixball/ndq.htm (via web.archive.org) - "RJ's Poker Variants" (~58 variants across Draw, 5-Stud, 7-Stud, Ludicrous)
  - New JSON: Pig Poker (stud+draw hybrid), Dr. Pepper, Four Forty-Four (8-card stud), Woolworth Stud, Pistol Pete
  - New engine: Minus Man (card rank modification), Butcher Boy (card redirection), Color Poker, Stud Jack (poker+blackjack dual eval)
  - Missing page: variantstexasholdem.htm (not archived), variantsdecathlon.htm (not saved)
- https://www.barge.org/rulebook/ - BARGE Rulebook (62 games). 57 of 62 already have JSON configs
  - New JSON: Short Deck Texas Hold'em (trivial — Hold'em with short_6a deck + 36card_ffh_high eval)
  - Engine needed: Crayfish (die-hides-card), Madison (ignore-pairs low eval), Omaha X or Better (dynamic qualifier), Reno Straight (lowest straight eval)
  - New engine: Take-it-or-leave-it dealing, card relationship wilds (Touchies), Chinese/Russian Poker
- https://pvdb.org/ (via web.archive.org) - Poker Variant Database (29 variants). 18 already covered
  - New JSON: Super Eight (Hold'em with 3 hole cards), Highlander (Omaha Hi-Lo with expose/roll)
  - Engine needed: Phold'em (Pinochle deck), 3-Card Brag (unique betting), Billmaha (T-high qualifier), Joemaha (per-direction wilds), Jack Shit (custom rankings), Do Ya/Howdy Do Ya (card draft dealing), Georgia Hold'em (worst starting hand split), Samurai Sevens (match-pot-or-fold on wild)
- https://forumserver.twoplustwo.com/21/other-poker-games/bored-now-invent-novel-poker-variant-1475/ - "Bored now. Invent a novel poker variant" thread (13 pages, saved locally)
  - New JSON: Murder, Fargo, Thermonuclear Pineapple, Lowmaha Triple Draw, Chinese Badugi, Draw with Expose Rounds, and more
  - Engine needed: True Inversion eval, Indian poker visibility, Badugi High eval, face-up draw replacements
- coloradothegame.com, tablebrain.com, bitshifters.com (inaccessible)

**Date:** 2026-02-21
**Purpose:** Identify games we can add via JSON configs vs. those needing engine changes

## Overview

The ichabod801 database contains **1,000+ poker variants** organized into 8 categories:
Stud, Draw, Common (community), Flip, Guts, Pass, Straight, and Discard.

Most are home-game variants with exotic mechanics (guts, no-peek, auctions, leg-based victory).
However, a significant number use only standard mechanics that our engine already supports.

## Current Engine Capabilities (for reference)

**Actions supported:** deal, bet, draw, discard, expose, pass, declare, choose, separate, replace_community, roll_die
**Wild card types:** rank-based, joker, lowest_hole (per-player), last_community_card, lowest_community
**Evaluation types:** high, high_wild, a5_low, 27_low, badugi, three_card_high, four_card_high, two_card_high, pip-count (49, zero, 6, 21), short-deck variants, suit-specific, and many more (97+ types)
**Deck types:** standard (52), short_6a (36), short_ta (20), short_27_ja (40), joker variants
**Betting:** blinds, bring-in, antes_only
**Community layouts:** linear, multi-row, branching, grid

---

## SECTION 1: Games Supportable with JSON Only

These games use only mechanics we already support. Grouped by type.

### 1A. Stud Variants (Different Deal Patterns)

These are standard stud games with non-standard face-up/face-down sequences.

| # | Game | Cards | Deal Pattern | Eval | Notes |
|---|------|-------|-------------|------|-------|
| 104 | **Blind Stud** | 5 | 4 up, 1 down (final) | High | Reversed 5-card stud |
| 127 | **Last Card Down** | 5 | 1 down, 3 up, 1 down | High | Classic variant |
| 138 | **Oklahoma Lowball** | 5 | 1 down, 4 up | A-5 Low | Lowball stud |
| 142 | **Pistol Pete** | 5 | Ante, then 1 down, 4 up | High | Extra initial bet round |
| 143 | **Pure Luck** | 5 | 2 up, 3 up | High | No hole cards |
| 144 | **Raze** | 5 | 1 down, 4 up | High | Standard 5-card stud |
| 147 | **Six Card Stud** | 6 | 1 down, 4 up, 1 down | High | Already have this |
| 492 | **Kiss of Death** | 5 | 1 down, 3 up, 1 down | A-5 Low | Lowball, last down |
| 517 | **Beelzebub** | 5 | 1 down, 4 up | Hi/Lo Declare | A-5 low, declare |
| 518 | **Five Stud High/Low** | 5 | 2 down, 3 up | Hi/Lo Declare | Standard hi/lo |
| 522 | **One Three One** | 5 | 1D, 2U, 1D, 1U | Hi/Lo Declare | Alternating pattern |
| 525 | **Alligator Stud** | 6 | 1D, 1U, 2U, 1U, 1U | High | Unusual up pattern |
| 533 | **Zanetti Sound** | 6 | 2 down, 4 up | High | Simple 6-card |
| 187 | **Eight Card Stud** | 8 | 2D, 4U, 2D | High | Already have this |
| 600 | **Nine Card Stud** | 9 | 2D, 4U, 3D | High | Extension |
| 145 | **Satan** | 5 | 1D, 4U | Hi/Lo Declare | Standard hi/lo stud |

**With expose (flip) action:**

| # | Game | Cards | Deal Pattern | Eval | Notes |
|---|------|-------|-------------|------|-------|
| 521 | **Low Todd** | 5 | 2D, expose 1, 3U | Hi/Lo Declare | Player flips 1 hole card |
| 523 | **Silberstang** | 5 | 1D, 1U, declare, 3U | Hi/Lo Declare | Early declare |

### 1B. Community Card Variants (Different Layouts)

Standard hold'em-style games with different hole card counts or community card deal patterns.

| # | Game | Hole | Community Pattern | Eval | Notes |
|---|------|------|------------------|------|-------|
| 305 | **Three Card Hold'em** | 1 | 2 community | High | Minimal hold'em |
| 724 | **Rhode Island Poker** | 1 | 1+1 community | High | 3 bet rounds |
| 280 | **Hold Me** | 2 | 1+1+1+1+1 | High | 6 bet rounds, all singles |
| 291 | **Party Girl Hold'em** | 2 | 2+2+1 | High | Paired community deals |
| 293 | **Reverse Flop** | 2 | 1+1+3 | High | Flop dealt last |
| 307 | **Triple Flop Hold'em** | 2 | 2+2+2 | High | Three pairs |
| 308 | **Turbo Hold'em** | 2 | 3+1+1 | High | No pre-flop bet |
| 283 | **Kansas Hold'em** | 3 | 2+1+1 | High | 3 hole cards |
| 295 | **Seven Card Mutual** | 2 | 1+1+1+1, then 1D | High | Final card face-down to player |
| 299 | **St. Louis Flops** | 2 | 3+2+1 | High | Big-medium-small flop |
| 714 | **Drunken Monkey Hold'em** | 3 | 2+2+1 | High | 3 hole + paired community |
| 965 | **Denton** | 3 | 3+1+1 | High | Must use ≥1 hole card |
| 931 | **Dublin Hold'em** | 4 | 3+1+1 | High | Omaha without use-2 rule |
| 298 | **Spanish Hold'em** | 2 | 1+1+1+1+1 | High | Must use exactly 2, 5 singles |

**With "must use" constraints (already supported):**

| # | Game | Hole | Community | Constraint | Eval | Notes |
|---|------|------|-----------|-----------|------|-------|
| 279 | **Greek Hold'em** | 2 | 3+1+1 | Must use 2 | High | Already have |
| 719 | **Tahoe** | 3 | 3+1+1 | Must use 2 of 3 | High | Already have |
| 695 | **Three Card Manila** | 3 | 1+1+1+1+1 | Must use 2, short deck | High | Short deck (remove 2-6) |
| 956 | **Down in the Delta** | 2+2U | 3+1+1 | Must use 2 down | High | 2 down + 2 up player cards |
| 285 | **Manila** | 2 | 1+1+1+1+1 | Must use 2 | High | Short deck (remove 2-6), 5 bet rounds |
| 721 | **Yogi Hold'em** | 3 | 3+1+1 | Must use 3 hole + 2 comm | High | Strict composition |
| 701 | **Nebraska II** | 4 | 3+1+1 | Must use 3 of 4 | High | Inverse Omaha |

**With special community layouts (grid/cross - already supported):**

| # | Game | Hole | Layout | Eval | Notes |
|---|------|------|--------|------|-------|
| 731 | **Cross Over** | 4 | 5-card cross | High | Use 1 row, must use 2 hole |
| 743 | **Twin Beds** | 4 | 2 rows of 5 | High | Use 1 row |
| 983 | **Southern Cross** | 4 | 9-card cross | High | Use 1 row |

### 1C. Draw Game Variants

| # | Game | Cards | Draw | Eval | Notes |
|---|------|-------|------|------|-------|
| 43 | **Four Card Draw** | 4 | Up to 4 | High | Simple 4-card draw |
| 90 | **Three Card Draw** | 3 | Up to 2 | High | Simple 3-card draw |
| 463 | **Don Juan** | 3 | Up to 3 | High | 3-card draw, 2 bet rounds |
| 78 | **Seven Card Draw II** | 7 | Up to 5 | High | Big draw game |
| 466 | **Three Card Double Draw Lowball** | 3 | 2+1 draws | Low | Multiple draws, lowball |

### 1D. Stud with Wild Cards (rank-based wilds supported)

These use our `"type": "rank"` wild card support with `high_wild` evaluation.

| # | Game | Cards | Deal | Wild Cards | Eval | Notes |
|---|------|-------|------|-----------|------|-------|
| 169 | **Ben Franklin** | 7 | Standard 7-stud | 5s and 10s | High Wild | Two wild ranks |
| 532 | **Three Thirty Three** | 6 | 2D, 1D, 2U, 1U | 3s | High Wild | Single wild rank |
| 259 | **Three Forty Five** | 8 | 3D, 4U, 1D | 5s | High Wild | 8-card stud |
| 598 | **Eighty-Eight** | 8 | 2D, 4U, 2D | 8s | High Wild | 8-card stud |
| 599 | **Four Forty Four** | 8 | 4D, 3U, 1D | 4s | High Wild | 4 down start |
| 888 | **Four Forty Two** | 8 | 4D, 3U, 1D | 2s | High Wild | Same deal as 599 |
| 891 | **Ninety Nine** | 9 | 2D, 4U, 3D | 9s | High Wild | 9-card stud |

### 1E. Community Games with Wild Cards

| # | Game | Hole | Community | Wild Rule | Eval | Notes |
|---|------|------|-----------|----------|------|-------|
| 269 | **Austin Hold'em** | 2 | 1+2+1+1 | Lowest community + rank | High Wild | `lowest_community` wild |
| 273 | **Cool Hand Luke** | 2 | 3+1+1 | Lowest community + rank | High Wild | Standard structure |
| 732 | **Dianna's Game** | 3 | 3 face-down (revealed) | Last community + rank | High Wild | `last_community_card` |
| 735 | **Forty Four** | 4 | 4 face-down (revealed) | Last community + rank | High Wild | `last_community_card` |

### 1F. Stud with Player-Specific Wilds (lowest_hole supported)

| # | Game | Cards | Deal | Wild Rule | Eval | Notes |
|---|------|-------|------|----------|------|-------|
| 129 | **Little Ones** | 5 | 1D, 4U | Low hole card + rank | High Wild | `lowest_hole` per player |
| 158 | **Who da Babby Daddy Is?** | 5 | 2D, 3U | Last dealt card + rank | High Wild | Similar to last_community |

### 1G. Anaconda / Pass-Flip Variants

These use pass + discard + expose (flip) + declare - all actions we support.

| # | Game | Cards | Pass Pattern | Eval | Notes |
|---|------|-------|-------------|------|-------|
| 10 | **Anaconda** | 7 | 3L, 2L, 1L, discard 2 | Hi/Lo Declare | Classic pass-the-trash |
| 389 | **Anaconda II** | 7 | 2L+1R, discard 2 | Hi/Lo Declare | Bidirectional pass |
| 390 | **Anaconda III** | 7 | 3L, discard 2 | High | Single pass, no declare |
| 394 | **Australian Rules Anaconda** | 7 | 3R, 2R, 1R, discard 2 | Hi/Lo Declare | Pass right |
| 396 | **Bisexual** | 7 | 2L+2R, 1L+1R, discard 2 | Hi/Lo Declare | Symmetric passing |
| 403 | **Nasty Anaconda** | 7 | 1L, 2L, 3L, discard 2 | Hi/Lo Declare | Reverse pass order |
| 408 | **Screwy Louie** | 7 | 2L with bet, discard 2 | Hi/Lo Declare | Single pass + bet |
| 493 | **Grodnikonda** | 7 | No pass, discard 2 | Hi/Lo Declare | Anaconda without passing |
| 793 | **Orchids** | 7 | 3L only, discard 2 | Hi/Lo Declare | Single pass |
| 795 | **Rich's Revenge** | 7 | 3R, 2R, 1R, discard 2 | Low only | Pass right, lowball |
| 916 | **Shawnahoma** | 7 | No pass, discard 2 | Hi/Lo Declare | Just flip+declare |
| 843 | **Seven Card Reverse** | 7 | No pass, expose 5, discard 2 | Hi/Lo Declare | All expose, then discard |

### 1H. Stud with Expose (Roll Your Own / Mexican Stud)

Players choose which cards to flip face-up each round.

| # | Game | Cards | Deal | Expose Rule | Eval | Notes |
|---|------|-------|------|------------|------|-------|
| 132 | **Mexican Stud** | 5 | 2D, then 1D per round | Expose 1 each round | High | Player-choice flip |
| 633 | **Roll Your Own** | 7 | 3D, then 1D per round | Expose 1 each round | High Wild | Low hole wild |
| 166 | **Australian Stud** | 6 | 3D, discard 1, 3U, 1D | Expose pattern | High | Discard then stud |

### 1I. Draw + Community Hybrids

| # | Game | Hole | Community | Draw | Eval | Notes |
|---|------|------|-----------|------|------|-------|
| 37 | **Five and Two** | 5 | 2 | Draw up to 3 | High | Draw then community |
| 304 | **Texas Two-Step** | 2 | 3+1+1 | Twist up to 2 | High | Hold'em + draw |

### 1J. Three-Card Poker (three_card_high eval supported)

| # | Game | Cards | Deal | Eval | Notes |
|---|------|-------|------|------|-------|
| 462 | **Brag** | 3 | 3 down | 3-card High Wild | Specific wilds (9D, JC, AD) |
| 823 | **American Brag** | 3 | 3 down | 3-card High Wild | 9s and Js wild |

### 1K. Straight Poker (all cards dealt, then bet)

| # | Game | Cards | Deal | Eval | Notes |
|---|------|-------|------|------|-------|
| 238 | **Seven Card Mike** | 7 | 3D, then 1D×4 | High | All face-down stud |
| 661 | **Seven Card Charlie** | 7 | 3D, then 1D×4 | High | Rotating blinds variant |

### 1L. Games with Omaha-Style Constraints + Extra Features

| # | Game | Hole | Community | Constraint | Extra | Eval |
|---|------|------|-----------|-----------|-------|------|
| 710 | **Courchevel** | 4 | 1+2+1+1 | Use 2 | First comm before bet | High |
| 706 | **Studaha** | 4→2D+2U | 3+1+1 | Use 2 | Expose 2 of 4 | High |
| 704 | **Omaha High/Low** | 4 | 3+1+1 | Use 2 | A-5 low qualifier | Hi/Lo |
| 947 | **Highlander** | 4 | 3+1+1 | Use 2 | Expose 1 after turn | Hi/Lo |
| 949 | **Mutual of Omaha** | 3 | 3+1+1 | Use 2 | 3 hole (can buy 4th) | Hi/Lo |

### 1M. Patent Games

#### Stud Hold'em (US Patent US20060125180A1)

A hybrid of Stud, Hold'em, and Omaha. The patent describes it as "a happy medium between Hold'em and Omaha" — the exposed hole card gives information like Stud, while community cards play like Hold'em, and the "must use exactly 2" constraint comes from Omaha.

**Two embodiments — both supportable:**

**Embodiment 1 (Blinds):**
1. Post blinds (small/big blind)
2. Deal 3 cards per player: 2 face-down, 1 face-up
3. Pre-flop betting (starts UTG / after big blind)
4. Flop: 3 community cards
5. Flop betting (starts left of dealer)
6. Turn: 1 community card
7. Turn betting
8. River: 1 community card
9. Final betting
10. Showdown: best 5-card hand using exactly 2 of 3 personal cards + 3 community cards

**Embodiment 2 (Bring-in):**
- Uses antes instead of blinds
- Player with lowest face-up card posts bring-in (first round)
- Player with highest face-up card leads subsequent rounds
- Otherwise identical flow

**Variants mentioned in patent:**
- Hi/Lo split (8-or-better qualifier)
- Crazy Pineapple style (discard 1 hole card after flop)

**All fully supportable.** Very similar to our existing Studaha config but adds the Omaha "must use exactly 2" constraint. The bring-in embodiment uses stud-style betting order based on exposed card.

#### 2-11 Poker (211poker.com)

A Hold'em/Omaha hybrid with a smaller board.

**Game flow:**
1. Post blinds
2. Deal 4 hole cards face-down (like Omaha)
3. Flop: 2 community cards (not 3)
4. Flop betting
5. Turn: 1 community card
6. Turn betting
7. River: 1 community card
8. Final betting
9. Showdown: best 5-card hand using 2 OR 3 hole cards + 2 or 3 community cards

**Key differences from Omaha:**
- Board has only 4 community cards (2+1+1) instead of 5 (3+1+1)
- Players may use 2 OR 3 of their hole cards (Omaha forces exactly 2)
- Hi/Lo variant uses **7-low qualifier** instead of standard 8-or-better

**Variants:**
- Hi/Lo (7-low qualifier)
- Hi-only (Pot Limit recommended)
- Crazy 2-11: deal 5 hole cards, discard 1 after flop

**Supportability:** MOSTLY YES via JSON. The 2+1+1 community layout and 4 hole cards are straightforward. The "use 2 or 3" constraint may already work via `holeCards: [2, 3]` and `communityCards: [2, 3]` array syntax in the showdown config. The 7-low qualifier needs verification that our qualifier system supports a 7-high cutoff (may need a new qualifier index value).

#### Flatline Hold'em (INAG - inag11.com)

A dual-board Hold'em with a cross-shaped community layout.

**Game flow:**
1. Post blinds
2. Deal 2 hole cards face-down
3. "Flop": deal 1 card face-up in each of 4 outer positions (corners of cross)
4. Flop betting
5. "Turn": deal 1 card face-up in each of 4 inner positions (adjacent to center)
6. Turn betting
7. "River": deal center card face-up
8. Final betting
9. Showdown: split pot between best hand on the "Flat" (horizontal row) and best hand on the "Line" (vertical row)

**Layout (9 community cards in cross):**
```
        [T1]
    [F1] [T2] [F2]
[F3] [T3] [R]  [T4] [F4]
    [F5] [T6] [F6]
        [T5]
```
Wait - actually it's more like a plus/cross with:
- 4 outer cards dealt first (flop)
- 4 cards around center dealt second (turn)
- 1 center card dealt last (river)
- "Flat" = horizontal row of 5
- "Line" = vertical row of 5
- Center card shared between both

**Pot split:** Best 5-card hand using hole cards + Flat community cards wins half. Best 5-card hand using hole cards + Line community cards wins the other half. Win both = scoop.

**Supportability:** YES via JSON. Very similar to our existing cross-layout community games (Iron Cross, Criss Cross). We already support cross community layouts and multiple bestHand evaluations. Would need a cross layout with 9 cards and two separate bestHand configs referencing different community subsets (horizontal vs vertical).

### 1N. Circus / Mixed Game Variants (from poker forums & articles)

#### Poppyha (Doyle Brunson's game)

A Brunson favorite, played with "George the Greek." Essentially Omaha with a smaller board.

**Game flow:**
1. Post blinds
2. Deal 4 hole cards face-down
3. Flop: 2 community cards (not 3)
4. Flop betting
5. Turn: 1 community card
6. Turn betting
7. River: 1 community card
8. Final betting
9. Showdown: must use exactly 2 of 4 hole cards + 3 community (Omaha rules)

**Supportability:** YES via JSON. Nearly identical to 2-11 Poker above but with the standard Omaha "must use exactly 2" constraint instead of "2 or 3". Simple: 4 hole, 2+1+1 community, use 2.

#### Scrotum / Scrotum 8 (popular circus game)

Deal 5, publicly discard before the flop, then play Omaha-style.

**Game flow:**
1. Post blinds
2. Deal 5 hole cards face-down
3. Pre-flop: on your action, publicly discard 1-3 cards (keeping 2-4)
4. Pre-flop betting
5. Flop: 3 community cards
6. Flop betting
7. Turn: 1 community card
8. Turn betting
9. River: 1 community card
10. Final betting
11. Showdown: must use exactly 2 hole cards + 3 community

**Scrotum 8 variant:** Hi/Lo split with 8-or-better low qualifier. Aces play high or low.

**Also playable as:** 4-card Scrotum (deal 4, discard 0-2).

**Supportability:** YES via JSON. The discard step with `min_number: 1, number: 3` handles the variable discard. Then standard Omaha showdown. The "public discard" is an information detail that doesn't affect engine mechanics.

#### Route 66 (6-card Dramaha)

The "craziest" circus game. A Dramaha variant with 6 hole cards.

**Game flow:**
1. Post blinds
2. Deal 6 hole cards face-down
3. Flop: 3 community cards, betting
4. Draw phase (discard 0-6, draw replacements)
5. Turn: 1 community card, betting
6. River: 1 community card, betting
7. Showdown split pot:
   - Best 5-card hand from 6 hole cards alone (draw hand)
   - Best Omaha hand: exactly 2 of 6 hole cards + 3 community cards

**Supportability:** YES via JSON. We already have Dramaha configs with dual `bestHand` arrays (draw eval + Omaha eval). The engine's `showdown_manager.py` processes multiple `bestHand` configs and splits the pot accordingly. This is just a 6-card version of existing Dramaha.

#### Sassy (Stud variant with optional draw)

A Tahoe Pitch & Roll variant with a "Sassy or Pat" draw option.

**Game flow:**
1. Dealer antes for the table
2. Deal 4 cards face-down
3. All players simultaneously: discard 1 + expose (flip) 1
4. Low exposed card brings it in, betting round
5. Deal 1 face-up card, bet (high hand leads) — 3 rounds
6. After 6th street: players declare "Sassy" (discard 2 + draw 2, preserving face-up/down state) or "Pat"
7. Final betting round
8. Showdown: Hi/Lo split (8-or-better low qualifier)

**Supportability:** MOSTLY YES via JSON. Discard + expose + bring-in + stud dealing all supported. The draw with `preserve_state` is supported. The "exactly 0 or 2" draw constraint (not 1) may need approximation with min 0, max 2.

#### Cincinnati (classic home game)

5 hole cards + 5 community cards, use any combination.

**Game flow:**
1. Ante
2. Deal 5 cards face-down to each player
3. Deal 5 cards face-down to table
4. Reveal community cards one at a time, bet after each (5 betting rounds)
5. Showdown: best 5-card hand from any of your 10 available cards

**Supportability:** YES via JSON. We may already have this config. 5 hole + 5 community with `anyCards: 5` in showdown.

### 1O. TwoPlusTwo Forum Variants

#### Reverse Hold'em

Standard Hold'em but with the community card dealing reversed: 1+1+3 instead of 3+1+1.

**Game flow:**
1. Post blinds
2. Deal 2 hole cards face-down
3. "Flop": 1 community card
4. Flop betting
5. "Turn": 1 community card (2 total)
6. Turn betting
7. "River": 3 community cards (5 total)
8. River betting
9. Showdown: best 5-card hand, standard high

**Supportability:** YES via JSON. Identical to our Reverse Flop (#293). Just a deal pattern change: `deal 1, bet, deal 1, bet, deal 3, bet`. Can support all betting structures (NL, PL, FL).

#### Oklahoma (Omaha with Progressive Discards)

4-card Omaha with mandatory discards between streets.

**Game flow:**
1. Post blinds
2. Deal 4 hole cards face-down
3. Pre-flop betting
4. Flop: 3 community cards
5. Discard 1 hole card (mandatory)
6. Flop betting
7. Turn: 1 community card
8. Discard 1 hole card (mandatory)
9. Turn betting
10. River: 1 community card
11. River betting
12. Showdown: must use exactly 2 of remaining 2 hole cards + 3 community (Omaha rules)

**Supportability:** YES via JSON. The discard steps fit between deal/bet steps. Use `discard` action with `number: 1, min_number: 1`. Standard Omaha showdown. Player ends with exactly 2 hole cards.

**Variants:** Could also be played Hi/Lo (Oklahoma 8-or-better).

#### 9-Card Omaha

Omaha variant with 9 hole cards instead of 4.

**Game flow:**
1. Post blinds
2. Deal 9 hole cards face-down
3. Pre-flop betting
4. Flop: 3 community cards, betting
5. Turn: 1 community card, betting
6. River: 1 community card, betting
7. Showdown: must use exactly 2 of 9 hole cards + 3 community (Omaha rules)

**Max players:** 4 (9×4=36 hole + 5 community = 41 cards from 52-card deck). With 5 players would need 50 cards.

**Notes from TwoPlusTwo:** Discussion about whether additional betting streets are needed given the massive number of hole cards. Some suggest extra community card streets or discard rounds.

**Supportability:** YES via JSON. Simple config: deal 9 face-down, then standard 3+1+1 community with Omaha showdown constraints (`holeCards: 2, communityCards: 3`). Max 4 players.

### 1P. OnlinePoker.org Dealer's Choice Games

Source: https://onlinepoker.org/dealers-choice/ (56 games listed, many courtesy of HomePokerEdge.com)

Games already covered elsewhere in this doc: Cincinnati, Oklahoma, Reverse Hold'em, King Tut (+Tomb/Revenge), Criss Cross, Crazy Pineapple, Pineapple, Super Omaha (= Big O), Thirty-Two (= 32-Card Draw). Below are the NEW games not previously documented.

#### JSON-Supportable Games

| Game | Hole | Community | Eval | Mechanics | Notes |
|------|------|-----------|------|-----------|-------|
| **Criss Cross Wild** | 4 | 5 cross (3V+3H, shared center) | High Wild | Center card + rank = wild | Like our Criss Cross + `last_community_card` wild |
| **Super Texas Hold'em** | 3 | 5 (3+1+1) | High | Must use ≥1 hole card | 3-hole Hold'em, almost identical to Kansas Hold'em |
| **Double Omaha** | 4 | 10 (2 separate boards × 5) | High split | Use 2+3 from each board | Split pot: best hand on Board A + best on Board B. Dual `bestHand` config |
| **Double Omaha Hi-Lo** | 4 | 10 (2 boards × 5) | Hi/Lo split per board | Use 2+3 from each board | Same as above + A5 low qualifier per board |
| **Forty-Two Draw** | 4 | 2 (revealed one at a time) | High | Draw up to 2, must use ≥3 hole | Name = "4 hole + 2-card draw limit" |
| **Fifty-Two Draw** | 5 | None | High | 2 draw phases | Multi-draw. Name = "5 cards + 2 draws" |
| **Rock-Leigh** | 4 | 8 (4 pairs revealed sequentially) | High | Bet after each pair revealed | Stud/community hybrid |
| **Pineapple Stud** | 4→2 | None (stud) | High | Deal 4 down, choose 1 to expose, discard 1, keep 2 hole. Then 7-card stud continuation | Pineapple + stud hybrid |
| **Turnpike** | 5 | 12 (4 sets of 3, revealed per set) | High | Bet after each set | Massive community game. Max 8 players |
| **West Cincinnati** | 5 | 4 (revealed one at a time) | High or Hi/Lo | Wild card variant of Cincinnati | Like Cincinnati but fewer community + wild |
| **3 Card Drop** | 3 | None | High (3-card) | Sequential expose: reveal 1 card per round × 3 rounds, bet after each | "Roll your own" style |
| **Outhouse** | ? | ? | High + 2-card | Split pot: 5-card high + 2-card high | Dual `bestHand`: one `high` + one `two_card_high`. Up to 7 players |

#### Mostly Supportable (minor questions)

| Game | Notes | Question |
|------|-------|----------|
| **Bummer** | 5 hole + 2 community, last community determines wild rank. 7s wild variant | "No checking allowed" betting rule — need to verify if our bet config can force bet-or-fold |
| **Slot Machine** | 4 hole + 9 community in 3×3 grid, 7s wild, use hole cards + 1 pay line (3 rows + 2 diagonals) | Grid layout exists, but do we support diagonal pay lines? If yes, fully JSON |
| **Bermuda Triangle** | 4 hole + 6 community (layout unclear, page truncated) | Need full rules to determine layout type |
| **Double Texas Hold'em** | 3 hole + community (page truncated) | Need full rules for community card count |

#### Need Engine Changes

| Game | Feature Needed | Priority |
|------|---------------|----------|
| **Follow the Queen** | Dynamic wild card: when queen dealt face-up, next face-up card's rank becomes wild. Shifts when new queen appears. Queens always wild. If queen is last face-up card, only queens wild. Very popular home game | **MEDIUM** |
| **Draft Stud** | Card drafting: players choose/draft face-up cards instead of random dealing. "Socialist Poker" | LOW |
| **Elevator** | Possibly card re-hiding (community cards cycle visible/hidden). Page truncated, unclear | LOW |
| **Train Wreck** | 5 hole + 12 community in 3×4, top row causes card elimination. Conditional mechanics | LOW |
| **Hex** | 4 hole + 7 community in hexagonal layout with position-based adjacency constraints | LOW |

#### Already Have / Not Applicable

- **Super Omaha** = Big O (5-card PLO) — already have config
- **Thirty-Two** = 32-Card Draw — already in Section 2I
- **5 Card Stud with Replacement** = twist/paid draw — already in Section 2C
- **Pyramid** = Pai Gow-style hand arrangement — house game, not standard poker
- **Draw Poker with Joker** = standard draw + joker wild — trivial, already supported
- **Kings and Deuces** = 7-card stud, Ks and 2s wild — trivial rank-based wild config
- **Countdown**, **Dog Leg**, **Frame Up**, **Crazy Pineapple with Replacement** — pages too truncated for assessment

### 1Q. PokerMike.com Variants

Source: https://pokermike.com/poker/ (~115 variants). Many overlap with ichabod801 and onlinepoker.org. Below are NEW games not previously documented.

#### JSON-Supportable

| Game | Cards | Deal/Layout | Eval | Mechanics | Notes |
|------|-------|-------------|------|-----------|-------|
| **Spit in the Ocean** | 4+1 | 4 hole + 1 community face-up | High Wild | Community card's rank is wild everywhere. Draw up to 3 | Classic game! Possibly the oldest community card variant. `last_community_card` wild |
| **Hurricane** | 2 | 2 hole, draw up to 2 | Hi/Lo Declare | Only pairs and high cards count | 2-card poker. Max 13 players. Use `two_card_high` eval |
| **Three Card Monte** | 3 | 3 hole, draw up to 3 | Hi/Lo Declare | Trips > SF > S > F > P > HC | 3-card poker with draw. Use `three_card_high` eval |
| **Kings And Low-Men** | 5 | 5-card draw | High Wild | Kings wild + each player's lowest card wild | Combine `rank: K` + `lowest_hole` wild types |
| **Six Back To Five** | 6→5 | Deal 6, discard 1, then draw up to 3 | High | Must end at 5 cards | Deal 6, mandatory discard step (1), then standard draw |
| **Padre** | 5+5 | 5 hole + 5 community (1 at a time) | High | Use any combo of hole + community | Like Cincinnati but with unrestricted card usage |
| **Show Five** | 7 | 7 all down | Hi/Lo Declare | Progressive flip (expose 1 at a time, bet after each) | Very similar to Grodnikonda (#493). No passing |
| **Phlegm** | 4+1 | 4 hole + 1 community wild | High Wild | Draw, then progressive flip with betting | Spit in the Ocean + progressive expose |
| **In The Snatch** | 4+1 | 4 hole + 1 face-down community | High Wild | Draw first, THEN community revealed, THEN betting | Spit variant with delayed community reveal |
| **Jacks or Back** | 5 | 5-card draw | High or Low | If nobody opens high (Jacks+), plays as lowball | Dual-mode game. Could model as two configs? |
| **Love Thy Neighbor** | 7 | Anaconda format | High | Winner + player to winner's right split pot | Novel pot split (winner + neighbor). May need engine support for neighbor-based pot splitting |

#### Community Layout Variants (may need layout extensions)

| Game | Hole | Layout | Eval | Notes |
|------|------|--------|------|-------|
| **Death Wheel** | 4 | 8 community in circle | High | Use any 3 ADJACENT circle cards + hole. Circular adjacency constraint |
| **No Holds Barred** | 4 | 8 community in hollow 3×3 (no center) | High | Use any 3 adjacent cards. Grid adjacency without center |
| **Cage Match** | 4 | 8 hollow 3×3 | High Wild | Like No Holds Barred + corner cards you use become wild | Adjacent selection + conditional wild |

#### Games Reinforcing Existing Engine Change Categories

Many PokerMike games overlap with categories already documented in Section 2:

- **Follow the Queen family** (Section 2P): Follow Queen And Queens, Black Mariah, Follow Queen In Chicago, Cluster Fuck, Follow The Ho At Midnight. Confirms high demand for dynamic wild cards
- **Anaconda family** (Section 1G): Progressive Passing, Pansy (pot-limit), Rich's Revenge (pass right, low), Bisexual, Howdy Doody (split wilds). All JSON-supportable
- **Guts/Match-pot** (Section 2A): 3-5-7, 6-7-8, One/Two/Four Card Guts, Omaha Burns, Piranha, Position Match Pot, Two More Inches
- **No-peek** (Section 2B): Midnight Baseball
- **Baseball family** (Section 2Q): Football (6s+3s wild), Little League (5-card), Rain-outs, Strikes
- **Chicago/Split-card** (Section 2F): High/Low Chicago, High/Low San Francisco (hearts instead of spades), Two Of Three, Follow Queen In Chicago
- **Twist/Replacement** (Section 2C): Three Card Substitution
- **Kill mechanics** (Section 2E): Murder, No Murder No Game, Deadly 69s/7s/Low/Spades/Diamonds

#### New Engine Change Categories Identified

| Category | Games | Feature Needed |
|----------|-------|----------------|
| **Card relationship wilds** | Touchies (consecutive suited = wild), Hippity-Hops (suited 1 apart = wild) | Wild card based on card-to-card relationships within a hand, not just rank/position |
| **Conditional per-player wilds** | Homicide, Suicide | If hole card pairs face-up card, matching rank becomes wild for that player |
| **Take-it-or-leave-it dealing** | Take It Or Leave It, TIOLI For The Other Guy | Each card offered face-up; player accepts or declines (passed to next player) |
| **Opening requirements** | Jackpots (Jacks+), Progression (trips+ to win) | Must show qualifying hand to open betting; requirement escalates if no opener |
| **Modified hand rankings** | Float Your Boat (no straights/flushes), Best Flush (flush-only rankings) | Non-standard rank order evaluation types |
| **Chinese/Russian Poker** | Russian Poker (13 cards → 3 hands), Polish Poker (low version) | Completely different game: arrange 13 cards into 3 sub-hands; compare per-position |
| **Pip-count target games** | 727, 828, 333, 222, 7½/27½ variants | Accept/decline cards to reach target total; hi-lo split between two targets (e.g., closest to 7 vs closest to 27) |
| **Player-to-player trading** | Trees (trade cards between players, equal swaps) | Direct card exchange between players (not via deck) |

### 1R. PokerTips.org Variants

Source: https://pokertips.org/en/rules/variants/ (83 variants). Many overlap with ichabod801, onlinepoker.org, and PokerMike. Below are NEW games not previously documented.

#### JSON-Supportable

| Game | Cards | Deal/Layout | Eval | Mechanics | Notes |
|------|-------|-------------|------|-----------|-------|
| **Alabama Hold'em** | 4+5 | 4 hole + 5 community (Hold'em board) | High (or Hi/Lo) | Must use exactly 3 hole + 2 community | Reverse Omaha constraint. `holeCards: 3, communityCards: 2`. Can play Hi/Lo |
| **River Poker** | 2+4+1 | 2 hole, 3+1 community, then 1 dealt to PLAYER | High | River is individual card, not community | Last deal step is `location: player` instead of `community`. Novel twist on Hold'em |
| **Houston Hold'em** | 3+4 | 3 hole + 4 community (1 at a time) | High | Best 5 from 7 | Simple: more hole cards, fewer community. 7-card best-of eval |
| **Pass the Pineapple** | 3+5 | 3 hole + Hold'em board | High | After flop bet, pass 1 card left | Uses `pass` action (already supported). Distinctive Pineapple variant |
| **Long Crazy Pineapple** | 3+5 | 3 hole + Hold'em board | High | After each street: deal 1 to player + discard 1 | Draw step after each community card. Player always has 3 hole cards |
| **Texas League Baseball** | 2+5 | Standard Hold'em | High Wild | 3s and 9s are wild | Standard Hold'em + `rank` wild cards (3, 9). Fun theme game |
| **Fort Worth Hold'em** | 2+5 | Standard Hold'em | High | Must use both hole cards | Hold'em with Omaha hand constraint. `holeCards: 2, communityCards: 3` |
| **Kings** | 5 | 5-card stud (1D+4U) with buy option | Hi/Lo Declare | Kings wild. Chip declaration | Combines rank wild, hi-lo split, declare action. All supported |
| **Satan** | 5 | 5-card stud hi-lo | Hi/Lo | Pot-limit, last card face up | Straightforward 5-card stud hi-lo variant |
| **5 Card Straight** | 5 | 5 face down, no draw | High | Single betting round, pure bluff game | Simplest possible poker. Deal 5 face down, bet, showdown |
| **5 Card Blind** | 5 | 5 face UP, bet after each | High | All cards exposed, progressive betting | Like 5-card stud but all face up. Escalating antes per card |
| **Oklahoma Lowball** | 5 | 5-card stud (1D+4U) | 2-7 Low | Lowest hand opens | Already have `27_low` evaluation type |

#### Games Reinforcing Existing Engine Change Categories

Many PokerTips games overlap with categories already documented:

- **Follow the Queen family** (Section 2P): Partridge (paired up-cards trigger wilds — variant trigger), She Swings Both Ways (red/black queen distinction). Confirms demand for dynamic wild card framework
- **Chicago / San Francisco** (Section 2F): San Francisco (highest/lowest HEART splits pot — same as Chicago but hearts instead of spades). Reinforces "best card of suit" evaluation need
- **Take-it-or-leave-it** (Section 1Q): Orchard Street (cascading card rejection — declined card passes to next player)
- **Card buying** (Section 2D): Cold Petroleum (choose between visible card, blind card, or pair purchase at escalating costs)
- **Twist / paid replacement** (Section 2C): English Stud (exchange cards between rounds, replacement maintains face-up/down state), Little Squeeze / Low Hole Roll Your Neighbor (buy replacement card)
- **Force fold / card events** (Section 2E): Black Mariah (Queen of Spades face-up kills the hand), The Good the Bad & the Ugly (community cards trigger wild/discard/fold effects)
- **Modified hand rankings** (Section 1Q): Best Flush (flush-only ranking system), Spanish/Synthetic Poker (32-card deck, flush > full house)
- **Guts** (Section 2A): Wisconsin Guts, Studded Guts, Balls, 5-2
- **Trick-taking (NOT poker)**: Bourré, P-Bourré — card game, not poker. Not supportable
- **Physical game**: Scramble (real-time card grabbing) — not supportable

#### New Engine Change Observations

| Category | Games | Feature Needed |
|----------|-------|----------------|
| **Card-triggered pot effects** | Divorce Court (queens = take half pot, kings face-up = eliminated, jacks = split with winner) | Beyond force-fold: cards trigger immediate pot actions |
| **Indivisible community stacks** | Pendulum (3 hole + 4 stacks of 1/2/3/2 cards; must use whole stacks, max 4 community) | Community cards grouped in inseparable stacks; constraint on total used |
| **Multi-condition winning** | Fifty-Two (must achieve 2 of 3: highest suit card, lowest suit card, best poker hand) | Victory requires meeting multiple independent conditions; multi-round accumulation |
| **Inverted visibility** | Upside-Down Pineapple (hole cards turned face UP, flop dealt face DOWN and revealed later) | Reverse normal card visibility; delayed community card reveal |
| **Multi-group community constraints** | Two Two and One (4 hole + 6 community in 2 groups; must use exactly 2+2+1 from specific groups) | Require specific number of cards from each named community group |
| **Per-player wilds from hole match** | Match Your Hole Card (face-up cards matching hole card rank become wild for that player only) | Per-player wild cards based on matching own hole card |
| **Escalating limits per round** | Mannheim Hold'em (SB → BB → SB+BB → No Limit across 4 rounds) | Different betting limits/structures within a single hand |
| **Single-card showdown** | Louisiana Lo-Flop (look at 1 of 2 cards; keep or blind-swap; highest single card wins) | Showdown evaluates single cards, not 5-card hands |

### 1S. RJ's Poker Variants (prodigy.net/sixball)

Source: https://pages.prodigy.net/sixball/ (via web.archive.org, ~58 variants, circa 2001). Well-written home game guide with detailed rules. Missing: Texas Hold'em page (not archived), Decathlon page (not saved).

#### JSON-Supportable

| Game | Cards | Deal/Layout | Eval | Mechanics | Notes |
|------|-------|-------------|------|-----------|-------|
| **Pig Poker** | 5 | 3 down, then 4th up, 5th up (stud), then draw | High | Stud+draw hybrid — stud betting then draw phase | Sequence: deal 3D, bet, deal 1U, bet, deal 1U, bet, draw, bet, showdown |
| **Dr. Pepper** | 7 | Standard 7-card stud | High Wild | 2s, 4s, and 10s are ALL wild (up to 12 wilds!) | Simple rank wild config. "Spill" variant: fold if all 3 wild ranks appear face-up |
| **Four Forty-Four** | 8 | 4 down + 4 up (8-card stud) | High Wild | All 4s wild | 8-card stud variant. Deal 4 down then 4 up with betting after each up |
| **Woolworth Stud** | 7 | Standard 7-card stud | High Wild | 5s and 10s wild | Simple rank wild. "Chapter 11" variant: pay premium per face-up wild or fold |
| **Pistol Pete** | 5 | 5-card stud with extra bet | High | Extra betting round after hole card, before first upcard | aka "Hole-Card Stud" or "Five Bets". Just an extra bet step in config |
| **Big Sol / TNT** | 7→5 | Deal 7 down one-at-a-time (bet after each), discard 2, flip 4 | Hi/Lo Declare | Progressive flip with declare | Like Grodnikonda but dealt one card at a time with betting per card |
| **Twin Beds** | 4+10 | 4 hole + 2 rows of 5 community | High Wild | Last card each row is wild + matching rank. Use cards from ONE row only | Multi-row community layout with row restriction. `communityCardLayout: multi-row` |
| **Five and Ten Draw** | 5 | 5-card draw | High Wild | 5s and 10s wild | aka St. Louis, Woolworth. Simple rank wild draw |
| **Rockleigh** | 4+8 | 4 hole + 4 groups of 2 community | Hi/Lo Declare | Use 1-2 cards from same group only. Hi-lo-both declare | Multi-group community. Similar constraint to Two Two and One |

#### Games Reinforcing Existing Engine Change Categories

- **Follow the Queen family** (Section 2P): Follow the Queen, Follow Mary (queens always wild), Follow the King. Very detailed descriptions confirm the mechanic
- **7-27 family** (Section 1Q pip-count targets): Extremely detailed 7-27 rules with 9 sub-variants (Overbooked Flight, Aisle Seat, Pick Your Seat, Exit Row, Diverted Flight, Not Exactly, Inside, Outside, 7-47 Wide Body). Best single reference for this game family
- **Chicago / split-card** (Section 2F): Draw Poker - High Spade (draw variant of Chicago split)
- **Twist / paid replacement** (Section 2C): Three-Card Substitution (detailed: 1st buy = 3 ante, 2nd = 6, 3rd = 9), Heinz (pay for wild cards), Woolworth Chapter 11
- **Soko / four-flush** (Section 2I): New York Stud ("four flush higher than pair, less than two-pair"), Macintosh (adds four-flush ranking)
- **No-peek** (Section 2B): Rollover / No Look / No Peek
- **Multiple hands** (Section 2G): Double-Handed Stud (play 2 hands, can't raise between them)
- **Leg-based** (Section 2H): Leg Poker (must win 2 hands)
- **Baseball / conditional dealing** (Section 2Q): Baseball Stud (9s wild, 4 up = extra card, 3 up = fold), Night Baseball, Rainout
- **Opening requirements** (Section 1Q): Progressive Draw (escalating openers: J → Q → K → A)
- **Per-player wilds** (Section 1R): Kankakee (first upcard wild for that player), Shifting Sands (first flipped card wild)
- **Guts** (Section 2A): Guts (3-card, 2-3, 4-3, 5-2 variants detailed)
- **Card buying** (Section 2D): Balls (must match pot for 7th card)
- **Force fold on card** (Section 2E): Rainout (Queen of Spades kills hand), Dr. Pepper Spill (all 3 wild ranks showing = fold)

#### New Engine Change Observations

| Category | Games | Feature Needed |
|----------|-------|----------------|
| **Card rank modification** | Minus Man / Duker Poker (optionally reduce one card's rank by 1, e.g. 7→6; affects all matching cards). Double Negative (reduce 2 ranks or 1 rank by 2) | Player action to permanently modify card rank. Original game by "RJ" |
| **Card redirection on match** | Butcher Boy (if dealt card matches another player's face-up card, it goes to that player instead; win = four-of-a-kind) | Dealing redirects based on matching existing face-up cards. Completely different dealing model |
| **Color-based evaluation** | Color Poker (mixed red/black hands must fold; pure-color hands rank above mixed) | New evaluation dimension based on card color (red vs black), not suit |
| **Poker + blackjack dual eval** | Stud Jack (pot split between best poker hand and best blackjack total from hole cards only) | Second evaluation using blackjack scoring on card subset (hole cards) |
| **Voting / player elimination** | Survivor Stud (players vote by secret ballot to kick one player out before final bet; eliminated player can pay to return) | Non-card-based elimination via player voting. Social mechanic |
| **Forced bet on pair-up** | Macintosh (if face-up pair appears, must bet half pot or fold) | Card-triggered mandatory bet (not just force fold, but forced bet amount) |
| **Instant win on specific hand** | Fairview (pair of 7s instantly wins the pot, bypassing all play) | Specific hand pattern triggers immediate win, ending the hand |

### 1T. BARGE Rulebook

Source: https://www.barge.org/rulebook/ (62 games, regularly updated). The definitive rulebook for the BARGE (Big August Rec.Gambling Excursion) poker tournament. Well-structured with complete rules for each game.

**Coverage: 57 of 62 games already have JSON configs** in our system. The 5 missing games are analyzed below.

#### JSON-Supportable (1 game)

| Game | Cards | Deal/Layout | Eval | Mechanics | Notes |
|------|-------|-------------|------|-----------|-------|
| **Short Deck Texas Hold'em** | 2+5 | Standard Hold'em | `36card_ffh_high` | 36-card deck (6-A), flush > full house | Already have `short_deck_omaha.json` with same deck+eval. Just need Hold'em version without Omaha constraint |

#### Needs Engine Changes (4 games)

| Game | What It Is | What's Missing |
|------|-----------|----------------|
| **Crayfish** | Omaha/Hold'em where all 5 community cards dealt face-up on flop, then die rolls on turn/river hide board cards (1-5 = hide that card, 6 = no change) | We have `roll_die` action but no "hide community card based on die result" effect. Need die-result-to-card-visibility linkage |
| **Madison** | Triple draw lowball where **pairs are completely ignored** in evaluation. Best hand is 2AAAA (four aces is just four low cards). Worst is KKKKQ | New evaluation type needed: "lowest hand ignoring pairs, straights, and flushes." Different from A-5 low which still recognizes pairs |
| **Omaha X or Better** | Omaha Hi/Lo where the low qualifier (X) is determined by a dice roll (2d6: 12=Q, 11=J, 10-5=face value, 2-4=no low) | We have dice rolling and Omaha Hi/Lo, but qualifier is currently fixed in config. Need dynamic qualifier from die result |
| **Reno Straight** | 5 hole cards, dual boards, Omaha constraints (2+3). Hi-lo split where low = lowest straight (not standard low). Greg Raymer game | Need "lowest straight" evaluation type + dual-board interaction. If no player has a straight, high scoops |

### 1U. PVDB.org (Poker Variant Database)

Source: pvdb.org via web.archive.org (29 variants total, 18 already covered by existing configs or previous analysis)

**JSON-Supportable Games (2):**

| Game | Description | Config Notes |
|------|-------------|--------------|
| **Super Eight** | Texas Hold'em with 3 hole cards instead of 2. Best 5-card hand from 8 cards (3 hole + 5 community). 2-10 players | Deal 3 face-down to player. Standard Hold'em community dealing. Showdown: `anyCards: 5` (best 5 from 8). Very similar to existing Manila/Tahoe configs |
| **Highlander** (aka Roll Your Omaha, Rollmaha) | Omaha Hi-Lo where after each community card stage (flop/turn/river), each player exposes one face-down card. By showdown, each player has only 1 face-down card remaining | 4 hole cards dealt face-down, then: flop → expose 1 → bet → turn → expose 1 → bet → river → expose 1 → bet → showdown. We have `expose` action support. Use Omaha Hi-Lo showdown with `holeCards: 2, communityCards: 3` for both hi/lo evals |

**Engine Changes Needed (9 games, 7 observations):**

| Game | Description | What's Needed |
|------|-------------|---------------|
| **Phold'em** | Hold'em played with Pinochle deck (48 cards: 2 each of 9, T, J, Q, K, A per suit). Only 3 community cards. Five of a kind is valid. Custom rankings: SF > 5oaK > Flush > 4oaK > FH > Straight > High Card > 3oaK > 2P > Pair | New deck type `pinochle` (48 cards with doubled ranks). Brand new hand evaluation for doubled-rank deck (completely different probability distribution — pair is most common, high card ranks 7th). See 2K |
| **3-Card Brag** | British card game. 3 face-down cards, single betting round. Unusual betting: previous pot contributions ignored, must match or raise previous bet. "Seeing" mechanic (double bet to force 2-player showdown). Blind play option. Rankings: prial > running flush > run > flush > pair > high. 3-3-3 is best prial | Completely different betting structure (not standard poker betting), blind play mechanic, "seeing" to force showdown, no shuffling between hands, unique hand rankings. Not poker-compatible betting — see 1X (NOT Supportable) |
| **Billmaha** (aka Omaha 10) | Omaha Hi-Lo with 10-high as the highest qualifying low hand instead of 8-high. Otherwise identical to Omaha Hi-Lo | Configurable low qualifier threshold. Currently the 8-or-better qualifier is presumably fixed. Need config parameter for max low card rank (8, 9, 10, etc.) to generalize. Overlaps with **Omaha X or Better** from BARGE. See 2I |
| **Joemaha** (aka Omahady Doody) | Omaha Hi-Lo where a single 3 from hole cards is wild for the high hand, and a single King is wild for the low hand. Only one wild card per hand | Per-direction wild cards (different wilds for hi vs lo in split pot). Also "single wild" limitation (only 1 card of the wild rank can be used as wild, not all matching). See 2P |
| **Jack Shit** | 5-Card Draw where Jack-high (J with 4 lesser values, no pairs/straights/flushes) beats everything including royal flush. Lowest kickers win ties (J-5-4-3-2 is best). Standard draw otherwise | Custom evaluation where a specific high-card combination is top-ranked. Novel evaluation type. See 2I |
| **Do Ya** (aka Dugan) | Each player gets 1 face-down card (that rank is wild for their entire hand). Then dealer turns over deck cards one at a time, offering them to each player in turn. Player can accept or reject up to 2 cards; forced to take 3rd. Continues until everyone has 5 cards. Betting after each round | Card draft/offer dealing mechanic — completely non-standard. Cards turned over from deck and offered to specific players who accept/reject. Rejected cards remain available for next player. See 2L |
| **Howdy Do Ya** (aka Howdy Dugan) | Cross between Do Ya and Howdy Doody. Same card draft/offer dealing mechanic as Do Ya, but with direction-based wilds: 3s wild for high, Kings wild for low. Uses declare (chip/no chip for hi/lo) | Same card draft dealing as Do Ya + per-direction wild cards + declare. Multiple engine features needed. See 2L, 2P |
| **Georgia Hold'em** | Texas Hold'em where the worst 2-card starting hand wins half the pot. Aces high for low eval. Offsuit beats suited for low. Pairs only lose to higher pairs | Novel split pot mechanic: half the pot awarded based on worst 2-card hole cards (not the 5-card hand). Needs new evaluation type for "worst starting hand" with custom suited/offsuit/pair rankings. See 2F |
| **Samurai Sevens** (aka Samurai 7s) | 7-Card Stud where 7s are wild, but if dealt a face-up 7, player must match the pot or fold | "Match the pot or fold" mechanic triggered by dealing a specific card face-up. Wild cards with conditional cost. See 2E |

### 1V. TwoPlusTwo Forum Thread ("Bored now. Invent a novel poker variant")

Source: forumserver.twoplustwo.com, 13 pages of user-invented variants (2008-2018). ~145 games posted, many jokes/duplicates/vague. Best candidates below.

**JSON-Supportable Games (15):**

| Game | Description | Config Notes |
|------|-------------|--------------|
| **Murder** | 5 cards dealt + 3-card community flop + draw up to 3. Best 5-card hand from any combination of hand + community. PL/NL | Deal 5 down, bet, deal 3 community, bet, draw (max 3), bet, showdown. Simple draw+community hybrid |
| **Fargo** | 3-Card Omaha with expose. 3 hole cards, standard flop/turn/river. After flop bet, expose 1 hole card. Omaha rules (must use exactly 2 from hand) | Deal 3 down, bet, deal flop, bet, expose 1, deal turn, bet, deal river, bet, showdown. Omaha constraint with 3 hole cards |
| **Thermonuclear Pineapple** (Hold'em or Throw'em) | 5 hole cards. Discard 1 after pre-flop, 1 after flop, 1 after turn. By river, down to 2 cards. PL | Extended Pineapple with 3 discard rounds. All steps exist |
| **Draw High with Expose Rounds** | 5-card draw, one draw. After draw: expose 2 simultaneously + bet, expose 1 more + bet. Showdown reveals remaining 2 | Deal 5, bet, draw, bet, expose 2, bet, expose 1, bet, showdown. Draw/stud hybrid |
| **Lowmaha Triple Draw** | 4 hole cards. Draw, flop, draw, turn, draw, river, showdown. 2-7 low with Omaha constraint (use 2 hole + 3 community). HU/3-4 max | Interleaved draw+community. All step types exist. Novel hybrid of Omaha + triple draw |
| **9-Card Split / Chinese Badugi** | Deal 9, one draw. Separate into 5-card high hand + 4-card badugi hand. Split pot. 3-max | Uses separate mechanic. Dual eval: high (5-card) + badugi (4-card) |
| **2-7 Triple Draw + Community** | Standard 2-7 TD, but after 2nd draw, deal 1 community card. Best 5-of-6 using 2-7 low | Draw + community hybrid. Simple extension |
| **4-Card Ocean Crazy Pineapple** | Deal 4. Flop, bet, discard 1. Turn, bet, discard 1. River, bet. Deal 6th community ("ocean"), bet, showdown | Extended Pineapple with 6th community card |
| **Texas Hold It** (Stud Hold'em, Tecumseh) | Hold'em where each player gets their own face-down river card instead of shared 5th community. 3 player cards + 4 community = best 5 from 7 | Deal 2, flop/turn as normal, then deal 1 face-down to each player. Showdown with `anyCards: 5` |
| **Five-Card Draw/Stud Hybrid** | Deal 5 down, bet. Deal 2 more face-down, discard 2 (keeping best 5), bet. Expose 4 of 5, bet. Showdown | Draw + expose pattern. All steps exist |
| **Omadraw H/L** | Omaha Hi/Lo with a draw (up to 2 cards) after flop. Standard turn/river/showdown | Omaha + draw. Simple hybrid |
| **A-5 Draw High-Low 8** | Standard 5-card draw, hi/lo split with 8-or-better qualifier, A-5 low | Basic draw hi/lo. `a5_low` + `high` dual eval |
| **Seven-Card 2-7 Single Draw** | Deal 7, single draw up to 5 (must keep 2). Best 5-card 2-7 low. NL, 4-handed max | Large-hand draw. Simple config |
| **2-Board Pineapple** | Standard Pineapple (3 cards, discard 1 on flop) with two parallel community boards. Win each board for half pot | Multi-row community layout + Pineapple discard + dual-board split |
| **Rich Man's Tin Kan** | 5 hole + 4-card flop + 3-card turn + 2-card river (9 community total). Best 5-card high from any combination | Decreasing community deal pattern. Unusual but configurable |

**Engine Changes Needed (notable new observations):**

| Game | Description | What's Needed |
|------|-------------|---------------|
| **True Inversion** (Vienna, Second Best Hold'em, Deuce-to-Eight) | Multiple games where the worst "best high hand" wins. NOT lowball — each player makes their best HIGH hand, then the weakest best-high wins. Vienna: worst flush triple draw. Second Best Hold'em: 2nd-best hand wins | New evaluation mode: "true inversion" — evaluate best high hand, then rank inversely. Distinct from lowball (which avoids pairs/straights). See 2I |
| **Forehead Omaha** (Indian poker variants) | Omaha where 2 of 4 hole cards are placed on forehead — visible to opponents but NOT to the player. Must use 1 down + 1 forehead card. Also: Vero Beach (stud, 7th street on forehead), Prognostication (stud, river visible to left neighbor) | "Indian poker" visibility mode: card visible to opponents, hidden from owner. Fundamentally different from face-up (all see) or face-down (only owner sees). See 2R |
| **Omadugi / Dugaha** | Omaha-style (4 hole, flop/turn/river) with split pot: half for Omaha high (use 2+3), half for badugi evaluation. Badugi eval uses 2 from hand + 2 from board | Badugi evaluation from mixed hole+community cards. Currently badugi evaluates only a player's hand cards, not a combination of hand + community. See 2I |
| **Badugi Hi/Lo** | Triple draw. Split pot: best standard badugi (low) + best "high badugi" (highest rainbow 4-card hand). A234 and AKQJ auto-scoop | New `badugi_high` evaluation type (reverse badugi ranking). See 2I |
| **Slash / Backslash** | Stud/draw hybrid. Draw 0-3, but replacement cards come face-up. Slash = high, Backslash = 2-7 low. | Face-up draw replacement mechanic. See 2C |
| **Scooter** (variable must-use) | Omaha variant. Discard any number pre/post-flop, but must use ALL remaining hole cards at showdown. Keep 3 = use 3, keep 2 = use 2, etc | Variable "must use N" constraint based on cards held. See 2I |
| **Colombian Necktie** | Deal 5. Choose 3 and pass face-down to player on left — these become that player's personal "flop." Keep 2 as hole cards. Community turn + river. Best 5 from hole + personal flop + community | Passed cards become a player-specific community board. The pass action exists, but using passed cards as personal community (not added to hand) is novel |
| **Democratic Poker** | Players vote on which community cards to use (from face-up candidates). Majority rules | Voting mechanic for community card selection. Novel step type |
| **40 or Nothing** | Triple draw targeting pip-count of exactly 40 (A=1, 2-9=face, T=10, J/Q/K=0). 4 face cards = auto half-pot | New pip-count target (40). Similar to existing `49`, `zero`, `21` eval types. See 2I |
| **Hit-or-Stand Poker** | Stud/blackjack hybrid. Players choose to "hit" (get dealt another card) or "stand." Bust (over target) is dead. Target varies (21, 27) | Hit-or-stand dealing mechanic — variable-length rounds where players individually choose to stop receiving cards |

### 1W. Additional Variants (from articles)

#### Americana / American Poker (32-card deck stud)

Italian-style 5-card stud with a stripped deck.

**Deck:** 32 cards (7, 8, 9, 10, J, Q, K, A in all 4 suits)
**Game flow:** Standard 5-card stud (1 down, 4 up) with bring-in betting
**Hand rankings:** Flush beats Full House (short deck probability). Lowest straight: A-7-8-9-10.
**No blinds** — uses antes + bring-in by highest exposed card.

**Supportability:** NEEDS MINOR ENGINE WORK. Requires:
- New deck type `short_7a` (32 cards, 7-A)
- New evaluation type for 32-card rankings (Flush > Full House)
- Both are straightforward extensions of existing short-deck support (we have `short_6a` for 36 cards)

#### Telesina / Teresina (Italian 5-card stud + community card)

The Italian national poker game.

**Deck:** Variable based on player count: 11 minus players × 4 suits (e.g., 5 players = 36 cards)
**Game flow:**
1. Ante
2. Deal 1 down, 1 up per player
3. Betting (highest exposed card leads, ties broken by suit: hearts > diamonds > clubs > spades)
4. Deal 1 up card, bet — repeat 3 more times (4 up cards total)
5. "Vela" (community card) revealed — deal 1 face-down community card at start, flip after all streets
6. Showdown: best 5 from 5 personal + 1 community

**Hand rankings:** Flush > Full House. Suit-based tiebreaking.

**Supportability:** NEEDS ENGINE CHANGES:
- Variable deck based on player count (not currently supported)
- Suit-based tiebreaking (not supported)
- Could partially support with fixed deck sizes (e.g., "Telesina for 5 players" with 36-card deck)

### 1X. Not Game Variants

#### Position Poker (Johnny Chan / Bellagio)

NOT a card game variant. It's a table management mechanic: two buttons (dealer + "winner's button"). The winner of the previous hand gets last-to-act position regardless of seat. Approved by Nevada Gaming Commission. Plays with standard Hold'em rules otherwise.

**Not applicable to our game config system** — this is a seating/position feature.

### 1Y. Games NOT Supportable (from additional sources)

#### Stardeck 5-Suit Poker (stardeck.com) - NOT SUPPORTABLE

Uses a 65-card deck with 5 suits (the 5th is "Stars"). Modified hand rankings:
- Flush beats Full House (rarer with 5 suits)
- Five-of-a-Kind possible without wild cards
- New "Spectrum" hand (one card from each of 5 suits) ranks between Two Pair and Three of a Kind

**Would need:** New 65-card deck type, new suit, completely new hand evaluation tables. Not worth the effort.

#### 60-Card Unsuited Hold'em (Patent WO2007011781A2) - NOT SUPPORTABLE

Custom 60-card deck with "unsuited" 10s and 11s that can't form flushes. Both hole cards required for straights/flushes. Would need new deck type and card-level suit suppression.

#### Poker Deluxe (nobochamp.de) - NOT A POKER VARIANT

Card buying game with progressive costs and point-differential payouts. More of a custom card game than a poker variant. Fundamentally different game structure.

#### Colorado, TableBrain, Bitshifters - INACCESSIBLE

These websites are either completely defunct or blocked by web.archive.org restrictions. No rules could be recovered.

#### TwoPlusTwo Thread-Only Variants - RULES NOT FOUND

The following games are mentioned in TwoPlusTwo forum threads but the forums returned 403 errors
and web search could not find their rules documented elsewhere:

- **New England Hold'em** - No rules found online. Likely a local/regional variant.
- **Crazy Candiru** - Home poker thread. No rules found.
- **Goodugi** - Mentioned in Imperial Palace mixed game thread. Probably a Badugi hybrid (Good + Badugi?). Rules unknown.
- **Badaraha** - Mentioned as one of "two best poker variants you aren't playing." Possibly Badugi + Omaha hybrid (cf. Badacey, Baducey naming pattern). Rules unknown.
- **"Seeking Playtesters" game** - Thread about a new NL game. Name and rules unknown.
- **PCA Players Choice nominations** (2011, 2012) - Lists of game variants nominated for PokerStars Caribbean Adventure event. Thread content inaccessible.
- **"Bored now, invent a novel poker variant"** thread - 13 pages of invented games. Now analyzed — see Section 1V.

#### Additional Inaccessible Sites

- **pages.prodigy.net/sixball** (variantsludicrous.htm) - Early 2000s personal page. Completely dead, no cached content or search results found.
- **thejokerking.com** (home variation index) - Poker home game variants site. No search results found, site fully defunct.
- **homepokeredge.com** - 175+ dealer's choice games. Site down (ECONNREFUSED). Partial game details recovered via search snippets: King Tut (pyramid community, see Section 2O), Bummer (5-card draw, no checking allowed), Low Hole Card Wild (already supported).

#### 3-Card Brag (from pvdb.org) - NOT SUPPORTABLE

British card game that is fundamentally NOT poker. While it uses playing cards and hand rankings, its core mechanics are incompatible:
- **Non-poker betting:** Previous pot contributions are ignored; you must match or exceed the last bet on every turn. No concept of calling/raising as in poker.
- **"Seeing" mechanic:** Double the last bet to force a 2-player showdown. The game continues until only 2 remain.
- **Blind play:** Players can bet without looking at cards, paying half cost. Open players cannot force blind players out.
- **No shuffling:** Cards from previous hand go to bottom of deck without shuffling.
- **Unusual rankings:** Prial (trips) > Running Flush > Run (straight) > Flush > Pair > High Card. 3-3-3 is best hand. A-2-3 beats A-K-Q.

Would require a completely different betting engine and game loop. Not a candidate for the poker engine.

---

## SECTION 1 SUMMARY

**Total JSON-only games identified: ~115-130 new variants** (including ~15 from TwoPlusTwo thread)

Many are minor variations of each other. Recommended implementation priority:

### High Priority (well-known games, fills gaps)
1. **Anaconda** (#10) - Classic home game, pass-the-trash
2. **Manila** (#285) - Popular Asian variant, short deck
3. **Kansas Hold'em** (#283) - 3-hole-card hold'em
4. **Scrotum 8** - Deal 5, discard 1-3, then Omaha 8. Top circus game
5. **Route 66** - 6-card Dramaha. "Craziest" circus game
6. **Poppyha** - 4 hole, 2+1+1 community, Omaha rules. Brunson's game
7. **Oklahoma** - 4 hole, discard 1 after flop + 1 after turn, Omaha showdown
8. **Nebraska II** (#701) - Must use 3 of 4 (inverse Omaha)
9. **Three Card Hold'em** (#305) - Simple, popular
10. **Ben Franklin** (#169) - Classic wild card stud
11. **Mexican Stud** (#132) - Roll-your-own classic
12. **Grodnikonda** (#493) - Anaconda without passing (simplest flip game)
13. **Dublin Hold'em** (#931) - 4-card no-constraint hold'em
14. **Down in the Delta** (#956) - Omaha-like with 2 exposed
15. **Stud Hold'em** (Patent) - 3 hole (2D+1U), use exactly 2, blinds or bring-in
16. **2-11 Poker** - 4 hole, 2+1+1 community, use 2-or-3
17. **Flatline Hold'em** - 2 hole, 9 community cross, dual-board split pot
18. **Cincinnati** - 5 hole + 5 community, use any combo. Classic home game
19. **Sassy** - 4 cards, discard+expose, stud, optional draw, hi/lo

### Medium Priority (interesting variants)
20. **Double Omaha** - 4 hole, 2 boards × 5 community, split pot per board
21. **Criss Cross Wild** - 4 hole, 5 cross community, center card + rank wild
22. **Party Girl Hold'em** (#291) - 2+2+1 community
23. **Reverse Flop** (#293) - Flop dealt last
24. **Triple Flop Hold'em** (#307) - 2+2+2 community
25. **Hold Me** (#280) - All community singles
26. **St. Louis Flops** (#299) - 3+2+1 community
27. **Drunken Monkey Hold'em** (#714) - 3 hole, 2+2+1 community
28. **Roll Your Own** (#633) - 7-card stud, player-choice flip + low hole wild
29. **Austin Hold'em** (#269) - Lowest community wild
30. **Cool Hand Luke** (#273) - Standard hold'em + lowest community wild
31. **Cross Over** (#731) - Omaha + cross layout
32. **Southern Cross** (#983) - Omaha + 9-card cross
33. **Twin Beds** (#743) - Omaha + 2 rows of 5
34. **Yogi Hold'em** (#721) - Must use exactly 3+2
35. **Pineapple Stud** - Deal 4, expose 1, discard 1, then stud
36. **Rock-Leigh** - 4 hole + 8 community (4 pairs)
37. **Forty-Two Draw** - 4 hole + 2 community + draw
38. **Fifty-Two Draw** - 5-card draw with 2 draw phases
39. **Four Card Draw** (#43) - Simple draw
40. **Three Card Draw** (#90) - Simple draw

### Lower Priority (niche variants)
41+. Turnpike (5 hole + 12 community), West Cincinnati, 3 Card Drop, Outhouse (5-card + 2-card split pot), various stud/community deal pattern permutations, additional Anaconda variants, etc.

---

## SECTION 2: Games Needing Engine Changes

### 2A. GUTS FORMAT (~100+ games)

**What it is:** Players declare "in" or "out" simultaneously. Those who are "in" play for the pot. Losers must match the pot. Repeat until one player wins or pot is claimed.

**Games blocked:** All games in the Guts category (3-card guts, 5-card guts, etc.) plus many variants in other categories.

**Engine changes needed:**
- New game loop: in/out declaration → play → losers match pot → repeat
- "Match the pot" penalty mechanism
- "Must beat table hand" qualifier
- Progressive pot growth

**Representative games:** Three Card Guts (#6), Five Card Guts (#7), Baseball Guts (#321), Four Card Guts (#328), Cowpie Guts (#354)

**Priority: LOW** - Guts is a fundamentally different game structure. Large engine change.

### 2B. NO-PEEK / BEAT IT FORMAT (~30+ games)

**What it is:** Players receive all cards face-down without looking. They flip cards one at a time, trying to beat the current best hand showing (or a table card). If you can't beat it after a flip, you must fold or keep flipping.

**Games blocked:** Beat It (#168), Mexican Sweat (#560), Midnight Baseball (#561), Night of the Living Dead (#563), and 25+ variants.

**Engine changes needed:**
- "No peek" deal state (player can't see their own cards)
- Sequential single-card flip with comparison after each flip
- Variable-length rounds (flip until beat or fold)
- Table qualifier hand to beat

**Priority: LOW** - Very different game flow. Fun but niche.

### 2C. TWIST / PAID CARD REPLACEMENT (~20+ games)

**What it is:** After regular dealing, players may pay (usually max bet) to replace one card. Different from regular draw because it costs money.

**Games blocked:** Option Alley (#139), Six Kick (#250), Three Card Substitution (#154), One/Two Card Substitution (#538/#539), Six Card Option (#529), Seattle Six (#858), etc.

**Engine changes needed:**
- "Twist" action: pay a cost to draw one replacement card
- Cost configuration (ante, double ante, max bet, etc.)
- Optional twist (player may decline)
- Face-up draw replacement: **Slash/Backslash** (TwoPlusTwo) — draw where replacement cards come face-up instead of face-down. Slash is high, Backslash is 2-7 low. **Brentwood** (TwoPlusTwo) — draw N cards, receive N+1 back face-up. These are related but distinct from paid twist: the replacement visibility is the non-standard element

**Priority: MEDIUM** - Relatively small engine change. Unlocks ~20 variants. Could potentially be modeled as a draw step with a cost attribute.

### 2D. CARD BUYING / AUCTION (~10 games)

**What it is:** Cards from the deck are auctioned off. Highest bidder gets the card.

**Games blocked:** Bid'em (#102), Super Bid'em (#472), Abyssinia (#98), Let's Make a Deal (#401), Fire Sale (#449)

**Engine changes needed:**
- Auction round: reveal card, players bid, highest bidder gets it
- Variable bidding mechanics

**Priority: LOW** - Significant new mechanic, few games benefit.

### 2E. FORCE FOLD ON SPECIFIC CARDS (~15 games)

**What it is:** If you're dealt a specific card face-up (e.g., a 7), you must fold immediately.

**Games blocked:** .357 Magnum (#159) - face-up 7 forces fold, Deadly 69s (#325) - face-up wild forces fold, Foosball (#474) - face-up 6 forces extra ante, **Samurai Sevens** (pvdb.org) - face-up 7 = match pot or fold, etc.

**Engine changes needed:**
- Conditional fold trigger on specific dealt cards
- "Kill card" configuration in deal steps
- "Match pot or fold" variant (Samurai Sevens) - forced bet equal to pot, or fold

**Priority: LOW** - Niche home-game mechanic.

### 2F. SPLIT-CARD / SPECIFIC CARD WINS HALF (~10 games)

**What it is:** Half the pot goes to whoever holds a specific card (e.g., highest face-down spade).

**Games blocked:** Chicago (#173) - high face-down spade, Hawaii High/Low (#520) - best down cards, Uncle Bob (#157), Devil's Own (#527), **Georgia Hold'em** (pvdb.org) - worst 2-card starting hand wins half pot, etc.

**Engine changes needed:**
- "Split card" evaluation: identify holder of specific card
- Additional pot split mechanic beyond hi/lo
- Configuration for which card qualifies
- "Worst starting hand" evaluation: Georgia Hold'em evaluates only the 2 hole cards for worst hand, with custom rules (offsuit < suited < pairs for "worst", aces high). Novel split where the "low" side ignores community cards entirely

**Priority: MEDIUM** - We already have `one_card_high_spade` evaluation type. Chicago (#173) is a well-known game. May only need JSON config + minor plumbing.

### 2G. MULTIPLE HANDS PER PLAYER (~10 games)

**What it is:** Each player manages two (or more) separate hands simultaneously.

**Games blocked:** Double Double (#111), Double Handed (#112), Bunk Beds (#485), Henway (#450), Goodfield (#944)

**Engine changes needed:**
- Multiple hand objects per player
- Independent betting per hand (or identical bets)
- Separate evaluation per hand

**Priority: LOW** - Significant architecture change. Niche games.

### 2H. LEG-BASED VICTORY (~8 games)

**What it is:** Players accumulate "legs" (wins). First player to reach N legs wins the accumulated pot.

**Games blocked:** Three Legged Race (#468), Three Legged Low Ball (#828), Roller Coaster (#1005), Three Card Man or Mouse with Legs (#759)

**Engine changes needed:**
- Multi-hand tracking (legs counter)
- Game continues across multiple deals
- Accumulated pot across hands

**Priority: LOW** - Fundamentally different game lifecycle.

### 2I. MODIFIED HAND RANKINGS / SHORT DECK VARIANTS (~12 games)

**What it is:** Non-standard hand rankings (e.g., 4-card flush beats a pair, Flush > Full House in short decks, second-best hand wins).

**Games blocked:**
- **Soko/Canadian Stud** (#148/#134) - 5-card stud, 4-card flush beats pair, 4-card straight beats pair, 4-flush beats 4-straight. Rankings: SF > 4K > FH > F > S > 3K > 2P > 4-Flush > 4-Straight > P > HC. Was offered on NoiQ online poker platform.
- **Canadian** (#107) - 4-card flush beats 4-card straight, which beats pair
- **Sows'em Hold'em** (#297) - Same as Soko but community game
- **Five Stud Place** (#122) - Second-best hand wins
- **Mediocre** (#130/#286) - Middle hand wins
- **Americana** - 32-card deck (7-A), 5-card stud, Flush > Full House. Needs new `short_7a` deck type + 32-card FFH eval type. Very similar to our existing `short_6a` (36-card) support. Was offered on NoiQ.
- **32-Card Draw** - 32-card deck (7-A), 5-card draw, Flush > Full House, suit tiebreaking (H>D>C>S), max discard 4. Was offered on NoiQ alongside Americana. Same deck/eval needs as Americana but draw format.
- **Telesina** - Variable deck by player count, 5-card stud + 1 community ("Vela"), Flush > Full House, suit-based tiebreaking. Was offered on NoiQ. Could partially support with fixed-size configs per player count.

**Engine changes needed:**
- New evaluation types for modified rankings (4-card flush between pair and two pair)
- New `short_7a` deck type (32 cards) — straightforward extension
- Suit-based tiebreaking (hearts > diamonds > clubs > spades) - used by 32-Card Draw, Telesina
- "Nth best hand" showdown logic
- Configurable low qualifier threshold: **Billmaha** (pvdb.org) uses T-high qualifier instead of 8-high for Omaha Hi-Lo. Need config parameter for max qualifying low card rank. Also needed for BARGE's Omaha X or Better (die-roll qualifier)
- Custom "best hand" definitions: **Jack Shit** (pvdb.org) makes J-high (with 4 lesser values, no pairs/straights/flushes) the best hand, better than royal flush. Lowest kickers win (J-5-4-3-2 is nut). Novel evaluation type
- True inversion evaluation: **Vienna, Second Best Hold'em, Deuce-to-Eight** (TwoPlusTwo) — 3+ games where the worst "best high hand" wins. NOT lowball: each player makes their best HIGH hand, then the weakest best-high wins. Distinct from A-5/2-7 low which avoids pairs/straights
- Badugi High evaluation: **Badugi Hi/Lo** (TwoPlusTwo) — reverse badugi ranking where highest rainbow 4-card hand wins. Need `badugi_high` eval type
- Badugi from mixed cards: **Omadugi/Dugaha** (TwoPlusTwo) — badugi evaluation using 2 hole + 2 community cards in an Omaha-style split pot. Currently badugi only evaluates a player's hand cards
- New pip-count targets: **40 or Nothing** (TwoPlusTwo) — pip-count targeting 40. Straightforward extension of existing `49`, `zero`, `21` pip-count eval types
- Variable "must use" constraint: **Scooter** (TwoPlusTwo) — must use ALL remaining hole cards after optional discards. Dynamic constraint based on cards held

**Note:** Soko, 32-Card Draw, Americana, and Telesina were all offered on the NoiQ online poker platform (now merged with 24hPoker/Microgaming), demonstrating real commercial demand for these variants.

**Priority: MEDIUM for Americana/32-Card Draw** (straightforward short-deck extension, unlocks 2 games at once), **MEDIUM for Soko** (popular variant), **MEDIUM for Billmaha** (simple qualifier change unlocks a popular Omaha variant), **LOW for Place/Mediocre**, **LOW for Jack Shit** (novel eval, low demand), **LOW for Telesina full support** (suit tiebreaking is niche, but fixed-player-count configs possible sooner), **LOW for True Inversion** (interesting concept, 3+ games), **LOW for Badugi High** (niche), **MEDIUM for pip-count 40** (trivial extension).

### 2J. REANTE / PROGRESSIVE ANTES (~5 games)

**What it is:** Players must re-ante or fold before each new community card.

**Games blocked:** Progressive Hold'em (#292), Five Card Blind II (#115)

**Engine changes needed:**
- "Reante or fold" action between deal steps
- Cost to continue playing

**Priority: LOW** - Could potentially be modeled as a bet step with forced-ante semantics.

### 2K. PINOCHLE / DOUBLE DECK (~2 games)

**What it is:** Uses a pinochle deck (48 cards: 9-A from two standard decks) or two full decks shuffled together.

**Games blocked:** Pinochle Hold'em (#966), Night Baseball (#876), **Phold'em** (pvdb.org) - Pinochle deck Hold'em with 3 community cards and custom hand rankings (five of a kind valid; completely different probability distribution)

**Engine changes needed:**
- Pinochle deck type (duplicate ranks)
- Handle duplicate cards in evaluation
- Phold'em needs entirely new hand ranking tables for the 48-card deck: SF > 5oaK > Flush > 4oaK > FH > Straight > High Card > 3oaK > 2P > Pair (note: high card is ranked ABOVE three of a kind due to probability in this deck)

**Priority: LOW** - Very niche.

### 2L. CARD REJECTION (~5 games)

**What it is:** Player may reject a dealt card and receive another (possibly face-up as penalty).

**Games blocked:** Do Ya (#110), Do Ya Too (#484), No Low (#136), Cathy's Game (#516), **Do Ya** (pvdb.org) - card draft with accept/reject from deck, **Howdy Do Ya** (pvdb.org) - Do Ya + direction-based wilds

**Engine changes needed:**
- "Reject" option during dealing
- Replacement card with different state (face-up penalty)
- Limited rejection count
- Card "draft/offer" mechanic (Do Ya): dealer turns over cards one at a time for each player. Player accepts or rejects up to 2 cards, forced to take 3rd. Rejected cards remain available for next player to pick from. This is more complex than simple card rejection — it's a sequential card draft where multiple face-up cards can accumulate

**Priority: LOW** - Niche mechanic.

### 2M. OPPONENT CARD BORROWING - Swingo (~3 games)

**What it is:** Players can use one exposed card from another player's hand as part of their own hand.

**Swingo rules (Steve Albini, 2007):**
1. Deal 5 cards face-down to each player
2. Betting round
3. Each player SEPARATES hand into 2 hole cards + 3 board cards
4. 3 board cards EXPOSED face-up
5. Betting round (highest board leads)
6. Deal 1 community "river" card
7. Final betting round
8. Showdown: best 5-card hand from 7 cards: 2 hole + 3 own board + river + **any 1 exposed card from another player's board**

**Special rule:** A player who has called the latest bet/raise cannot fold (to protect other players' access to their board cards).

**Variants:**
- **Sweet Chariot** - Lowball version (lowest hand wins)
- **High-Low Swingo** - Hi/Lo with declaration, limit betting

**Engine changes needed:**
- "Borrow opponent card" mechanic: at showdown, each player selects 1 card from any other player's exposed cards
- Modified hand evaluation that considers opponent board cards as additional options
- Fold restriction rule (optional but part of official rules)

**Supportability:** The separate + expose steps are supported. The deal+bet structure is supported. The MISSING piece is the showdown hand construction that allows using an opponent's exposed card. This is a unique mechanic not shared with any other variant family.

**Priority: MEDIUM** - Swingo is a well-known home game (invented by a WSOP bracelet winner). The separate+expose flow works already, only the showdown evaluation needs extension.

### 2N. SVITEN SPECIAL ONE-CARD-OPEN DRAW (~1 game)

**What it is:** Sviten Special (the Swedish variant of Drawmaha) has a unique draw mechanic where a one-card draw is offered face-up, and the player can accept or reject it (taking the next card face-down instead).

**NOTE:** Standard Drawmaha/Dramaha is **ALREADY SUPPORTED** via JSON. We have 9 Dramaha configs (`dramaha.json`, `dramaha_27.json`, `dramaha_49.json`, etc.) that use dual `bestHand` arrays. The engine's `showdown_manager.py` already processes multiple bestHand configs and splits the pot. Route 66 (6-card Dramaha) is also JSON-supportable.

**What's NOT supported:** Only the Sviten Special one-card-open-draw variant:
- If player discards exactly 1 card, dealer reveals replacement face-up
- Player can accept the face-up card, or reject it and take the next card face-down
- This "accept or reject revealed card" mechanic doesn't exist in the engine

**Engine changes needed:**
- "Revealed draw with accept/reject" mechanic in draw step
- Two-step draw resolution: reveal → accept/reject → resolve

**Priority: LOW** - Standard Dramaha works fine without this. Sviten Special's one-card-open is a minor flavor variant.

### 2O. PER-GROUP COMMUNITY CARD SELECTION - King Tut (~5 games)

**What it is:** Community cards are arranged in groups (rows of a pyramid), and the hand construction rule requires using exactly 1 card from each group, rather than a flat "use N community cards."

**King Tut rules:**
1. Deal 4 hole cards face-down to each player
2. Deal 6 community cards face-down in pyramid (3 bottom, 2 middle, 1 top)
3. Reveal bottom 3 cards, betting round
4. Reveal middle 2 cards, betting round
5. Reveal top 1 card, betting round
6. Showdown: best 5 using exactly 2 hole + 1 from each pyramid level (1 bottom + 1 middle + 1 top)

**Wild cards:** Top pyramid card and all cards of that rank are wild (similar to `last_community_card` type).

**Variants:**
- **King Tut's Tomb** - Same structure, dynamic wild card reveal timing
- **King Tut's Revenge** - Similar structure with minor wild card variation

**Engine changes needed:**
- Per-group community card constraints in bestHand config (e.g., "1 from group A, 1 from group B, 1 from group C")
- Currently bestHand only supports `communityCards: N` (total count), not per-group selection
- The pyramid layout itself (multi-row reveal) already works

**What already works:** Multi-row community layout, row-by-row reveal, last_community_card wild type with rank matching.

**Priority: LOW** - Niche home-game mechanic. The pyramid deal and wild card work already; only the per-group selection constraint is missing.

### 2P. DYNAMIC WILD CARDS - Follow the Queen (~10+ games)

**What it is:** Wild card designation changes during the deal based on which cards appear. When a trigger card (e.g., a Queen) is dealt face-up, the next face-up card's rank becomes wild. If another trigger card appears later, the wild designation shifts.

**Follow the Queen rules (very popular home game):**
- Standard 7-card stud structure (2 down, 4 up, 1 down)
- Queens are always wild
- When any queen is dealt face-up, the NEXT card dealt face-up determines the additional wild rank
- If another queen appears face-up later, the wild shifts to whatever follows THAT queen
- If a queen is the last face-up card dealt, only queens are wild (nothing follows)
- If no queens appear face-up, the hand is void — everyone re-antes and redeals

**Variants using similar mechanic:**
- **Follow the Bitch** (same game, different name)
- **Black Mariah** - If Queen of Spades is dealt face-up, hand immediately ends and redeals
- **Follow the King** / **Follow the Jack** - Same mechanic with different trigger card
- Various ichabod801 games with "card X triggers wild" mechanics

**Engine changes needed:**
- "Follow" wild card type: trigger rank (queen) + "next face-up card determines wild rank"
- Dynamic wild card state that updates during dealing
- Wild shift when new trigger appears
- Re-deal trigger (if no trigger card appears)
- Card state tracking during multi-round stud deals
- Per-direction wild cards: **Joemaha** (pvdb.org) uses 3s wild for high only and Kings wild for low only in an Omaha Hi-Lo split pot. Also "single wild" limit — only 1 card of the wild rank can be used as wild per hand. **Howdy Do Ya** (pvdb.org) uses same direction-based wilds in a Do Ya format

**Priority: MEDIUM** - Follow the Queen is one of the most popular dealer's choice games alongside Baseball. Frequently requested. Would unlock a family of ~10+ "follow" variants.

### 2Q. CONDITIONAL DEALING (Extra Cards) (~5 games)

**What it is:** If a specific card appears, deal extra cards (e.g., Baseball: face-up 4 = buy extra card).

**Games blocked:** Baseball (#167) - face-up 4 buys extra card, Little League (#549), Wild Kingdom (#709)

**Engine changes needed:**
- Conditional deal trigger on specific card appearance
- "Buy extra card" option with payment
- Variable hand sizes

**Priority: LOW** - Complex conditional logic for few games.

### 2R. INDIAN POKER / ASYMMETRIC VISIBILITY (~3+ games)

**What it is:** Cards are visible to opponents but hidden from the card's owner. In "forehead" variants, cards are placed on the player's forehead — everyone else can see them, but the player cannot.

**Games blocked:** **Forehead Omaha** (TwoPlusTwo) - 2 of 4 hole cards on forehead (visible to opponents, hidden from player), must use 1 forehead + 1 hole card. **Vero Beach** (TwoPlusTwo) - 7-card stud where 7th card is on forehead until final street. **Prognostication** (TwoPlusTwo) - stud where river cards are visible to the player on your left.

**Engine changes needed:**
- New card visibility mode: "visible to opponents, hidden from owner" (currently only face-up = all see, face-down = only owner sees)
- Modified state serialization to show/hide cards based on this asymmetric visibility
- Potentially "delayed integration" where forehead cards are revealed to the owner at a specific game step

**Priority: LOW** - Fun home-game mechanic but niche. Requires changes to the fundamental card visibility model.

---

## SECTION 2 SUMMARY: Engine Feature Priority

| Feature | Games Unlocked | Effort | Priority |
|---------|---------------|--------|----------|
| Dynamic wild cards (Follow the Queen) | ~10+ | Medium | **MEDIUM** |
| Twist (paid draw) | ~20 | Small-Medium | **MEDIUM** |
| Split-card (Chicago) | ~10 | Small | **MEDIUM** |
| Soko rankings (4-card flush) | ~5 | Medium | **MEDIUM** |
| 32-card deck + eval (Americana/32-Card Draw) | ~3 | Small | **MEDIUM** |
| Opponent card borrowing (Swingo) | ~3 | Medium | **MEDIUM** |
| Guts format | ~100+ | Large | LOW |
| No-peek / Beat It | ~30+ | Large | LOW |
| Card buying / auction | ~10 | Large | LOW |
| Force fold on card | ~15 | Medium | LOW |
| Multiple hands per player | ~10 | Large | LOW |
| Leg-based victory | ~8 | Large | LOW |
| Reante / progressive | ~5 | Small | LOW |
| Configurable low qualifier (Billmaha) | ~3 | Small | MEDIUM |
| Card rejection / card draft | ~7 | Medium | LOW |
| Conditional dealing | ~5 | Medium | LOW |
| Suit-based tiebreaking (Telesina) | ~2 | Medium | LOW |
| Variable deck by player count | ~2 | Medium | LOW |
| Per-direction wilds (Joemaha) | ~3 | Medium | LOW |
| Pinochle / double deck | ~3 | Medium | LOW |
| Sviten Special open-draw | ~1 | Small | LOW |
| Per-group community selection (King Tut) | ~3 | Medium | LOW |
| True inversion eval (Vienna, Second Best) | ~3 | Medium | LOW |
| Badugi High eval | ~2 | Small | LOW |
| Badugi from mixed hole+community (Omadugi) | ~2 | Medium | LOW |
| Pip-count 40 (40 or Nothing) | ~1 | Small | MEDIUM |
| Indian poker / asymmetric visibility | ~3 | Medium | LOW |
| Face-up draw replacements (Slash) | ~3 | Small | LOW |
| Hit-or-stand dealing (Blackjack Poker) | ~2 | Medium | LOW |
| Variable "must use" constraint (Scooter) | ~2 | Small | LOW |

---

## SECTION 3: Implementation Recommendations

### Phase 1: JSON-Only Games (No Engine Changes)

Implement the highest-priority games from Section 1. These are all just new JSON config files.

**Batch 1 - Circus/Mixed Game Staples:**
1. Scrotum 8 - deal 5, discard 1-3, then Omaha 8 community cards
2. Route 66 - 6-card Dramaha (6 hole + draw + flop/turn/river, split pot)
3. Poppyha - 4 hole, 2+1+1 community, Omaha rules
4. Cincinnati - 5 hole + 5 community, use any combo
5. Sassy - 4 cards, discard+expose, stud, optional draw, hi/lo
6. Oklahoma - 4 hole, discard 1 after flop + 1 after turn, Omaha showdown

**Batch 2 - Well-Known Classics:**
6. Anaconda (#10) - pass 3-2-1, discard 2, flip 4, hi/lo declare
7. Manila (#285) - 2 hole, 5 community singles, short deck, use 2
8. Three Card Hold'em (#305) - 1 hole, 2 community
9. Kansas Hold'em (#283) - 3 hole, 2+1+1 community
10. Ben Franklin (#169) - 7-card stud, 5s and 10s wild

**Batch 3 - Interesting Variants:**
11. Mexican Stud (#132) - 2 down, player-choice flip each round
12. Nebraska II (#701) - 4 hole, use 3 (inverse Omaha)
13. Dublin Hold'em (#931) - 4 hole, no use constraint
14. Grodnikonda (#493) - 7 down, discard 2, flip 4, hi/lo declare
15. Roll Your Own (#633) - 7-card stud, player-flip, low hole wild

**Batch 4 - Community Card Varieties:**
16. Stud Hold'em (Patent) - 3 hole (2D+1U), use 2, blinds or bring-in
17. 2-11 Poker - 4 hole, 2+1+1 community, use 2-or-3
18. Flatline Hold'em - 2 hole, 9 community cross, dual-board split
19. Party Girl Hold'em (#291) - 2+2+1 community
20. Reverse Hold'em - 2 hole, 1+1+3 community (reverse dealing order)
21. 9-Card Omaha - 9 hole, 3+1+1 community, use exactly 2+3 (max 4 players)

**Batch 5 - More Variants:**
22. Triple Flop Hold'em (#307) - 2+2+2 community
23. Hold Me (#280) - 5 single community cards
24. Austin Hold'em (#269) - lowest community wild
25. Cross Over (#731) - Omaha + cross layout
26. Yogi Hold'em (#721) - must use 3+2

### Phase 2: Engine Changes (Medium Priority)

After JSON-only games are done, consider:
1. **Follow the Queen dynamic wilds** - One of the most popular dealer's choice games. ~10+ variants
2. **32-card deck (Americana)** - Small extension, adds a classic Italian stud game
3. **Twist support** - Would unlock ~20 more variants
4. **Chicago split-card** - Well-known game, may mostly work already
5. **Soko evaluation type** - Adds 4-card flush ranking for a few variants
6. **Swingo opponent card borrowing** - Well-known home game by WSOP bracelet winner

### Not Recommended (for now)
- Guts, No-Peek, Auctions, Legs - fundamentally different game structures
- Would require significant engine architecture changes
- Very few people play these online (mostly home games)
