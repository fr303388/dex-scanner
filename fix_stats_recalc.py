f = r"C:\Users\ANGEL\Doubao\chats\2026-09-12\new-chat\dex_scanner\server.py"
with open(f, "r", encoding="utf-8") as fh:
    c = fh.read()

# Remove the incremental stats block
old = '''            print(f"[SELL] {pos['symbol']} {sell_reason} 盈餘${round(pos['pnl'],2)}", flush=True)
            if "stats" not in pf:
                pf["stats"] = {"wins":0,"losses":0,"rugs":0,"win_amount":0,"loss_amount":0,"total_sells":0}
            pf["stats"]["total_sells"] += 1
            if "停損" in sell_reason:
                pf["stats"]["losses"] += 1
                pf["stats"]["loss_amount"] += pos["pnl"]
                if pos["pnl_pct"] <= -70:
                    pf["stats"]["rugs"] = pf["stats"].get("rugs", 0) + 1
            elif pos["pnl"] >= 0:
                pf["stats"]["wins"] += 1
                pf["stats"]["win_amount"] += pos["pnl"]
            else:
                pf["stats"]["losses"] += 1
                pf["stats"]["loss_amount"] += pos["pnl"]
        else:'''

new = '''            print(f"[SELL] {pos['symbol']} {sell_reason} 盈餘${round(pos['pnl'],2)}", flush=True)
        else:'''

c = c.replace(old, new)

# Add full recalc after save_portfolio, before computing totals
old2 = '''    pf["positions"] = kept
    save_portfolio(pf)'''

new2 = '''    pf["positions"] = kept
    # 從全部交易紀錄重算統計
    all_sells = [t for t in pf.get("trades",[]) if t["action"]=="SELL"]
    wins = [t for t in all_sells if t["pnl"]>0]
    losses = [t for t in all_sells if t["pnl"]<=0]
    rugs = [t for t in all_sells if t.get("pnl_pct",0)<=-70]
    buys = [t for t in pf.get("trades",[]) if t["action"]=="BUY"]
    pf["stats"] = {
        "wins": len(wins),
        "losses": len(losses),
        "rugs": len(rugs),
        "win_amount": round(sum(t["pnl"] for t in wins),2),
        "loss_amount": round(sum(t["pnl"] for t in losses),2),
        "total_sells": len(all_sells),
        "unique_bought": len(set(t["symbol"] for t in buys))
    }
    save_portfolio(pf)'''

c = c.replace(old2, new2)

with open(f, "w", encoding="utf-8") as fh:
    fh.write(c)
print("done")
