"""Generate human-readable game descriptions from JSON configs.

Extracts subtitle tags, visual timeline, final hand descriptions,
and other display information from game config dictionaries.
"""


# --- Evaluation type descriptions ---

EVAL_DESCRIPTIONS = {
    "high": "Best poker hand",
    "a5_low": "Lowest 5 unique ranks (Ace is low). Straights and flushes do not count",
    "27_low": "Lowest ranked 5-card poker hand (Ace is high). Straights and flushes count",
    "badugi": "Lowest 4 unique ranks and suits (Ace is low)",
    "badugi_ah": "Lowest 4 unique ranks and suits (Ace is high)",
    "higudi": "Highest 4-card hand with unique ranks and suits",
    "high_wild": "Best poker hand with wild cards (Five of a Kind possible)",
    "high_wild_bug": "Best poker hand with wild cards (Five of a Kind possible)",
    "49": "Closest to 49 pip count",
    "zero": "Closest to zero pip count",
    "6": "Closest to 6 pip count",
    "low_pip_6": "Lowest pip count using 6 cards",
    "21": "Closest to 21 without going over",
    "a5_low_high": "Best A-5 low hand used as high",
    "one_card_high_spade": "Highest single spade",
    "two_card_high": "Best 2-card poker hand",
    "two_card_a5_low": "Lowest 2-card hand (Ace is low)",
    "ne_seven_card_high": "Best 5-card hand from 7 cards",
    "36card_ffh_high": "Best poker hand (36-card deck)",
    "20card_high": "Best poker hand (20-card deck)",
    "27_ja_ffh_high_wild_bug": "Best poker hand with bug wild (40-card deck)",
}

EVAL_BEST_HANDS = {
    "a5_low": "5432A",
    "27_low": "75432 (no flush)",
    "badugi": "432A rainbow",
    "badugi_ah": "5432 rainbow",
}


def get_forced_bet_style(config):
    """Determine the forced bet style from config."""
    if "forcedBets" in config:
        style = config["forcedBets"].get("style", "")
        if style == "bring-in":
            return "Antes", "Low Card Bring-In"
        elif style == "antes_only":
            return "Antes", None
        else:
            return "Blinds", None

    bet_type_map = {
        "blinds": ("Blinds", None),
        "antes": ("Antes", None),
        "bring-in": ("Antes", "Low Card Bring-In"),
    }
    for step in config.get("gamePlay", []):
        if "bet" in step:
            bet_type = step["bet"].get("type", "")
            if bet_type in bet_type_map:
                return bet_type_map[bet_type]
    return "Blinds", None


def get_wild_cards_info(config):
    """Extract wild card info from config."""
    wilds = []

    # Check deal steps
    for step in config.get("gamePlay", []):
        if "deal" in step and "wildCards" in step["deal"]:
            for wc in step["deal"]["wildCards"]:
                _add_wild_label(wc, wilds)

    # Check showdown
    for bh in config.get("showdown", {}).get("bestHand", []):
        if "wildCards" in bh:
            for wc in bh["wildCards"]:
                _add_wild_label(wc, wilds)

    return wilds


def _add_wild_label(wc, wilds):
    """Add a wild card label to the list if not already present."""
    wc_type = wc.get("type", "")
    role = wc.get("role", "wild")

    rank_names = {
        "2": "Deuces",
        "3": "Threes",
        "4": "Fours",
        "5": "Fives",
        "6": "Sixes",
        "7": "Sevens",
        "8": "Eights",
        "9": "Nines",
        "10": "Tens",
        "J": "Jacks",
        "Q": "Queens",
        "K": "Kings",
        "A": "Aces",
    }

    if wc_type == "rank":
        rank = wc.get("rank", "")
        name = rank_names.get(rank, rank)
        label = f"Bug ({name})" if role == "bug" else f"{name} Wild"
    elif wc_type == "joker":
        label = "Bug" if role == "bug" else "Joker Wild"
    elif wc_type == "lowest_community":
        label = "Lowest Board Card Wild"
    elif wc_type == "lowest_hole":
        label = "Lowest Hole Card Wild"
    elif wc_type == "last_community_card":
        label = "Last Community Card Wild"
    else:
        label = f"{wc_type} wild"

    if label not in wilds:
        wilds.append(label)


def get_subtitle_tags(config):
    """Build the subtitle tags list."""
    tags = []

    bet_style, bring_in = get_forced_bet_style(config)
    tags.append(bet_style)
    if bring_in:
        tags.append(bring_in)

    showdown = config.get("showdown", {})
    best_hands = showdown.get("bestHand", [])

    if len(best_hands) > 1:
        tags.append("Split Pot")

    if showdown.get("declaration_mode") == "declare":
        tags.append("Declare")

    for bh in best_hands:
        if "qualifier" in bh:
            tags.append("8 Qualifier")
            break

    wilds = get_wild_cards_info(config)
    tags.extend(wilds)

    deck_type = config.get("deck", {}).get("type", "standard")
    if deck_type != "standard":
        deck_names = {
            "short_6a": "36-Card Deck",
            "short_ta": "20-Card Deck",
            "short_27_ja": "40-Card Deck",
        }
        tags.append(deck_names.get(deck_type, f"{deck_type} Deck"))

    if config.get("deck", {}).get("jokers", 0) > 0:
        n = config["deck"]["jokers"]
        tags.append(f"{n} Joker{'s' if n > 1 else ''}")

    max_players = config.get("players", {}).get("max", 9)
    if max_players < 9:
        tags.append(f"{max_players} Players Max")

    return tags


def _get_deal_label(cards_list):
    """Get label like '2 DOWN', '2 DOWN 1 UP'."""
    down = 0
    up = 0
    for card_spec in cards_list:
        n = card_spec.get("number", 1)
        state = card_spec.get("state", "face down")
        if state == "face down":
            down += n
        else:
            up += n

    parts = []
    if down > 0:
        parts.append(f"{down} DOWN")
    if up > 0:
        parts.append(f"{up} UP")
    return "\n".join(parts)


def build_timeline(config):
    """Build the visual timeline from gamePlay steps.

    Returns a list of tuples:
    - ("individual", label, cards_list)
    - ("community", count)
    - ("draw", label)
    - ("discard", label)
    - ("expose", label)
    - ("pass", label)
    - ("separate", label)
    - ("declare", label)
    - ("choose", label)
    - ("bet",)
    """
    timeline = []
    current_group = []
    skip_first_bet = True
    last_was_bet = False

    for step in config.get("gamePlay", []):
        if "bet" in step:
            bet_type = step["bet"].get("type", "")
            if skip_first_bet and bet_type in ("blinds", "antes", "bring-in"):
                continue
            skip_first_bet = False

            if last_was_bet:
                continue

            if current_group:
                timeline.extend(current_group)
                current_group = []
            timeline.append(("bet",))
            last_was_bet = True
            continue

        # Reset last_was_bet for all non-bet steps
        last_was_bet = False

        if "deal" in step:
            skip_first_bet = False
            deal = step["deal"]
            location = deal.get("location", "player")
            cards_list = deal.get("cards", [])

            if location == "player":
                label = _get_deal_label(cards_list)
                current_group.append(("individual", label, cards_list))
            else:
                total = sum(c.get("number", 1) for c in cards_list)
                current_group.append(("community", total))

        elif "draw" in step:
            skip_first_bet = False
            draw = step["draw"]
            cards = draw.get("cards", [{}])
            max_draw = sum(c.get("number", 0) for c in cards)
            min_draw = sum(c.get("min_number", 0) for c in cards)
            label = "DRAW"
            if min_draw > 0 and min_draw < max_draw:
                label = f"DRAW\n{min_draw}-{max_draw}"
            elif max_draw > 0 and max_draw < 5:
                label = f"DRAW\n{max_draw} MAX"
            current_group.append(("draw", label))

        elif "discard" in step:
            skip_first_bet = False
            cards = step["discard"].get("cards", [{}])
            num = sum(c.get("number", 1) for c in cards)
            label = f"DISCARD\n{num} CARD{'S' if num > 1 else ''}"
            current_group.append(("discard", label))

        elif "expose" in step:
            skip_first_bet = False
            cards = step["expose"].get("cards", [{}])
            num = sum(c.get("number", 1) for c in cards)
            label = f"EXPOSE\n{num} CARD{'S' if num > 1 else ''}"
            current_group.append(("expose", label))

        elif "pass" in step:
            skip_first_bet = False
            cards = step["pass"].get("cards", [{}])
            num = sum(c.get("number", 1) for c in cards)
            direction = cards[0].get("direction", "left") if cards else "left"
            label = f"PASS {num}\n{direction.upper()}"
            current_group.append(("pass", label))

        elif "separate" in step:
            skip_first_bet = False
            cards = step["separate"].get("cards", [])
            subsets = [f"{c.get('number', 0)} {c.get('hole_subset', '')}" for c in cards]
            label = "SEPARATE\n" + "\n".join(subsets)
            current_group.append(("separate", label))

        elif "declare" in step:
            skip_first_bet = False
            current_group.append(("declare", "DECLARE\nHI/LO"))

        elif "choose" in step:
            skip_first_bet = False
            current_group.append(("choose", "CHOOSE\nVARIANT"))

        elif "replace_community" in step:
            skip_first_bet = False
            current_group.append(("draw", "REPLACE\nCOMMUNITY"))

        elif "remove" in step:
            skip_first_bet = False
            current_group.append(("discard", "REMOVE\nCARD"))

        elif "roll_die" in step:
            skip_first_bet = False
            current_group.append(("choose", "ROLL\nDIE"))

        elif "showdown" in step:
            pass

    if current_group:
        timeline.extend(current_group)

    return timeline


def get_final_hand_description(config):
    """Generate Final Hand text from showdown config."""
    showdown = config.get("showdown", {})
    best_hands = showdown.get("bestHand", [])

    if not best_hands:
        return ["Best poker hand"]

    descriptions = []
    for bh in best_hands:
        eval_type = bh.get("evaluationType", "high")
        name = bh.get("name", "")
        desc = EVAL_DESCRIPTIONS.get(eval_type, f"Best hand ({eval_type})")

        hole = bh.get("holeCards", 0)
        comm = bh.get("communityCards", 0)
        any_cards = bh.get("anyCards", 0)

        # Handle list/string values
        if isinstance(hole, list):
            hole = sum(hole)
        elif isinstance(hole, str):
            hole = 0
        if isinstance(comm, list):
            comm = sum(comm)
        elif isinstance(comm, str):
            comm = 0
        if isinstance(any_cards, list):
            any_cards = sum(any_cards)
        elif isinstance(any_cards, str):
            any_cards = 0

        usage = ""
        if hole > 0 and comm > 0:
            usage = f" using {hole} Individual and {comm} Community"
        elif hole > 0 and comm == 0 and any_cards == 0:
            usage = f" using all {hole} hole cards"
        elif any_cards > 0 and any_cards != 5:
            usage = f" ({any_cards}-card hand)"

        qualifier = ""
        if "qualifier" in bh:
            qualifier = " with 8-or-better qualifier"

        if name:
            descriptions.append(f"**{name}:** {desc}{usage}{qualifier}")
        else:
            descriptions.append(f"{desc}{usage}{qualifier}")

    return descriptions


def get_split_pot_description(config):
    """Generate Split Pot line if applicable."""
    showdown = config.get("showdown", {})
    best_hands = showdown.get("bestHand", [])

    if len(best_hands) <= 1:
        return None

    parts = []
    for bh in best_hands:
        name = bh.get("name", "")
        eval_type = bh.get("evaluationType", "high")

        if name:
            parts.append(name)
        elif eval_type == "high":
            parts.append("High hand")
        elif eval_type in ("a5_low", "27_low"):
            parts.append("Low hand")
        else:
            parts.append(eval_type)

    return " / ".join(parts)
