"""Does the score gate help or hurt? Tested on the unbiased cohort population.

cohort.csv seeds tokens from the trending feed BEFORE any entry gate runs,
so score-bucket comparison here is NOT censored by the score>=5 filter.
That is exactly the comparison decisions.csv can never give us.

Restricted to liq0 >= 150k, i.e. the population that now reaches the score
gate at all.
"""
import csv, io, os, collections, statistics

D = r"C:\Users\ANGEL\Doubao\chats\2026-09-27\new-chat-10\dex-scanner"
def f(v):
    try: return float(v)
    except (TypeError, ValueError): return None

series = collections.defaultdict(list)
meta = {}
for r in csv.DictReader(io.open(os.path.join(D, "cohort.csv"), encoding="utf-8")):
    a = r["address"]; p = f(r["price"])
    if not p: continue
    series[a].append((int(r["ts"]), p))
    if a not in meta:
        meta[a] = (f(r["score0"]), f(r["liq0"]), (r.get("symbol") or "")[:12])
for v in series.values(): v.sort(key=lambda x: x[0])

W = 78
def hdr(t): print("="*W); print(t); print("="*W)

def forward(a, mins):
    """Return (max fwd %, end fwd %) at `mins` after the token's first sighting."""
    s = series[a]
    if len(s) < 6: return None
    t0, p0 = s[0]
    win = [p for t, p in s if t0 <= t <= t0 + mins * 60]
    if len(win) < 4: return None
    return (max(win) / p0 * 100 - 100, win[-1] / p0 * 100 - 100)

POOL = [a for a in series if (meta[a][1] or 0) >= 150000]
hdr("TESTING THE SCORE GATE ON %d COHORT TOKENS WITH liq0 >= $150k" % len(POOL))
print("  cohort seeds tokens before any entry gate, so these buckets are")
print("  complete -- including the ones the score>=5 gate currently blocks.\n")

for HOR in (30, 60, 120):
    hdr("FORWARD RETURN AT +%d MIN,  by score0 bucket  (liq0 >= $150k)" % HOR)
    buckets = collections.defaultdict(list)
    for a in POOL:
        r = forward(a, HOR)
        sc = meta[a][0]
        if r is None or sc is None: continue
        b = "<5 BLOCKED" if sc < 5 else "5-7" if sc < 7 else "7+"
        buckets[b].append(r)
    print("  %-14s %5s %10s %10s %9s %9s %9s" %
          ("score0", "n", "med peak", "med end", "up>10%", "dn<-30%", "net"))
    for k in ("<5 BLOCKED", "5-7", "7+"):
        v = buckets.get(k)
        if not v: continue
        pk = [x[0] for x in v]; en = [x[1] for x in v]
        up = 100.0*sum(1 for x in pk if x > 10)/len(v)
        dn = 100.0*sum(1 for x in en if x < -30)/len(v)
        print("  %-14s %5d %9.1f%% %9.1f%% %8.0f%% %8.0f%% %+8.1f" %
              (k, len(v), statistics.median(pk), statistics.median(en), up, dn,
               sum(en)/len(en)))
    print()
    b5 = buckets.get("<5 BLOCKED"); b57 = buckets.get("5-7"); b7 = buckets.get("7+")
    if b5 and b57:
        m5 = sum(x[1] for x in b5)/len(b5)
        m57 = sum(x[1] for x in b57)/len(b57)
        verdict = ("gate HELPS: blocked bucket underperforms" if m5 < m57 else
                   "gate HURTS: blocked bucket OUTPERFORMS the admitted one")
        print("  mean end-return  <5 = %+.1f%%   vs   5-7 = %+.1f%%" % (m5, m57))
        print("  -> %s  (gap %.1f pp)" % (verdict, m5 - m57))
        print()

hdr("SAME TEST WITHOUT THE $150k FILTER (all cohort tokens)")
for HOR in (60,):
    buckets = collections.defaultdict(list)
    for a in series:
        r = forward(a, HOR); sc = meta[a][0]
        if r is None or sc is None: continue
        b = "<5 BLOCKED" if sc < 5 else "5-7" if sc < 7 else "7+"
        buckets[b].append(r)
    print("  %-14s %5s %10s %10s %9s" % ("score0", "n", "med peak", "med end", "net"))
    for k in ("<5 BLOCKED", "5-7", "7+"):
        v = buckets.get(k)
        if not v: continue
        pk = [x[0] for x in v]; en = [x[1] for x in v]
        print("  %-14s %5d %9.1f%% %9.1f%% %+8.1f" %
              (k, len(v), statistics.median(pk), statistics.median(en), sum(en)/len(en)))
    print()
    b5 = buckets.get("<5 BLOCKED"); b57 = buckets.get("5-7")
    if b5 and b57:
        print("  mean end-return  <5 = %+.1f%%   vs   5-7 = %+.1f%%"
              % (sum(x[1] for x in b5)/len(b5), sum(x[1] for x in b57)/len(b57)))

hdr("MEDIAN / MEAN SPOT CHECK AT +60 MIN, liq>=150k")
vals = collections.defaultdict(list)
for a in POOL:
    r = forward(a, 60); sc = meta[a][0]
    if r is None or sc is None: continue
    vals["<5" if sc < 5 else "5-7" if sc < 7 else "7+"].append(r[1])
for k in ("<5", "5-7", "7+"):
    if vals[k]:
        print("  %-6s n=%4d  mean %+6.1f%%  median %+6.1f%%  stdev %5.1f"
              % (k, len(vals[k]), sum(vals[k])/len(vals[k]),
                 statistics.median(vals[k]), statistics.stdev(vals[k])))
