f = r"C:\Users\ANGEL\Doubao\chats\2026-09-12\new-chat\dex_scanner\app.js"
with open(f, "r", encoding="utf-8") as fh:
    c = fh.read()

c = c.replace(
    """    } else if (walletType === 'Phantom') {
      // 直接顯示地址，餘額由後端讀取
      document.getElementById('walletBalance').textContent = '💰 Phantom 已連接';
      document.getElementById('walletBalDisplay').textContent = '已連接';
    }""",
    """    } else if (walletType === 'Phantom') {
      try {
        const r = await fetch('/api/balance/' + walletPubkey);
        const d = await r.json();
        if (d.ok) {
          document.getElementById('walletBalance').textContent = '💰 ' + d.sol.toFixed(4) + ' SOL';
          document.getElementById('walletBalDisplay').textContent = d.sol.toFixed(4) + ' SOL';
        } else {
          document.getElementById('walletBalance').textContent = '💰 讀取失敗';
          document.getElementById('walletBalDisplay').textContent = '--';
        }
      } catch(e) {
        document.getElementById('walletBalance').textContent = '💰 錯: ' + e.message.slice(0,20);
      }
    }"""
)

with open(f, "w", encoding="utf-8") as fh:
    fh.write(c)
print("done")
