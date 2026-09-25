f = r"C:\Users\ANGEL\Doubao\chats\2026-09-12\new-chat\dex_scanner\dashboard.html"
with open(f, "r", encoding="utf-8") as fh:
    c = fh.read()

# Fix recTrack pnl undefined
c = c.replace(
    '${recTrack[t.symbol] ? `<span class="${recTrack[t.symbol].pnl>=0?"up":"down"}" style="font-weight:bold">餘額 $${(100*(1+recTrack[t.symbol].pnl/100)).toFixed(2)} (${recTrack[t.symbol].pnl>=0?"+":""}${recTrack[t.symbol].pnl}%)</span>` : ""}',
    '${recTrack[t.symbol] ? `<span class="${(recTrack[t.symbol].pnl||0)>=0?"up":"down"}" style="font-weight:bold">餘額 $${(100*(1+(recTrack[t.symbol].pnl||0)/100)).toFixed(2)} (${(recTrack[t.symbol].pnl||0)>=0?"+":""}${(recTrack[t.symbol].pnl||0)}%)</span>` : ""}'
)

with open(f, "w", encoding="utf-8") as fh:
    fh.write(c)
print("done")
