import json, os
os.chdir(r"C:\Users\ANGEL\Doubao\chats\2026-09-12\new-chat\dex_scanner")
with open('portfolio.json', encoding='utf-8') as f:
    pf = json.load(f)

buys = [t for t in pf.get('trades', []) if t['action']=='BUY']
unique_coins = set(t['symbol'] for t in buys)
pf['stats']['unique_bought'] = len(unique_coins)
pf['stats']['total_buys'] = len(buys)

with open('portfolio.json', 'w', encoding='utf-8') as f:
    json.dump(pf, f, ensure_ascii=False, indent=2)

print(f"買入次數: {len(buys)}")
print(f"不同MEME幣: {len(unique_coins)}")
print(f"幣種: {', '.join(sorted(unique_coins))}")
