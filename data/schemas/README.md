# Poker Game Configuration Schema

This document describes the JSON schema for configuring poker games. The schema defines the structure and properties required to specify various poker game variants.

## Root Object

| Field | Name | Type | Definition | Required |
| ----- | ---- | ---- | ---------- | -------- |
| **game** | Game Name | String | The name of the poker game | Yes |
| **references** | References | Array of Strings | URLs pointing to descriptions or rules of the game | No |
| **players** | Players | Object | Defines the minimum and maximum number of players | Yes |
| **deck** | Deck | Object | Specifies the type and number of cards in the deck. | Yes |
| **bettingStructures** | Betting Structures | Array of Strings | List of allowed betting structures | Yes |
| **forcedBets** | Forced Bets | Object | Defines the forced betting rules | No |
| **bettingOrder** | Betting Order | Object | Controls who bets first in different betting rounds | No |
| **gamePlay** | Game Play | Array of Objects | Describes the sequence of actions in the game | Yes |
| **showdown** | Showdown | Object | Defines the showdown rules and hand evaluation | Yes |

### Players Object

| Field | Name | Type | Definition | Required |
| ----- | ---- | ---- | ---------- | -------- |
| **min** | Minimum Players | Integer | Minimum number of players | Yes |
| **max** | Maximum Players | Integer | Maximum number of players | Yes |

### Deck Object

| Field | Name | Type | Definition | Required |
| ----- | ---- | ---- | ---------- | -------- |
| **type** | Deck Type | String | Type of deck. | Yes |
| **cards** | Number of Cards | Integer | Number of cards in the deck. Allowed values: 20, 36, 40, 52 | Yes |
| **jokers** | Number of Jokers | Integer | Number of joker cards to include | No |

### Deck Types

The following deck types are supported:

- **standard**: A standard 52-card deck containing all cards from 2 through Ace in four suits.
- **short_6a**: A 36-card deck with cards 2 through 5 removed, containing cards from 6 through Ace in four suits.
- **short_ta**: A 20-card deck containing only 10, Jack, Queen, King, and Ace in four suits.
- **short_27_ja**: A 40-card deck with cards 8 through 10 removed, containing cards from 2-7 and Jack through Ace in four suits.

The `cards` field in the deck object should match the number of cards in the chosen deck type.

### Betting Order Object

| Field | Name | Type | Definition | Required |
| ----- | ---- | ---- | ---------- | -------- |
| **initial** | Initial Order | String | Determines the starting player for the first betting round | Yes |
| **subsequent** | Subsequent Order | String or Object | Determines the starting player for subsequent betting rounds | Yes |

**initial** options:

- `after_big_blind`: The player left of the big blind starts (common in community card games)
- `bring_in`: The bring-in player starts (common in stud games)
- `dealer`: The player left of the dealer button starts

**subsequent** options:

- `high_hand`: The player with the highest visible hand starts (common in stud games)
- `dealer`: The player left of the dealer button starts (common in community card games)
- `last_actor`: The last player to act starts

The `subsequent` field can also be an object with conditional orders based on player choices:

```json
"subsequent": {
  "conditionalOrders": [
    {
      "condition": {
        "type": "player_choice",
        "subset": "Game",
        "values": ["Hold'em", "Omaha 8"]
      },
      "order": "dealer"
    }
  ],
  "default": "high_hand"
}
```

### Forced Bets Object

The `forcedBets` field can be either a simple object or a conditional object for games where forced bets depend on player choices.

#### Simple Forced Bets

| Field | Name | Type | Definition | Required |
| ----- | ---- | ---- | ---------- | -------- |
| **style** | Bet Style | String | Style of forced bets (e.g., "bring-in", "blinds", "antes_only") | Yes |
| **rule** | Bet Rule | String | Rule for hand evaluation for bring-in bets | No |
| **bringInEval** | Bring-in Evaluation | String | Evaluation type to use for bring-in with multiple cards | No |

#### Conditional Forced Bets

For games where forced bets change based on player choices:

```json
"forcedBets": {
  "conditionalOrders": [
    {
      "condition": {
        "type": "player_choice",
        "subset": "Game",
        "value": "Razz"
      },
      "forcedBet": {
        "style": "bring-in",
        "rule": "high card"
      }
    }
  ],
  "default": {
    "style": "blinds"
  }
}
```

### Game Play Array

The Game Play array contains objects that describe each step of the game. Each object can have the following properties:

| Field | Name | Type | Definition | Required |
| ----- | ---- | ---- | ---------- | -------- |
| **name** | Step Name | String | Name of the gameplay step | Yes |
| **conditional_state** | Conditional State | Object | Determines if this step should be executed | No |
| **bet** | Bet | Object | A betting action | No |
| **deal** | Deal | Object | Describes a dealing action | No |
| **draw** | Draw | Object | Describes a drawing action | No |
| **expose** | Expose | Object | Describes an exposing action | No |
| **pass** | Pass | Object | Describes an passing action | No |
| **separate** | Separate | Object | Describes a separating action | No |
| **discard** | Discard | Object | Describes a discarding action | No |
| **remove** | Remove | Object | Describes a removing action | No |
| **roll_die** | Roll Die | Object | Describes a die rolling action | No |
| **declare** | Declare | Object | Describes a declaration action | No |
| **choose** | Choose | Object | Describes a player choice action | No |
| **showdown** | Showdown | Object | Indicates a showdown step | No |
| **groupedActions** | Grouped Actions | Array | Sequence of actions performed by each player in turn | No |

### Grouped Actions Array

The `groupedActions` array allows multiple actions to be executed by each player in sequence before moving to the next player.

Example:

```json
"groupedActions": [
  { "bet": { "type": "small" } },
  { "discard": { "cards": [{ "min_number": 0, "number": 4, "state": "face down" }] } }
],
"name": "Bet and Discard"
```

#### Bet Object 

| Field | Name | Type | Definition | Required |
| ----- | ---- | ---- | ---------- | -------- |
| **type** | Bet Type | String | Type of bet (e.g., "small", "big", "blinds", "antes", "bring-in") | Yes |
| **zeroCardsBetting** | Zero Cards Betting | String | Betting restriction for players with 0 cards | No |

The `zeroCardsBetting` property can have the following values:

- `call_only`: Player can only call, not raise (used in games like Scarney)
- `normal`: Normal betting rules apply

#### Deal Object

| Field | Name | Type | Definition | Required |
| ----- | ---- | ---- | ---------- | -------- |
| **location** | Deal Location | String | Location of the deal (player or community) | Yes |
| **conditional_state** | Conditional State | Object | Determines card state based on a condition | No |
| **wildCards** | Wild Cards | Array | Wild card rules for this deal | No |
| **cards** | Cards | Array of Objects | Describes the cards being dealt | Yes |

##### Conditional State Object

Allows cards to be dealt with different visibility based on conditions:

| Field | Name | Type | Definition | Required |
| ----- | ---- | ---- | ---------- | -------- |
| **type** | Condition Type | String | Type of condition to check | Yes |
| **true_state** | True State | String | Card state if condition is true | Yes |
| **false_state** | False State | String | Card state if condition is false | Yes |
| **subset** | Subset | String | Community card subset to check or choice variable name | No |
| **check** | Check | String | Type of card property to check ("color", "suit", "rank") | No |
| **color** | Color | String | Card color to check for ("red" or "black") | No |
| **min_count** | Min Count | Integer | Minimum number of matching cards required | No |
| **value** | Value | String | Single value to match for player_choice condition | No |
| **values** | Values | Array | Array of values to match for player_choice condition | No |

The `type` can be:

- `all_exposed`: True if all player's cards are face up
- `any_exposed`: True if any of player's cards are face up
- `none_exposed`: True if none of player's cards are face up
- `board_composition`: True if community cards match certain criteria
- `player_choice`: True if player choice matches specified value(s)

Each object in the cards array has the following properties:

| Field | Name | Type | Definition | Required |
| ----- | ---- | ---- | ---------- | -------- |
| **number** | Number of Cards | Integer | Number of cards to deal | Yes |
| **state** | Card State | String | State of the cards (face up or face down) | No |
| **subset** | Card Subset | String or Array of Strings | Subset(s) of cards if applicable | No |

#### Choose Object

| Field | Name | Type | Definition | Required |
| ----- | ---- | ---- | ---------- | -------- |
| **possible_values** | Possible Values | Array of Strings | List of possible values that can be chosen | Yes |
| **value** | Value | String | Name of variable to store the chosen value | Yes |
| **default** | Default | String | Default value if no choice is made | No |
| **chooser** | Chooser | String | Position that gets to make the choice (utg, button, dealer, sb, bb) | No |
| **time_limit** | Time Limit | Integer | Time limit in seconds for making the choice | No |

#### Dynamic Wild Cards

Some wild card rules are determined by cards actually dealt during the game:

- **last_community_card**: The last community card dealt determines wildness
  - `match: "rank"`: All cards of the same rank as the last community card become wild
  - `match: "card"`: Only the specific last community card dealt is wild
  - `match: "suit"`: All cards of the same suit as the last community card become wild

Example for Tic Tac Hold'em:
```json
"wildCards": [
  {
    "type": "last_community_card",
    "role": "wild",
    "scope": "global", 
    "match": "rank"
  }
]

#### Roll Die Object

| Field | Name | Type | Definition | Required |
| ----- | ---- | ---- | ---------- | -------- |
| **subset** | Die Result Subset | String | Community subset to store die result | Yes |

Example: 

```json
"roll_die": {
  "subset": "Die"
},
"name": "Roll Die"
```

#### Draw Object

| Field | Name | Type | Definition | Required |
| ----- | ---- | ---- | ---------- | -------- |
| **cards** | Cards | Array of Objects | Describes the cards to draw | Yes |

Each object in the cards array has the following properties:

| Field | Name | Type | Definition | Required |
| ----- | ---- | ---- | ---------- | -------- |
| **number** | Number of Cards | Integer | Number of cards to draw | Yes |
| **min_number** | Minimum Number | Integer | Minimum number of cards that must be drawn | No |
| **state** | Card State | String | State of the cards (face up or face down) | Yes |
| **hole_subset** | Hole Subset | String | Subset of player's hand to draw to | No |
| **draw_amount** | Draw Amount | Object | Specifies draw amount relative to discard | No |

##### Draw Amount Object

| Field | Name | Type | Definition | Required |
| ----- | ---- | ---- | ---------- | -------- |
| **relative_to** | Relative To | String | Reference for relative draw amount (only "discard" supported) | Yes |
| **amount** | Amount | Integer | Difference between draw and discard amounts | Yes |

Example that draws one less card than discarded:

```json
"draw_amount": {
  "relative_to": "discard",
  "amount": -1
}
```

#### Discard Object

| Field | Name | Type | Definition | Required |
| ----- | ---- | ---- | ---------- | -------- |
| **cards** | Cards | Array of Objects | Describes the cards to discard | Yes |

Each object in the cards array has the following properties:

| Field | Name | Type | Definition | Required |
| ----- | ---- | ---- | ---------- | -------- |
| **rule** | Discard Rule | String | Rule for discarding cards | No |
| **hole_subset** | Subset of Cards | String | Subset of cards for discarding | No |
| **number** | Number of Cards | Integer | Number of cards to discard | No |
| **min_number** | Minimum Number | Integer | Minimum number of cards to discard | No |
| **state** | Card State | String | State of the discarded cards | No |
| **discardLocation** | Discard Location | String | Where discarded cards go ("community" or "discard_pile") | No |
| **discardSubset** | Discard Subset | String | Subset name in the discard location | No |
| **entire_subset** | Entire Subset | Boolean | If true, discard must be an entire named subset | No |
| **oncePerStep** | Once Per Step | Boolean | If true, discard happens only once per grouped step | No |

#### Expose Object

| Field | Name | Type | Definition | Required |
| ----- | ---- | ---- | ---------- | -------- |
| **cards** | Cards | Array of Objects | Describes the cards to expose | Yes |

Each object in the cards array has the following properties:

| Field | Name | Type | Definition | Required |
| ----- | ---- | ---- | ---------- | -------- |
| **number** | Number of Cards | Integer | Number of cards to expose | Yes |
| **min_number** | Minimum Number | Integer | Minimum number of cards to expose | No |
| **state** | Card State | String | State of the cards (face up or face down) | Yes |
| **immediate** | Immediate | Boolean | If true, expose immediately rather than at round end | No |

#### Pass Object

| Field | Name | Type | Definition | Required |
| ----- | ---- | ---- | ---------- | -------- |
| **cards** | Cards | Array of Objects | Describes the cards to pass | Yes |

Each object in the cards array has the following properties:

| Field | Name | Type | Definition | Required |
| ----- | ---- | ---- | ---------- | -------- |
| **number** | Number of Cards | Integer | Number of cards to pass | Yes |
| **direction** | Pass Direction | String | Direction to pass the cards (left, right, or across) | Yes |
| **state** | Card State | String | State of the cards being passed | Yes |

#### Separate Object

| Field | Name | Type | Definition | Required |
| ----- | ---- | ---- | ---------- | -------- |
| **cards** | Cards | Array of Objects | Describes the cards to separate | Yes |
| **visibility_requirements** | Visibility Requirements | Array of Objects | Requirements for face-up/face-down cards | No |
| **hand_comparison** | Hand Comparison | Object | Rules for comparing separated hands | No |

Each object in the cards array has the following properties:

| Field | Name | Type | Definition | Required |
| ----- | ---- | ---- | ---------- | -------- |
| **hole_subset** | Subset Name | String | Name of the subset | Yes |
| **number** | Number of Cards | Integer | Number of cards in the subset | Yes |

Visibility Requirements Object

| Field | Name | Type | Definition | Required |
| ----- | ---- | ---- | ---------- | -------- |
| **hole_subset** | Subset Name | String | Name of the subset | Yes |
| **min_face_down** | Min Face Down | Integer | Minimum number of face-down cards required | No |
| **min_face_up** | Min Face Up | Integer | Minimum number of face-up cards required | No |

Hand Comparison Object

| Field | Name | Type | Definition | Required |
| ----- | ---- | ---- | ---------- | -------- |
| **subsets** | Subsets | Array of Objects | Subsets to compare | Yes |
| **comparison_rule** | Comparison Rule | String | Rule for comparison ("greater_than", "less_than", "equal") | Yes |

#### Declare Object

| Field | Name | Type | Definition | Required |
| ----- | ---- | ---- | ---------- | -------- |
| **type** | Type | String | Always "declare" | Yes |
| **options** | Options | Array of Strings | Possible declarations (e.g., ["high", "low", "high_low"]) | Yes |
| **per_pot** | Per Pot | Boolean | If true, declare for each pot separately | No |
| **simultaneous** | Simultaneous | Boolean | If true, all players declare at the same time | No |

#### Remove Object

| Field | Name | Type | Definition | Required |
| ----- | ---- | ---- | ---------- | -------- |
| **type** | Type | String | Type of removal (e.g., "subset") | Yes |
| **criteria** | Criteria | String | Criteria for determining which subsets to remove | Yes |
| **subsets** | Subsets | Array of Strings | List of community card subsets to evaluate for removal | Yes |

#### Showdown Object

| Field | Name | Type | Definition | Required |
| ----- | ---- | ---- | ---------- | -------- |
| **type** | Showdown Type | String | Type of showdown | Yes |

The following is the Showdown object for the game definition:

### Showdown Object

| Field | Name | Type | Definition | Required |
| ----- | ---- | ---- | ---------- | -------- |
| **order** | Showdown Order | String | Order of showdown (currently unused) | Yes |
| **startingFrom** | Starting Player | String | Player starting the showdown (currently unused) | Yes |
| **cardsRequired** | Cards Required | String | Description of cards required for showdown | Yes |
| **bestHand** | Best Hand | Array of Objects | Defines the hand evaluation rules | Yes* |
| **conditionalBestHands** | Conditional Best Hands | Array of Objects | Defines conditional hand evaluation rules | No* |
| **defaultBestHand** | Default Best Hand | Array of Objects | Default hand evaluation when no conditions match | No |
| **classification_priority** | Classification Priority | Array of Strings | Order of precedence for classified hands | No |
| **declaration_mode** | Declaration Mode | String | Mode for determining winners ("cards_speak" or "declare") | No |
| **defaultActions** | Default Actions | Array of Objects | Per-configuration default actions | No |
| **globalDefaultAction** | Global Default Action | Object | Default action when no hand configurations have winners | No |

*Either bestHand or conditionalBestHands must be provided.

#### Conditional Best Hands Object

| Field | Name | Type | Definition | Required |
| ----- | ---- | ---- | ---------- | -------- |
| **condition** | Condition | Object | Condition to check | Yes |
| **bestHand** | Best Hand | Array of Objects | Hand evaluation to use when condition is true | Yes |

##### Condition Object

| Field | Name | Type | Definition | Required |
| ----- | ---- | ---- | ---------- | -------- |
| **type** | Type | String | Type of condition | Yes |
| **subset** | Subset | String | Community card subset to check or choice variable name | No |
| **values** | Values | Array | Card values that match condition | No |
| **hand_sizes** | Hand Sizes | Array of Integers | Player hand sizes that match this condition | No |
| **min_hand_size** | Min Hand Size | Integer | Minimum hand size for condition to be true | No |
| **max_hand_size** | Max Hand Size | Integer | Maximum hand size for condition to be true | No |

**Condition Types:**

- `community_card_value`: Checks if community cards have specific values
- `community_card_suit`: Checks if community cards have specific suits  
- `board_composition`: Checks board composition (colors, suits, etc.)
- `player_choice`: Checks if player choice matches specified value(s)
- `player_hand_size`: Checks if player's hand size matches criteria

#### Best Hand Object

| Field | Name | Type | Definition | Required |
| ----- | ---- | ---- | ---------- | -------- |
| **name** | Hand Name | String | Name of the hand type | No |
| **evaluationType** | Evaluation Type | String | Type of hand evaluation | Yes |
| **holeCards** | Hole Cards | Integer, Array, or String | Number of hole cards required, list of indices, "remaining", or "all" | No |
| **communityCards** | Community Cards | Integer or Array | Number of community cards required or list of indices | No |
| **anyCards** | Any Cards | Integer | Number of any cards required | No |
| **hole_subset** | Hole Subset | String | Subset of hole cards to use | No |
| **community_subset** | Community Subset | String or Array of Strings | Subset(s) of community cards to use | No |
| **cardState** | Card State | String | State of cards to consider ("face up" or "face down") | No |
| **holeCardsAllowed** | Allowed Hole Cards | Array of Objects | Allowed combinations of hole card subsets | No |
| **communityCardCombinations** | Community Card Combinations | Array of Arrays | Allowed combinations of community card subsets | No |
| **communityCardSelectCombinations** | Community Card Select Combinations | Array | Specific card selection rules from subsets | No |
| **communitySubsetRequirements** | Community Subset Requirements | Array of Objects | Required cards from specific community subsets | No |
| **wildCards** | Wild Cards | Array of Objects | List of wild card rules for the hand evaluation | No |
| **qualifier** | Qualifier | Array of Integers | Qualifier for the hand | No |
| **padding** | Padding | Boolean | If true, pads out hole cards to the specified length | No |
| **minimumCards** | Minimum Cards | Integer | The minimum number of cards required for the hand to qualify | No |
| **zeroCardsPipValue** | Zero Cards Pip Value | Integer | Value when no cards are held for pip-based games | No |
| **combinations** | Combinations | Array of Objects | Specific allowed hole/community combinations | No |
| **usesUnusedFrom** | Uses Unused From | String | Name of hand configuration from which to use unused cards | No |
| **classification** | Classification | Object | Hand classification rules | No |

##### Classification Object

Used to classify hands (e.g., face/butt in Action Razz):

| Field | Name | Type | Definition | Required |
| ----- | ---- | ---- | ---------- | -------- |
| **type** | Classification Type | String | Type of classification (e.g., "face_butt") | Yes |
| **faceRanks** | Face Ranks | Array of Strings | Ranks that qualify as "face" | Yes |
| **fieldName** | Field Name | String | Field name to store classification result | Yes |

##### Hole Cards Allowed Object

| Field | Name | Type | Definition | Required |
| ----- | ---- | ---- | ---------- | -------- |
| **hole_subsets** | Allowed Subsets | Array of Strings | List of allowed subsets for this combination | Yes |

##### Community Subset Requirements Object

| Field | Name | Type | Definition | Required |
| ----- | ---- | ---- | ---------- | -------- |
| **subset** | Subset | String | Name of the community subset | Yes |
| **count** | Count | Integer | Number of cards required from this subset | Yes |
| **required** | Required | Boolean | Whether this subset is required (default: true) | No |

##### Wild Cards Object

Each object in the `wildCards` array includes:

| Field | Name | Type | Definition | Required |
| ----- | ---- | ---- | ---------- | -------- |
| **type** | Wild Type | String | One of "joker", "rank", "lowest_community", "lowest_hole" | Yes |
| **count** | Count | Integer | Number of wild cards (e.g., for Jokers) | No |
| **rank** | Rank | String | Required for "rank" type | No |
| **subset** | Subset | String | For "lowest_*" types | No |
| **visibility** | Visibility | String | For "lowest_hole" (e.g., "face down") | No |
| **match** | Match | String | Match condition (e.g., "rank") | No |
| **scope** | Scope | String | "player" or "global" (default) | No |
| **role** | Role | String | "wild", "bug", or "conditional" | Yes |
| **condition** | Condition | Object | For "conditional" role | No |

##### Community Card Select Combinations

Example for selecting specific numbers of cards from multiple community subsets:

```json
"communityCardSelectCombinations": [
  [
    ["Flop 1.1", 1, 1],
    ["Flop 2.2", 1, 1],
    ["Flop 3.3", 1, 1]
  ]
]
```

Each inner array contains: [subset_name, min_count, max_count]

#### Default Action Object

| Field | Name | Type | Definition | Required |
| ----- | ---- | ---- | ---------- | -------- |
| **condition** | Condition | String | Condition for applying the default action | Yes |
| **appliesTo** | Applies To | Array of Strings | Hand evaluation names this applies to | No |
| **action** | Action | Object | Action to take when the condition is met | Yes |

#### Action Object

| Field | Name | Type | Definition | Required |
| ----- | ---- | ---- | ---------- | -------- |
| **type** | Type | String | Type of action ("split_pot", "best_hand", "evaluate_special") | Yes |
| **bestHand** | Best Hand | Array of Objects | Hand evaluation rules for "best_hand" action | No |
| **evaluation** | Evaluation | Object | Evaluation rules for "evaluate_special" action | No |

##### Evaluation Object

| Field | Name | Type | Definition | Required |
| ----- | ---- | ---- | ---------- | -------- |
| **criterion** | Criterion | String | Criterion for evaluating cards (e.g., "highest_rank", "lowest_rank") | Yes |
| **suit** | Suit | String | Suit to evaluate or "river_card_suit" for dynamic suit | No |
| **from** | From | String | Source of cards to evaluate ("hole_cards", "community_cards") | Yes |
| **subsets** | Subsets | Array of Strings | Subsets of cards to consider | No |

### Evaluation Types

The schema supports various evaluation types:

#### Standard Types

* **high** - traditional high-hand in Poker
* **a5_low** - A-5 lowball - Ace is low, flushes/straights do not count against player
* **27_low** - 2-7 lowball - Ace is high, flushes/straights do count
* **badugi** - Badugi
* **badugi_ah** - Badugi, except Ace is high
* **higudi** - Hi-Dugi

#### Pip-Based Types

* **49** - Highest number of pips - face cards are 0, all other cards are their rank
* **zero** - Lowest number of pips - face cards are 0, all other cards are their rank
* **6** - Lowest number of pips - face cards are 10, all other cards are their rank (so best hand is AAAA2) 
* **low_pip_6** - Lowest number of pips - face cards are 10, all other cards are their rank. Hand sizes from 1 to 6 are allowed.
* **21** - Closest to 21 using as many cards as possible. 5-card 21 is the best hand, following by 4-card 21, 3-card 21, 5-card 20, etc.

#### Special Types

* **a5_low_high** - A-5 lowball, but highest unpaired hand is best (KQJT9). If all players have pairs, highest pair is best, etc.
* **high_wild** - traditional high-hand, but for use when wild cards are in play. Five of a kind is highest hand, otherwise joker can substitute for any card not in player's hand (so no double ace flushes, etc.)
* **one_card_high_spade** - Highest spade in the hole
* **two_card_high** - Highest hand using exactly two cards
* **ne_seven_card_high** - New England Hold'em seven-card high evaluation

#### Deck-Specific Types

* **36card_ffh_high** - High hands using a 36-card deck, with flushes ranked higher than full houses
* **20card_high** - High hands using a 20-card deck (A, K, Q, J, 10 of each suit)
* **27_ja_ffh_high_wild_bug** - High hands using a 40-card deck (8, 9, 10 of each suit removed)

## Common Qualifiers

### A-5 Lowball
- 10 or Better - 1,252
- 9 or Better - 1,126
- 8 or Better - 1,56
- 7 or Better - 1,21

### 2-7 Lowball
- J or Better - 1,246
- 10 or Better - 1,121
- 9 or Better - 1,52
- 8 or Better - 1,18
- 7 or Better - 1,4

### High
- 66s or better - 9,1980
- 77s or better - 9,1760
- 88s or better - 9,1540
- 99s or better - 9,1320
- TTs or better - 9,1100
- JJs or better - 9,880
- Two pair or better - 8,858
- Three of a kind or better - 7,858
- Flush or better - 5,1277