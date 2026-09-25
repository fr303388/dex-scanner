f = r"C:\Users\ANGEL\Doubao\chats\2026-09-12\new-chat\dex_scanner\dashboard.html"
with open(f, "r", encoding="utf-8") as fh:
    c = fh.read()

# Add stats bar after portfolio summary
c = c.replace(
    '  </div>\n  <div class="pf-positions" id="pfPositions"></div>',
    '''  </div>
  <div id="pfStats" style="display:flex;gap:16px;padding:8px 12px;font-size:13px;color:#8b949e;border-top:1px solid #21262d">
    <span>勝 <b id="stWins" style="color:#3fb950">0</b></span>
    <span>敗 <b id="stLosses" style="color:#f85149">0</b></span>
    <span>被rug <b id="stRugs" style="color:#f85149">0</b></span>
    <span>賺 <b id="stWinAmt" style="color:#3fb950">$0</b></span>
    <span>賠 <b id="stLossAmt" style="color:#f85149">$0</b></span>
  </div>
  <div class="pf-positions" id="pfPositions"></div>'''
)

# Add JS to update stats
c = c.replace(
    "document.getElementById('pfValue').textContent = '$' + pf.total_value.toFixed(2);",
    """document.getElementById('pfValue').textContent = '$' + pf.total_value.toFixed(2);
    const st = pf.stats || {};
    document.getElementById('stWins').textContent = st.wins||0;
    document.getElementById('stLosses').textContent = st.losses||0;
    document.getElementById('stRugs').textContent = st.rugs||0;
    document.getElementById('stWinAmt').textContent = '$'+((st.win_amount||0).toFixed(2));
    document.getElementById('stLossAmt').textContent = '$'+((st.loss_amount||0).toFixed(2));"""
)

with open(f, "w", encoding="utf-8") as fh:
    fh.write(c)
print("done")
