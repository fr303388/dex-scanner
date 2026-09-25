import json, os
os.chdir(r"C:\Users\ANGEL\Doubao\chats\2026-09-12\new-chat\dex_scanner")
with open('portfolio.json', encoding='utf-8') as f:
    pf = json.load(f)

sells = [t for t in pf.get('trades', []) if t['action']=='SELL']
wins = [t for t in sells if t['pnl']>0]
losses = [t for t in sells if t['pnl']<=0]
rugs = [t for t in sells if t.get('pnl_pct',0) <= -90]

pf['stats'] = {
    'wins': len(wins),
    'losses': len(losses),
    'rugs': len(rugs),
    'win_amount': round(sum(t['pnl'] for t in wins), 2),
    'loss_amount': round(sum(t['pnl'] for t in losses), 2),
    'total_sells': len(sells)
}

with open('portfolio.json', 'w', encoding='utf-8') as f:
    json.dump(pf, f, ensure_ascii=False, indent=2)

print(f"勝: {len(wins)} 賺 ${pf['stats']['win_amount']}")
print(f"敗: {len(losses)} 賠 ${pf['stats']['loss_amount']}")
print(f"被rug: {len(rugs)}")
print(f"勝率: {len(wins)/(len(wins)+len(losses))*100:.0f}%")
