"""Post-change diagnostics: did the $150k floor keep the bot trading,
and is the so15 counterfactual actually being recorded?"""
import csv, io, os, json, time, collections, datetime, statistics

D = r"C:\Users\ANGEL\Doubao\chats\2026-09-27\new-chat-10\dex-scanner"
def f(v):
    try: return float(v)
    except (TypeError, ValueError): return None

CUT = time.mktime(time.strptime("2026-09-30 19:29", "%Y-%m-%d %H:%M"))
W = 76
def hdr(t): print("="*W); print(t); print("="*W)

pf = json.load(io.open(os.path.join(D, "sim_portfolio.json"), encoding="utf-8"))
sells = [t for t in pf["trades"] if t["action"] == "SELL"]

hdr("1  DID THE $150k FLOOR KEEP THE BOT TRADING?")
new = [t for t in sells if t["time"] >= "09-30 19:29"]
print("  closed trades since 19:29 : %d" % len(new))
print("  minutes elapsed            : %.0f" % ((time.time() - CUT) / 60))
prev = [t for t in sells if "09-30 12:00" <= t["time"] < "09-30 19:29"]
print("  closed trades in the 7h before, for comparison: %d" % len(prev))
print()
dec = [r for r in csv.DictReader(io.open(os.path.join(D, "decisions.csv"), encoding="utf-8"))
       if int(r["ts"]) >= CUT]
print("  decisions.csv rows since 19:29 : %d" % len(dec))
ent = [r for r in dec if r.get("decision") == "ENTERED" or r.get("reason") == "ENTERED"]
print("  ENTERED rows                   : %d" % len(ent))
lq = [f(r["liquidity"]) for r in dec if f(r["liquidity"])]
above = [x for x in lq if x >= 150000]
print("  rows with liquidity >= 150k    : %d  (%.0f%%)" %
      (len(above), 100.0*len(above)/max(1,len(lq))))
print()
c = collections.Counter()
for r in dec:
    rs = r.get("reason") or ""
    if "150K" in rs:      c["liquidity floor $150k"] += 1
    elif "分數" in rs:      c["score gate"] += 1
    elif "買盤" in rs:      c["buy_ratio gate"] += 1
    elif "熔斷" in rs:      c["circuit breaker"] += 1
    elif "齡" in rs:        c["token age"] += 1
    elif "冷卻" in rs or "黑名單" in rs: c["cooldown/blacklist"] += 1
    elif "觸發" in rs or "收集" in rs:   c["price trigger"] += 1
    elif "鏈上" in rs or "RPC" in rs:   c["onchain risk"] += 1
print("  stop reasons since 19:29:")
for k, v in c.most_common(10):
    print("    %-24s %6d  (%4.1f%%)" % (k, v, 100.0*v/max(1,len(dec))))

hdr("2  SCORE DISTRIBUTION OF TOKENS THAT CLEAR THE $150k FLOOR")
print("  (the score gate is now the main filter -- is it selecting well?)")
cleared = [f(r["score"]) for r in dec if (f(r["liquidity"]) or 0) >= 150000]
if cleared:
    cleared.sort()
    print("  n=%d   min %.1f  p25 %.1f  p50 %.1f  p75 %.1f  max %.1f" %
          (len(cleared), cleared[0], cleared[len(cleared)//4], cleared[len(cleared)//2],
           cleared[len(cleared)*3//4], cleared[-1]))
    b = collections.Counter()
    for s in cleared:
        b["<5 (blocked)" if s < 5 else "5-7" if s < 7 else "7+" ] += 1
    for k in ("<5 (blocked)", "5-7", "7+"):
        if b[k]: print("    %-14s %6d  (%.0f%%)" % (k, b[k], 100.0*b[k]/len(cleared)))
    print()
    print("  -> share of $150k+ candidates blocked by the score>=5 gate: %.0f%%"
          % (100.0*b["<5 (blocked)"]/len(cleared)))
print()
print("  reference: r(score, pnl) = -0.46 (n=27, disasters excluded)")
print("  a negative r means the LOW scores are the profitable ones,")
print("  so a score>=5 gate removes exactly the better half.")

hdr("3  IS so15 ACTUALLY BEING RECORDED?")
withso = [t for t in sells if "so15_pnl_pct" in t]
print("  closed trades carrying so15_pnl_pct : %d of %d" % (len(withso), len(sells)))
if withso:
    for t in withso[-6:]:
        a = f(t.get("pnl_pct")); s = f(t.get("so15_pnl_pct"))
        print("    %s %-11s actual %7s   so15 %7s   delta %s" %
              (t["time"], t["symbol"], a, s,
               ("%+.1f" % (s - a)) if (a is not None and s is not None) else "-"))
else:
    print("  none yet -- the field only appears on trades closed after 19:29")
print()
print("  (this is a PEAK-based estimate: it assumes the 40%% filled at exactly")
print("   +15%%, not at the actual pnl when the threshold was crossed.)")

hdr("4  WHAT TO EXPECT NEXT")
print("  the $150k floor means the bot now only sees the top ~1/3 of the feed")
print("  by pool size. At the pre-change rate of ~7 trades/day, expect roughly")
print("  2-3 trades/day, with a materially different token mix.")
print("  the score gate is now the binding constraint on that smaller set.")
