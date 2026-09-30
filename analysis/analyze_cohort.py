"""Cohort forward-return analysis. Uncensored within the admitted population.

What this fixes vs analyze.py
-----------------------------
decisions.csv only logs tokens that are in the trending feed at that instant,
so a token that left the feed before the forward horizon completed was dropped.
Measured survival there was 0.1-2.7%, which made every bucket comparison
meaningless. The cohort polls each admitted token independently for COHORT_TTL,
so samples survive the feed leaving. A token that genuinely dies is counted as
DEAD instead of vanishing.

What it still cannot answer
---------------------------
* It only covers tokens the scanner actually saw (recently trending ones), so
  conclusions do NOT generalise to all Solana memecoins.
* Forward returns remain conditional on the token being observable at t0+W.
  That is why the DEAD-rate table is the primary output, not the return table:
  a dead token contributes a row to the death table and cannot contribute an
  inflated return to the other one.

Usage:  python analyze_cohort.py [cohort.csv]
"""
import csv, io, os, sys, json, collections, bisect, statistics

HERE = os.path.dirname(os.path.abspath(__file__))
CSV = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "cohort.csv")

TTL = 4 * 3600
EXPIRY_GRACE = 120
MISS_DEAD = 5
# addr -> cohort record, loaded from cohort_state.json. The current miss
# count and the seen_once flag both live here, never in cohort.csv.
STATE = {}
WINDOWS = (45, 60, 90, 120)


def p(*a):
    print(*a)


def med(v):
    v = sorted(v)
    return v[len(v) // 2] if v else float("nan")


def load():
    if not os.path.exists(CSV):
        sys.exit(f"not found: {CSV}")
    by = collections.defaultdict(list)
    with io.open(CSV, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            try:
                by[r["address"]].append({
                    "ts": int(r["ts"]), "px": float(r["price"]),
                    "liq": float(r["liquidity"]), "vol": float(r["volume_h24"]),
                    "br24": float(r["br_h24"]), "br5": float(r["br_m5"]),
                    "age": int(r["age_sec"]), "score0": float(r["score0"]),
                    "liq0": float(r["liq0"]),
                    "nolq": r["no_liquidity"] == "True",
                    "miss": int(r["miss"]),
                })
            except (ValueError, KeyError):
                pass
    for v in by.values():
        v.sort(key=lambda x: x["ts"])
    by = {a: v for a, v in by.items() if v}

    # Tokens the scanner admitted but the poll never observed even once.
    # fetch_tokens' GMGN supplement deliberately adds tokens DexScreener does
    # NOT index (it only fills gaps: `if addr in seen_addr: continue`), and
    # DexScreener answers {"pairs": null} for those. They are untrackable,
    # not dead -- counting them as DEAD inflates the death rate, which is the
    # primary output here.
    not_indexed = []
    st = {}
    sp = os.path.join(os.path.dirname(os.path.abspath(CSV)), "cohort_state.json")
    if os.path.exists(sp):
        st = json.load(io.open(sp, encoding="utf-8"))
        not_indexed = [(v.get("sym", "?"), a, v.get("liq0", 0))
                       for a, v in st.items() if a not in by]
    STATE.clear()
    STATE.update(st)
    return by, not_indexed


def outcome(g, times, t_target, addr=None):
    """Classify what happened at t_target for this token.

    Order matters. EXPIRED (we stopped watching) is a stronger explanation
    than DEAD, and PENDING (the window has not closed yet) is stronger than
    both -- it must be checked before any 'no data' conclusion, otherwise a
    young dataset reports 100% anomalies.
    """
    # The authoritative miss count lives in cohort_state.json, not in the
    # csv. The csv only ever carried the value from BEFORE the sample that
    # row belongs to, so classifying from it could never distinguish DEAD
    # from UNRESOLVED. See analysis/README.md.
    rec = STATE.get(addr) or {}
    cur_miss = int(rec.get("miss", 0) or 0)
    seen_once = bool(rec.get("seen_once", False))

    j = bisect.bisect_left(times, t_target)
    if j < len(g) and g[j]["ts"] - t_target <= 300:
        return "ALIVE", g[j]["px"]
    # No observation at t_target. First ask whether the window has even closed.
    if t_target > g[-1]["ts"]:
        return "PENDING", None          # not enough elapsed time yet
    # The window has closed and we still have nothing. Why?
    last = g[j - 1] if j > 0 else g[-1]
    if last["age"] >= TTL - EXPIRY_GRACE:
        return "EXPIRED", last["px"]   # we stopped watching
    if cur_miss >= MISS_DEAD and seen_once:
        return "DEAD", last["px"]      # was indexed, then disappeared
    if cur_miss >= MISS_DEAD:
        # Never returned by DexScreener even once. It came from the scanner's
        # GMGN supplement, which by design only adds tokens DexScreener lacks.
        # Not a death -- the token was never observable.
        return "UNTRACKABLE", None
    if cur_miss >= 1:
        return "UNRESOLVED", last["px"]  # API gap, not a death
    return "GONE", last["px"]          # answered, miss=0, yet no row: anomaly


def bucket(s):
    return ("6+" if s >= 6 else "5-6" if s >= 5 else "3-5" if s >= 3 else "<3")


def main():
    ser, not_indexed = load()
    rows = sum(len(v) for v in ser.values())
    span = max(v[-1]["ts"] for v in ser.values()) - min(v[0]["ts"] for v in ser.values())
    p("=" * 76)
    p("COHORT ANALYSIS")
    p("=" * 76)
    p("  file        : %s" % CSV)
    p("  tokens      : %d      samples: %d" % (len(ser), rows))
    p("  wall span   : %.1f h" % (span / 3600.0))
    if not ser:
        return
    ages = [v[-1]["age"] for v in ser.values()]
    p("  token age   : p50 %ds  max %ds  (TTL %ds)" % (med(ages), max(ages), TTL))
    p()
    p("  SCOPE: tokens the scanner saw in the recent trending feed only.")
    p("  Conclusions do NOT generalise to all Solana memecoins.")
    p()
    if not_indexed:
        p("  !! UNTRACKABLE: %d admitted token(s) were never observed once." % len(not_indexed))
        p("     DexScreener does not index them (returns {\"pairs\": null}).")
        p("     They come from the scanner's GMGN supplement, which by design")
        p("     only adds tokens DexScreener lacks. They are EXCLUDED from the")
        p("     DEAD rate below -- counting them would inflate it.")
        p("     e.g. %s" % ", ".join(x[0] for x in not_indexed[:8]))
        p()

    # ---------- section 1: outcome taxonomy (survivorship-free) ----------
    p("=" * 76)
    p("1  OUTCOME TAXONOMY  -- every admitted sample, no survivor filtering")
    p("=" * 76)
    for W in WINDOWS:
        H = W * 60
        tally = collections.defaultdict(collections.Counter)
        noletq = collections.defaultdict(collections.Counter)
        for a, g in ser.items():
            times = [x["ts"] for x in g]
            last_taken = None
            for i, x in enumerate(g):
                if last_taken is not None and x["ts"] - last_taken < H:
                    continue
                o, _ = outcome(g, times, x["ts"] + H, a)
                b = bucket(x["score0"])
                tally[b][o] += 1
                if x["nolq"]:
                    noletq[b][o] += 1
                last_taken = x["ts"]
        p("  --- +%d min (non-overlapping) ---" % W)
        hdr = ["ALIVE", "DEAD", "UNTRACKABLE", "UNRESOLVED", "EXPIRED", "GONE",
               "PENDING"]
        p("     %-6s %7s " % ("score0", "closed") + "".join("%12s" % h for h in hdr))
        tots = collections.Counter()
        pend = collections.Counter()
        for b in ("<3", "3-5", "5-6", "6+"):
            c = tally[b]
            t = sum(v for k, v in c.items() if k != "PENDING")
            for k, v in c.items():
                if k == "PENDING":
                    pend[b] += v
                else:
                    tots[k] += v
            if t + pend[b] == 0:
                continue
            p("     %-6s %7d " % (b, t) + "".join("%12d" % c.get(h, 0) for h in hdr))
        T = sum(tots.values())
        p("     %-6s %7d " % ("ALL", T) + "".join("%12d" % tots.get(h, 0) for h in hdr))
        p("     %-6s %7s " % ("rate", "") + "".join("%11.1f%%" % (100.0*tots.get(h, 0)/T) if T else ""
                                                   for h in hdr))
        p("     PENDING (window not closed yet, excluded from rates): %d" % sum(pend.values()))
        if T < 20:
            p("     -> only %d closed samples; treat as a smoke test, not a result." % T)
        p()

    # ---------- section 2: forward return, ALIVE only ----------
    p("=" * 76)
    p("2  FORWARD RETURN by score0, ALIVE only")
    p("   (conditioned on surviving -- read section 1 alongside this)")
    p("=" * 76)
    for W in WINDOWS:
        H = W * 60
        B = collections.defaultdict(list)
        base = []
        for a, g in ser.items():
            times = [x["ts"] for x in g]
            last_taken = None
            for i, x in enumerate(g):
                if last_taken is not None and x["ts"] - last_taken < H:
                    continue
                o, px = outcome(g, times, x["ts"] + H, a)
                last_taken = x["ts"]
                if o != "ALIVE" or not px:
                    continue
                r = (px / x["px"] - 1) * 100
                base.append(r)
                B[bucket(x["score0"])].append(r)
        if not base:
            p("  +%d min: no ALIVE samples yet" % W); p(); continue
        bm = med(base)
        p("  --- +%d min ---  baseline n=%d  median %+.2f%%  win %.0f%%"
          % (W, len(base), bm, 100.0*sum(1 for x in base if x > 0)/len(base)))
        for b in ("6+", "5-6", "3-5", "<3"):
            v = B.get(b, [])
            if len(v) < 5:
                p("     %-5s n=%-4d (too few)" % (b, len(v))); continue
            p("     %-5s n=%-4d median %+8.2f%%  excess %+8.2f%%  win %3.0f%%"
              % (b, len(v), med(v), med(v)-bm, 100.0*sum(1 for x in v if x > 0)/len(v)))
        p()

    # ---------- section 3: br_h24 vs br_m5 ----------
    p("=" * 76)
    p("3  br_h24 vs br_m5 as predictors  (the lagging-aggregate question)")
    p("=" * 76)
    for key, label in (("br24", "br_h24 (24h aggregate)"), ("br5", "br_m5 (5 min)")):
        B = collections.defaultdict(list)
        for W in (60, 120):
            H = W * 60
            b = collections.defaultdict(list)
            for a, g in ser.items():
                times = [x["ts"] for x in g]
                lt = None
                for x in g:
                    if lt is not None and x["ts"] - lt < H: continue
                    o, px = outcome(g, times, x["ts"] + H, a)
                    lt = x["ts"]
                    if o != "ALIVE" or not px: continue
                    b[(x[key] < 52)].append((px/x["px"]-1)*100)
            row = []
            for lo, hi, name in ((True, False, "<52%"), (False, True, ">=52%")):
                v = b.get(lo, [])
                row.append("%s n=%-4d med %+7.2f%%" % (name, len(v), med(v)) if len(v) >= 3
                           else "%s n=%-3d (few)" % (name, len(v)))
            p("  +%3d min  %-24s  %s" % (W, label, "   |   ".join(row)))
    p()

    # ---------- section 4: liquidity trajectory ----------
    p("=" * 76)
    p("4  ENTRY LIQUIDITY vs OUTCOME  (is liq0 predictive of dying?)")
    p("=" * 76)
    p("  %-14s %6s %8s %9s %9s" % ("liq0 band", "n", "median", "DEAD%", "NO_LIQ%"))
    for lo, hi, name in ((0, 35000, "<35k"), (35000, 75000, "35-75k"),
                         (75000, 300000, "75-300k"), (300000, 1e18, ">300k")):
        n = d = nl = 0
        for a, g in ser.items():
            if not (lo <= g[0]["liq0"] < hi):
                continue
            n += 1
            times = [x["ts"] for x in g]
            o, _ = outcome(g, times, g[0]["ts"] + 7200, a)
            if o == "DEAD":
                d += 1
            if any(x["nolq"] for x in g):
                nl += 1
        if n:
            p("  %-14s %6d %8s %8.0f%% %8.0f%%" % (name, n, "-", 100.0*d/n, 100.0*nl/n))
    p()
    p("  (DEAD% here is 'outcome at +120min'. Tokens still being watched are")
    p("   UNRESOLVED, not DEAD -- treat the early numbers as a lower bound.)")


if __name__ == "__main__":
    main()
