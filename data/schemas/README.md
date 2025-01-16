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
| **gamePlay** | Game Play | Array of Objects | Describes the sequence of actions in the game | Yes |
| **showdown** | Showdown | Object | Defines the showdown rules and hand evaluation | Yes |

The **references** field is an optional array of URLs that point to external resources describing the rules or variations of the game. This can be useful for providing additional context or for tracing the origin of the game configuration.

### Players Object

| Field | Name | Type | Definition | Required |
| ----- | ---- | ---- | ---------- | -------- |
| **min** | Minimum Players | Integer | Minimum number of players | Yes |
| **max** | Maximum Players | Integer | Maximum number of players | Yes |

### Deck Object

| Field | Name | Type | Definition | Required |
| ----- | ---- | ---- | ---------- | -------- |
| **type** | Deck Type | String | Type of deck. Allowed value: "standard" | Yes |
| **cards** | Number of Cards | Integer | Number of cards in the deck. Allowed values: 52 (standard deck), 36 (deck with cards 2-5 removed) | Yes |

### Deck Types

The following deck types are supported:

- **standard**: A standard 52-card deck containing all cards from 2 through Ace in four suits.
- **short_6a**: A 36-card deck with cards 2 through 5 removed, containing cards from 6 through Ace in four suits.
- **short_ta**: A 20-card deck containing only 10, Jack, Queen, King, and Ace in four suits.

The `cards` field in the deck object should match the number of cards in the chosen deck type.

### Forced Bets Object

| Field | Name | Type | Definition | Required |
| ----- | ---- | ---- | ---------- | -------- |
| **style** | Bet Style | String | Style of forced bets (e.g., "bring-in", "blinds", "antes"). | Yes |
| **rule** | Bet Rule | String | Rule for hand evaluation for bring-in bets.   Currently supported values are 'high card', 'low card', 'high card ah' and 'low card al'. | Yes |
| **variation** | Bet Variation | String | Optional variation on the standard bring-in rules to support unusual hand evaluation.   "a5 low high" is the only currently supported variation.  | No |

### Game Play Array

The Game Play array contains objects that describe each step of the game. Each object can have the following properties:

| Field | Name | Type | Definition | Required |
| ----- | ---- | ---- | ---------- | -------- |
| **name** | Step Name | String | Name of the gameplay step | Yes |
| **bet** | Bet | Object | A betting action | No |
| **deal** | Deal | Object | Describes a dealing action | No |
| **draw** | Draw | Object | Describes a drawing action | No |
| **expose** | Expose | Object | Describes an exposing action | No |
| **pass** | Expose | Object | Describes an passing action | No |
| **separate** | Separate | Object | Describes a separating action | No |
| **discard** | Discard | Object | Describes a discarding action | No |
| **remove** | Remove | Object | Describes a removing action | No |
| **showdown** | Showdown | Object | Indicates a showdown step | No |

#### Deal Object

| Field | Name | Type | Definition | Required |
| ----- | ---- | ---- | ---------- | -------- |
| **location** | Deal Location | String | Location of the deal (player or community) | Yes |
| **cards** | Cards | Array of Objects | Describes the cards being dealt | Yes |

Each object in the cards array has the following properties:

| Field | Name | Type | Definition | Required |
| ----- | ---- | ---- | ---------- | -------- |
| **number** | Number of Cards | Integer | Number of cards to deal | Yes |
| **state** | Card State | String | State of the cards (face up or face down) | Yes |
| **subset** | Card Subset | String | Subset of cards if applicable | No |

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
| **subset** | Card Subset | String | Subset of cards if applicable | No |
| **draw_amount** | Draw Amount | Object | Specifies how many cards are drawn when different from the discard amount | No |

if a single **number** is given, then any amount of cards from 0 up to that number may be discarded and drawn.   The **min_number** is used if the minimum amount is not zero.    

##### Draw Amount Object

| Field | Name | Type | Definition | Required |
| ----- | ---- | ---- | ---------- | -------- |
| **relative_to** | Relative To | String | Specifies that the draw amount is relative to the discard amount (only allowed value is "discard") | Yes |
| **amount** | Amount | Integer | The difference between the draw amount and the discard amount | Yes |

The only supported **relative_to** value is "discard".   For example,

```json
"draw_amount": {
    "relative_to": "discard",
    "amount": -1
}
```

Indicates that the draw amount is one less than the discard amount.   Discarding 4 cards will result in drawing 3 cards.    

#### Discard Object

| Field | Name | Type | Definition | Required |
| ----- | ---- | ---- | ---------- | -------- |
| **cards** | Cards | Array of Objects | Describes the cards to discard | Yes |

Each object in the cards array has the following properties:

| Field | Name | Type | Definition | Required |
| ----- | ---- | ---- | ---------- | -------- |
| **rule** | Discard Rule | String | Rule for discarding cards | No |
| **subset** | Subset of Cards | String | Subset of cards for discarding | No |
| **number** | Number of Cards | Integer | Number of cards to discard | No |
| **state** | Card State | String | State of the discarded cards (face up or face down) | No |

If **state** of 'face up' is used, the cards will appear to all players.  

#### Expose Object

| Field | Name | Type | Definition | Required |
| ----- | ---- | ---- | ---------- | -------- |
| **cards** | Cards | Array of Objects | Describes the cards to expose | Yes |

Each object in the cards array has the following properties:

| Field | Name | Type | Definition | Required |
| ----- | ---- | ---- | ---------- | -------- |
| **number** | Number of Cards | Integer | Number of cards to expose | Yes |
| **state** | Card State | String | State of the cards (face up or face down) | Yes |

#### Pass Object

| Field | Name | Type | Definition | Required |
| ----- | ---- | ---- | ---------- | -------- |
| **cards** | Cards | Array of Objects | Describes the cards to pass | Yes |

Each object in the cards array has the following properties:

| Field | Name | Type | Definition | Required |
| ----- | ---- | ---- | ---------- | -------- |
| **number** | Number of Cards | Integer | Number of cards to pass | Yes |
| **direction** | Pass Direction | String | Direction to pass the cards (left, right, or across) | Yes |
| **state** | Card State | String | State of the cards being passed (face up or face down) | Yes |

This step allows players to pass cards to other players in a specified direction.

Example:
```json
"pass": {
    "cards": [
        {
            "number": 1,
            "direction": "left",
            "state": "face down"
        }
    ]
}

#### Separate Object

| Field | Name | Type | Definition | Required |
| ----- | ---- | ---- | ---------- | -------- |
| **cards** | Cards | Array of Objects | Describes the cards to separate | Yes |

Each object in the cards array has the following properties:

| Field | Name | Type | Definition | Required |
| ----- | ---- | ---- | ---------- | -------- |
| **subset** | Subset Name | String | Name of the subset | Yes |
| **number** | Number of Cards | Integer | Number of cards in the subset | Yes |

This step subdivides a player's hand into one or more subsets.

```json
"separate": {
    "cards": [
        {
            "subset": "Hold'em",
            "number": 2
        },
        {
            "subset": "Super Hold'em",
            "number": 3
        }
    ]
},
```

requires the player to pick 2 cards to put into a subset called "Hold'em" and 3 cards to put into a subset called "Super Hold'em".

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
| **bestHand** | Best Hand | Array of Objects | Defines the hand evaluation rules | Yes |
| **defaultAction** | Default Action | Object | Defines the default action for showdown if no hand meets hand evaluation rules | No |

#### Best Hand Object

| Field | Name | Type | Definition | Required |
| ----- | ---- | ---- | ---------- | -------- |
| **name** | Hand Name | String | Name of the hand type | No |
| **evaluationType** | Evaluation Type | String | Type of hand evaluation | Yes |
| **holeCards** | Hole Cards | Integer or Array of Integers | Number of hole cards required or list of indices | No |
| **communityCards** | Community Cards | Integer or Array of Integers | Number of community cards required or list of indices | No |
| **anyCards** | Any Cards | Integer | Number of any cards required | No |
| **holeCardsAllowed** | Allowed Hole Cards | Array of Objects | Allowed combinations of hole card subsets | No |
| **communityCardsAllowed** | Allowed Community Cards | Array of Objects | Allowed combinations of community card subsets | No |
| **communitySubsetsAllowed** | Allowed Community Subsets | Array of Strings | List of allowed community subsets | No |
| **subset** | Subset | String | Specific subset of cards to be used for this hand evaluation (deprecated) | No |
| **wildCard** | Wild Card | Object | Wild card rules | No |
| **qualifier** | Qualifier | Array of Integers | Qualifier for the hand | No |
| **padding** | Padding | Boolean | If true, pads out the hole cards to the specified length if there are fewer cards | No |
| **minimumCards** | Minimum Cards | Integer | The minimum number of cards required for the hand to qualify | No |

Evaluation Types currently supported are:

* **high** - traditional high-hand in Poker
* **a5_low** - A-5 lowball - Ace is low, flushes/straights do not count against player
* **27_low** - 2-7 lowball - Ace is high, flushes/straights do count
* **badugi** - Badugi
* **badugi_ah** - Badugi, except Ace is high
* **higudi** - Hi-Dugi
* **49** - Highest number of pips - face cards are 0, all other cards are their rank
* **zero** - Lowest number of pips - face cards are 0, all other cards are their rank
* **6** - Lowest number of pips - face cards are 10, all other cards are their rank (so best hand is AAAA2) 
* **low_pip_6** - Lowest number of pips - face cards are 10, all other cards are their rank.   Hand sizes from 1 to 6 are allowed.
* **21** - Closest to 21 using as many cards as possible.  5-card 21 is the best hand, following by 4-card 21, 3-card 21, 5-card 20, etc.
* **a5_low_high** - A-5 lowball, but highest unpaired hand is best (KQJT9).  If all players have pairs, highest pair is best, etc.
* **high_wild** - traditional high-hand, but for use when wild cards are in play.   Five of a kind is highest hand, otherwise joker can subsitute for any card not in player's hand (so no double ace flushes, etc.)

For 36-card decks (2's, 3's, 4's, 5's are removed)

* **36card_ffh_high** - High hands using a 36-card deck, with flushes ranked higher than full houses

For 20-card decks (only T, J, Q, K, A are present))

* **20card_high** - High hands using a 20-card deck (A, K, Q, J, 10 of each suit)

For holeCards and communityCards, either a single value can be given, or an array of possible choices.  For example:

```
holeCards: [2.3],
communityCards: [3,2]
```

indicates that either 2 hole cards and 3 community cards can be used, or 3 hole cards and 2 community cards.   The arrays, if used, should always be the same length.

The **qualifier** is specified as an array of integers, but really is a pair of number representing the rank and ordered rank within that rank for a given hand.

For example,

```json
{
    "name": "Low Hand",
    "evaluationType": "a5_low",
    "holeCards": 3,
    "communityCards": 2,
    "qualifier": [1,56]
}
```            

Indicates we are using the A-5 Lowball evaluation rules (from a5_low), and there is a qualifier of rank 1,56, which indicates an 8-high.   So, this represents the fairly standard 8 or better qualifier that many hi/lo games have.

Here are some common qualifiers and the pairs of numbers for them.   Other values can be obtained by looking at the hand evaluation files (such as all_card_hands_ranked_a5_low.csv)

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

#### Card Subset Allowed Object

This object is used in the `holeCardsAllowed` and `communityCardsAllowed` fields of the Best Hand Object.

| Field | Name | Type | Definition | Required |
| ----- | ---- | ---- | ---------- | -------- |
| **subsets** | Allowed Subsets | Array of Strings | List of allowed subsets for this combination | Yes |
| **indices** | Card Indices | Array of Integers | List of indices for the allowed cards | No |

For example,

```json               
"holeCardsAllowed": [
    {
        "subsets": ["Point","Hole Card"],
        "indices": [0,0]
    },
    {
        "subsets": ["Point","Hole Card"],
        "indices": [0,1]
    }
]
```

This indicates that there are 2 choices of hold cards to use - card 0 in the Point subset, and either card 0 or 1 in the Hold Card subset.   

If **indicies** are not present, then all cards in the subset are available to be used.

**communityCardsAllowed** works in the same manner.   There is an array of subsets and an optional array of indicies to specify specific cards to use.

#### Wild Card Object

This object is used in the `wildCard` field of the Best Hand Object.

| Field | Name | Type | Definition | Required |
| ----- | ---- | ---- | ---------- | -------- |
| **communityCards** | Community Card Rule | String | Wild card rule for community cards | No |
| **otherCards** | Other Cards Rule | String | Wild card rule for other cards | No |

This describes what rules define wild cards in the game.   Currently, only one set of values is supported:

```json
    "wildCard": {
        "communityCards": "low",
        "otherCards": "same_rank"
    }
```
which indicates that the low community card is wild, along with any other cards of the same rank.   In the future, more sets of rules will be implemented.

#### Default Action Object

This object is used in the `defaultAction` field of the Showdown Object.

| Field | Name | Type | Definition | Required |
| ----- | ---- | ---- | ---------- | -------- |
| **condition** | Condition | String | Condition for applying the default action | Yes |
| **action** | Action | String | Action to take when the condition is met | Yes |
| **bestHand** | Best Hand | Array of Best Hand Objects | Hand evaluation rules for the default action | No |

This indicates how hand evaulation should work no winner is met from rules in **bestHand**.    'no_qualifier_met' is the only supported value for **condition** - indicating that no hands met qualifiers.

For 'action' - there are two supported values:

* **best_hand** - use the rules in the bestHand object located in the defaultAction object to determine the winner
* **split_pot** - split the pot among all active players

This README provides an overview of the main components of the Poker Game Configuration Schema. For more detailed information, please refer to the full JSON schema file.