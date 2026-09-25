f = r"C:\Users\ANGEL\Doubao\chats\2026-09-12\new-chat\dex_scanner\server.py"
with open(f, "r", encoding="utf-8") as fh:
    c = fh.read()

old = '''            print(f"[SELL] {pos['symbol']} {sell_reason} 盈餘${round(pos['pnl'],2)}", flush=True)
        else:'''

new = '''            print(f"[SELL] {pos['symbol']} {sell_reason} 盈餘${round(pos['pnl'],2)}", flush=True)
            if "stats" not in pf:
                pf["stats"] = {"wins":0,"losses":0,"rugs":0,"win_amount":0,"loss_amount":0,"total_sells":0}
            pf["stats"]["total_sells"] += 1
            if "停損" in sell_reason:
                pf["stats"]["rugs"] += 1
                pf["stats"]["losses"] += 1
                pf["stats"]["loss_amount"] += pos["pnl"]
            elif pos["pnl"] >= 0:
                pf["stats"]["wins"] += 1
                pf["stats"]["win_amount"] += pos["pnl"]
            else:
                pf["stats"]["losses"] += 1
                pf["stats"]["loss_amount"] += pos["pnl"]
        else:'''

c = c.replace(old, new)
with open(f, "w", encoding="utf-8") as fh:
    fh.write(c)
print("done")
