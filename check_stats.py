import json, os
os.chdir(r"C:\Users\ANGEL\Doubao\chats\2026-09-12\new-chat\dex_scanner")
with open('portfolio.json', encoding='utf-8') as f:
    pf = json.load(f)

print("saved stats:", json.dumps(pf.get("stats",{}), ensure_ascii=False))
print(f"positions: {len(pf.get('positions',[]))}")
trades = pf.get("trades",[])
print(f"total trades: {len(trades)}")

sells = [t for t in trades if t["action"]=="SELL"]
wins = [t for t in sells if t["pnl"]>0]
losses = [t for t in sells if t["pnl"]<=0]
rugs = [t for t in sells if t.get("pnl_pct",0)<=-70]
buys = [t for t in trades if t["action"]=="BUY"]
coins = set(t["symbol"] for t in buys)

print(f"\n實際計算:")
print(f"wins: {len(wins)}  amt=${sum(t['pnl'] for t in wins):.2f}")
print(f"losses: {len(losses)}  amt=${sum(t['pnl'] for t in losses):.2f}")
print(f"rugs(-70%): {len(rugs)}")
print(f"unique coins: {len(coins)}")

# 補算最新
pf["stats"] = {
    "wins": len(wins),
    "losses": len(losses),
    "rugs": len(rugs),
    "win_amount": round(sum(t["pnl"] for t in wins),2),
    "loss_amount": round(sum(t["pnl"] for t in losses),2),
    "total_sells": len(sells),
    "unique_bought": len(coins)
}
with open("portfolio.json","w",encoding="utf-8") as f:
    json.dump(pf,f,ensure_ascii=False,indent=2)
print("\n已更新 portfolio.json")
