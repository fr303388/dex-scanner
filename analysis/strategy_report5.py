"""Part 5: is the liquidity-band result driven by the 2 disasters?"""
import csv, io, os, json, collections, statistics

D = r"C:\Users\ANGEL\Doubao\chats\2026-09-27\new-chat-10\dex-scanner"
def f(v):
    try: return float(v)
    except (TypeError, ValueError): return None
pf = json.load(io.open(os.path.join(D, "sim_portfolio.json"), encoding="utf-8"))
sells = [t for t in pf["trades"] if t["action"] == "SELL"]
dec = collections.defaultdict(list)
for r in csv.DictReader(io.open(os.path.join(D, "decisions.csv"), encoding="utf-8")):
    if r.get("decision") == "ENTERED" or r.get("reason") == "ENTERED":
        dec[r["address"]].append(r)

print("="*76); print("ENTRY LIQUIDITY OF EVERY TRADE, worst first"); print("="*76)
print("  %-11s %10s %9s %8s  %s" % ("symbol", "entry liq", "pnl%", "held", "MFE"))
rows = []
for s in sells:
    rs = dec.get(s.get("address")) or []
    l0 = f(rs[0].get("liquidity")) if rs else None
    rows.append((l0, s))
for l0, s in sorted(rows, key=lambda x: (f(x[1]["pnl_pct"]) or 0)):
    print("  %-11s %10s %+9.1f %7s  %+.1f" % (s["symbol"],
          "$%.0fk" % (l0/1000) if l0 else "-", f(s["pnl_pct"]),
          int(f(s.get("held_min")) or 0), f(s.get("mfe")) or 0))

print()
print("="*76); print("THE TWO DISASTERS' ENTRY LIQUIDITY"); print("="*76)
for s in sells:
    if s["symbol"] in ("Speed", "BUBBLE"):
        rs = dec.get(s.get("address")) or []
        l0 = f(rs[0].get("liquidity")) if rs else None
        print("  %-10s entry liq = %s" % (s["symbol"], "$%.0fk" % (l0/1000) if l0 else "not in decisions"))

print()
print("="*76); print("BANDS, with and without the 2 disasters"); print("="*76)
CATA = {"Speed", "BUBBLE"}
def band(l):
    return ("35-50k" if l < 50000 else "50-75k" if l < 75000 else
            "75-150k" if l < 150000 else "150k+")
for tag, keep in (("ALL 34", lambda s: True), ("EXCL 2 DISASTERS", lambda s: s["symbol"] not in CATA)):
    b = collections.defaultdict(list)
    for l0, s in rows:
        if not l0 or not keep(s): continue
        b[band(l0)].append(f(s["pnl_pct"]))
    print("\n  %s" % tag)
    print("  %-9s %5s %10s %8s" % ("band", "n", "sum pp", "win%"))
    for k in ("35-50k", "50-75k", "75-150k", "150k+"):
        v = b.get(k)
        if not v: continue
        print("  %-9s %5d %10.1f %7.0f%%" % (k, len(v), sum(v),
              100.0*sum(1 for x in v if x > 0)/len(v)))
    v150 = b.get("150k+") or []
    below = [x for k in ("35-50k","50-75k","75-150k") for x in (b.get(k) or [])]
    print("    -> below $150k: n=%2d  sum %+7.1f pp" % (len(below), sum(below)))
    print("    -> 150k+     : n=%2d  sum %+7.1f pp" % (len(v150), sum(v150)))

print()
print("="*76); print("LIQUIDITY LEFT AFTER 60 MIN  (cohort, excl. nothing)"); print("="*76)
path = collections.defaultdict(list)
for r in csv.DictReader(io.open(os.path.join(D, "cohort.csv"), encoding="utf-8")):
    path[r["address"]].append((int(r["ts"]), f(r["liquidity"])))
for v in path.values(): v.sort(key=lambda x: x[0])
seen = set(); rem = collections.defaultdict(list)
for r in csv.DictReader(io.open(os.path.join(D, "cohort.csv"), encoding="utf-8")):
    a = r["address"]
    if a in seen: continue
    l0 = f(r["liq0"]); t0 = int(r["ts"])
    if not l0 or l0 < 5000: continue
    seen.add(a)
    fut = [l for t, l in path[a] if t0+3300 <= t <= t0+3900 and l]
    if fut: rem[band(l0)].append(min(fut)/l0*100)
print("  %-9s %6s %12s %14s" % ("band", "n", "median left", "lost >50%"))
for k in ("35-50k", "50-75k", "75-150k", "150k+"):
    v = rem.get(k)
    if not v: continue
    print("  %-9s %6d %11.0f%% %13.0f%%" % (k, len(v), statistics.median(v),
          100.0*sum(1 for x in v if x < 50)/len(v)))

print()
print("="*76); print("WHAT DOES THE BOT ACTUALLY SEE?  funnel in last 24h"); print("="*76)
import time
cut = time.time() - 86400
recent = [r for r in csv.DictReader(io.open(os.path.join(D, "decisions.csv"), encoding="utf-8")) if int(r["ts"]) > cut]
print("  decisions.csv rows in last 24h: %d" % len(recent))
b2 = collections.Counter()
for r in recent:
    l = f(r["liquidity"]) or 0
    b2["<150k" if l < 150000 else "150k+"] += 1
print("  by liquidity: %s" % dict(b2))
ent = [r for r in recent if r.get("decision") == "ENTERED" or r.get("reason") == "ENTERED"]
print("  ENTERED rows: %d" % len(ent))
cnt = collections.Counter()
for r in recent:
    rs = r.get("reason") or ""
    if "35K" in rs: cnt["liquidity floor $35k"] += 1
    elif "分數" in rs: cnt["score gate"] += 1
    elif "買盤" in rs: cnt["buy_ratio gate"] += 1
    elif "待確認" in rs or "確認中" in rs: cnt["2-stage confirm"] += 1
    elif "熔斷" in rs: cnt["circuit breaker"] += 1
    elif "觸發" in rs or "收集" in rs: cnt["price trigger"] += 1
    elif "鏈上" in rs or "RPC" in rs: cnt["onchain risk"] += 1
    elif "齡" in rs: cnt["token age"] += 1
    elif "冷卻" in rs or "黑名單" in rs: cnt["cooldown/blacklist"] += 1
print("  top stop reasons (24h):")
for k, v in cnt.most_common(10):
    print("    %-24s %6d  (%4.1f%%)" % (k, v, 100.0*v/len(recent)))
