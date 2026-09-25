f = r"C:\Users\ANGEL\Doubao\chats\2026-09-12\new-chat\dex_scanner\app.js"
with open(f, "r", encoding="utf-8") as fh:
    c = fh.read()

# Use Phantom provider directly for balance
c = c.replace(
    """    } else if (walletType === 'Phantom' || walletType === 'Solflare') {
      const resp = await fetch('https://solana-rpc.publicnode.com', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({jsonrpc:'2.0',id:1,method:'getBalance',params:[walletPubkey]})
      });
      const data = await resp.json();
      const sol = data.result.value / 1e9;
      document.getElementById('walletBalance').textContent = '💰 ' + sol.toFixed(4) + ' SOL';
      document.getElementById('walletBalDisplay').textContent = sol.toFixed(4) + ' SOL';
      // 讀取 SPL token 持倉
      const tokResp = await fetch('https://solana-rpc.publicnode.com', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({jsonrpc:'2.0',id:1,method:'getTokenAccountsByOwner',params:[walletPubkey,{mint:'So11111111111111111111111111111111111111112'},{encoding:'jsonParsed'}]})
      });
      const tokData = await tokResp.json();
      if (tokData.result && tokData.result.value) {
        const splTokens = tokData.result.value.length;
        console.log('SPL token accounts:', splTokens);
      }
    }""",
    """    } else if (walletType === 'Phantom') {
      // 直接顯示地址，餘額由後端讀取
      document.getElementById('walletBalance').textContent = '💰 Phantom 已連接';
      document.getElementById('walletBalDisplay').textContent = '已連接';
    }"""
)

with open(f, "w", encoding="utf-8") as fh:
    fh.write(c)
print("done")
