#!/usr/bin/env python3
"""Generate visual game description cards from JSON configs.

Reads all game configs and produces a standalone HTML file with visual
game cards similar to the abby99 Mixed Game Cards format.

Usage:
    python tools/generate_game_cards.py [output_file] [--filter PATTERN]
    python tools/generate_game_cards.py                          # All games -> game_cards.html
    python tools/generate_game_cards.py --filter "hold_em"       # Single game
    python tools/generate_game_cards.py --filter "Draw"          # Category filter
"""

import json
import re
import sys
from pathlib import Path

# Add src/ to path so we can import the shared module
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from generic_poker.config.game_description import (
    EVAL_BEST_HANDS,
    build_timeline,
    get_final_hand_description,
    get_split_pot_description,
    get_subtitle_tags,
    get_wild_cards_info,
)

CONFIG_DIR = Path(__file__).parent.parent / "data" / "game_configs"


def load_config(path):
    """Load a game config JSON file."""
    with open(path) as f:
        return json.load(f)


def render_timeline_element(elem):
    """Render a single timeline element as HTML."""
    elem_type = elem[0]

    if elem_type == "individual":
        label = elem[1] if len(elem) > 1 else ""
        cards_list = elem[2] if len(elem) > 2 else None
        lines = label.split("\n") if label else [""]
        label_html = "<br>".join(lines)

        total_cards = 0
        has_up = False
        has_down = False
        if cards_list:
            for cs in cards_list:
                total_cards += cs.get("number", 1)
                if cs.get("state", "face down") == "face up":
                    has_up = True
                else:
                    has_down = True

        if total_cards <= 1 and has_up:
            return f'<div class="tl-group"><div class="card-front stud-card-up">I</div><div class="card-label">{label_html}</div></div>'
        elif total_cards <= 1 and has_down:
            return f'<div class="tl-group"><div class="card-front stud-card-down">I</div><div class="card-label">{label_html}</div></div>'
        elif has_up and has_down:
            return f'<div class="tl-group"><div class="card-stack individual"><div class="card-back card-back-1"></div><div class="card-back card-back-2"></div><div class="card-front individual-card">I</div></div><div class="card-label">{label_html}</div></div>'
        else:
            return f'<div class="tl-group"><div class="card-stack individual"><div class="card-back card-back-1"></div><div class="card-back card-back-2"></div><div class="card-back card-back-3"></div><div class="card-front individual-card">I</div></div><div class="card-label">{label_html}</div></div>'

    elif elem_type == "community":
        count = elem[1] if len(elem) > 1 else 1
        cards_html = "".join('<div class="card-front community-card">C</div>' for _ in range(min(count, 6)))
        return f'<div class="tl-group"><div class="community-cards">{cards_html}</div></div>'

    elif elem_type == "bet":
        return '<div class="tl-group bet-group"><div class="bet-chip">Bet</div></div>'

    else:
        label = elem[1] if len(elem) > 1 else elem_type.upper()
        label_html = "<br>".join(label.split("\n"))
        css_class = f"action-box action-{elem_type}"
        return f'<div class="tl-group"><div class="{css_class}">{label_html}</div></div>'


def generate_card_html(config, filename):
    """Generate HTML for a single game card."""
    game_name = config.get("game", filename)
    tags = get_subtitle_tags(config)
    timeline = build_timeline(config)
    final_hands = get_final_hand_description(config)
    split_pot = get_split_pot_description(config)
    wilds = get_wild_cards_info(config)
    category = config.get("category", "Other")

    subtitle = " &bull; ".join(tags)
    tl_html = "".join(render_timeline_element(elem) for elem in timeline)

    # Final hand text
    if len(final_hands) == 1:
        desc = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", final_hands[0])
        final_html = f'<div class="final-hand"><strong>Final Hand:</strong> {desc}</div>'
    else:
        parts = [re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", d) for d in final_hands]
        final_html = f'<div class="final-hand"><strong>Final Hands:</strong><br>{"<br>".join(parts)}</div>'

    split_html = f'<div class="split-pot"><strong>Split Pot:</strong> {split_pot}</div>' if split_pot else ""

    wild_html = ""
    for w in wilds:
        if "Bug" in w:
            wild_html += '<div class="wild-note">Bug completes straight or flush, otherwise acts as an Ace.</div>'
        elif "Wild" in w:
            wild_html += f'<div class="wild-note">{w}.</div>'

    best_hand_html = ""
    for bh in config.get("showdown", {}).get("bestHand", []):
        eval_type = bh.get("evaluationType", "")
        if eval_type in EVAL_BEST_HANDS:
            best_hand_html = f'<div class="best-hand"><strong>Best Hand:</strong> {EVAL_BEST_HANDS[eval_type]}</div>'
            break

    return f"""
    <div class="game-card" data-category="{category}">
        <div class="card-title">{game_name}</div>
        <div class="card-subtitle">{subtitle}</div>
        <div class="timeline">{tl_html}</div>
        {wild_html}{final_html}{split_html}{best_hand_html}
    </div>"""


# --- CSS ---

CSS = """
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background: #f0f0f0; padding: 20px; color: #333; }
.header { text-align: center; margin-bottom: 30px; }
.header h1 { font-size: 2rem; margin-bottom: 8px; }
.header .count { color: #666; font-size: 1.1rem; }
.nav { display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; margin-bottom: 30px; }
.nav-link { background: #fff; padding: 6px 14px; border-radius: 20px; text-decoration: none; color: #2563eb; font-size: 0.9rem; border: 1px solid #ddd; transition: all 0.2s; }
.nav-link:hover { background: #2563eb; color: #fff; }
.category-header { font-size: 1.5rem; margin: 30px 0 15px; padding-bottom: 8px; border-bottom: 2px solid #333; }
.cards-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(420px, 1fr)); gap: 20px; }
.game-card { background: #fff; border: 2px solid #333; border-radius: 12px; padding: 20px; break-inside: avoid; }
.card-title { font-size: 1.5rem; font-weight: 800; text-align: center; margin-bottom: 4px; }
.card-subtitle { font-size: 0.85rem; text-align: center; color: #555; margin-bottom: 16px; font-weight: 500; }
.timeline { display: flex; flex-wrap: wrap; align-items: flex-end; gap: 6px; justify-content: center; margin-bottom: 14px; min-height: 80px; padding: 8px 0; }
.tl-group { display: flex; flex-direction: column; align-items: center; gap: 4px; }
.card-stack { position: relative; width: 44px; height: 60px; }
.card-back { position: absolute; width: 40px; height: 56px; border: 2px solid #666; border-radius: 4px; background: linear-gradient(135deg, #c8c8c8 25%, #e0e0e0 25%, #e0e0e0 50%, #c8c8c8 50%, #c8c8c8 75%, #e0e0e0 75%); background-size: 8px 8px; }
.card-back-1 { top: 0; left: 0; }
.card-back-2 { top: 2px; left: 2px; }
.card-back-3 { top: 4px; left: 4px; }
.card-front { position: relative; width: 40px; height: 56px; border: 2px solid #333; border-radius: 4px; display: flex; align-items: center; justify-content: center; font-weight: 800; font-size: 1.2rem; z-index: 1; }
.individual-card { background: #fff; position: absolute; top: 4px; left: 4px; }
.stud-card-up { background: #fff; width: 40px; height: 56px; border: 2px solid #333; border-radius: 4px; display: flex; align-items: center; justify-content: center; font-weight: 800; font-size: 1.2rem; }
.stud-card-down { background: linear-gradient(135deg, #c8c8c8 25%, #e0e0e0 25%, #e0e0e0 50%, #c8c8c8 50%, #c8c8c8 75%, #e0e0e0 75%); background-size: 8px 8px; width: 40px; height: 56px; border: 2px solid #666; border-radius: 4px; display: flex; align-items: center; justify-content: center; font-weight: 800; font-size: 1.2rem; color: #555; }
.community-cards { display: flex; gap: 3px; }
.community-card { background: #fff; width: 34px; height: 48px; font-size: 1rem; font-weight: 800; border: 2px solid #333; border-radius: 3px; display: flex; align-items: center; justify-content: center; }
.card-label { font-size: 0.6rem; text-align: center; color: #555; font-weight: 600; line-height: 1.2; max-width: 60px; }
.bet-group { align-self: flex-end; margin: 0 2px; }
.bet-chip { width: 36px; height: 36px; border-radius: 50%; border: 3px solid #333; background: #f5f5f5; display: flex; align-items: center; justify-content: center; font-size: 0.6rem; font-weight: 700; color: #333; }
.action-box { border: 2px solid #555; border-radius: 4px; padding: 6px 8px; font-size: 0.6rem; font-weight: 700; text-align: center; line-height: 1.3; min-width: 50px; background: #f9f9f9; }
.action-draw { border-color: #2563eb; color: #2563eb; }
.action-discard { border-color: #dc2626; color: #dc2626; }
.action-expose { border-color: #059669; color: #059669; }
.action-pass { border-color: #7c3aed; color: #7c3aed; }
.action-separate { border-color: #d97706; color: #d97706; }
.action-declare { border-color: #be185d; color: #be185d; }
.action-choose { border-color: #0891b2; color: #0891b2; }
.wild-note { font-size: 0.8rem; color: #555; margin-bottom: 6px; font-style: italic; }
.final-hand { font-size: 0.82rem; margin-bottom: 4px; line-height: 1.4; }
.split-pot { font-size: 0.82rem; margin-bottom: 4px; line-height: 1.4; }
.best-hand { font-size: 0.82rem; color: #555; }
.filter-bar { display: flex; gap: 10px; justify-content: center; margin-bottom: 20px; flex-wrap: wrap; }
.filter-bar input { padding: 8px 16px; border: 1px solid #ccc; border-radius: 20px; font-size: 0.95rem; width: 300px; outline: none; }
.filter-bar input:focus { border-color: #2563eb; box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.2); }
@media print { body { background: #fff; padding: 10px; } .nav, .header, .filter-bar { display: none; } .game-card { break-inside: avoid; border-width: 1px; } .cards-grid { grid-template-columns: repeat(2, 1fr); gap: 10px; } }
"""


def generate_html(configs, output_path):
    """Generate the full HTML page with all game cards."""
    categories = {}
    for filename, config in sorted(configs.items(), key=lambda x: x[1].get("game", x[0])):
        cat = config.get("category", "Other")
        if cat not in categories:
            categories[cat] = []
        categories[cat].append((filename, config))

    cat_order = ["Hold'em", "Omaha", "Stud", "Draw", "Dramaha", "Mixed", "Other"]
    all_cats = list(categories.keys())
    ordered_cats = [c for c in cat_order if c in all_cats]
    ordered_cats.extend(c for c in all_cats if c not in ordered_cats)

    cards_html = ""
    nav_html = ""
    for cat in ordered_cats:
        games = categories[cat]
        cat_id = cat.lower().replace("'", "").replace(" ", "-")
        cards_html += (
            f'<h2 class="category-header" id="cat-{cat_id}">{cat} ({len(games)})</h2>\n<div class="cards-grid">\n'
        )
        nav_html += f'<a href="#cat-{cat_id}" class="nav-link">{cat} ({len(games)})</a>\n'
        for filename, config in games:
            cards_html += generate_card_html(config, filename)
        cards_html += "</div>\n"

    total = sum(len(v) for v in categories.values())

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Poker Game Cards ({total} variants)</title>
<style>{CSS}</style>
</head>
<body>
<div class="header"><h1>Poker Game Cards</h1><div class="count">{total} variants</div></div>
<div class="filter-bar"><input type="text" id="filter" placeholder="Filter games..." oninput="filterCards(this.value)"></div>
<div class="nav">{nav_html}</div>
{cards_html}
<script>
function filterCards(query) {{
    query = query.toLowerCase();
    document.querySelectorAll('.game-card').forEach(card => {{
        const title = card.querySelector('.card-title').textContent.toLowerCase();
        const subtitle = card.querySelector('.card-subtitle').textContent.toLowerCase();
        const cat = card.dataset.category.toLowerCase();
        const match = !query || title.includes(query) || subtitle.includes(query) || cat.includes(query);
        card.style.display = match ? '' : 'none';
    }});
}}
</script>
</body>
</html>"""

    with open(output_path, "w") as f:
        f.write(html)
    return total


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Generate visual game cards from JSON configs")
    parser.add_argument("output", nargs="?", default="game_cards.html", help="Output HTML file")
    parser.add_argument("--filter", "-f", default="", help="Filter by game name or category")
    args = parser.parse_args()

    configs = {}
    for path in sorted(CONFIG_DIR.glob("*.json")):
        try:
            config = load_config(path)
            name = path.stem

            if args.filter:
                game_name = config.get("game", "")
                category = config.get("category", "")
                if (
                    args.filter.lower() not in name.lower()
                    and args.filter.lower() not in game_name.lower()
                    and args.filter.lower() not in category.lower()
                ):
                    continue

            configs[name] = config
        except Exception as e:
            print(f"Warning: Could not load {path.name}: {e}", file=sys.stderr)

    if not configs:
        print("No matching configs found.", file=sys.stderr)
        sys.exit(1)

    total = generate_html(configs, args.output)
    print(f"Generated {args.output} with {total} game cards")


if __name__ == "__main__":
    main()
