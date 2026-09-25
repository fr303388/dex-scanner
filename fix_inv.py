f = r"C:\Users\ANGEL\Doubao\chats\2026-09-12\new-chat\dex_scanner\server.py"
with open(f, "r", encoding="utf-8") as fh:
    c = fh.read()

old = '''    pf["total_value"] = sum(p.get("current_value", p["invested"]) for p in pf["positions"])
    pf["total_pnl"] = pf["total_value"] - pf["total_invested"]'''

new = '''    pf["total_value"] = sum(p.get("current_value", p["invested"]) for p in pf["positions"])
    pf["total_invested"] = sum(p["invested"] for p in pf["positions"])
    pf["total_pnl"] = pf["total_value"] - pf["total_invested"]'''

c = c.replace(old, new)
with open(f, "w", encoding="utf-8") as fh:
    fh.write(c)
print("done")
