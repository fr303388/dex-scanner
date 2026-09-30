# analysis/

Every conclusion in this project came from one of these scripts. They used to
live in %TEMP%\opencode, which does not survive a reboot.

Run any of them with no arguments, or pass the project directory:

    python analysis\cohort_health.py
    python analysis\live_check.py
    python analysis\exit_lab.py

## Which source answers which question

| script | question | why that source |
|---|---|---|
| `live_check.py` | what happened to tokens we exited? | queries DexScreener **now**, so delisted and rugged tokens are visible. cohort.csv cannot answer this: it stops tracking a token once it leaves the trending feed, which is correlated with dying. Measured: 83%% of stopped-out tokens are dead on-chain, while the cohort-based estimate said 8%%. |
| `cohort_health.py` | is the data pipeline trustworthy? | observation rate, miss distribution, no_liquidity by entry band |
| `analyze_cohort.py` | forward returns, DEAD rate | cohort population is seeded before any entry gate, so it is not censored by the score or liquidity filters |
| `exit_lab.py` | scale-out and vol-stop counterfactuals | `trajectory.csv`, recorded during the hold, so no survivorship bias |
| `hold_vs_stop.py` | would holding have beaten the stop? | cohort path, and it is only indicative: tokens that die are under-represented |
| `stopped_out_fate.py` | disposition of every stopped-out trade | cohort plus on-chain |
| `concentration_backtest.py` | does holder concentration separate dead from alive? | measured **after** the tokens died, so top1 is inflated by the surviving deployer. Not a valid test of an entry-time filter. |
| `score_gate_test.py` | is the score gate helping? | cohort, restricted to liq0 >= 150k. n was 16, far too small. |
| `criteria_test.py` | do the Insentos-style criteria predict anything? | cohort at the 150k tier, n=16 |
| `post_change_check.py` | did the $150k floor keep the bot trading? | `decisions.csv` funnel since the change |
| `strategy_report*.py` | the original 34-trade review | trade records plus live on-chain state |
| `healthcheck.py`, `why_no_entry.py` | bot-wide funnel | `decisions.csv` |

## Known traps

1. **Never ask "what happened to a token we exited" using cohort.csv.** It
   stops tracking tokens that leave the trending feed, and leaving the feed is
   correlated with dying. Use `live_check.py`.

2. **The `miss` column in cohort.csv is NOT the current miss count, and is
   almost always 0.** Two separate reasons:
   - It used to be read *after* the counter was reset, so it was structurally
     0 for every row ever written. Measured: 2146 distinct tokens, peak-miss
     distribution `{0: 2146}`. That part is fixed -- it now carries the value
     from *before* the sample, which is what the field's comment always
     claimed.
   - It is still 0 for any token that is *currently* missing, because
     `poll_cohort` only writes rows for tokens the API returned. A missing
     token increments in memory and produces no row at all. So the column
     only becomes non-zero for a token that went missing and came back.

   **The authoritative live count is in `cohort_state.json`.** Read it from
   there. Writing rows for missing tokens too would close this properly, but
   it changes the csv contract (null price and liquidity) and every reader of
   it, so it was not done while the scheduled run still depends on those
   readers.

3. **`seen_once` separates two things that look identical.** A token never
   indexed by DexScreener accumulates misses from its first poll and crosses
   the death threshold while being completely unobservable. Measured on the
   live cohort: all 20 members at miss >= 5 were UNTRACKABLE, zero were DEAD.
   All had entry liquidity between $10k and $19k, far below the $150k entry
   floor, so none of them were ever tradable.

   The direction of the error this avoids matters: labelling an unobservable
   token DEAD inflates the death rate, which is the number this directory
   exists to measure.

4. **As of 2026-10-01 the cohort contains zero observed deaths.** Every member
   is either currently observed or was never indexed. Tokens that actually die
   leave the trending feed and get evicted, so "died" remains something this
   population cannot measure. That is a property of the design, not a bug, and
   it is why `live_check.py` is the source for any "what happened to the
   tokens we exited" question.

5. **Anything measured after a token died is not a test of an entry filter.**
   See `concentration_backtest.py`.
