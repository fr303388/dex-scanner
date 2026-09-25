f = r"C:\Users\ANGEL\Doubao\chats\2026-09-12\new-chat\dex_scanner\server.py"
with open(f, "r", encoding="utf-8") as fh:
    c = fh.read()

old = '''    pf["total_value"] = sum(p.get("current_value", p["invested"]) for p in pf["positions"])
    pf["total_pnl"] = pf["total_value"] - pf["total_invested"]
    pf["total_pnl_pct"] = round((pf["total_pnl"] / pf["total_invested"]) * 100, 1) if pf["total_invested"] > 0 else 0'''

new = '''    pf["total_value"] = sum(p.get("current_value", p["invested"]) for p in pf["positions"])
    pf["total_pnl"] = pf["total_value"] - pf["total_invested"]
    pf["total_pnl_pct"] = round((pf["total_pnl"] / pf["total_invested"]) * 100, 1) if pf["total_invested"] > 0 else 0
    # 從$1000本金開始的總盈虧（含已實現）
    realized = sum(t.get("pnl", 0) for t in pf.get("trades", []) if t.get("action") == "SELL")
    cash_left = pf.get("capital", 1000) - pf["total_invested"]
    pf["cash_left"] = round(cash_left, 2)
    pf["realized_pnl"] = round(realized, 2)
    pf["total_equity"] = round(pf["total_value"] + cash_left, 2)
    pf["all_time_pnl"] = round(pf["total_equity"] - pf.get("capital", 1000), 2)
    pf["all_time_pnl_pct"] = round((pf["all_time_pnl"] / pf.get("capital", 1000)) * 100, 1)'''

c = c.replace(old, new)
with open(f, "w", encoding="utf-8") as fh:
    fh.write(c)
print("done")
