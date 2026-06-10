# UX Test Findings — New-Player Journey (2026-06-09)

Method: drove the local site (same code as Render) in a real Chromium browser via Playwright
at iPad Air dimensions (1180×820 landscape, 820×1180 portrait), acting as a brand-new player:
register → lobby → read rules → create tables → buy in → play hands with bots → leave.
Variants exercised: Texas Hold'em (NL), 5-Card Draw (NL, draw UI), 7-Card Stud (Limit,
bring-in), Omaha 8 (Limit, hi-lo split). Screenshots in `docs/ux-testing/`.

> **Fix status:** C1, C2, C3, H1, H2, H3, H4, M1, M3, P1, P2, P3, P4, P9 fixed 2026-06-09.
> M2, M6, P5, P6, P7, P8, P10 fixed 2026-06-10 — M2 became a full stud betting-rules
> correction verified against Robert's Rules of Poker v11 (see STATUS.md): completion
> instead of raise vs the bring-in, limit raise cap (bet + 3 raises, unlimited heads-up),
> and the 4th-street open-pair double bet for stud high. Still open: M4 (iPad portrait,
> Phase 7.4) and M5 (card sizes in 5+ card games).

Note: diagonal "X" marks visible across gray boxes in some screenshots are an artifact of the
headless renderer (1px border + border-radius miter bug in the software rasterizer), NOT a site
bug — verified with a minimal repro (`ux-14-repro-box.png`).

---

## Critical (testers will hit these in their first session)

### C1. Second hand is unplayable — action buttons never come back
After the first hand's showdown, the showdown strip is rendered by **replacing
`#action-panel`'s innerHTML**, which destroys the `.action-buttons` container. On the next
hand, `updateActionButtons` (table.js:948) throws `TypeError: Cannot set properties of null`
on every state update. Result: it's the player's turn but **no buttons render — the game is
soft-locked**. Only a page reload recovers (session state survives, so reload works).
The throw also aborts `updateGameState` mid-function, so everything after it (including
`updateGameInfo`) stops running — which is why the hand counter sticks at #1 (the L004
regression is actually this bug).
Repro: play any hand to showdown with bots → Ready → hand 2 starts → no action buttons;
console shows the TypeError every 5s (polling).

### C2. Draw/discard card selection breaks after any state refresh
Card click handlers are attached once via `_setupCardSelectionHandlers`, but every state
broadcast re-renders the seats (innerHTML), wiping the listeners. On a bot table the state
refreshes constantly, so by the time a human tries to click cards to discard, **clicks do
nothing** — they can only Stand Pat. Verified: cards have `.selectable` class and
`data-card-index` but no listener; both synthetic and real clicks fail to select.
Fix direction: event delegation (one listener on a stable ancestor) instead of per-card
listeners.

### C3. Money operations silently fail — dual SQLAlchemy instances
`websocket_manager.py:203,415,1421` import `from online_poker.services.player_action_manager ...`
while the app runs as `src.online_poker.*`. Both paths are importable, so Python loads a
**second copy of the module tree with its own `db` (unbound to Flask)**. DB writes through
that copy fail: `The current Flask app is not registered with this 'SQLAlchemy' instance`
(seen in server log during mid-hand leave).
Observed consequences in one short session:
- Mid-hand leave: in-memory removal succeeded but the DB cashout failed → `table_access`
  row still active, **$395 never returned to bankroll**, lobby still shows the player seated.
- Stack sync after hands didn't persist (draw table `current_stack` stayed = buy-in $80
  despite finishing the hand with $40 — leaving returned the wrong amount, +$40 free).
- `transactions` table is completely empty — no buy-in/cashout audit trail at all.
Fix: make the 3 imports relative (`from .player_action_manager import ...`) and audit for any
other absolute `online_poker.` imports; consider removing the dual import path entirely.

---

## High

### H1. Showdown is hidden by the ready overlay
The instant a hand completes, the "N/M players ready" overlay appears centered on the table,
covering the revealed hands and winner highlight (`ux-19`, `ux-26`). The player learns who
won only from the chat. Suggest delaying the ready panel ~4-5s (or until the player clicks),
letting the showdown moment play out.

### H2. View Rules is broken (404)
Lobby "View Rules" fetches `/api/tables/variants/<id>/rules`, but `table_bp` declares
`url_prefix="/api/tables"` and `app.py:119` registers it with `url_prefix="/table"`, which
**overrides** the blueprint prefix → endpoint actually lives at `/table/variants/<id>/rules`.
Modal shows "Failed to load rules." This is broken on Render too.

### H3. Registration/login error handling is silent
Submitting mismatched passwords on Register clears the whole form with **no error message**
(`ux-05`). Same pattern risk on login failures. A new player has no idea what happened.

### H4. Auth pages look unstyled
Login/Register are plain white default-browser pages (off-center, default inputs, a broken
glyph "□" in the title) — jarring vs. the polished purple lobby (`ux-03`, `ux-04`). Looks
like a different/broken site at the exact moment of first impression.

---

## Medium

### M1. Guest lobby is half-broken
Anonymous visitors see the lobby but the variants API call fails (returns login-redirect HTML
→ JSON parse error in console), leaving the variant filter and the create-table variant
dropdown empty. Clicking Create Table as guest opens the full form (with empty variant list)
instead of prompting login (`ux-02`).

### M2. Stud bring-in betting options look wrong
Facing a $5 bring-in at $10/$20, the next player gets "Call $5 / **Raise $15**". Card-room
standard is *complete to $10*. Needs review of bring-in completion in the engine/UI mapping
(may be COMPLETE mislabeled/miscalculated as bring-in + small bet).

### M3. Player count denominator wrong
Header shows "6/9" on a 6-max table. `updateGameInfo` (table.js:1595) falls back to
`gameState.max_players || 9` — `max_players` is missing from the game-state payload.

### M4. iPad portrait table layout is broken
At 820×1180: table goes near-circular, seat panels overflow the felt, revealed showdown cards
spill outside the table onto the page background, header wraps to two cramped lines
(`ux-31`). Confirms Phase 7.4 (tablet optimization) is needed. No rotate prompt shows at
iPad size (prompt is phone-only).

### M5. Cards are too small to read/tap in 5-card games
Own hole cards in 5-card games render at **24×34px** at iPad-landscape size — below Apple's
~44pt touch-target guideline and genuinely hard to read (`ux-21`–`ux-23`). Fine for 2 cards,
not for 5-7. Draw selection (C2) requires tapping exactly these tiny targets.

### M6. Seat-selection modal layout issues
Seats 3/4 crowd and overlap the "Select Your Seat" dealer box (`ux-09`); modal content
slightly wider than the modal (horizontal scrollbar).

---

## Polish

- P1. "Collected $20 from main pot **[Unspecified]**" in chat for single-config games (no
  `name` in bestHand config). Omaha 8 correctly shows [High Hand]/[Low Hand]; default the
  label or drop the brackets.
- P2. Raw variant IDs shown to users: seat modal says "Game: **7 Card_stud**", "Hold Em".
- P3. Duplicate checkboxes in the create-table form — native checkbox + styled checkbox both
  render side by side (`ux-27`).
- P4. favicon.ico 404 — no tab icon, console noise.
- P5. The 311-option variant dropdown is overwhelming on touch devices; the optgroups help
  but search/filter would be better long-term.
- P6. Seeded "Omaha 2/6 PLAYING" lobby table is phantom (seed data, no real players) —
  confusing for testers; consider seeding empty tables only.
- P7. Open chat covers the left seat entirely (`ux-18`).
- P8. DEBUG `console.log` noise throughout table.js in production.
- P9. Bots buy in for the table minimum (20BB) while the player default is 40BB — looks odd.
- P10. No "forgot password" link on login (auth_service supports reset tokens).

## What worked well

- Registration → auto-login → lobby flow is smooth; bankroll visible immediately.
- Create table → auto-opening seat modal → buy-in → table is a coherent, fast flow.
- Bots auto-fill, auto-ready, play promptly with believable decisions (MC bots fold trash,
  raise strong hands, check behind appropriately).
- Action bar (Fold/Check/Call/Bet + slider + Min/Pot/½Pot/All-In presets) is clear and the
  right size on iPad landscape.
- Chat action log reads well: bet amounts spaced correctly, street markers, timestamps,
  showdown summary with board and hand descriptions.
- Stud per-player up/down card rendering is correct (opponents' hole cards hidden, door
  cards visible); turn highlight and bet badges are readable.
- Hi-lo split pots display correctly labeled in Omaha 8.
- Mid-hand leave UX (confirmation modal with chip-return message) is clear — the failure is
  in the DB layer (C3), not the UI flow.
