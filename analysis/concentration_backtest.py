"""Does holder concentration separate the 20 dead stopped-out tokens from
the 4 survivors?

This is the validation that decides whether restoring the concentration
check is worth wiring in. We already know the outcome of every stopped-out
trade from the live on-chain check, so we can measure the filter against
known labels instead of guessing.

Ground truth from live_check.py:
    DEAD / DELISTED : 20 of 24
    ALIVE           : 4 of 24  (SI, ARTHUR, baton, GP)
"""
import json, io, os, csv, time, base64, collections, urllib.request, urllib.error

D = r"C:\Users\ANGEL\Doubao\chats\2026-09-27\new-chat-10\dex-scanner"
RPC = "https://api.mainnet-beta.solana.com"
P2022 = "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"
POLD  = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"

pf = json.load(io.open(os.path.join(D, "sim_portfolio.json"), encoding="utf-8"))
sells = [t for t in pf["trades"] if t["action"] == "SELL"]
stopped = [t for t in sells if (t.get("pnl_pct") or 0) < 0]
entry_liq = {}
for r in csv.DictReader(io.open(os.path.join(D, "decisions.csv"), encoding="utf-8")):
    if r.get("decision") == "ENTERED" or r.get("reason") == "ENTERED":
        entry_liq.setdefault(r["address"], r.get("liquidity"))

# ground truth, from the live check
ALIVE = {"SI", "ARTHUR", "baton", "GP"}          # survived on-chain
DELISTED = {"BUBBLE", "Speed", "COCKROACH", "inu", "NEWCAT", "LEVERAGE",
            "goon", "swordcat", "INSTA", "BOB", "XSI", "SpaceXSI", "CHILL"}
# (NEWCAT is a typo guard; the real symbol is NEARCAT)
ALIVE |= {"SI", "ARTHUR", "baton", "GP"}


def rpc(method, params, timeout=45):
    req = urllib.request.Request(
        RPC,
        data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": method,
                         "params": params}).encode(),
        headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def concentration(addr):
    """Return (n_holders, top1%, top10%, top20%) or raise."""
    j = rpc("getAccountInfo", [addr, {"encoding": "jsonParsed"}])
    v = ((j.get("result") or {}).get("value") or {})
    info = ((v.get("data") or {}).get("parsed") or {}).get("info") or {}
    if not info:
        raise RuntimeError("no mint info (likely delisted)")
    is_2022 = bool(info.get("extensions"))
    pid = P2022 if is_2022 else POLD
    j2 = rpc("getProgramAccounts", [pid, {
        "encoding": "base64",
        "filters": [{"dataSize": 165},
                    {"memcmp": {"offset": 0, "bytes": addr}}]}])
    if "error" in j2:
        raise RuntimeError(str(j2["error"].get("message"))[:40])
    amts = []
    for a in j2.get("result") or []:
        try:
            b = base64.b64decode(a["account"]["data"][0])
            amt = int.from_bytes(b[64:72], "little")
            if amt > 0: amts.append(amt)
        except Exception:
            pass
    if not amts:
        raise RuntimeError("no non-zero holders")
    tot = sum(amts); amts.sort(reverse=True)
    return (len(amts), amts[0]/tot*100, sum(amts[:10])/tot*100,
            sum(amts[:20])/tot*100)


W = 78
print("=" * W)
print("HOLDER CONCENTRATION vs KNOWN OUTCOME  (24 stopped-out trades)")
print("=" * W)
print("  %-11s %8s %7s %8s %8s  %s" % ("symbol", "exit%", "holders", "top1%", "top10%", "on-chain"))
rows = []
for s in sorted(stopped, key=lambda x: x.get("pnl_pct") or 0):
    sym = s["symbol"]; a = s.get("address")
    ex = s.get("pnl_pct")
    try:
        n, t1, t10, t20 = concentration(a)
        truth = "ALIVE" if sym in ALIVE else "DEAD/delisted"
        rows.append((sym, ex, n, t1, t10, truth))
        print("  %-11s %+8.1f %7d %7.1f%% %7.1f%%  %s" % (sym, ex, n, t1, t10, truth))
    except Exception as e:
        print("  %-11s %+8.1f %7s %8s %8s  %s" % (sym, ex, "n/a", "n/a", "n/a",
                                                    "RPC: %s" % str(e)[:34]))
    time.sleep(0.6)

good = [r for r in rows if r[5] == "ALIVE"]
dead = [r for r in rows if r[5].startswith("DEAD")]
print()
print("=" * W)
print("DOES CONCENTRATION SEPARATE THEM?")
print("=" * W)
if good and dead:
    def med(v): 
        v = sorted(v); n = len(v)
        return v[n//2] if n % 2 else (v[n//2-1]+v[n//2])/2
    print("  %-22s %6s %10s %10s" % ("group", "n", "med top1%", "med top10%"))
    print("  %-22s %6d %9.1f%% %9.1f%%" % ("ALIVE (survived)", len(good),
          med([r[3] for r in good]), med([r[4] for r in good])))
    print("  %-22s %6d %9.1f%% %9.1f%%" % ("DEAD (delisted)", len(dead),
          med([r[3] for r in dead]), med([r[4] for r in dead])))
    print()
    for thr in (10, 20, 30, 40, 50):
        tp = sum(1 for r in dead if r[3] < thr)
        fp = sum(1 for r in good if r[3] < thr)
        print("    rule: reject if top1 > %2d%%   -> catches %2d/%2d dead, wrongly rejects %d/%d alive"
              % (thr, tp, len(dead), fp, len(good)))
    print()
    def corr(xs, ys):
        n = len(xs)
        if n < 3: return None
        mx = sum(xs)/n; my = sum(ys)/n
        num = sum((x-mx)*(y-my) for x, y in zip(xs, ys))
        dx = (sum((x-mx)**2 for x in xs))**.5; dy = (sum((y-my)**2 for y in ys))**.5
        return num/(dx*dy) if dx and dy else None
    ys = [1 if r[5] == "ALIVE" else 0 for r in rows]
    r1 = corr([r[3] for r in rows], ys)
    r10 = corr([r[4] for r in rows], ys)
    print("  r(top1%%,  survived) = %s" % (("%+.3f" % r1) if r1 is not None else "-"))
    print("  r(top10%%, survived) = %s" % (("%+.10f".replace("10","3f") % r10) if r10 is not None else "-"))
else:
    print("  not enough labelled data")
