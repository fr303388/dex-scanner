"""What actually happened to every stopped-out token?

My earlier test used only 7 of 24 stopped-out trades (the ones with
cohort price data after the exit) and found a +22% median bounce. That
sample is suspect: tokens that die get delisted and produce NO forward
data, so the survivors are over-represented. This tests all 24 and
classifies the outcome instead of assuming one.
"""
import csv, io, os, json, collections, datetime, statistics

D = r"C:\Users\ANGEL\Doubao\chats\2026-09-27\new-chat-10\dex-scanner"
def f(v):
    try: return float(v)
    except (TypeError, ValueError): return None

pf = json.load(io.open(os.path.join(D, "sim_portfolio.json"), encoding="utf-8"))
sells = [t for t in pf["trades"] if t["action"] == "SELL"]
stopped = [s for s in sells if (f(s["pnl_pct"]) or 0) < 0]

# full cohort history per address
hist = collections.defaultdict(list)
seen_entry = {}
for r in csv.DictReader(io.open(os.path.join(D, "cohort.csv"), encoding="utf-8")):
    a = r["address"]
    hist[a].append((int(r["ts"]), f(r["price"]), f(r["liquidity"])))
    if a not in seen_entry:
        seen_entry[a] = (f(r["liq0"]), int(r["ts"]))
for v in hist.values(): v.sort(key=lambda x: x[0])

def parse_exit(s):
    tt = s["time"]
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%m-%d %H:%M:%S", "%m-%d %H:%M"):
        try:
            dt = datetime.datetime.strptime(tt, fmt)
            if fmt.startswith("%m"): dt = dt.replace(year=datetime.datetime.now().year)
            return dt.timestamp()
        except ValueError: pass
    return None

W = 78
def hdr(t): print("="*W); print(t); print("="*W)

hdr("1  COHORT COVERAGE OF THE 24 STOPPED-OUT TRADES")
ever = [s for s in stopped if s["address"] in hist]
never = [s for s in stopped if s["address"] not in hist]
print("  stopped-out trades total              : %d" % len(stopped))
print("  address appears ANYWHERE in cohort.csv : %d" % len(ever))
print("  address never in cohort.csv at all     : %d" % len(never))
print()
print("  never-cohorted symbols: %s" % ", ".join(s["symbol"] for s in never))
print("  -> a token that never entered the cohort was never in a trending feed,")
print("     or predates the tracker. Its fate is simply UNKNOWN, not 'dead'.")

hdr("2  FATE OF EACH STOPPED-OUT TOKEN (last cohort observation vs exit)")
print("  %-11s %8s %9s %9s %9s %8s  %s" %
      ("symbol", "exit%", "span", "last_px", "last_liq", "liq%", "verdict"))
cls = collections.Counter()
detail = []
for s in sorted(stopped, key=lambda x: f(x["pnl_pct"]) or 0):
    a = s["address"]; et = parse_exit(s); sp = f(s.get("sell_price"))
    if a not in hist or et is None:
        cls["NO DATA"] += 1
        print("  %-11s %+8.1f %9s %9s %9s %8s  NO DATA" %
              (s["symbol"], f(s["pnl_pct"]), "-", "-", "-", "-"))
        continue
    after = [x for x in hist[a] if x[0] > et]
    l0 = seen_entry.get(a, (None, None))[0]
    if not after:
        cls["no fwd data"] += 1
        print("  %-11s %+8.1f %9s %9s %9s %8s  no fwd data" %
              (s["symbol"], f(s["pnl_pct"]), "-", "-", "-", "-"))
        continue
    span = (after[-1][0] - et) / 60.0
    lastp = after[-1][1]; lastl = after[-1][2]
    lp = ("%+.0f%%" % (lastp / sp * 100 - 100)) if (sp and lastp) else "-"
    lq = ("%.0f%%" % (lastl / l0 * 100)) if (l0 and lastl is not None) else "-"
    # DIED = liquidity collapsed to a shell OR price fell >90% from exit
    died = (lastl is not None and l0 and lastl / l0 < 0.10) or \
           (sp and lastp and lastp / sp < 0.10)
    # best forward excursion
    best = max(p for _, p, _ in after if p)
    fwd = (best / sp * 100 - 100) if (sp and best) else None
    if died:
        v = "DIED"; cls["DIED"] += 1
    elif fwd is not None and fwd > 15:
        v = "recovered +%.0f%%" % fwd; cls["RECOVERED"] += 1
    else:
        v = "flat/dead-ish"; cls["FLAT"] += 1
    detail.append((s["symbol"], f(s["pnl_pct"]), span, lp, lq, v))
    print("  %-11s %+8.1f %8.0fm %9s %9s %8s  %s" %
          (s["symbol"], f(s["pnl_pct"]), span, lp,
           ("$%.0fk" % (lastl/1000)) if lastl else "-", lq, v))

hdr("3  TALLY")
tot = sum(cls.values())
for k in ("DIED", "RECOVERED", "FLAT", "no fwd data", "NO DATA"):
    if cls[k]:
        print("  %-14s %2d  (%.0f%%)" % (k, cls[k], 100.0*cls[k]/tot))
print("  %-14s %2d" % ("TOTAL", tot))

hdr("4  THE HONEST VERSION OF MY EARLIER CLAIM")
an = [d for d in detail if d[5].startswith("recovered")]
di = [d for d in detail if d[5] == "DIED"]
if an:
    print("  tokens that recovered after the stop : %d  %s" %
          (len(an), ", ".join(d[0] for d in an)))
if di:
    print("  tokens that DIED after the stop      : %d  %s" %
          (len(di), ", ".join(d[0] for d in di)))
print()
print("  Earlier report said: 'median +22.1%% forward, 5/7 rose >15%%'.")
print("  That was computed on the 7 with usable data. The full tally above")
print("  shows what the other 17 did.")

hdr("5  CONTROL: DID THE TOKENS THAT DID NOT STOP OUT DO BETTER?")
notst = [s for s in sells if (f(s["pnl_pct"]) or 0) >= 0]
nd = 0; nr = 0
for s in notst:
    a = s["address"]; et = parse_exit(s); sp = f(s.get("sell_price"))
    if a not in hist or et is None: continue
    after = [x for x in hist[a] if x[0] > et]
    if not after: continue
    l0 = seen_entry.get(a, (None, None))[0]
    lastl = after[-1][2]; lastp = after[-1][1]
    died = (lastl is not None and l0 and lastl / l0 < 0.10) or \
           (sp and lastp and lastp / sp < 0.10)
    if died: nd += 1
    elif sp:
        best = max(p for _, p, _ in after if p)
        if best / sp * 100 - 100 > 15: nr += 1
print("  non-stopped-out trades with forward data: %d" % (nd + nr))
print("    died                          : %d" % nd)
print("    recovered >+15%%               : %d" % nr)
