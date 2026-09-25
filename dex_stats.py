import json, os
os.chdir(r"C:\Users\ANGEL\Doubao\chats\2026-09-12\new-chat\dex_scanner")
with open('portfolio.json', encoding='utf-8') as f:
    pf = json.load(f)

trades = pf.get('trades', [])
sells = [t for t in trades if t['action']=='SELL']
print(f"總交易: {len(trades)}  賣出: {len(sells)}")

wins = [t for t in sells if t['pnl']>0]
losses = [t for t in sells if t['pnl']<=0]
rugs = [t for t in sells if t.get('pnl_pct',0) <= -90]

print(f"\n勝: {len(wins)} 筆, 賺 ${sum(t['pnl'] for t in wins):.2f}")
print(f"敗: {len(losses)} 筆, 賠 ${sum(t['pnl'] for t in losses):.2f}")
print(f"被rug(-90%+): {len(rugs)} 筆")

if wins+losses:
    print(f"勝率: {len(wins)/(len(wins)+len(losses))*100:.0f}%")

print("\n所有賣出:")
for t in sells:
    print(f"  {t['symbol']} pnl=${t['pnl']:.2f} ({t['pnl_pct']}%) {t['reason']}")
