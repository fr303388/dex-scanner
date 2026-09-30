"""One-command cohort health check. Run this at the 90-minute mark.

Covers the four acceptance items plus an explicit alert on false DEAD.
Read-only. Lives outside the project dir.
"""
import csv, io, os, sys, json, collections, bisect, datetime

D = r"C:\Users\ANGEL\Doubao\chats\2026-09-27\new-chat-10\dex-scanner"
CSV = os.path.join(D, "cohort.csv")
STATE = os.path.join(D, "cohort_state.json")
LOG = os.path.join(D, "server_run.log")
TTL, GRACE, MISS_DEAD, W = 4 * 3600, 120, 5, 3600

def ok(cond, good, bad):
    return ("  OK   " if cond else "  !!   ") + (good if cond else bad)

# ---- 1. observation rate, from the log -------------------------------------
rates, fails = [], 0
if os.path.exists(LOG):
    for line in io.open(LOG, encoding="utf-8", errors="replace"):
        if "[cohort]" in line and "observed" in line:
            try:
                rates.append(int(line.split("=")[1].strip().split("%")[0]))
            except (IndexError, ValueError):
                pass
        if "fetch error" in line:
            fails += 1

# ---- 2/3. classification ---------------------------------------------------
by = collections.defaultdict(list)
if os.path.exists(CSV):
    for r in csv.DictReader(io.open(CSV, encoding="utf-8")):
        try:
            by[r["address"]].append({
                "ts": int(r["ts"]), "px": float(r["price"]),
                "age": int(r["age_sec"]), "miss": int(r["miss"]),
                "score0": float(r["score0"]), "liq0": float(r["liq0"]),
                "nolq": r["no_liquidity"] == "True"})
        except (ValueError, KeyError):
            pass
for v in by.values():
    v.sort(key=lambda x: x["ts"])

def outcome(g, times, tgt):
    j = bisect.bisect_left(times, tgt)
    if j < len(g) and g[j]["ts"] - tgt <= 300:
        return "ALIVE"
    if tgt > g[-1]["ts"]:
        return "PENDING"
    last = g[j-1] if j > 0 else g[-1]
    if last["age"] >= TTL - GRACE:
        return "EXPIRED"
    if last["miss"] >= MISS_DEAD:
        return "DEAD"
    if last["miss"] >= 1:
        return "UNRESOLVED"
    return "GONE"

closed = collections.Counter()
for a, g in by.items():
    times = [x["ts"] for x in g]
    lt = None
    for x in g:
        if lt is not None and x["ts"] - lt < W:
            continue
        lt = x["ts"]
        closed[outcome(g, times, x["ts"] + W)] += 1

# ---- 4. NO_LIQ by entry liquidity -----------------------------------------
nolq = collections.defaultdict(lambda: [0, 0])
for a, g in by.items():
    b = ("<35k" if g[0]["liq0"] < 35000 else "35-75k" if g[0]["liq0"] < 75000
         else "75-300k" if g[0]["liq0"] < 300000 else ">300k")
    nolq[b][0] += 1
    if any(x["nolq"] for x in g):
        nolq[b][1] += 1

# ---- miss distribution -----------------------------------------------------
missd = collections.Counter()
n_state = 0
untrack = 0
tracked = set(by)
if os.path.exists(STATE):
    st = json.load(io.open(STATE, encoding="utf-8"))
    missd = collections.Counter(v.get("miss", 0) for v in st.values())
    n_state = len(st)
    untrack = sum(1 for a in st if a not in tracked)
bad = sum(v for k, v in missd.items() if k >= MISS_DEAD)

print("=" * 70)
print("COHORT HEALTH  --  %s" % datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))
print("=" * 70)
span = (max(v[-1]["ts"] for v in by.values()) - min(v[0]["ts"] for v in by.values())) if by else 0
print("  tokens %d   samples %d   span %.0f min"
      % (len(by), sum(len(v) for v in by.values()), span / 60.0))
print()
print("1  OBSERVATION RATE")
if rates:
    print(ok(min(rates[-8:]) >= 90,
              "last 8 polls: %s  (min %d%%)" % (rates[-8:], min(rates[-8:])),
              "DROPPED below 90%%: %s" % rates[-8:]))
else:
    print("  ??  no '[cohort] ... observed' lines in the log")
print(ok(fails == 0, "0 API fetch errors", "%d API fetch errors" % fails))
print()
print("2/3  CLASSIFICATION at +%d min" % (W // 60))
for k in ("ALIVE", "DEAD", "UNRESOLVED", "EXPIRED", "GONE", "PENDING"):
    print("     %-11s %5d" % (k, closed.get(k, 0)))
c = sum(closed.get(k, 0) for k in ("ALIVE", "DEAD", "UNRESOLVED", "EXPIRED", "GONE"))
print(ok(c > 0, "%d closed samples" % c,
          "0 closed samples -- window has not elapsed, or age_sec is wrong"))
print(ok(closed.get("GONE", 0) <= 2, "GONE <= 2 (normal)",
          "GONE = %d -- anomaly, check miss column and BATCH_SIZE" % closed.get("GONE", 0)))
print()
print("4  NO_LIQ by entry liquidity")
for b in ("<35k", "35-75k", "75-300k", ">300k"):
    n, k = nolq.get(b, [0, 0])
    if n:
        print("     %-8s n=%-4d NO_LIQ %3.0f%%%s" % (b, n, 100.0*k/n, "   (small n)" if n < 30 else ""))
print()
print("MISS DISTRIBUTION  %s" % dict(sorted(missd.items())))
print(ok(bad <= untrack, "no false DEAD",
          "ALERT: %d at miss >= %d, %d untrackable, %d genuinely suspicious"
          % (bad, MISS_DEAD, untrack, bad - untrack)))
print("     untrackable: %d of %d admitted (%.1f%%) -- GMGN-sourced tokens that"
      % (untrack, n_state, 100.0*untrack/max(1, n_state)))
print("     DexScreener never indexed; excluded from the DEAD rate.")
print("=" * 70)
