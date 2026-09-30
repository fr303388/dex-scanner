"""The decision-relevant test: if we had NOT stopped out, where would we END?

Earlier analyses used the PEAK forward excursion. That is the wrong
metric for judging a stop loss. A stop is only harmful if holding to the
end of the window would have produced a BETTER result than the exit.
This computes the END-of-window return, and the hypothetical P&L of
holding vs stopping, for every stopped-out trade.
"""
import csv, io, os, json, collections, datetime, statistics

D = r"C:\Users\ANGEL\Doubao\chats\2026-09-27\new-chat-10\dex-scanner"
def f(v):
    try: return float(v)
    except (TypeError, ValueError): return None
pf = json.load(io.open(os.path.join(D, "sim_portfolio.json"), encoding="utf-8"))
sells = [t for t in pf["trades"] if t["action"] == "SELL"]
stopped = [s for s in sells if (f(s["pnl_pct"]) or 0) < 0]
hist = collections.defaultdict(list)
seen_entry = {}
for r in csv.DictReader(io.open(os.path.join(D, "cohort.csv"), encoding="utf-8")):
    a = r["address"]
    hist[a].append((int(r["ts"]), f(r["price"]), f(r["liquidity"])))
    if a not in seen_entry: seen_entry[a] = (f(r["liq0"]), int(r["ts"]))
for v in hist.values(): v.sort(key=lambda x: x[0])
def parse_exit(s):
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%m-%d %H:%M:%S", "%m-%d %H:%M"):
        try:
            dt = datetime.datetime.strptime(s["time"], fmt)
            if fmt.startswith("%m"): dt = dt.replace(year=datetime.datetime.now().year)
            return dt.timestamp()
        except ValueError: pass
    return None
W = 78
def hdr(t): print("="*W); print(t); print("="*W)

HORIZON = 3600   # 60 minutes after the stop
rows = []
for s in stopped:
    a = s["address"]; et = parse_exit(s); sp = f(s.get("sell_price"))
    if a not in hist or et is None or not sp: continue
    aft = [x for x in hist[a] if et < x[0] <= et + HORIZON]
    if len(aft) < 8: continue
    endp = aft[-1][1]
    peak = max(p for _, p, _ in aft if p)
    l0 = seen_entry.get(a, (None, None))[0]
    endl = aft[-1][2]
    rows.append({
        "sym": s["symbol"], "exit": f(s["pnl_pct"]),
        "end": endp / sp * 100 - 100,
        "peak": peak / sp * 100 - 100,
        "liq": (endl / l0 * 100) if (l0 and endl is not None) else None,
        "mins": (aft[-1][0] - et) / 60.0,
    })

hdr("1  HOLD-TO-END vs STOP-OUT  (60 min horizon, %d trades with data)" % len(rows))
print("  'exit'   = what the -12%% stop actually locked in")
print("  'end'    = where the price was 60 min later, vs the same exit price")
print("  'delta'  = end - exit.  POSITIVE means holding beat stopping.\n")
print("  %-11s %8s %9s %9s %8s %9s  %s" %
      ("symbol", "exit%", "end%", "peak%", "delta", "liq_left", "verdict"))
deltas = []
for r in sorted(rows, key=lambda x: -(x["end"] - x["exit"])):
    d = r["end"] - r["exit"]; deltas.append(d)
    v = "HOLD was better" if d > 3 else ("STOP was better" if d < -3 else "same")
    print("  %-11s %+8.1f %+9.1f %+9.1f %+8.1f %8s  %s" %
          (r["sym"], r["exit"], r["end"], r["peak"], d,
           ("%.0f%%" % r["liq"]) if r["liq"] is not None else "-", v))

hdr("2  TALLY")
better = sum(1 for d in deltas if d > 3)
worse  = sum(1 for d in deltas if d < -3)
same   = len(deltas) - better - worse
print("  holding 60 min would have been BETTER : %2d  (%.0f%%)" % (better, 100.0*better/len(deltas)))
print("  the stop was BETTER                   : %2d  (%.0f%%)" % (worse, 100.0*worse/len(deltas)))
print("  a wash                                : %2d" % same)
print()
print("  median delta (end - exit) : %+.1f pp" % statistics.median(deltas))
print("  mean   delta             : %+.1f pp" % (sum(deltas)/len(deltas)))
print("  sum of all deltas        : %+.1f pp" % sum(deltas))

hdr("3  THE 24 STOPPED-OUT TRADES: FULL DISPOSITION")
n_nodeath = 6
print("  %-11s %8s %s" % ("symbol", "exit%", "disposition"))
for s in sorted(stopped, key=lambda x: f(x["pnl_pct"]) or 0):
    a = s["address"]; et = parse_exit(s)
    m = [r for r in rows if r["sym"] == s["symbol"] and abs(r["exit"] - (f(s["pnl_pct"]) or 0)) < 0.01]
    if m:
        d = m[0]["end"] - m[0]["exit"]
        v = "holding better by %+.0f pp" % d if d > 3 else ("stop better by %+.0f pp" % d if d < -3 else "wash")
    else:
        v = "UNKNOWN - never in cohort / no forward data"
        n_nodeath += 0
    print("  %-11s %+8.1f %s" % (s["symbol"], f(s["pnl_pct"]), v))
print()
print("  of the %d stopped-out trades, %d have no forward data at all" % (len(stopped), len(stopped) - len(rows)))

hdr("4  END-STATE DISTRIBUTION  (your '80%% died' claim, made precise)")
ends = [r["end"] for r in rows]
buckets = [(-100, -80, "collapsed (<-80%)"), (-80, -50, "dead-ish (-80..-50)"),
           (-50, -20, "down (-50..-20)"), (-20, 0, "slightly down"),
           (0, 1e9, "up")]
for lo, hi, lbl in buckets:
    n = sum(1 for e in ends if lo <= e < hi)
    print("  %-22s %2d  (%.0f%%)" % (lbl, n, 100.0*n/len(ends)))
print()
print("  ended DOWN (any amount)      : %d of %d  (%.0f%%)" %
      (sum(1 for e in ends if e < 0), len(ends), 100.0*sum(1 for e in ends if e < 0)/len(ends)))
print("  ended down more than 50%%    : %d of %d  (%.0f%%)" %
      (sum(1 for e in ends if e < -50), len(ends), 100.0*sum(1 for e in ends if e < -50)/len(ends)))
print()
print("  +-- the 6 with no forward data, if all of them died, would give")
print("     %d of %d = %.0f%%" % (2 + 6, len(stopped), 100.0*(2+6)/len(stopped)))
