f = r"C:\Users\ANGEL\Doubao\chats\2026-09-12\new-chat\dex_scanner\dashboard.html"
with open(f, "r", encoding="utf-8") as fh:
    c = fh.read()

# 改標題
c = c.replace(
    '<div class="lbl">全體盈虧($1000起)</div>',
    '<div class="lbl">總資產($1000起)</div>'
)

# 改 JS 顯示總資產而非盈虧
c = c.replace(
    """allPnlEl.textContent = (pf.all_time_pnl>=0?'+':'') + '$' + pf.all_time_pnl.toFixed(2) + ' (' + (pf.all_time_pnl_pct>=0?'+':'') + pf.all_time_pnl_pct + '%)';""",
    """allPnlEl.textContent = '$' + pf.total_equity.toFixed(2) + ' (' + (pf.all_time_pnl>=0?'+':'') + pf.all_time_pnl.toFixed(0) + ')';"""
)

with open(f, "w", encoding="utf-8") as fh:
    fh.write(c)
print("done")
