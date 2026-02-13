# Visual UI Testing Checklist - 2-Player Hold'em Game

## Objective
Verify that two players can play a complete Texas Hold'em hand through the web interface at `http://localhost:5000`.

## Prerequisites
- [ ] Server running (`python app.py`)
- [ ] Database seeded with test users (`python tools/seed_db.py`)
- [ ] Two browser sessions (or incognito windows) for two different players

## Test Credentials
| Username | Password | Starting Bankroll |
|----------|----------|-------------------|
| alice    | password | $1000 |
| bob      | password | $1500 |

---

## Phase 1: Login and Table Join

### Player 1 (Alice)
- [ ] Navigate to `http://localhost:5000`
- [ ] Redirected to login page
- [ ] Login with alice/password
- [ ] Lobby displays with user info (username, bankroll) in header
- [ ] Active tables list is visible

### Player 2 (Bob) - Second Browser
- [ ] Navigate to `http://localhost:5000`
- [ ] Login with bob/password
- [ ] Lobby displays correctly

### Create/Join Table
- [ ] Alice creates a new Texas Hold'em table OR joins existing one
  - Stakes: $1/$2 No Limit
  - Buy-in: $100-200
- [ ] Alice selects buy-in amount (e.g., $100)
- [ ] Alice selects a seat
- [ ] Alice successfully joins table, redirected to table view
- [ ] Bob joins the same table
- [ ] Bob selects buy-in and seat
- [ ] Both players visible at table with chip stacks displayed

---

## Phase 2: Ready System and Hand Start

### Ready Status
- [ ] Both players see "Ready" button
- [ ] Status shows "0/2 players ready" or similar
- [ ] Alice clicks Ready - button state changes
- [ ] Status updates to "1/2 players ready"
- [ ] Bob clicks Ready
- [ ] Status updates to "2/2 players ready"

### Hand Starts
- [ ] "Starting hand..." message appears
- [ ] Dealer button (D) appears at correct position
- [ ] Small blind is posted automatically (visible in pot/player bet)
- [ ] Big blind is posted automatically
- [ ] Pot shows $3 (SB $1 + BB $2)
- [ ] Both players receive 2 hole cards
- [ ] Cards display face-down for opponent, face-up for self
- [ ] Each player sees their own cards clearly

---

## Phase 3: Pre-Flop Betting Round

### First to Act (Small Blind/Button in heads-up)
- [ ] Action indicator shows whose turn it is
- [ ] Timer/time bank visible (if implemented)
- [ ] Action panel appears for the player to act
- [ ] Valid actions displayed: Fold, Call ($2), Raise

### Test Actions
- [ ] **Call**: Player clicks Call
  - Chips move to pot area
  - Pot updates correctly
  - Action broadcasts to other player
- [ ] **Check** (for BB if SB just calls): Check option available
- [ ] OR **Raise**: Raise slider/input works
  - Amount validation (min raise, max all-in)
  - Raise executes correctly

### Pre-Flop Completion
- [ ] After both players act, betting round closes
- [ ] Game advances to flop automatically

---

## Phase 4: Flop

### Community Cards
- [ ] 3 community cards dealt face-up in center
- [ ] Cards animate/appear visibly
- [ ] Cards are clearly readable

### Post-Flop Betting
- [ ] BB/first position acts first (post-flop order)
- [ ] Check option available (no bet yet)
- [ ] Bet option available with amount selector
- [ ] Both players can check through

---

## Phase 5: Turn and River

### Turn Card
- [ ] 4th community card dealt
- [ ] Betting round with check/bet options
- [ ] Actions work correctly

### River Card
- [ ] 5th community card dealt
- [ ] Final betting round
- [ ] Actions work correctly

---

## Phase 6: Showdown

### Hand Completion
- [ ] After river betting completes, showdown occurs
- [ ] Both players' hole cards revealed (if applicable)
- [ ] Winning hand highlighted or indicated
- [ ] Winner announcement displayed in chat or overlay
- [ ] Hand description shown (e.g., "Pair of Kings")
- [ ] Pot awarded to winner
- [ ] Winner's stack increases by pot amount
- [ ] Loser's stack unchanged (already deducted during betting)

---

## Phase 7: Next Hand (Future - Task 8.6)

*Note: This may not be implemented yet*

- [ ] Ready buttons reappear OR
- [ ] Next hand starts automatically after delay
- [ ] Dealer button rotates
- [ ] New blinds posted

---

## Alternative Scenarios to Test

### Fold Win
- [ ] One player folds pre-flop
- [ ] Remaining player wins pot immediately
- [ ] Game state shows COMPLETE
- [ ] No showdown display needed

### All-In
- [ ] Player can go all-in
- [ ] Side pot created if necessary (3+ players)
- [ ] All-in player's cards stay visible

---

## UI Elements to Verify

### Table Layout
- [ ] Poker table graphic displays correctly
- [ ] Seat positions arranged properly (9-max or 6-max layout)
- [ ] Player info boxes at each occupied seat
- [ ] Community card area in center
- [ ] Pot display visible

### Player Info Boxes
- [ ] Username displayed
- [ ] Chip stack displayed
- [ ] Current bet displayed (during betting)
- [ ] Dealer button indicator
- [ ] Active player highlight
- [ ] Folded state indicator (grayed out)

### Cards
- [ ] Hole cards display correctly for player
- [ ] Opponent cards show as face-down (backs)
- [ ] Community cards face-up and readable
- [ ] Card images load properly

### Action Panel
- [ ] Shows only when it's player's turn
- [ ] Correct actions available based on game state
- [ ] Bet/Raise amount input works
- [ ] Slider (if present) functions correctly
- [ ] Buttons are clickable and responsive

### Chat Panel
- [ ] System messages appear (player joined, hand started, etc.)
- [ ] Player chat messages work
- [ ] Action log shows (Alice bets $10, Bob calls, etc.)

### Side Panel
- [ ] Game info displayed (hand #, blinds, etc.)
- [ ] Debug info (if enabled) shows useful state

---

## Known Issues to Watch For

From bugs.md:
- [ ] Bug #006: Player's own cards may disappear intermittently after actions
- [ ] Action panel width changes causing layout shift

---

## Browser Console Checks
- [ ] No JavaScript errors
- [ ] WebSocket connection established
- [ ] Game state updates received via WebSocket
- [ ] No 404s for static resources (images, CSS)

---

## Test Completion Criteria

A successful test requires:
1. Both players can join the same table
2. Both can mark ready and hand starts
3. Cards are dealt and visible to correct players
4. At least one betting action works (call/check/fold)
5. Hand completes (via fold or showdown)
6. Winner receives pot
7. Chip stacks update correctly

---

## Commands Reference

```bash
# Start server
source env/bin/activate
python app.py

# Reset database if needed
python tools/reset_db.py

# Watch logs
tail -f poker_platform.log
```

---

*Last Updated: 2026-01-21*
*Status: Pending visual UI testing*
