import json
pf = {"positions": [], "started": "", "total_invested": 0, "trades": [], "capital": 1000}
with open(r"C:\Users\ANGEL\Doubao\chats\2026-09-12\new-chat\dex_scanner\portfolio.json", "w") as f:
    json.dump(pf, f, ensure_ascii=False, indent=2)
print("portfolio reset")
