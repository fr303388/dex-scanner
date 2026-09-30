"""Part 2: does the stop-loss actually help? Plus MFE timing curve."""
import csv, io, os, json, collections, datetime, statistics, bisect

D = r"C:\Users\ANGEL\Doubao\chats\2026-09-27\new-chat-10\dex-scanner"
def f(v):
    try: return float(v)
    except (TypeError, ValueError): return None

pf = json.load(io.open(os.path.join(D, "sim_portfolio.json"), encoding="utf-8"))
sells = [t for t in pf["trades"] if t["action"] == "SELL"]

# cohort price path per address, for the post-exit recovery test
path = collections.defaultdict(list)
for r in csv.DictReader(io.open(os.path.join(D, "cohort.csv"), encoding="utf-8")):
    a = r["address"]; ts = int(r["ts"]); p = f(r["price"])
    if p: path[a].append((ts, p))
for v in path.values():
    v.sort(key=lambda x: x[0])

W = 76
def hdr(t): print("="*W); print(t); print("="*W)

# ---------------------------------------------------------------- A
hdr("A  POST-STOPOUT RECOVERY  --  did stopped-out tokens keep going up?")
print("  For every SELL, look at the token's cohort price path AFTER the exit")
print("  and compute the best forward return in the following 60 minutes.")
print("  If stopped-out tokens then ran +50%, the stop is destroying signal.\n")
print("  %-11s %8s %8s %8s %9s" % ("symbol", "exit%", "fwd+15", "fwd+60", "verdict"))
stopped = [s for s in sells if (f(s["pnl_pct"]) or 0) < 0]
recovered = 0; checked = 0; fwd60 = []
for s in stopped:
    a = s.get("address")
    if a not in path: continue
    tt = s["time"]
    exit_ts = None
    for cand in ("%s 00:00:00",):
        try: exit_ts = datetime.datetime.strptime(tt, "%Y-%m-%d %H:%M:%S").timestamp()
        except ValueError: pass
    if exit_ts is None:
        try: exit_ts = datetime.datetime.strptime(tt, "%Y-%m-%d %H:%M").timestamp()
        except ValueError: continue
    after = [(t, p) for t, p in path[a] if t > exit_ts and t <= exit_ts + 3600]
    if len(after) < 8: continue
    px0 = after[0][1]
    m15 = max(p for t, p in after if t <= exit_ts + 900) / px0 * 100 - 100
    m60 = max(p for t, p in after) / px0 * 100 - 100
    checked += 1; fwd60.append(m60)
    up = m60 > 15
    if up: recovered += 1
    print("  %-11s %+8.1f %+8.1f %+8.1f %9s" % (s["symbol"], f(s["pnl_pct"]),
          m15, m60, "STOUP" if up else "-"))
print()
if checked:
    print("  stopped-out trades with usable forward data : %d / %d" % (checked, len(stopped)))
    print("  of those, rose >+15%% within 60 min after the stop: %d  (%.0f%%)"
          % (recovered, 100.0*recovered/checked))
    print("  median best forward 60min return after a stop : %+.1f%%"
          % statistics.median(fwd60))
    print("  mean                                     : %+.1f%%" % (sum(fwd60)/len(fwd60)))

# ---------------------------------------------------------------- B
hdr("B  WHEN DOES THE MFE HAPPEN?  (all trades, 15s resolution)")
traj = collections.defaultdict(list)
for r in csv.DictReader(io.open(os.path.join(D, "trajectory.csv"), encoding="utf-8")):
    traj[r["address"]].append(r)
for v in traj.values(): v.sort(key=lambda x: int(x["ts"]))
sell_by_addr = {s["address"]: s for s in sells}

curve = {m: [] for m in (1, 2, 3, 5, 10, 15, 30, 60, 120)}
tpeak = []
for a, s in sell_by_addr.items():
    t = traj.get(a)
    if not t: continue
    t0 = int(t[0]["ts"]); p0 = f(t[0]["price"])
    if not p0: continue
    best_m, best_t = None, 0
    for r in t:
        p = f(r["price"])
        if not p: continue
        m = p / p0 * 100 - 100
        mins = (int(r["ts"]) - t0) / 60
        if best_m is None or m > best_m: best_m, best_t = m, mins
    if best_m is None or best_m <= 0: continue
    tpeak.append(best_t)
    for m in curve:
        win = [f(r["price"]) for r in t if (int(r["ts"]) - t0) / 60 <= m and f(r["price"])]
        if win: curve[m].append(max(win) / p0 * 100 - 100)
if curve[1]:
    print("  cumulative MFE available by time (n=%d trades with a positive MFE)" % len(curve[1]))
    print("  %-8s %8s %10s %10s" % ("by", "n", "mean MFE", "vs final"))
    fin = sum(curve[120] + curve[30]) / max(1, len(curve[120]) + len(curve[30]))
    for m in (1, 2, 3, 5, 10, 15, 30, 60, 120):
        v = curve[m]
        if not v: continue
        print("  %-8s %8d %9.1f%% %9.0f%%" % ("%d min" % m, len(v), sum(v)/len(v),
              100.0*sum(v)/len(v)/fin if fin else 0))
    if tpeak:
        print()
        print("  time of the MFE peak: median %.0f min, mean %.0f min" %
              (statistics.median(tpeak), sum(tpeak)/len(tpeak)))
        print("  peaks within 5 min  : %d (%.0f%%)" %
              (sum(1 for x in tpeak if x <= 5), 100.0*sum(1 for x in tpeak if x <= 5)/len(tpeak)))
        print("  peaks within 15 min : %d (%.0f%%)" %
              (sum(1 for x in tpeak if x <= 15), 100.0*sum(1 for x in tpeak if x <= 15)/len(tpeak)))

# ---------------------------------------------------------------- C
hdr("C  LOSERS DIE FAST  --  holding time by outcome")
for lo, hi, lbl in ((0,1,"0-2 min"),(2,6,"2-6 min"),(6,15,"6-15 min"),
                    (15,45,"15-45 min"),(45,1e9,"45+ min")):
    g = [s for s in sells if lo <= (f(s.get("held_min")) or 0) < hi]
    if not g: continue
    ps = [f(s["pnl_pct"]) for s in g]
    mf = [f(s.get("mfe")) or 0 for s in g]
    print("  %-8s n=%2d   avg pnl %7.1f   avg MFE %6.1f   win%% %3.0f"
          % (lbl, len(g), sum(ps)/len(g), sum(mf)/len(g),
             100.0*sum(1 for p in ps if p > 0)/len(g)))

# ---------------------------------------------------------------- D
hdr("D  ENTRY LIQUIDITY OF THE ACTUAL 34 TRADES  (cohort says <35k is toxic)")
ok = miss = 0
buck = collections.defaultdict(list)
for s in sells:
    a = s.get("address")
    li = None
    for r in csv.DictReader(io.open(os.path.join(D, "decisions.csv"), encoding="utf-8")):
        pass
    break
# cheaper: read decisions once
dec = collections.defaultdict(list)
for r in csv.DictReader(io.open(os.path.join(D, "decisions.csv"), encoding="utf-8")):
    if r.get("decision") == "ENTERED" or r.get("reason") == "ENTERED":
        dec[r["address"]].append(f(r["liquidity"]))
for s in sells:
    v = dec.get(s.get("address")) or []
    l0 = v[0] if v else None
    if l0 is None: continue
    k = "35-75k" if l0 < 75000 else "75-150k" if l0 < 150000 else "150k+"
    buck[k].append(f(s["pnl_pct"]))
print("  %-9s %5s %10s %8s" % ("entry liq", "n", "avg pnl", "win%"))
for k in sorted(buck):
    v = buck[k]
    print("  %-9s %5d %10.1f %7.0f%%" % (k, len(v), sum(v)/len(v),
          100.0*sum(1 for x in v if x > 0)/len(v)))
print("  (entered rows found for %d of 34 trades)" % sum(len(v) for v in buck.values()))
