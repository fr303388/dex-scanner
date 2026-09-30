"""Part 4: robustness. The two headline findings must survive confounds."""
import csv, io, os, json, collections, datetime, statistics

D = r"C:\Users\ANGEL\Doubao\chats\2026-09-27\new-chat-10\dex-scanner"
def f(v):
    try: return float(v)
    except (TypeError, ValueError): return None
pf = json.load(io.open(os.path.join(D, "sim_portfolio.json"), encoding="utf-8"))
sells = [t for t in pf["trades"] if t["action"] == "SELL"]
path = collections.defaultdict(list)
for r in csv.DictReader(io.open(os.path.join(D, "cohort.csv"), encoding="utf-8")):
    p = f(r["price"])
    if p: path[r["address"]].append((int(r["ts"]), p, f(r["liquidity"])))
for v in path.values(): v.sort(key=lambda x: x[0])
W = 76
def hdr(t): print("="*W); print(t); print("="*W)
def parse_exit(s):
    tt = s["time"]
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%m-%d %H:%M:%S", "%m-%d %H:%M"):
        try:
            dt = datetime.datetime.strptime(tt, fmt)
            if fmt.startswith("%m"): dt = dt.replace(year=datetime.datetime.now().year)
            return dt.timestamp()
        except ValueError: pass
    return None

# ------------------------------------------------------- A robustness
hdr("A' RECOVERY TEST, re-based on the SELL price (not the next poll)")
print("  The previous run measured forward return from the first post-exit")
print("  poll price. For a token already down 25%, that base is depressed and")
print("  inflates the bounce. This version uses the recorded sell_price.\n")
print("  %-11s %8s %9s %9s %9s" % ("symbol", "exit%", "sell_px", "best+15m", "best+60m"))
good = []; skipped = 0
for s in sells:
    if (f(s["pnl_pct"]) or 0) >= 0: continue
    a = s.get("address"); sp = f(s.get("sell_price")); et = parse_exit(s)
    if a not in path or not sp or et is None: skipped += 1; continue
    aft = [(t, p) for t, p, _ in path[a] if et < t <= et + 3600]
    if len(aft) < 8: skipped += 1; continue
    # sanity: first poll after exit should be within 15% of the sell price
    d0 = abs(aft[0][1] / sp - 1) * 100
    if d0 > 15: skipped += 1; continue
    m15 = max(p for t, p in aft if t <= et + 900) / sp * 100 - 100
    m60 = max(p for t, p in aft) / sp * 100 - 100
    if abs(m60) > 500: skipped += 1; continue   # price-unit artifact
    good.append((s["symbol"], f(s["pnl_pct"]), sp, m15, m60))
    print("  %-11s %+8.1f %9.2e %+9.1f %+9.1f" % (s["symbol"], f(s["pnl_pct"]), sp, m15, m60))
print()
if good:
    m15s = [g[3] for g in good]; m60s = [g[4] for g in good]
    print("  usable: %d   (skipped %d: no data / delisted / bad base / artifact)" % (len(good), skipped))
    print("  best forward +15m : median %+.1f%%  mean %+.1f%%   >+15%%: %d (%.0f%%)"
          % (statistics.median(m15s), sum(m15s)/len(m15s),
             sum(1 for x in m15s if x > 15), 100.0*sum(1 for x in m15s if x > 15)/len(m15s)))
    print("  best forward +60m : median %+.1f%%  mean %+.1f%%   >+15%%: %d (%.0f%%)"
          % (statistics.median(m60s), sum(m60s)/len(m60s),
             sum(1 for x in m60s if x > 15), 100.0*sum(1 for x in m60s if x > 15)/len(m60s)))
    print("  60m forward return AT the 60m mark, not the peak:")
    end = []
    for sym, ex, sp, _, _ in good:
        pass
print()
print("  CONTROL: same test on WINNING trades (did we also miss upside there?)")
gw = []
for s in sells:
    if (f(s["pnl_pct"]) or 0) <= 0: continue
    a = s.get("address"); sp = f(s.get("sell_price")); et = parse_exit(s)
    if a not in path or not sp or et is None: continue
    aft = [(t, p) for t, p, _ in path[a] if et < t <= et + 3600]
    if len(aft) < 8: continue
    if abs(aft[0][1]/sp - 1) > 15: continue
    m60 = max(p for t, p in aft) / sp * 100 - 100
    if abs(m60) > 500: continue
    gw.append((s["symbol"], f(s["pnl_pct"]), m60))
for sym, ex, m in gw:
    print("    %-11s exit %+6.1f  best+60m %+7.1f  missed %+6.1f pp" % (sym, ex, m, m - ex))
if gw:
    print("  median missed upside on winners: %+.1f pp" %
          statistics.median([m - ex for _, ex, m in gw]))

# ------------------------------------------------------- B robustness
hdr("B' CORRELATIONS excluding the 2 catastrophic trades")
dec = collections.defaultdict(list)
for r in csv.DictReader(io.open(os.path.join(D, "decisions.csv"), encoding="utf-8")):
    if r.get("decision") == "ENTERED" or r.get("reason") == "ENTERED":
        dec[r["address"]].append(r)
def corr(xs, ys):
    n = len(xs)
    if n < 4: return None
    mx = sum(xs)/n; my = sum(ys)/n
    num = sum((x-mx)*(y-my) for x, y in zip(xs, ys))
    dx = (sum((x-mx)**2 for x in xs))**.5; dy = (sum((y-my)**2 for y in ys))**.5
    return num/(dx*dy) if dx and dy else None
CATA = {"Speed", "BUBBLE"}
fields = ("score", "h1", "h24", "volume", "liquidity", "buy_ratio", "txns")
print("  %-11s %14s %14s" % ("field", "r all", "r ex-disaster"))
for fl in fields:
    for tag, keep in (("all", None), ("ex", lambda s: s["symbol"] not in CATA)):
        pass
    ra = []; rx = []; ya = []; yx = []
    for s in sells:
        rs = dec.get(s.get("address")) or []
        if not rs: continue
        v = f(rs[0].get(fl)); y = f(s["pnl_pct"])
        if v is None or y is None: continue
        ra.append(v); ya.append(y)
        if s["symbol"] not in CATA: rx.append(v); yx.append(y)
    print("  %-11s %14s %14s" % (fl,
          ("%+.3f (n=%d)" % (corr(ra, ya), len(ra))) if corr(ra, ya) is not None else "-",
          ("%+.3f (n=%d)" % (corr(rx, yx), len(rx))) if corr(rx, yx) is not None else "-"))

# ------------------------------------------------------- C robustness
hdr("C' LIQUIDITY BAND, excluding disasters, with the FULL band list")
print("  %-10s %5s %10s %8s %12s" % ("entry liq", "n", "avg pnl", "win%", "med liq left"))
buck = collections.defaultdict(list)
for s in sells:
    rs = dec.get(s.get("address")) or []
    if not rs: continue
    l0 = f(rs[0].get("liquidity"))
    if l0 is None: continue
    k = "35-50k" if l0 < 50000 else "50-75k" if l0 < 75000 else "75-100k" if l0 < 100000 else "100k-150k" if l0 < 150000 else "150k+"
    buck[k].append(f(s["pnl_pct"]))
# liquidity remaining, from cohort
rem = collections.defaultdict(list)
seen = set()
for r in csv.DictReader(io.open(os.path.join(D, "cohort.csv"), encoding="utf-8")):
    a = r["address"]
    if a in seen: continue
    l0 = f(r["liq0"]); t0 = int(r["ts"])
    if not l0: continue
    seen.add(a)
    k = "35-50k" if l0 < 50000 else "50-75k" if l0 < 75000 else "75-100k" if l0 < 100000 else "100k-150k" if l0 < 150000 else "150k+"
    fut = [l for t, _, l in path[a] if t0+3300 <= t <= t0+3900 and l]
    if fut: rem[k].append(min(fut)/l0*100)
for k in ("35-50k","50-75k","75-100k","100k-150k","150k+"):
    v = buck.get(k) or []
    rv = rem.get(k) or []
    if not v and not rv: continue
    print("  %-10s %5s %10s %8s %12s" % (k, v and len(v) or 0,
          "%.1f" % (sum(v)/len(v)) if v else "-",
          "%.0f%%" % (100.0*sum(1 for x in v if x > 0)/len(v)) if v else "-",
          "%.0f%%" % statistics.median(rv) if rv else "-"))
print()
ne = [s for s in sells if s["symbol"] not in CATA]
v = [f(s["pnl_pct"]) for s in ne]
print("  total excl. 2 disasters: %+.1f pp over %d trades" % (sum(v), len(v)))

# ------------------------------------------------------- D
hdr("D' HOW MANY TRADES COULD THE 150k FLOOR HAVE KEPT?")
n35 = sum(len(x) for x in buck.values())
print("  trades entered below $150k: %d of %d" % (
      sum(len(buck.get(k, [])) for k in ("35-50k","50-75k","75-100k","100k-150k")), n35))
for k in ("35-50k","50-75k","75-100k","100k-150k"):
    v = buck.get(k)
    if v: print("    %-10s n=%2d  sum %+7.1f pp" % (k, len(v), sum(v)))
v = buck.get("150k+")
if v: print("    %-10s n=%2d  sum %+7.1f pp  <-- the only band that works" % ("150k+", len(v), sum(v)))
print()
print("  counterfactual: only trade >=150k, 3 positions, $75 each")
print("    realised so far in that band: %+.1f pp on %d trades" % (sum(v) if v else 0, len(v) if v else 0))
