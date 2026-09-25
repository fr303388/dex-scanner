f = r"C:\Users\ANGEL\Doubao\chats\2026-09-12\new-chat\dex_scanner\server.py"
with open(f, "r", encoding="utf-8") as fh:
    c = fh.read()

# 1. 改標題和初始建倉邏輯
old_init = '''    # 自動建倉：如果是空倉，買前三名
    pf = load_portfolio()
    if not pf["positions"] and all_tokens:
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

new_init = '''    # 模擬組合：本金$1000，每筆$100，停利+50% / 停損-50%
    pf = load_portfolio()
    pf.setdefault("trades", [])
    pf.setdefault("capital", 1000)
    if not pf["positions"] and all_tokens:
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

c = c.replace(old_init, new_init)

# 2. 改停損/停利邏輯
old_sl = '''    # 止虧：虧損超過 50% 自動賣出，換下一個
    STOP_LOSS_PCT = -50.0
    kept = []
    for pos in pf["positions"]:
        if pos["pnl_pct"] <= STOP_LOSS_PCT:
            continue  # 忍痛剃除
        kept.append(pos)
    
    # 主動追蹤：新推薦幣(score>=4)出現時自動買入$100，最多8倉
    held_syms = [p["symbol"] for p in kept]
    fresh = [t for t in all_tokens if t["symbol"] not in held_syms and t["score"] >= 4]
    for t in fresh:
        if len(kept) >= 8: break
        now2 = datetime.now(UTC8).strftime("%Y-%m-%d %H:%M")
        kept.append({
            "symbol": t["symbol"], "buy_price": t["price"], "buy_time": now2,
            "invested": 100, "shares": 100/t["price"] if t["price"]>0 else 0,
            "url": t["url"], "buy_score": t["score"],
            "address": t.get("address",""), "chain": t.get("chain",""),
            "image": t.get("image","")
        })
        pf["total_invested"] += 100
        print(f"[NEW] 買入 {t['symbol']} @ ${t['price']} score={t['score']}", flush=True)

    if len(kept) < len(pf["positions"]):
        # 有被剃除的，從推薦中補新的
        held_symbols = [p["symbol"] for p in kept]
        while len(kept) < 8:
            candidates = [t for t in all_tokens if t["symbol"] not in held_symbols and t["score"] >= 0]
            candidates.sort(key=lambda x: x["score"], reverse=True)
            if not candidates: break
            nxt = candidates[0]
            now = datetime.now(UTC8).strftime("%Y-%m-%d %H:%M")
            kept.append({
                "symbol": nxt["symbol"], "buy_price": nxt["price"], "buy_time": now,
                "invested": 100, "shares": 100 / nxt["price"] if nxt["price"] > 0 else 0,
                "url": nxt["url"], "buy_score": nxt["score"],
                "address": nxt.get("address",""), "chain": nxt.get("chain",""),
            })
            held_symbols.append(nxt["symbol"])
    pf["positions"] = kept
    save_portfolio(pf)'''

new_sl = '''    # 停利+50% / 停損-50%
    TAKE_PROFIT_PCT = 50.0
    STOP_LOSS_PCT = -50.0
    kept = []
    now_str = datetime.now(UTC8).strftime("%Y-%m-%d %H:%M")
    for pos in pf["positions"]:
        sell_reason = None
        if pos["pnl_pct"] >= TAKE_PROFIT_PCT:
            sell_reason = f"停利+{pos['pnl_pct']}%"
        elif pos["pnl_pct"] <= STOP_LOSS_PCT:
            sell_reason = f"停損{pos['pnl_pct']}%"
        if sell_reason:
            pf["trades"].append({
                "time": now_str, "symbol": pos["symbol"],
                "action": "SELL", "buy_price": pos["buy_price"],
                "sell_price": pos["current_price"], "pnl": round(pos["pnl"],2),
                "pnl_pct": pos["pnl_pct"], "reason": sell_reason
            })
            print(f"[SELL] {pos['symbol']} {sell_reason} 盈餘${round(pos['pnl'],2)}", flush=True)
        else:
            kept.append(pos)
    
    # 主動追蹤：新推薦幣(score>=4)出現時自動買入$100，最多10倉（$1000本金）
    held_syms = [p["symbol"] for p in kept]
    fresh = [t for t in all_tokens if t["symbol"] not in held_syms and t["score"] >= 4]
    for t in fresh:
        if len(kept) >= 10: break
        now2 = datetime.now(UTC8).strftime("%Y-%m-%d %H:%M")
        kept.append({
            "symbol": t["symbol"], "buy_price": t["price"], "buy_time": now2,
            "invested": 100, "shares": 100/t["price"] if t["price"]>0 else 0,
            "url": t["url"], "buy_score": t["score"],
            "address": t.get("address",""), "chain": t.get("chain",""),
            "image": t.get("image","")
        })
        pf["trades"].append({
            "time": now2, "symbol": t["symbol"],
            "action": "BUY", "buy_price": t["price"],
            "sell_price": 0, "pnl": 0, "pnl_pct": 0,
            "reason": f"推薦score={t['score']}"
        })
        pf["total_invested"] += 100
        print(f"[NEW] 買入 {t['symbol']} @ ${t['price']} score={t['score']}", flush=True)

    pf["positions"] = kept
    save_portfolio(pf)'''

c = c.replace(old_sl, new_sl)

with open(f, "w", encoding="utf-8") as fh:
    fh.write(c)
print("done")
