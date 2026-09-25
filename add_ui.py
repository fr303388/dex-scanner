f = r"C:\Users\ANGEL\Doubao\chats\2026-09-12\new-chat\dex_scanner\dashboard.html"
with open(f, "r", encoding="utf-8") as fh:
    c = fh.read()

# HTML: 在總盈虧後面加全體盈虧
c = c.replace(
    '<div class="pf-stat"><div class="lbl">總盈虧</div><div class="num" id="pfPnl">--</div></div>\n  </div>',
    '<div class="pf-stat"><div class="lbl">總盈虧</div><div class="num" id="pfPnl">--</div></div>\n    <div class="pf-stat"><div class="lbl">全體盈虧($1000起)</div><div class="num" id="pfAllPnl">--</div></div>\n  </div>'
)

# JS: 在 pnlEl.className 後面加全體盈虧
c = c.replace(
    "pnlEl.className = 'num ' + (pf.total_pnl>=0?'up':'down');",
    "pnlEl.className = 'num ' + (pf.total_pnl>=0?'up':'down');\n    const allPnlEl = document.getElementById('pfAllPnl');\n    allPnlEl.textContent = (pf.all_time_pnl>=0?'+':'') + '$' + pf.all_time_pnl.toFixed(2) + ' (' + (pf.all_time_pnl_pct>=0?'+':'') + pf.all_time_pnl_pct + '%)';\n    allPnlEl.className = 'num ' + (pf.all_time_pnl>=0?'up':'down');"
)

with open(f, "w", encoding="utf-8") as fh:
    fh.write(c)
print("done")
