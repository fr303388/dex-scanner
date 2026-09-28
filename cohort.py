"""Cohort: censoring-free fixed-population price tracking.

Why
---
decisions.csv only logs tokens that are in the trending feed *at that moment*.
A token that leaves the feed before the forward horizon completes is silently
dropped, censoring the sample (measured survival rate: 0.1%-2.7%). The cohort
polls each admitted token independently of the scanner for COHORT_TTL, so a
token keeps contributing observations after it stops trending -- and after it
rugs.

Design constraints -- do not "optimise" these away
-------------------------------------------------
* poll_cohort applies NO liquidity filter. A rug that drains the pool to $0
  must still be recorded; that collapse curve is the data we want.
* Solana base58 addresses are case-sensitive. Never .lower() them.
* cohort.csv is append-only. Never rewrite the whole file.
* age_sec is the token's age at the moment of that sample.
* COHORT_TTL must stay >= 2x the longest forward window used in analysis
  (120 min). 4h gives 2x margin.
* A batch request that FAILS must not count as a token miss. Only a token
  that the API successfully answered for, and did not include, has missed.
"""
import requests
import csv
import json
import os
from typing import Dict, List

# ===================== constants =====================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
COHORT_STATE_PATH = os.path.join(BASE_DIR, "cohort_state.json")
COHORT_STATE_TMP = os.path.join(BASE_DIR, "cohort_state.tmp.json")
COHORT_CSV_PATH = os.path.join(BASE_DIR, "cohort.csv")

COHORT: Dict[str, dict] = {}
COHORT_TTL = 4 * 3600        # must be >= 2x the 120min analysis window
COHORT_MAX = 200
MIN_SEED_LIQ = 10000         # seed-time only. poll-time applies no filter.
# DexScreener's batch endpoint has an undocumented internal cap. Measured
# return rate against this cohort's own addresses:
#     batch  5 -> 97%    batch 12 -> 82%
#     batch 10 -> 88%    batch 20 -> 67%    batch 30 -> 42%
# The drop is deterministic per token, not random, so a low rate makes miss
# climb to DEAD for tokens that are perfectly alive. Do not raise this.
BATCH_SIZE = 5
MISS_THRESHOLD = 5           # consecutive answered-but-absent polls = DEAD


# ===================== helpers =====================
def safe_float(v):
    try:
        return float(v)
    except (ValueError, TypeError):
        return 0.0


def load_cohort_state():
    global COHORT
    if not os.path.exists(COHORT_STATE_PATH):
        COHORT = {}
        return
    try:
        with open(COHORT_STATE_PATH, "r", encoding="utf-8") as f:
            COHORT = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"[cohort] state load failed ({e}); starting empty")
        COHORT = {}


def save_cohort_state():
    if not COHORT:
        return
    try:
        with open(COHORT_STATE_TMP, "w", encoding="utf-8") as f:
            json.dump(COHORT, f, ensure_ascii=False)
        os.replace(COHORT_STATE_TMP, COHORT_STATE_PATH)
    except OSError as e:
        print(f"[cohort] state save failed: {e}")


def init_cohort_csv():
    """Create the header once. Never truncates."""
    if os.path.exists(COHORT_CSV_PATH):
        return
    header = ["ts", "address", "symbol", "price", "liquidity",
              "volume_h24", "br_h24", "br_m5", "age_sec",
              "score0", "liq0", "no_liquidity", "miss"]
    with open(COHORT_CSV_PATH, "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(header)


# ===================== core =====================
def seed_cohort(tokens: List[dict], now_ts) -> int:
    now_ts = int(now_ts)      # caller may pass a float (time.time())
    skip = 0
    for t in tokens:
        addr = t.get("address")
        if not addr:
            skip += 1
            continue
        liq = safe_float(t.get("liquidity", 0))
        if liq < MIN_SEED_LIQ:
            skip += 1
            continue
        if addr in COHORT:
            continue
        if len(COHORT) >= COHORT_MAX:
            skip += 1
            continue
        COHORT[addr] = {
            "sym": t.get("symbol", "?"),
            "first_ts": now_ts,
            "expiry": now_ts + COHORT_TTL,
            "score0": safe_float(t.get("score", 0)),
            "liq0": liq,
            "miss": 0,
        }
    return skip


def poll_cohort(now_ts) -> int:
    now_ts = int(now_ts)
    for a in [a for a, r in COHORT.items() if now_ts > r["expiry"]]:
        del COHORT[a]

    active = [a for a, r in COHORT.items() if now_ts <= r["expiry"]]
    if not active:
        save_cohort_state()
        return 0

    best: Dict[str, tuple] = {}
    failed: set = set()          # addresses whose batch call did not succeed
    for start in range(0, len(active), BATCH_SIZE):
        batch = active[start:start + BATCH_SIZE]
        url = ("https://api.dexscreener.com/latest/dex/tokens/"
               + ",".join(batch))
        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code != 200:
                raise RuntimeError(f"HTTP {resp.status_code}")
            pairs = resp.json().get("pairs", [])
        except Exception as e:
            print(f"[cohort] fetch error: {e}")
            failed.update(batch)      # API gap, NOT a token miss
            continue
        for p in pairs:
            base = p.get("baseToken", {}).get("address", "")
            if not base:
                continue
            li = safe_float(p.get("liquidity", {}).get("usd", 0))
            if base not in best or li > best[base][0]:
                best[base] = (li, p)

    # miss accounting: only count tokens the API answered for
    for addr in active:
        if addr in failed:
            continue                       # transport failure -> no penalty
        rec = COHORT[addr]
        rec["miss"] = 0 if addr in best else rec.get("miss", 0) + 1

    rows = []
    for addr, (li, p) in best.items():
        rec = COHORT.get(addr)
        if not rec:
            continue
        tx = p.get("txns", {})
        b24 = safe_float(tx.get("h24", {}).get("buys", 0))
        s24 = safe_float(tx.get("h24", {}).get("sells", 0))
        b5 = safe_float(tx.get("m5", {}).get("buys", 0))
        s5 = safe_float(tx.get("m5", {}).get("sells", 0))
        rows.append([
            now_ts,
            addr,                                  # original case, never lowered
            rec["sym"],
            safe_float(p.get("priceUsd")),
            li,
            safe_float(p.get("volume", {}).get("h24", 0)),
            (b24 / (b24 + s24) * 100) if (b24 + s24) else 50.0,
            (b5 / (b5 + s5) * 100) if (b5 + s5) else 50.0,
            now_ts - rec["first_ts"],              # age at sample time
            rec["score0"],
            rec["liq0"],
            li <= 0.0,                             # pool emptied
            rec["miss"],                           # consecutive misses BEFORE
                                                  # this sample; lets the analyzer
                                                  # classify a window by the miss
                                                  # count at that moment, not by
                                                  # the token's final value
        ])

    if rows:
        with open(COHORT_CSV_PATH, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerows(rows)
    save_cohort_state()
    # Observation rate is the health metric. If this drops, BATCH_SIZE is
    # too high again (or the API is throttling) and miss will poison.
    rate = len(rows) / len(active) * 100.0 if active else 0.0
    print(f"[cohort] {len(rows)}/{len(active)} = {rate:.0f}% observed, "
          f"{len(COHORT)} active, {len(failed)} api-failed", flush=True)
    return len(rows)


if __name__ == "__main__":
    load_cohort_state()
    init_cohort_csv()
    print(f"cohort ready: {len(COHORT)} members, csv at {COHORT_CSV_PATH}")
