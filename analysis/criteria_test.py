"""Do the criteria a '100x hunt' checklist relies on actually predict
anything, measured on our own unbiased cohort at the $150k tier?

The classic memecoin screening checklist is mostly about (a) avoiding rugs
and (b) spotting early demand. Those map to:
    holder concentration / LP burn  -> we have NO data on this
    buy pressure                    -> br_h24, br_m5
    real volume                     -> volume_h24
    freshness                       -> age_sec
    smart money                     -> score0's gm_smart term

This measures the ones we CAN see, against forward survival, on the
population that now reaches the entry gate.
"""
import csv, io, os, collections, statistics

D = r"C:\Users\ANGEL\Doubao\chats\2026-09-27\new-chat-10\dex-scanner"
def f(v):
    try: return float(v)
    except (TypeError, ValueError): return None

FIELDS = ("br_h24", "br_m5", "volume_h24", "age_sec", "score0", "liq0")

# first sighting per address = the entry snapshot, before any outcome
snap = {}
series = collections.defaultdict(list)
for r in csv.DictReader(io.open(os.path.join(D, "cohort.csv"), encoding="utf-8")):
    a = r["address"]; p = f(r["price"])
    if not p: continue
    series[a].append((int(r["ts"]), p, f(r["liquidity"])))
    if a not in snap:
        snap[a] = {k: f(r.get(k)) for k in FIELDS}
        snap[a]["_t0"] = int(r["ts"])
for v in series.values(): v.sort(key=lambda x: x[0])

def outcome(a, mins=60):
    s = series[a]
    if len(s) < 6: return None
    t0, p0 = s[0][0], s[0][1]
    win = [x for x in s if t0 <= x[0] <= t0 + mins * 60]
    if len(win) < 4: return None
    return {"peak": max(x[1] for x in win) / p0 * 100 - 100,
            "end":  win[-1][1] / p0 * 100 - 100,
            "liq":  (win[-1][2] / s[0][2] * 100) if s[0][2] and win[-1][2] else None}

W = 80
def hdr(t): print("="*W); print(t); print("="*W)

POOL = [a for a in series if (snap[a].get("liq0") or 0) >= 150000]
hdr("SAMPLE: %d cohort tokens with liq0 >= $150k" % len(POOL))
if len(POOL) < 40:
    print("  !! n is small. Anything below is indicative, not conclusive.")
    print("  !! the whole $150k+ population is only ~24 distinct tokens/day,")
    print("  !! so this table cannot support a parameter change yet.\n")

recs = []
for a in POOL:
    o = outcome(a)
    if o: recs.append((a, o))
print("  with a 60-min outcome window: %d\n" % len(recs))

def corr(xs, ys):
    n = len(xs)
    if n < 5: return None
    mx = sum(xs)/n; my = sum(ys)/n
    num = sum((x-mx)*(y-my) for x, y in zip(xs, ys))
    dx = (sum((x-mx)**2 for x in xs))**.5; dy = (sum((y-my)**2 for y in ys))**.5
    return num/(dx*dy) if dx and dy else None

hdr("1  DOES IT PREDICT THE 60-MIN END RETURN?")
print("  %-12s %5s %14s %16s" % ("field", "n", "r vs end", "r vs peak"))
for fl in FIELDS:
    xs = [snap[a][fl] for a, _ in recs if snap[a].get(fl) is not None]
    ye = [o["end"] for a, o in recs if snap[a].get(fl) is not None]
    yp = [o["peak"] for a, o in recs if snap[a].get(fl) is not None]
    re_, rp = corr(xs, ye), corr(xs, yp)
    print("  %-12s %5d %14s %16s" % (fl, len(xs),
          ("%+.3f" % re_) if re_ is not None else "-",
          ("%+.3f" % rp) if rp is not None else "-"))

hdr("2  DOES IT PREDICT LIQUIDITY SURVIVAL?  (the thing that actually matters)")
print("  surviving >50% of entry liquidity after 60 min")
print("  %-12s %6s %14s %16s" % ("field", "n", "r vs liq", "split medians"))
for fl in FIELDS:
    xs, ys = [], []
    for a, o in recs:
        if snap[a].get(fl) is None or o["liq"] is None: continue
        xs.append(snap[a][fl]); ys.append(o["liq"])
    r = corr(xs, ys)
    if len(xs) >= 10:
        med = statistics.median(xs)
        lo = [y for x, y in zip(xs, ys) if x <= med]
        hi = [y for x, y in zip(xs, ys) if x >  med]
        split = "%.0f%% vs %.0f%%" % (statistics.median(lo), statistics.median(hi))
    else:
        split = "-"
    print("  %-12s %6d %14s %16s" % (fl, len(xs),
          ("%+.3f" % r) if r is not None else "-", split))

hdr("3  BUCKET VIEW: buy pressure (br_h5), the closest proxy to 'smart money'")
for fl in ("br_m5", "br_h24"):
    vals = [(snap[a][fl], o["liq"]) for a, o in recs
            if snap[a].get(fl) is not None and o["liq"] is not None]
    if len(vals) < 8: continue
    vals.sort()
    n = len(vals); q = n // 3
    print("  %s  (n=%d, split into thirds)" % (fl, n))
    for lbl, chunk in (("low  third", vals[:q]), ("mid  third", vals[q:2*q]),
                       ("high third", vals[2*q:])):
        if not chunk: continue
        pk = statistics.median([c[0] for c in chunk])
        lq = statistics.median([c[1] for c in chunk])
        print("    %-11s field %6.1f   ->  liquidity left %5.0f%%" % (lbl, pk, lq))
    print()

hdr("4  WHAT THE BOT ALREADY SCORES, vs WHAT SURVIVES")
print("  score_token() adds points for: vol>200k, liq>50k, br>70, smart>=5,")
print("  10<h24<=50, txns>=80.  Minus for: 追高, 已崩, 流動低, 賣壓, 筆數少.")
print()
print("  measured r against 60-min end return and liquidity survival:")
for fl in ("volume_h24", "liq0", "br_h24", "br_m5", "age_sec", "score0"):
    xs = [snap[a][fl] for a, _ in recs if snap[a].get(fl) is not None]
    ye = [o["end"] for a, o in recs if snap[a].get(fl) is not None]
    lq = [o["liq"] for a, o in recs if snap[a].get(fl) is not None and o["liq"] is not None]
    re_ = corr(xs, ye); rl = corr(xs, lq)
    print("    %-12s  r(end)=%s   r(liq survival)=%s"
          % (fl, ("%+.3f" % re_) if re_ is not None else "  -  ",
             ("%+.3f" % rl) if rl is not None else "  -  "))
