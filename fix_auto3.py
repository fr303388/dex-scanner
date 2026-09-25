f = r"C:\Users\ANGEL\Doubao\chats\2026-09-12\new-chat\dex_scanner\server.py"
with open(f, "r", encoding="utf-8") as fh:
    c = fh.read()

old = '''    if not pf["positions"] and all_tokens:
        now = datetime.now(UTC8).strftime("%Y-%m-%d %H:%M")
        pf["started"] = now
        pf["total_invested"] = 0
        for t in all_tokens[:3]:
            pf["positions"].append({
                "symbol": t["symbol"],
                "buy_price": t["price"],
                "buy_time": now,
                "invested": 100,
                "shares": 100 / t["price"] if t["price"] > 0 else 0,
                "url": t["url"],
                "buy_score": t["score"],
                "address": t.get("address",""),
                "chain": t.get("chain",""),
                "image": t.get("image","")
            })
            pf["total_invested"] += 100
        save_portfolio(pf)'''

new = '''    # AUTO BUY DISABLED - wait for wallet connection
    if not pf["positions"]:
        pf["started"] = pf.get("started", datetime.now(UTC8).strftime("%Y-%m-%d %H:%M"))
        pf["total_invested"] = 0'''

c = c.replace(old, new)

with open(f, "w", encoding="utf-8") as fh:
    fh.write(c)
print("done")
