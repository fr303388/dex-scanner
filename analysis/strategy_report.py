"""Strategy report: 34 closed trades. Read-only, no writes to the project."""
import csv, io, os, json, collections, datetime, statistics

D = r"C:\Users\ANGEL\Doubao\chats\2026-09-27\new-chat-10\dex-scanner"
def f(v):
    try: return float(v)
    except (TypeError, ValueError): return None

pf = json.load(io.open(os.path.join(D, "sim_portfolio.json"), encoding="utf-8"))
sells = [t for t in pf["trades"] if t["action"] == "SELL"]
traj = collections.defaultdict(list)
for r in csv.DictReader(io.open(os.path.join(D, "trajectory.csv"), encoding="utf-8")):
    traj[r["address"]].append(r)
for v in traj.values():
    v.sort(key=lambda x: int(x["ts"]))

W = 76
def hdr(t):
    print("=" * W); print(t); print("=" * W)

def reason_of(s):
    r = (s.get("reason") or "")
    for k, lbl in (("流動性崩潰", "LIQ COLLAPSE"), ("下架", "DELIST"),
                   ("波動停損", "VOL STOP"), ("鎖利", "LOCK PROFIT"),
                   ("移動停利", "TRAILING"), ("流動性流失", "LIQ DRAIN"),
                   ("45分未延續", "45MIN STALL"), ("最長持有", "MAX HOLD"),
                   ("停損", "STOP LOSS")):
        if k in r: return lbl
    return "OTHER: " + r[:20]

# ---------------------------------------------------------------- 1
hdr("1  EXIT REASON  --  34 closed trades")
g = collections.defaultdict(list)
for s in sells:
    g[reason_of(s)].append((f(s["pnl_pct"]), f(s.get("mfe"))))
print("  %-14s %4s %9s %9s %9s" % ("reason", "n", "sum pp", "avg pp", "win%"))
tot = 0
for k, v in sorted(g.items(), key=lambda x: sum(y[0] for y in x[1])):
    ps = [y[0] for y in v]
    tot += sum(ps)
    win = 100.0 * sum(1 for p in ps if p > 0) / len(ps)
    print("  %-14s %4d %9.1f %9.1f %8.0f%%" % (k, len(v), sum(ps), sum(ps)/len(v), win))
print("  %-14s %4d %9.1f" % ("TOTAL", len(sells), tot))

# ---------------------------------------------------------------- 2
hdr("2  THE MISSED-PROFIT PROBLEM  (MFE vs realised)")
buckets = [(-100, -20, "catastrophic"), (-20, 0, "small loss"),
           (0, 10, "flat win"), (10, 25, "good win"), (25, 1e9, "big win")]
print("  %-14s %4s %8s %8s" % ("realised", "n", "avg MFE", "left"))
for lo, hi, lbl in buckets:
    sel = [s for s in sells if lo <= (f(s["pnl_pct"]) or 0) < hi]
    if not sel: continue
    mf = [f(s.get("mfe")) or 0 for s in sel]
    gap = sum(m - (f(s["pnl_pct"]) or 0) for s, m in zip(sel, mf)) / len(sel)
    print("  %-14s %4d %8.1f %8.1f" % (lbl, len(sel), sum(mf)/len(mf), gap))

mfe_hi = [s for s in sells if (f(s.get("mfe")) or 0) >= 20]
print()
print("  trades that reached MFE >= +20%%:  n=%d" % len(mfe_hi))
gave = [s for s in mfe_hi if (f(s["pnl_pct"]) or 0) < 10]
print("    of those, ended below +10%%:      n=%d  (%.0f%%)" %
      (len(gave), 100.0*len(gave)/max(1,len(mfe_hi))))
print("    giveback (avg MFE - avg realised): %.1f pp" %
      (sum((f(s.get("mfe")) or 0) - (f(s["pnl_pct"]) or 0) for s in mfe_hi)/len(mfe_hi)))
print()
print("  MFE distribution of losers (pnl<0):")
for s in sorted([s for s in sells if (f(s["pnl_pct"]) or 0) < 0],
                key=lambda x: -(f(x.get("mfe")) or 0))[:10]:
    print("    %-11s realised %7.1f   MFE %7.1f   gave back %6.1f pp"
          % (s["symbol"], f(s["pnl_pct"]), f(s.get("mfe")),
             (f(s.get("mfe")) or 0) - (f(s["pnl_pct"]) or 0)))

# ---------------------------------------------------------------- 3
hdr("3  HOLDING TIME  --  winners are not held longer than losers")
wins = [s for s in sells if (f(s["pnl_pct"]) or 0) > 0]
loss = [s for s in sells if (f(s["pnl_pct"]) or 0) <= 0]
for lbl, grp in (("winners", wins), ("losers", loss)):
    hm = [f(s.get("held_min")) or 0 for s in grp]
    print("  %-8s n=%2d   median hold %5.0f min   mean %5.0f min"
          % (lbl, len(grp), statistics.median(hm), sum(hm)/len(hm)))
print()
print("  exit-time concentration (all trades):")
hb = collections.Counter()
for s in sells:
    h = (f(s.get("held_min")) or 0)
    hb["0-15 min" if h < 15 else "15-45 min" if h < 45 else
       "45-90 min" if h < 90 else "90+ min"] += 1
for k in ("0-15 min", "15-45 min", "45-90 min", "90+ min"):
    print("    %-10s %2d  (%2.0f%%)" % (k, hb[k], 100.0*hb[k]/len(sells)))

# ---------------------------------------------------------------- 4
hdr("4  BUY SCORE vs OUTCOME  (does the score predict anything?)")
paired = [s for s in sells if s["address"] in traj and s.get("buy_score") is not None]
print("  trades with trajectory: %d / %d" % (len(paired), len(sells)))
sc = [(f(s.get("buy_score")) or 0, f(s["pnl_pct"])) for s in paired]
if len(sc) >= 3:
    def corr(xs, ys):
        n = len(xs); mx = sum(xs)/n; my = sum(ys)/n
        num = sum((x-mx)*(y-my) for x, y in zip(xs, ys))
        dx = (sum((x-mx)**2 for x in xs))**.5; dy = (sum((y-my)**2 for y in ys))**.5
        return num/(dx*dy) if dx and dy else 0
    print("  Pearson r(score, pnl_pct) = %+.3f  (n=%d)" % (corr([a for a,_ in sc],[b for _,b in sc]), len(sc)))
    print()
    print("  %-10s %4s %9s %9s" % ("score", "n", "avg pnl", "win%"))
    for lo, hi in ((-99,4),(4,5.5),(5.5,7),(7,99)):
        sel = [b for a,b in sc if lo <= a < hi]
        if not sel: continue
        print("  %-10s %4d %9.1f %8.0f%%" % ("%.1f-%d"%(lo,hi), len(sel),
              sum(sel)/len(sel), 100.0*sum(1 for x in sel if x>0)/len(sel)))

# ---------------------------------------------------------------- 5
hdr("5  SCALE-OUT COUNTERFACTUAL on all 34 trades")
def first_cross(pv, thr):
    for p in pv:
        if p is not None and p >= thr: return p
    return None
PAIRS = [(15,30),(20,40),(25,50),(30,60),(40,None)]
rows = []
for s in sells:
    t = traj.get(s["address"])
    if not t: continue
    pv = [f(r["pnl_pct"]) for r in t]
    act = f(s["pnl_pct"])
    rec = {"sym": s["symbol"], "mfe": f(s.get("mfe")), "act": act}
    for a, b in PAIRS:
        e1 = first_cross(pv, a); e2 = first_cross(pv, b) if b else None
        if e1 is None: rec["so%d"%a] = None
        elif e2 is None: rec["so%d"%a] = 0.4*e1 + 0.6*act
        else: rec["so%d"%a] = 0.4*e1 + 0.4*e2 + 0.2*act
    rows.append(rec)
keys = ["act"] + ["so%d"%a for a,_ in PAIRS]
print("  trades with trajectory: %d / %d" % (len(rows), len(sells)))
print("  %-11s %7s" % ("", "MFE") + "".join("%8s"%k for k in keys))
for r in rows:
    if (r["mfe"] or 0) < 15: continue
    print("  %-11s %+7.1f" % (r["sym"], r["mfe"]) +
          "".join("%8s" % (("%+6.1f"%r[k]) if r.get(k) is not None else "     --") for k in keys))
print("  " + "-"*(19+8*len(keys)))
for lbl, fn in (("SUM pp", lambda xs: sum(x for x in xs if x is not None)),
                ("fired", lambda xs: sum(1 for x in xs if x is not None)),
                ("MEDIAN", lambda xs: statistics.median([x for x in xs if x is not None]) if [x for x in xs if x is not None] else 0)):
    print("  %-11s %7s" % (lbl, "") + "".join("%8.1f" % fn([r.get(k) for r in rows]) for k in keys))

# ---------------------------------------------------------------- 6
hdr("6  COHORT  --  forward liquidity behaviour by entry liquidity")
ch = collections.defaultdict(list)
seen = set()
for r in csv.DictReader(io.open(os.path.join(D, "cohort.csv"), encoding="utf-8")):
    a = r["address"]
    if a in seen: continue
    seen.add(a)
    l0 = f(r["liq0"]); nl = (r.get("no_liquidity") or "").strip() in ("1","True","true","TRUE")
    if l0 is None: continue
    ch["<35k" if l0 < 35000 else "35-75k" if l0 < 75000 else "75-300k" if l0 < 300000 else ">300k"].append(nl)
print("  %-9s %6s %10s" % ("entry liq", "n", "NO_LIQ%"))
for k in ("<35k","35-75k","75-300k",">300k"):
    v = ch.get(k) or []
    if not v: continue
    print("  %-9s %6d %9.1f%%" % (k, len(v), 100.0*sum(v)/len(v)))
print()
print("  token count: %d" % len(seen))

# ---------------------------------------------------------------- 7
hdr("7  CONCENTRATION OF DAMAGE")
acts = [f(s["pnl_pct"]) for s in sells]
worst = sorted(acts)[:2]
rest = acts[2:]
print("  total          %8.1f pp" % sum(acts))
print("  2 worst trades %8.1f pp  (%.0f%% of total loss)" % (sum(worst), 100.0*sum(worst)/sum(acts)))
print("  other %2d trades %7.1f pp" % (len(rest), sum(rest)))
print()
sl = [f(s["pnl_pct"]) for s in sells if reason_of(s) == "STOP LOSS"]
print("  STOP LOSS: n=%d  sum %.1f pp  (%.0f%% of all trades hit the -12%% rule)"
      % (len(sl), sum(sl), 100.0*len(sl)/len(sells)))
print("  the 2 disasters are inside that group, so ordinary stop-outs = %d trades, %.1f pp"
      % (len(sl)-2, sum(sl)-sum(worst)))
