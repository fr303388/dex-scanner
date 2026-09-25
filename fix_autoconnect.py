f = r"C:\Users\ANGEL\Doubao\chats\2026-09-12\new-chat\dex_scanner\app.js"
with open(f, "r", encoding="utf-8") as fh:
    c = fh.read()

c = c.replace(
    "load(); setInterval(load, 5000);",
    """load(); setInterval(load, 5000);

// 自動重連 Phantom
(async function autoReconnect() {
  try {
    if (window.solana && window.solana.isPhantom) {
      const resp = await window.solana.connect({ onlyIfTrusted: true });
      walletPubkey = resp.publicKey.toString();
      walletType = 'Phantom';
      document.getElementById('walletAddr').textContent = walletType + ': ' + walletPubkey.slice(0,4) + '...' + walletPubkey.slice(-4);
      setTimeout(fetchBalance, 300);
    }
  } catch(e) {}
})();"""
)

with open(f, "w", encoding="utf-8") as fh:
    fh.write(c)
print("done")
