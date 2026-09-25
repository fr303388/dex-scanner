f = r"C:\Users\ANGEL\Doubao\chats\2026-09-12\new-chat\dex_scanner\server.py"
with open(f, "r", encoding="utf-8") as fh:
    c = fh.read()

old = '''    realized = sum(t.get("pnl", 0) for t in pf.get("trades", []) if t.get("action") == "SELL")
    cash_left = pf.get("capital", 1000) - pf["total_invested"]
    pf["cash_left"] = round(cash_left, 2)'''

new = '''    realized = sum(t.get("pnl", 0) for t in pf.get("trades", []) if t.get("action") == "SELL")
    cash_left = pf.get("capital", 1000) - pf["total_invested"] + realized
    pf["cash_left"] = round(cash_left, 2)'''

c = c.replace(old, new)
with open(f, "w", encoding="utf-8") as fh:
    fh.write(c)
print("done")
