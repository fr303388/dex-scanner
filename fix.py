f = r'C:\Users\ANGEL\Doubao\chats\2026-09-12\new-chat\dex_scanner\dashboard.html'
with open(f, 'r', encoding='utf-8') as fh:
    lines = fh.readlines()
new_line = '''${recTrack[t.symbol] ? `<span class="${recTrack[t.symbol].pnl>=0?"up":"down"}" style="font-weight:bold">餘額 $${(100*(1+recTrack[t.symbol].pnl/100)).toFixed(2)} (${recTrack[t.symbol].pnl>=0?"+":""}${recTrack[t.symbol].pnl}%)</span>` : ""}\n'''
lines[123] = new_line
with open(f, 'w', encoding='utf-8') as fh:
    fh.writelines(lines)
print(lines[123].strip())
