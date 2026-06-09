# Monte Carlo Bot — Design

**Status:** Phase 1 implemented (2026-06-09) — see "Phase 1 results" below

## Phase 1 results (2026-06-09)

Implemented: `mc_rollout.py` (RolloutSpec snapshot + rollout engine), `mc_policy.py`
(equity → action mapping), `monte_carlo_bot.py` (MonteCarloBot, drop-in for SimpleBot),
`BotManager.create_bot(bot_type=...)`, `BOT_TYPE` config (default `mc`), `tools/bot_arena.py`
CLI, 26 unit tests (`tests/unit/test_monte_carlo_bot.py`).

Arena results vs SimpleBot (seeded, stacks reset per hand):

| Variant | Structure | Hands | MC edge |
|---------|-----------|-------|---------|
| Hold'em (heads-up) | No Limit | 200 | +1099 BB/100 |
| Omaha 8 (heads-up) | Limit | 100 | +141 BB/100 |
| 7-Card Stud (3-handed) | Limit | 100 | +349 BB/100 |
| Dramaha (heads-up) | Limit | 60 | +95 BB/100 |

Decision latency: well under the 300ms arena budget per decision; production default 1500ms.

**Engine bugs found by the arena** (all fixed with regression tests; they affected real play, not just bots):
1. `round_complete()` ignored an all-in raise — the remaining player was never required to call/fold, play skipped ahead and stranded the raise in an unawarded pot (`betting.py`).
2. All-in players stayed in the betting rotation on later streets and could even fold away their pot eligibility — now skipped via `Game.skip_betting_players_unable_to_act()` (`game.py`, `player_action_handler.py`).
3. Hi-lo odd chip vanished: the odd-chip rule matched low eval types with `startswith("low")` but real names are `a5_low`/`27_low`, so Omaha 8/Stud 8 split odd pots as floor/floor and dropped a chip (`showdown_manager.py`, both pot paths).
**Goal:** A smarter, variant-agnostic bot that makes decisions based on Monte Carlo equity estimation, using the existing engine's hand evaluator. No per-variant code, no training, bounded latency.

## Approved decisions (2026-06-09)

- **Phase 1 scope approved:** betting decisions only, SimpleBot fallback for everything else.
- **Priority variants:** WSOP mixed-game staples — Hold'em/Omaha (community), 7-Card Stud/Razz/Stud8 (stud), 5-Card Draw/2-7 Triple Draw/Badugi (draw), Dramaha-family splits. Wild cards, card swapping, exotic variants in later phases.
- **Time budget:** 1500ms default is arbitrary — drop if it feels slow. No "thinking" UI for now; revisit once real decision latency is known.
- **CLI arena (`tools/bot_arena.py`):** yes, build it early for offline A/B tuning. Longer-term: an MCP/network interface for remote control of site operations is wanted — keep tooling scriptable with that in mind.

## Engine audit findings (pre-implementation, 2026-06-09)

Resolves risk area #1. Key facts that shape `RolloutState`:

- **Evaluator is pure and standalone:** `HandEvaluator.evaluate_hand(cards, eval_type, qualifier=None) -> HandResult` (`evaluation/evaluator.py:192`). `HandResult.rank` (1 = best, for BOTH high and low games) + `ordered_rank` tiebreaker. Compare `(rank, ordered_rank)` tuples directly.
- **Qualifier trap:** non-qualifying hands come back as `HandResult(rank=0)`, and `compare_hands()`'s `if not result` guard never fires (dataclass is always truthy) — rank 0 would "beat" rank 1. The MC evaluator must do its own qualifier filtering (`rank > q[0]` → out; `rank == q[0] and ordered_rank > q[1]` → out; `rank == 0` → out) and never use `compare_hands` with qualifiers.
- **Phase 1 configs are simple:** the entire WSOP-mix target set uses only `evaluationType` + one of `anyCards` | (`holeCards` [+ `communityCards`]) + optional `qualifier` + `name`. No wild cards, no subsets beyond community `"default"`, no `conditionalBestHands`, no declarations, no `groupedActions`. Eval types needed: `high`, `a5_low`, `27_low`, `badugi`, `hidugi`, `49`, `6`, `21`, `zero`.
- **Best-hand finding:** `ShowdownManager._find_best_hand_for_player` exists but mutates Card objects (wild marking) and needs a Player. For Phase 1's tiny constraint vocabulary, implement our own combinatorial best-hand finder (`itertools.combinations`) instead of reusing it. Worst case Omaha: C(4,2)×C(5,3) = 60 evals per player per rollout — fine.
- **Hi-lo / split equity:** evaluate each `bestHand` config independently; each config is worth `1/len(configs)` of the pot; a config with no qualifiers redistributes its share to the configs that have winners (matches `_redistribute_exact_pot`). Equity = expected pot-share fraction averaged over rollouts — handles ties, hi-lo, and dramaha splits uniformly.
- **Snapshot inputs:** own cards `players[id].hand.get_cards()`; opponent face-up cards + face-down count via `card.visibility` (`Visibility.FACE_UP/FACE_DOWN`); community `table.community_cards: dict[subset, list[Card]]`; full deck `Deck(deck_type=game.table.deck_type)`; remaining streets from `rules.gameplay[game.current_step + 1:]` filtering `GameActionType.DEAL` (`action_config["location"]` = player|community, `cards: [{number, state, subset?}]`). Players still in the hand: `player.is_active` (fold sets it False).
- **Pot odds:** pot = `game.betting.get_total_pot()`; incremental call cost = `game.betting.get_additional_required(player_id)`. NOTE: amounts in valid-action tuples are TOTALS ("total amount a player must have bet after the action"), not increments — use them for `BotDecision.amount`, never for pot-odds math.
- **Dead cards:** `table.discard_pile` holds burns/discards. Exclude the whole pile from the unseen deck: statistically neutral for unknown cards (symmetry), and required for correctness for the bot's own past discards in draw games.
- **`Card` is unhashable** (defines `__eq__` only) — use `str(card)` (e.g. `"As"`) keys for set membership.
- **Wild-state attrs** (`dynamic_wild_rank`, `follow_card_wild_rank`, `player_wild_ranks`) and any `card.is_wild` ⇒ out of Phase 1 scope; snapshot builder must detect and refuse (fall back to SimpleBot).
- **Supportability gate** (refuse → SimpleBot fallback) when any of: remaining pre-showdown step is not BET/DEAL/SHOWDOWN; showdown uses `declaration_mode`/`conditionalBestHands`; a bestHand config has keys outside the Phase 1 vocabulary or non-integer `holeCards`/`communityCards`; community subsets other than `"default"`; wild state present.

## Motivation

`SimpleBot` plays purely on action-type weights (call 60%, raise 20%, fold 20%) with no awareness of card strength. It folds with quads, raises with junk, and never gets better. We want a bot that:

- Plays reasonably across all 246 variants without per-variant tuning
- Is noticeably smarter than `SimpleBot` (uses cards, pot odds, position-ish reasoning)
- Stays under a hard latency budget (~1.5s default, capped at 3s) so it doesn't block the game
- Is a drop-in replacement for `SimpleBot` — same `BotDecision` return type, same integration points

We're explicitly **not** trying to build a near-optimal solver. Goals = "intermediate human" skill, not GTO.

## Core Idea

At any decision point, generate N rollouts where:

1. Deep-copy (or lightweight-copy) the current game state
2. For each unknown card (opponent holes, undealt board), draw randomly from the unseen deck
3. Run the rollout forward to showdown using a simple in-rollout policy for opponent decisions
4. Use the engine's existing `HandEvaluator` / `get_hand_results()` to determine outcome
5. Tally wins, ties, losses

Equity ≈ `(wins + ties/2) / N`.

Translate equity to a betting action via pot odds:
- `equity > call_cost / (pot + call_cost)` → call/raise
- Higher equity → more aggression
- Add jitter so the bot isn't perfectly predictable

The engine already knows how to evaluate any variant's showdown. We don't have to teach the bot what makes a good Badugi or Big O hand — it samples completions and asks the evaluator. **That's why this generalizes.**

## Architecture

### File layout

```
src/online_poker/services/
├── simple_bot.py          # existing — keep as fallback / weighting baseline
├── monte_carlo_bot.py     # NEW — main MonteCarloBot class
├── mc_rollout.py          # NEW — rollout engine + state copying
├── mc_policy.py           # NEW — equity → action mapping
└── bot_action_service.py  # existing — minor change to pick bot type
```

### Class shape

```python
# monte_carlo_bot.py
class MonteCarloBot:
    """Variant-agnostic bot using Monte Carlo equity estimation."""

    def __init__(
        self,
        player_id: str,
        username: str,
        time_budget_ms: int = 1500,
        max_rollouts: int = 500,
        aggression: float = 1.0,
    ):
        self.player_id = player_id
        self.username = username
        self.is_bot = True
        self.time_budget_ms = time_budget_ms
        self.max_rollouts = max_rollouts
        self.aggression = aggression
        self._simple_fallback = SimpleBot(player_id, username)

    def choose_action_full(
        self, valid_actions: list[tuple], game=None, player_id=None
    ) -> BotDecision:
        """Same signature as SimpleBot.choose_action_full — drop-in compatible."""
        ...
```

### Returns existing `BotDecision`

No changes to `BotDecision` or to `bot_action_service._run_bot_loop`. The MC bot is interchangeable with `SimpleBot` at the call site.

### BotManager change

Tiny: `BotManager.create_bot()` gets an optional `bot_type` parameter (default `"simple"`, can be `"mc"`). The `fill_bots` socket handler passes a config-controlled type.

```python
# config.py
BOT_TYPE = os.environ.get("BOT_TYPE", "mc")  # "simple" or "mc"
```

This lets us A/B in dev and roll back instantly if MC bots misbehave in production.

## Algorithm Detail

### 1. Action dispatch

```python
def choose_action_full(self, valid_actions, game, player_id):
    action_types = {a[0] for a in valid_actions}

    # Phase 1 scope: only handle betting decisions with MC.
    # Everything else (draw/discard/expose/pass/separate/declare/choose/buy)
    # falls through to SimpleBot for now.
    betting_actions = {FOLD, CHECK, CALL, BET, RAISE, BRING_IN, COMPLETE}
    if not (action_types & betting_actions):
        return self._simple_fallback.choose_action_full(valid_actions, game, player_id)

    return self._choose_betting_action(valid_actions, game, player_id)
```

### 2. Equity estimation

```python
def _estimate_equity(self, game, player_id) -> EquityEstimate:
    deadline = time.monotonic() + self.time_budget_ms / 1000
    wins = ties = losses = 0
    completed = 0

    snapshot = RolloutState.from_game(game, player_id)

    for _ in range(self.max_rollouts):
        if time.monotonic() > deadline:
            break

        rollout = snapshot.copy()
        rollout.deal_unknowns_to_opponents()
        rollout.complete_remaining_streets()  # uses simple in-rollout policy
        outcome = rollout.evaluate(player_id)

        if outcome.win: wins += 1
        elif outcome.tie: ties += 1
        else: losses += 1
        completed += 1

    return EquityEstimate(
        equity=(wins + 0.5 * ties) / max(1, completed),
        n=completed,
        confidence=_wilson_interval(wins, completed),
    )
```

### 3. RolloutState (lightweight game copy)

Don't deep-copy `Game` — it carries `BettingManager`, `PotManager`, history, hooks, references to log files, etc. Build a slim struct that captures only what showdown evaluation needs:

```python
@dataclass
class RolloutState:
    bot_hole_cards: list[Card]              # face-down + face-up, kept verbatim
    opponent_visible_cards: dict[str, list[Card]]   # face-up cards per opponent
    opponent_hidden_count: dict[str, int]   # how many face-down opponents have
    community_cards: dict[str, list[Card]]  # by subset name
    remaining_streets: list[StreetSpec]     # what's still to be dealt
    unseen_deck: list[Card]                 # full deck minus everything visible to bot
    eval_config: EvalConfig                 # evaluation type, hi-lo, qualifiers
    rules: GameRules                        # for showdown evaluation only

    @classmethod
    def from_game(cls, game, player_id) -> "RolloutState":
        ...

    def copy(self) -> "RolloutState":
        # cheap: shallow copy with deck list copied
        ...

    def deal_unknowns_to_opponents(self):
        # Shuffle unseen_deck, deal to fill each opponent's hidden count
        ...

    def complete_remaining_streets(self):
        # Deal any remaining community cards from deck
        # If a street has a draw/pass/expose, use heuristic policy (Phase 2)
        ...

    def evaluate(self, player_id) -> Outcome:
        # Reuse engine's HandEvaluator on the synthetic showdown state
        ...
```

**Key insight:** for variants that have *no* mid-hand decisions left to make (Hold'em post-flop, all stud, all community games), `complete_remaining_streets` is just dealing cards from the deck. For variants with draws/discards/passes ahead, we need an in-rollout policy (see Phase 2).

### 4. Equity → action mapping

```python
def _equity_to_decision(equity, valid_actions, game, player_id) -> BotDecision:
    pot = game.betting.get_total_pot()
    call_cost = _calc_call_cost(game, player_id, valid_actions)
    pot_odds = call_cost / max(1, pot + call_cost) if call_cost > 0 else 0

    can_check = any(a[0] == PlayerAction.CHECK for a in valid_actions)
    can_bet = any(a[0] in (PlayerAction.BET, PlayerAction.RAISE) for a in valid_actions)

    # Margin = how much equity exceeds pot odds (negative = unprofitable to call)
    margin = equity - pot_odds

    if can_check:
        # Free option — never fold
        if equity > 0.55 and can_bet:
            return _make_bet(valid_actions, equity, game, aggression)
        return _make_check(valid_actions)

    if margin < -0.05:
        # Can't profitably call. Fold (with small bluff frequency).
        if can_bet and random.random() < 0.05 * aggression:
            return _make_bet(valid_actions, equity, game, aggression)
        return _make_fold(valid_actions)

    if margin > 0.15 and can_bet:
        return _make_bet(valid_actions, equity, game, aggression)

    return _make_call(valid_actions)
```

Bet sizing for NL/PL: pick from a small grid (1/3 pot, 2/3 pot, pot, all-in) weighted by equity strength + jitter. For limit: just `min_amount`.

## Performance

### Targets

| Variant family       | Rollouts/sec | Rollouts in 1.5s |
|----------------------|--------------|------------------|
| Hold'em / Omaha      | 800-1500     | 1200-2200        |
| Stud (no decisions)  | 600-1000     | 900-1500         |
| Draw / discard / pass| 100-300      | 150-450          |
| Hi-lo split          | 60-80% of above (two evaluations per showdown) |

200-500 completed rollouts gives ±3-5% equity confidence at the 95% level — plenty for pot-odds decisions.

### What makes it fast

- **No `Game` deep-copy.** `RolloutState` is a flat dataclass with primitive lists.
- **Reuse the existing `HandEvaluator`.** O(1) lookups via pre-computed CSVs. We don't reimplement.
- **Keep `unseen_deck` as a list, not the full `Deck` class.** Simple `random.shuffle` + slice.
- **Stop on deadline, not on rollout count.** Slow variants degrade gracefully to noisier-but-still-useful estimates.
- **Avoid logging in the rollout loop.** `SimpleBot` logs every action — kill that in MC's hot path.

### Wall-clock cap

Hard cap of 3000ms. If we hit it, log a warning and fall through to `SimpleBot`. Prevents pathological lockups.

## Phased implementation

### Phase 1 — Betting decisions only (MVP)

- `RolloutState` for community-card variants (Hold'em, Omaha, stud)
- Random in-rollout opponent dealing
- Pot-odds-based action mapping
- Falls back to `SimpleBot` for everything that's not a betting action
- Falls back to `SimpleBot` for variants whose remaining streets include draw/discard/expose/pass

**Estimated effort:** 1.5-2 days. Covers ~60% of variant play (everything except draw and stud-with-bring-in initial decisions).

### Phase 2 — In-rollout policy for mid-hand decisions

- Heuristic policy for opponent draw/discard during rollouts (e.g., "discard worst N cards by rank/suit-group")
- Heuristic policy for pass actions
- Coverage extends to draw poker, badugi, push games

**Estimated effort:** 2-3 days. Adds ~25% more variant coverage.

### Phase 3 — MC-driven non-betting choices

- Bot uses MC for *its own* draw/discard/declare/buy decisions: enumerate plausible options, mini-rollout each, pick highest-equity
- Equity-aware declare for hi-lo (try declaring high vs low vs both, compare expected value)

**Estimated effort:** 2-3 days. Covers the long tail and lifts overall play quality meaningfully.

### Phase 4 (optional) — Crude opponent modeling

- Track opponent VPIP / aggression per session
- Adjust assumed "random hand" sampling: tight opponents weight higher card pairs/big cards, loose ones don't
- Pure stats, no per-variant logic

**Estimated effort:** open-ended. Diminishing returns; only worth it if Phases 1-3 leave the bot feeling shallow.

## What MC won't fix (be honest about it)

- **No reads.** Bots will play their cards correctly but won't pick up on opponent patterns. A skilled human will still exploit them.
- **No bluff detection.** If equity says fold, the bot folds — even when an opponent is obviously bluffing.
- **No balanced bluff frequency.** The 5% bluff jitter is a hack, not a strategy. A solver-trained bot would have a properly mixed range; MC bot doesn't.
- **Naive opponent ranges.** Treating all opponent hole cards as uniform-random across the unseen deck overestimates weak hands. This is the single biggest accuracy gap. Phase 4 would help.
- **Multi-way pot equity is biased optimistic.** Heads-up MC equity scales reasonably to multi-way; pot-odds reasoning does not. We'll need to tune call thresholds higher when 3+ players are still in.

## Risk areas / open questions

1. **Rollout state fidelity.** When the engine has unusual mid-hand state (wild cards triggered, exposed cards in opponent hands, separate-action subsets), can `RolloutState` faithfully replay showdown? **Need to audit `HandEvaluator` inputs across all variants before locking the rollout struct.** Probably 1 day of investigation upfront.

2. **Hi-lo split equity.** Do we just compute hi-equity and lo-equity separately, then weight by expected pot share? Or simulate the actual hand and check who scoops? Latter is more accurate; former is faster. **Recommend the latter — engine already does it.**

3. **Wild cards and dynamic state.** `dynamic_wild_rank`, `follow_card_wild_rank`, `player_wild_ranks` need to flow through `RolloutState`. Doable but worth verifying.

4. **Stud bring-in / first-street decisions.** Stud bring-in is forced; that's fine. But the *first-betting-round* equity in stud (with one face-up card) is very low-information — equity estimates will be near 50%, so MC barely beats a coin flip. Fine.

5. **Discard policy in rollouts.** When a remaining street is "draw up to 3", what does an opponent discard? Simplest: random count. Better: a heuristic ("keep pairs, discard low unpaired cards"). Phase 2 problem.

6. **Lock contention.** MC computation runs in the bot loop background task, which holds the per-table lock. A 1.5s decision blocks other bots at the same table for 1.5s. Need to verify this doesn't cause UX issues with multi-bot tables.

7. **Determinism for testing.** Need a `seed` param on `MonteCarloBot` so unit tests are reproducible. (Default: random seed in production.)

## Configuration

All knobs live in env vars (Render dashboard) and `config.py`:

| Env var                     | Default | Purpose |
|-----------------------------|---------|---------|
| `BOT_TYPE`                  | `mc`    | `simple` or `mc` |
| `BOT_MC_TIME_BUDGET_MS`     | `1500`  | Soft deadline per decision |
| `BOT_MC_MAX_ROLLOUTS`       | `500`   | Hard cap on rollouts per decision |
| `BOT_MC_AGGRESSION`         | `1.0`   | Multiplier on bet/bluff frequency |

Per-bot overrides via constructor params for testing.

## Testing strategy

- **Unit tests** (`tests/unit/test_monte_carlo_bot.py`):
  - Equity estimate of pocket aces preflop heads-up should be ~85%
  - Equity estimate of 7-2o preflop heads-up should be ~35%
  - With check available, bot never folds
  - With negative pot-odds margin, bot folds (mostly)
  - Determinism with seeded RNG
- **Integration tests** (`tests/integration/test_mc_bot_play.py`):
  - MC bot vs SimpleBot, 100 hands of Hold'em — MC bot wins more often than not (sanity check)
  - MC bot completes a hand of every supported variant family without erroring
  - Decision time stays under 3s wall-clock for all variants tested
- **Smoke tests:** existing variant smoke suite should pass with `BOT_TYPE=mc`

## Out of scope

- Pre-trained models (CFR / NN bots). Per-variant; not what we're building.
- Bluff detection / opponent modeling beyond Phase 4.
- Multi-table thinking (no use case yet).
- Variant-specific overrides. The whole point is to stay generic.

## Decision points for review

1. Are we OK with `SimpleBot` fallback for non-betting actions in Phase 1, or should we ship Phase 1+2 together?
2. Default `BOT_MC_TIME_BUDGET_MS` of 1500 — too slow? (Bot loop already sleeps 1.5s between actions, so total turn time ~3s.)
3. Add a UI indicator (e.g., a "thinking..." pulse on the bot's seat) while MC is running, or keep it silent?
4. Do we want a CLI tool to A/B MC bots vs SimpleBot offline (`tools/bot_arena.py`)? Useful for tuning, not required.
