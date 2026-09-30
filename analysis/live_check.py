"""Live verification: what is the CURRENT on-chain state of every exited token?

This is the test I should have run first. cohort.csv only tracks tokens
while they sit in the trending feed, so "left the cohort" and "died" are
nearly the same thing -- a selection bias that can only be broken by
querying the chain NOW, for tokens that stopped being tracked long ago.

For each exited trade, ask DexScreener (which reads live AMM pool state)
and report:
  - does the pair still exist at all
  - current liquidity in USD   <- can you actually get out?
  - current price vs sell price <- what the position is worth now
  - a realistic exit test: could a $75 sale clear at any meaningful price
"""
import json, io, os, csv, time, datetime, collections, urllib.request, statistics

D = r"C:\Users\ANGEL\Doubao\chats\2026-09-27\new-chat-10\dex-scanner"
def f(v):
    try: return float(v)
    except (TypeError, ValueError): return None

pf = json.load(io.open(os.path.join(D, "sim_portfolio.json"), encoding="utf-8"))
sells = [t for t in pf["trades"] if t["action"] == "SELL"]

# entry liquidity, from the scanner's own decision log
entry_liq = {}
for r in csv.DictReader(io.open(os.path.join(D, "decisions.csv"), encoding="utf-8")):
    if r.get("decision") == "ENTERED" or r.get("reason") == "ENTERED":
        entry_liq.setdefault(r["address"], f(r["liquidity"]))

def fetch(batch):
    url = ("https://api.dexscreener.com/latest/dex/tokens/"
           + ",".join(batch))
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode()).get("pairs") or []

def best_pair(pairs, addr):
    """Deepest pool for this token, quoted in USD against SOL/USDC."""
    best = None
    for p in pairs or []:
        base = (p.get("baseToken") or {}).get("address")
        if not base or base != addr: continue
        li = f((p.get("liquidity") or {}).get("usd")) or 0
        quote = (p.get("quoteToken") or {}).get("symbol")
        if quote not in ("SOL", "USDC", "USDT"): continue
        if best is None or li > best[0]: best = (li, p)
    return best[1] if best else None

W = 80
def hdr(t): print("="*W); print(t); print("="*W)

hdr("LIVE ON-CHAIN STATE OF ALL %d CLOSED TRADES" % len(sells))
print("  queried %s   (US liquidity = exit capacity, not just a price print)"
      % datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))
print()

addrs = [s["address"] for s in sells if s.get("address")]
live = {}
BATCH = 5
for i in range(0, len(addrs), BATCH):
    try:
        for a, p in zip([x for x in addrs[i:i+BATCH]], []): pass
        pairs = fetch(addrs[i:i+BATCH])
        for a in addrs[i:i+BATCH]:
            bp = best_pair(pairs, a)
            if bp: live[a] = bp
    except Exception as e:
        print("  batch %d-%d failed: %s" % (i, i+BATCH, e))
    time.sleep(0.4)
print("  resolved %d / %d addresses to a live SOL/USDC pool\n" % (len(live), len(addrs)))

losers = [s for s in sells if (f(s["pnl_pct"]) or 0) < 0]
winners = [s for s in sells if (f(s["pnl_pct"]) or 0) >= 0]

def report(group, title):
    hdr(title)
    print("  %-11s %8s %10s %10s %9s %9s  %s" %
          ("symbol", "exit%", "now_px%", "now_liq", "liq/entry", "sellable", "verdict"))
    tally = collections.Counter()
    for s in sorted(group, key=lambda x: f(x["pnl_pct"]) or 0):
        sym = s["symbol"]; ex = f(s["pnl_pct"]); sp = f(s.get("sell_price"))
        bp = live.get(s.get("address"))
        if not bp:
            tally["delisted"] += 1
            print("  %-11s %+8.1f %10s %10s %9s %9s  %s" %
                  (sym, ex, "n/a", "n/a", "n/a", "NO", "DELISTED / no pool"))
            continue
        li = f((bp.get("liquidity") or {}).get("usd")) or 0
        px = f(bp.get("priceUsd"))
        now = (px / sp * 100 - 100) if (sp and px) else None
        e0 = entry_liq.get(s.get("address"))
        ratio = (li / e0) if e0 else None
        # a $75 position needs real depth: treat <$500 as unexitable
        sellable = li >= 500
        if not sellable or (now is not None and now < -50):
            v = "DEAD"; tally["DEAD"] += 1
        elif now is not None and now > 0:
            v = "ALIVE, up"; tally["ALIVE up"] += 1
        else:
            v = "ALIVE, down"; tally["ALIVE down"] += 1
        print("  %-11s %+8.1f %10s %10s %9s %9s  %s" %
              (sym, ex,
               ("%+.0f%%" % now) if now is not None else "n/a",
               "$%.1fk" % (li/1000),
               ("%.0f%%" % (ratio*100)) if ratio is not None else "n/a",
               "yes" if sellable else "NO", v))
    print()
    for k, v in tally.most_common():
        print("    %-12s %2d  (%.0f%%)" % (k, v, 100.0*v/len(group)))
    return tally

tl = report(losers, "A  STOPPED-OUT TRADES  (n=%d)" % len(losers))
tw = report(winners, "B  NON-STOPPED-OUT TRADES  (n=%d, control)" % len(winners))

hdr("C  THE ANSWER")
dead = tl.get("DEAD", 0) + tl.get("delisted", 0)
print("  stopped-out tokens that are DEAD or DELISTED now : %d of %d  (%.0f%%)"
      % (dead, len(losers), 100.0*dead/len(losers)))
print("  compare: the '80%%' figure, and my earlier 8%%")
