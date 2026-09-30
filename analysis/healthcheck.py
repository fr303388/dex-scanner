"""One-shot health check for the meme-coin bot. Read-only, lives outside the project.

Usage:
    python healthcheck.py              # last 30 minutes
    python healthcheck.py 60           # last 60 minutes
    python healthcheck.py 30 18:00     # since 18:00

Answers three questions:
  1. Did anything ENTER, and is ENTERED actually written to the log?
  2. Which gate is the bottleneck now?
  3. Is the on-chain / RPC failure rate healthy?
"""
import csv, io, sys, os, json, collections, statistics
from datetime import datetime, timedelta

D = r"C:\Users\ANGEL\Doubao\chats\2026-09-27\new-chat-10\dex-scanner"
DEC = os.path.join(D, "decisions.csv")
PF = os.path.join(D, "sim_portfolio.json")
TRAJ = os.path.join(D, "trajectory.csv")

mins = int(sys.argv[1]) if len(sys.argv) > 1 else 30
since = sys.argv[2] if len(sys.argv) > 2 else None

rows = list(csv.DictReader(io.open(DEC, encoding="utf-8")))
rows = [r for r in rows if 1_500_000_000 < int(r["ts"]) < 4_000_000_000]
rows.sort(key=lambda r: int(r["ts"]))
if not rows:
    print("no usable rows"); sys.exit(1)

last_ts = int(rows[-1]["ts"])
if since:
    hh, mm = map(int, since.split(":"))
    cut = datetime.now().replace(hour=hh, minute=mm, second=0).timestamp()
else:
    cut = last_ts - mins * 60
w = [r for r in rows if int(r["ts"]) >= cut]

def t(ts): return datetime.fromtimestamp(int(ts)).strftime("%H:%M:%S")

print("=" * 70)
print("WINDOW  %s -> %s   (%d rows, %.1f min)"
      % (t(w[0]["ts"]), t(w[-1]["ts"]), len(w),
         (int(w[-1]["ts"]) - int(w[0]["ts"])) / 60.0))
print("=" * 70)

# --- 1. entries -------------------------------------------------------------
dec = collections.Counter(r["decision"] for r in w)
ent_all = collections.Counter(r["decision"] for r in rows)
print("decision  window   all-time")
for k in ("ENTERED", "HELD", "COOLDOWN", "REJECTED"):
    print("  %-9s %6d %9d" % (k, dec.get(k, 0), ent_all.get(k, 0)))
print()
pf = json.load(io.open(PF, encoding="utf-8"))
buys = [x for x in pf["trades"] if x["action"] == "BUY"]
print("BUY trades in portfolio : %d" % len(buys))
print("ENTERED rows all-time  : %d" % ent_all.get("ENTERED", 0))
mismatch = [b for b in buys if b["time"] >= t(w[0]["ts"])[:5]]
if buys and ent_all.get("ENTERED", 0) == 0:
    print("  !! ENTERED is 0 for the whole file -- log_decisions may be broken.")
    print("     verify on the next fill:  Select-String -Path decisions.csv -Pattern ENTERED")
elif mismatch:
    print("  !! %d BUY(s) in this window but no ENTERED row" % len(mismatch))
else:
    print("  consistent")
print()

# --- 2. funnel --------------------------------------------------------------
def stage(x):
    if not x: return "(blank)"
    if "冷卻" in x or "黑名單" in x: return "cooldown/blacklist"
    if "過舊" in x: return "coin age too old"
    if "幣齡" in x: return "coin age new/unknown"
    if "流動性" in x: return "liquidity < 35k"
    if "分數" in x: return "score < 5.0"
    if "買盤" in x: return "buy_ratio < 52%"
    if "確認" in x: return "2-stage confirm"
    if "熔斷" in x: return "circuit breaker"
    if "鏈上" in x or "RPC" in x or "持倉查詢" in x or "權限" in x: return "on-chain gate"
    if "觸發" in x or "收集" in x or "等待" in x: return "price trigger"
    if "Jupiter" in x: return "no Jupiter quote"
    if "衝擊" in x: return "impact too high"
    return "other: " + x[:22]

c = collections.Counter(stage(r.get("reason") or "") for r in w)
tot = len(w)
print("STOP STAGE            rows    share")
for k, v in c.most_common():
    p = 100.0 * v / tot
    bar = "#" * int(p / 2)
    print("  %-22s %6d  %5.1f%% %s" % (k, v, p, bar))
print()

reached_onchain = sum(v for k, v in c.items()
                      if k in ("cooldown/blacklist", "coin age too old", "coin age new/unknown",
                               "liquidity < 35k", "score < 5.0", "buy_ratio < 52%",
                               "2-stage confirm", "circuit breaker"))
onchain_block = c.get("on-chain gate", 0)
past = reached_onchain - c.get("2-stage confirm", 0) - c.get("circuit breaker", 0)
print("reached on-chain check : %d" % past)
print("blocked by on-chain    : %d  (%.1f%% of those)" % (onchain_block, 100.0*onchain_block/max(1,past)))
if past and onchain_block == past:
    print("  !! 100%% blocked -- the on-chain gate is still a hard wall.")
print()

# --- 3. RPC health ----------------------------------------------------------
oc = collections.Counter(r.get("reason") for r in w
                         if any(k in (r.get("reason") or "")
                                for k in ("鏈上", "RPC", "持倉查詢")))
print("ON-CHAIN / RPC reason strings")
if not oc:
    print("  none -- RPC looks healthy")
for k, v in oc.most_common(8):
    print("  %5d  %s" % (v, k))
print()

# --- 4. candidate pool ------------------------------------------------------
def q(key, f):
    v = sorted(float(r[key]) for r in w if r.get(key))
    return v[min(len(v) - 1, int(len(v) * f))] if v else float("nan")
print("POOL  liquidity p50 %.0f / p90 %.0f   score p50 %.1f / p90 %.1f   buy p50 %.0f"
      % (q("liquidity", .5), q("liquidity", .9), q("score", .5), q("score", .9), q("buy_ratio", .5)))
ge5 = sum(1 for r in w if r.get("score") and float(r["score"]) >= 5.0)
print("      score >= 5.0: %.1f%% of observations" % (100.0 * ge5 / tot))
print()

# --- 5. files ---------------------------------------------------------------
for name, path in (("decisions.csv", DEC), ("trajectory.csv", TRAJ), ("sim_portfolio.json", PF)):
    if os.path.exists(path):
        st = os.stat(path)
        age = (datetime.now().timestamp() - st.st_mtime) / 60.0
        print("  %-20s %8.1f KB   updated %.1f min ago" % (name, st.st_size / 1024.0, age))
    else:
        print("  %-20s MISSING" % name)
print()
print("portfolio: cash $%.2f  positions %d  trades %d  pnl $%.2f"
      % (pf.get("cash", 0), len(pf.get("positions", [])), len(pf.get("trades", [])),
         pf.get("stats", {}).get("total_pnl", 0)))
