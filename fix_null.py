f = r"C:\Users\ANGEL\Doubao\chats\2026-09-12\new-chat\dex_scanner\app.js"
with open(f, "r", encoding="utf-8") as fh:
    c = fh.read()

c = c.replace(
    """    const allPnlEl = document.getElementById('pfAllPnl');
    allPnlEl.textContent = '$' + pf.total_equity.toFixed(2) + ' (' + (pf.all_time_pnl>=0?'+':'') + pf.all_time_pnl.toFixed(0) + ')';
    allPnlEl.className = 'num ' + (pf.all_time_pnl>=0?'up':'down');""",
    """    const allPnlEl = document.getElementById('pfAllPnl');
    if (allPnlEl) {
      allPnlEl.textContent = '$' + pf.total_equity.toFixed(2) + ' (' + (pf.all_time_pnl>=0?'+':'') + pf.all_time_pnl.toFixed(0) + ')';
      allPnlEl.className = 'num ' + (pf.all_time_pnl>=0?'up':'down');
    }"""
)

with open(f, "w", encoding="utf-8") as fh:
    fh.write(c)
print("done")
