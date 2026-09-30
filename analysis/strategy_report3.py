"""Part 3: fix the post-exit recovery test + liquidity decay magnitude."""
import csv, io, os, json, collections, datetime, statistics

D = r"C:\Users\ANGEL\Doubao\chats\2026-09-27\new-chat-10\dex-scanner"
def f(v):
    try: return float(v)
    except (TypeError, ValueError): return None

pf = json.load(io.open(os.path.join(D, "sim_portfolio.json"), encoding="utf-8"))
sells = [t for t in pf["trades"] if t["action"] == "SELL"]

path = collections.defaultdict(list)
for r in csv.DictReader(io.open(os.path.join(D, "cohort.csv"), encoding="utf-8")):
    a = r["address"]; ts = int(r["ts"]); p = f(r["price"]); l = f(r["liquidity"])
    path[a].append((ts, p, l))
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

# ---------------------------------------------------------------- A
hdr("A  POST-STOPOUT RECOVERY  --  did the stop destroy signal?")
print("  For each losing SELL, best forward return of the SAME token in the")
print("  following 60 min, using the cohort price path.\n")
print("  %-11s %8s %9s %9s  %s" % ("symbol", "exit%", "best+15m", "best+60m", "verdict"))
stopped = [s for s in sells if (f(s["pnl_pct"]) or 0) < 0]
rec15 = rec60 = 0; checked = 0; f60 = []; f15 = []
for s in stopped:
    a = s.get("address")
    if a not in path: continue
    et = parse_exit(s)
    if et is None: continue
    aft = [(t, p) for t, p, _ in path[a] if et < t <= et + 3600]
    if len(aft) < 8: continue
    p0 = aft[0][1]
    m15 = max(p for t, p in aft if t <= et + 900) / p0 * 100 - 100
    m60 = max(p for t, p in aft) / p0 * 100 - 100
    checked += 1; f15.append(m15); f60.append(m60)
    up = m60 > 15
    if up: rec60 += 1
    if m15 > 15: rec15 += 1
    print("  %-11s %+8.1f %+9.1f %+9.1f  %s" % (s["symbol"], f(s["pnl_pct"]),
          m15, m60, "STOUP" if up else ""))
print()
if checked:
    print("  stopped-out trades with usable forward data : %d / %d" % (checked, len(stopped)))
    print("  rose >+15%% within 15 min of the stop : %d  (%.0f%%)" % (rec15, 100.0*rec15/checked))
    print("  rose >+15%% within 60 min of the stop : %d  (%.0f%%)" % (rec60, 100.0*rec60/checked))
    print("  median best forward 15m : %+.1f%%" % statistics.median(f15))
    print("  median best forward 60m : %+.1f%%" % statistics.median(f60))
    print("  mean   best forward 60m : %+.1f%%" % (sum(f60)/len(f60)))
else:
    print("  NO MATCHES -- check timestamp alignment")

# ---------------------------------------------------------------- B
hdr("B  LIQUIDITY DECAY  --  binary NO_LIQ hides the real damage")
print("  For every cohorted token, how much of its entry liquidity was left")
print("  60 min later?  The boolean no_liquidity column only sees 0 vs nonzero.\n")
print("  %-9s %7s %10s %10s %12s" % ("entry liq", "n", "median %", "mean %", "lost >50%"))
rows = collections.defaultdict(list)
seen = set()
for r in csv.DictReader(io.open(os.path.join(D, "cohort.csv"), encoding="utf-8")):
    a = r["address"]
    if a in seen: continue
    l0 = f(r["liq0"]); t0 = int(r["ts"])
    if not l0 or l0 < 5000: continue
    seen.add(a)
    fut = [l for t, _, l in path[a] if t0 + 3300 <= t <= t0 + 3900 and l]
    if not fut: continue
    end = min(fut)
    k = "<35k" if l0 < 35000 else "35-75k" if l0 < 75000 else "75-150k" if l0 < 150000 else "150k+"
    rows[k].append(end / l0 * 100)
for k in ("<35k", "35-75k", "75-150k", "150k+"):
    v = rows.get(k)
    if not v: continue
    print("  %-9s %7d %9.0f%% %9.0f%% %11.0f%%" % (k, len(v),
          statistics.median(v), sum(v)/len(v),
          100.0*sum(1 for x in v if x < 50)/len(v)))
print()
print("  total tokens matched: %d" % sum(len(v) for v in rows.values()))

# ---------------------------------------------------------------- C
hdr("C  SCORE COMPONENT AUDIT  --  which inputs correlate with forward return?")
print("  Using the 34 real trades: correlate entry fields with pnl_pct.\n")
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
fields = ("score", "h1", "h24", "volume", "liquidity", "buy_ratio", "txns", "price")
print("  %-11s %5s %8s" % ("field", "n", "r vs pnl"))
for fl in fields:
    xs = []; ys = []
    for s in sells:
        rs = dec.get(s.get("address")) or []
        if not rs: continue
        v = f(rs[0].get(fl))
        if v is None: continue
        xs.append(v); ys.append(f(s["pnl_pct"]))
    r = corr(xs, ys)
    print("  %-11s %5d %8s" % (fl, len(xs), ("%+.3f" % r) if r is not None else "-"))
print()
print("  ...and vs MFE (the profit that was actually available):")
print("  %-11s %5s %8s" % ("field", "n", "r vs MFE"))
for fl in fields:
    xs = []; ys = []
    for s in sells:
        rs = dec.get(s.get("address")) or []
        if not rs: continue
        v = f(rs[0].get(fl))
        if v is None: continue
        xs.append(v); ys.append(f(s.get("mfe")))
    r = corr(xs, ys)
    print("  %-11s %5d %8s" % (fl, len(xs), ("%+.3f" % r) if r is not None else "-"))
