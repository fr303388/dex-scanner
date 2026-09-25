f = r"C:\Users\ANGEL\Doubao\chats\2026-09-12\new-chat\dex_scanner\server.py"
with open(f, "r", encoding="utf-8") as fh:
    c = fh.read()

c = c.replace("if pos[\"pnl_pct\"] <= -90:", "if pos[\"pnl_pct\"] <= -70:")

with open(f, "w", encoding="utf-8") as fh:
    fh.write(c)
print("server done")

# UI
f2 = r"C:\Users\ANGEL\Doubao\chats\2026-09-12\new-chat\dex_scanner\dashboard.html"
with open(f2, "r", encoding="utf-8") as fh:
    d = fh.read()

d = d.replace("被rug(-99%)", "被rug(-70%)")

with open(f2, "w", encoding="utf-8") as fh:
    fh.write(d)
print("ui done")

# Backfill stats
import json
with open(r"C:\Users\ANGEL\Doubao\chats\2026-09-12\new-chat\dex_scanner\portfolio.json", encoding="utf-8") as fh:
    pf = json.load(fh)
sells = [t for t in pf.get("trades", []) if t["action"]=="SELL"]
rugs = [t for t in sells if t.get("pnl_pct",0) <= -70]
pf["stats"]["rugs"] = len(rugs)
with open(r"C:\Users\ANGEL\Doubao\chats\2026-09-12\new-chat\dex_scanner\portfolio.json", "w", encoding="utf-8") as fh:
    json.dump(pf, fh, ensure_ascii=False, indent=2)
print(f"rug(-70%) count: {len(rugs)}")
