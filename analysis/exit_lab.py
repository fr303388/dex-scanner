"""Extended counterfactual exit analysis. Re-runnable at any time.

Compares the live rules against scale-out variants on every closed trade,
using the 15s path in trajectory.csv.

Scale-out model (single position, no compounding):
    realized = frac1*exit1 + frac2*exit2 + rest*final_exit
where exit1/exit2 are the pnl% at the first crossing of each threshold and
final_exit is what the position actually exited at.

Vol stop model:
    exit when pnl <= clamp(-k*ATR_15s, VOL_MIN, VOL_MAX), requiring at least
    VOL_MIN_SAMPLES of history so the ATR estimate exists.

A cell shows the exit the position WOULD have had under that rule. '--' means
the rule never fired, so it did not change the outcome.
"""
import csv, io, os, json, collections, sys

D = r"C:\Users\ANGEL\Doubao\chats\2026-09-27\new-chat-10\dex-scanner"
VOL_MIN, VOL_MAX, VOL_MIN_SAMPLES = -6.0, -12.0, 20
SCALE_PAIRS = [(15, 30), (20, 40), (25, 50), (30, 60), (40, None)]

def f(v):
    try: return float(v)
    except (TypeError, ValueError): return None

def load():
    pf = json.load(io.open(os.path.join(D, "sim_portfolio.json"), encoding="utf-8"))
    by = collections.defaultdict(list)
    for r in csv.DictReader(io.open(os.path.join(D, "trajectory.csv"), encoding="utf-8")):
        by[r["address"]].append(r)
    for v in by.values():
        v.sort(key=lambda x: int(x["ts"]))
    return [t for t in pf["trades"] if t["action"] == "SELL"], by

def first_cross(pv, thr):
    for p in pv:
        if p is not None and p >= thr:
            return p
    return None

def vol_exit(pv, pxs, k):
    for i, p in enumerate(pv):
        if p is None: continue
        r2 = [(pxs[j] - pxs[j-1]) / pxs[j-1] * 100
              for j in range(1, min(len(pxs), i+1)) if pxs[j-1]]
        if len(r2) < VOL_MIN_SAMPLES: continue
        m = sum(r2) / len(r2)
        sd = (sum((x-m)**2 for x in r2) / len(r2)) ** 0.5
        if p <= max(VOL_MAX, min(VOL_MIN, -k * sd)):
            return p
    return None

def main():
    sells, by = load()
    rows = []
    for s in sells:
        t = by.get(s["address"], [])
        if not t: continue
        act = f(s.get("pnl_pct")); mfe = f(s.get("mfe"))
        if act is None: continue
        pv = [f(r["pnl_pct"]) for r in t]
        pxs = [f(r["price"]) for r in t]
        pxs = [x for x in pxs if x is not None]
        rec = {"sym": s["symbol"], "mfe": mfe, "act": act, "n": len(t)}
        for a, b in SCALE_PAIRS:
            e1 = first_cross(pv, a)
            e2 = first_cross(pv, b) if b else None
            # 40% at e1, 40% at e2, 20% rides to the real exit
            if e1 is None:
                rec["so%d" % a] = None
            elif e2 is None:
                rec["so%d" % a] = 0.4 * e1 + 0.6 * act
            else:
                rec["so%d" % a] = 0.4 * e1 + 0.4 * e2 + 0.2 * act
        for k in (1.5, 2.0, 3.0):
            rec["vs%s" % k] = vol_exit(pv, pxs, k)
        rows.append(rec)

    keys = ["act"] + ["so%d" % a for a, _ in SCALE_PAIRS] + ["vs1.5", "vs2.0", "vs3.0"]
    hdr = ["actual"] + ["so%d" % a for a, _ in SCALE_PAIRS] + ["vs1.5", "vs2.0", "vs3.0"]

    print("=" * (14 + 8 * len(hdr)))
    print("COUNTERFACTUAL EXITS  --  %d closed trades" % len(rows))
    print("=" * (14 + 8 * len(hdr)))
    print("%-12s %8s" % ("symbol", "MFE") + "".join("%8s" % h for h in hdr))
    print("-" * (14 + 8 * len(hdr)))
    fmt = lambda v: ("%+6.1f" % v) if v is not None else "   --  "
    for r in rows:
        print("%-12s %+7.1f" % (r["sym"], r["mfe"] if r["mfe"] is not None else float("nan"))
              + "".join("%8s" % fmt(r.get(k)) for k in keys))
    print("-" * (14 + 8 * len(hdr)))

    def stat(sel, vals):
        v = [x for x in vals if x is not None]
        if not v: return None, 0
        v = sorted(v)
        return v[len(v)//2], len(v)

    print("%-12s %8s" % ("MEDIAN", "") + "".join(
        "%8s" % fmt(stat(None, [r.get(k) for r in rows])[0]) for k in keys))
    print("%-12s %8s" % ("fired", "") + "".join(
        "%8d" % stat(None, [r.get(k) for r in rows])[1] for k in keys))
    print("%-12s %8.1f" % ("SUM pp", sum(r["act"] for r in rows)) + "".join(
        "%8.1f" % sum(x for x in (r.get(k) for r in rows) if x is not None) for k in keys))
    print()
    print("Scale-out = sell 40%% at the first crossing, 40%% at the second")
    print("threshold, let the remaining 20%% ride to the recorded exit.")
    print("A '--' means the rule never fired on that position.")
    print()
    print("VERDICT GUIDE: a rule is only credible once 'fired' is >= 30.")
    print("              Below that, differences are single-trade noise.")

if __name__ == "__main__":
    main()
