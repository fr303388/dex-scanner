"""GeckoTerminal enrichment for cohort members.

Why
---
Insentos' published screening criteria (the widely-shared "100x hunt"
checklist) lean on two things this project has never measured:
  - buyers count  (unique buyers, not transaction count)  -> his "Num Buys >= 1"
  - pump.fun graduation percentage -> his New Pairs / Final Stretch / Migrated
DexScreener, which the scanner already uses, gives txns.*.buys (transaction
count) but NOT unique buyers, and has no concept of launchpad migration.

GeckoTerminal's free API supplies both. It is recorded here purely as data.
Nothing in this module changes trading behaviour.

Hard constraints, measured not assumed
--------------------------------------
The free tier is aggressive about rate limits. Measured on this host:
    0.5s between calls -> 0/6 succeeded (all HTTP 429)
    1.5s             -> 0/6
    3.0s             -> 1/6
    6.0s             -> 3/6
Comma-batched multi-address paths return 404, so batching is unavailable.

Required volume is small: after the $150k entry floor, roughly 22-27
distinct tokens per day clear the gate, and each is enriched exactly once.
That averages about 1.1 calls/hour, so the design is deliberately
best-effort: enrich once, cache forever, back off hard on 429, and never
let a failure reach the scan cycle.

Storage is a SEPARATE file. cohort.csv has a fixed 13-column header that
several analysis scripts depend on; widening it would break them, and
rewriting the file is forbidden by the cohort design rules.
"""
import csv
import json
import os
import time

import requests

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GT_CSV_PATH = os.path.join(BASE_DIR, "cohort_gt.csv")

GT_URL = ("https://api.geckoterminal.com/api/v2/networks/solana/tokens/"
          "%s")
GT_POOLS_URL = ("https://api.geckoterminal.com/api/v2/networks/solana/"
                "tokens/%s/pools")

GT_HEADER = ["ts", "time", "address", "symbol",
             "buyers_m5", "buys_m5", "sells_m5",
             "buyers_h1", "buys_h1", "sells_h1",
             "buyers_h24", "buys_h24", "sells_h24",
             "volume_usd_m5", "volume_usd_h1",
             "graduation_pct", "launchpad_completed"]

# Rate limiting. One call per MAX_CALLS_PER_CYCLES scan cycles keeps the
# average near 1 call/hour at the bot's cadence, which is the only volume
# the free tier tolerated in testing.
MAX_CALLS_PER_CYCLES = 45
CALL_TIMEOUT = 12
BACKOFF_START = 300       # 5 min after the first 429
BACKOFF_MAX = 3600        # never back off longer than 1h
BACKOFF_DECAY = 0.5       # halve the penalty after each success

ENRICHED: set = set()     # addresses already enriched, survives restarts
_gt_backoff_until = 0.0
_gt_failures = 0
_gt_cycle = 0
_gt_stats = {"ok": 0, "429": 0, "other": 0, "skipped_backoff": 0}


def _load_enriched():
    """Recover the enriched set so restarts do not re-burn API quota."""
    global ENRICHED
    if not os.path.exists(GT_CSV_PATH):
        return
    try:
        with open(GT_CSV_PATH, "r", newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                a = r.get("address")
                if a:
                    ENRICHED.add(a)
    except Exception as e:
        print(f"[gt] could not load enriched set: {e}")


def init_gt_csv():
    if os.path.exists(GT_CSV_PATH):
        return
    try:
        with open(GT_CSV_PATH, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(GT_HEADER)
    except OSError as e:
        print(f"[gt] csv init failed: {e}")


def gt_stats():
    return dict(_gt_stats)


def _sf(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _write_row(row):
    try:
        with open(GT_CSV_PATH, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(row)
    except OSError as e:
        print(f"[gt] write failed: {e}")


def _extract(addr, tok_attrs, pool_attrs):
    """Merge the two endpoints.

    Measured split, do not expect either one to carry everything:
        /tokens/<a>       launchpad_details  YES   transactions  EMPTY
        /tokens/<a>/pools transactions       YES   launchpad     ABSENT
    Whichever call succeeded contributes what it has; the rest stays None.
    """
    tok_attrs = tok_attrs or {}
    pool_attrs = pool_attrs or {}

    tx = pool_attrs.get("transactions") or tok_attrs.get("transactions") or {}
    m5 = tx.get("m5") or {}
    h1 = tx.get("h1") or {}
    h24 = tx.get("h24") or {}
    vol = pool_attrs.get("volume_usd") or tok_attrs.get("volume_usd") or {}
    lp = tok_attrs.get("launchpad_details") or {}

    return [
        addr,
        tok_attrs.get("symbol") or pool_attrs.get("name") or "?",
        m5.get("buyers"), m5.get("buys"), m5.get("sells"),
        h1.get("buyers"), h1.get("buys"), h1.get("sells"),
        h24.get("buyers"), h24.get("buys"), h24.get("sells"),
        vol.get("m5"), vol.get("h1"),
        lp.get("graduation_percentage"),
        lp.get("completed"),
    ]


def _fetch(url, addr):
    """Return (payload_attrs, status). Never raises.

    status: "ok" | "429" | "fail"
    """
    try:
        r = requests.get(url, timeout=CALL_TIMEOUT,
                         headers={"Accept": "application/json",
                                  "User-Agent": "Mozilla/5.0"})
    except Exception:
        return None, "fail"
    if r.status_code == 429:
        return None, "429"
    if r.status_code != 200:
        return None, "fail"
    try:
        data = (r.json() or {}).get("data")
    except Exception:
        return None, "fail"
    if isinstance(data, list):
        data = data[0] if data else None
    if not data:
        return None, "fail"
    return data.get("attributes") or {}, "ok"


def _backoff_ok():
    global _gt_failures, _gt_backoff_until
    if time.time() < _gt_backoff_until:
        _gt_stats["skipped_backoff"] += 1
        return False
    return True


def _note_success():
    """A success means the limit is probably per-window, so ease off the penalty."""
    global _gt_backoff_until, _gt_failures
    _gt_failures = 0
    _gt_backoff_until = 0.0


def _note_429():
    """Escalating penalty. The free tier gives no Retry-After, so back off
    on our own schedule rather than hammering it."""
    global _gt_backoff_until, _gt_failures
    _gt_failures += 1
    _gt_stats["429"] += 1
    wait = min(BACKOFF_MAX, BACKOFF_START * (2 ** (_gt_failures - 1)))
    _gt_backoff_until = time.time() + wait
    if _gt_failures in (1, 3, 6):
        print(f"[gt] rate limited, backing off {wait}s "
              f"(failures={_gt_failures}, enriched={len(ENRICHED)})", flush=True)


def enrich_cohort(tokens, now_ts) -> int:
    """Enrich at most one unenriched cohort member. Never raises.

    Called from the scan cycle. Any failure here must not be able to stop
    trading, so every path returns quietly.
    """
    global _gt_cycle
    try:
        init_gt_csv()
        if not ENRICHED:
            _load_enriched()

        _gt_cycle += 1
        if _gt_cycle % MAX_CALLS_PER_CYCLES != 0:
            return 0
        if not _backoff_ok():
            return 0

        # pick the first token in the feed that is not yet enriched
        target = None
        for t in tokens or []:
            a = t.get("address")
            if a and a not in ENRICHED:
                target = a
                break
        if not target:
            return 0

        # Two calls: the token endpoint carries launchpad status, the pools
        # endpoint carries the buyer counts. Whichever succeeds is kept.
        tok, s1 = _fetch(GT_URL % target, target)
        if s1 == "429":
            _note_429()
            return 0
        pool, s2 = _fetch(GT_POOLS_URL % target, target)
        if s2 == "429":
            _note_429()

        if tok is None and pool is None:
            _gt_stats["other"] += 1
            # mark as seen so a permanently bad address is not retried
            # on every eligible cycle
            ENRICHED.add(target)
            return 0

        vals = _extract(target, tok, pool)
        _write_row([int(now_ts),
                    time.strftime("%Y-%m-%d %H:%M:%S")] + vals)
        ENRICHED.add(target)
        _gt_stats["ok"] += 1
        _note_success()
        print(f"[gt] enriched {vals[1]}  buyers_m5={vals[2]} buyers_h1={vals[5]} "
              f"graduation={vals[13]}  (total {len(ENRICHED)}, "
              f"tok={'ok' if tok else s1} pools={'ok' if pool else s2})", flush=True)
        return 1
    except Exception as e:
        # Never propagate. The scanner's trade path must not depend on this.
        _gt_stats["other"] += 1
        print(f"[gt] enrichment error (ignored): {type(e).__name__}: {e}", flush=True)
        return 0
