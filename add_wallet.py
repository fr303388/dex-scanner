f = r"C:\Users\ANGEL\Doubao\chats\2026-09-12\new-chat\dex_scanner\dashboard.html"
with open(f, "r", encoding="utf-8") as fh:
    c = fh.read()

# Add wallet CSS
c = c.replace(
    "a { color:#58a6ff; text-decoration:none; } a:hover { text-decoration:underline; }",
    """a { color:#58a6ff; text-decoration:none; } a:hover { text-decoration:underline; }
.wallet-bar { display:flex; gap:8px; align-items:center; margin-bottom:14px; padding:10px 14px; background:#161b22; border:1px solid #30363d; border-radius:10px; }
.wallet-bar .wl-label { font-size:12px; color:#8b949e; margin-right:4px; }
.wl-btn { padding:6px 14px; border-radius:6px; border:1px solid #30363d; background:#21262d; color:#e6edf3; font-size:12px; cursor:pointer; display:flex; align-items:center; gap:6px; }
.wl-btn:hover { background:#30363d; }
.wl-btn.connected { border-color:#3fb950; color:#3fb950; }
.wl-addr { font-size:11px; color:#8b949e; margin-left:auto; font-family:monospace; }"""
)

# Add wallet bar after h1
c = c.replace(
    '<h1>🚀 迷因幣雷達 <span class="refresh" id="refresh">--</span></h1>',
    """<h1>🚀 迷因幣雷達 <span class="refresh" id="refresh">--</span></h1>
<div class="wallet-bar">
  <span class="wl-label">連接錢包:</span>
  <button class="wl-btn" id="btnPhantom" onclick="connectPhantom()">👻 Phantom</button>
  <button class="wl-btn" id="btnSolflare" onclick="connectSolflare()">☀️ Solflare</button>
  <button class="wl-btn" id="btnMetaMask" onclick="connectMetaMask()">🦊 MetaMask</button>
  <span class="wl-addr" id="walletAddr">未連接</span>
</div>"""
)

# Add wallet JS before closing script
wallet_js = """
// ===== 錢包連接 =====
let walletType = null;
let walletPubkey = null;

async function connectPhantom() {
  try {
    const provider = window.solana;
    if (!provider) { alert('請先安裝 Phantom 錢包\\nhttps://phantom.app/'); return; }
    const resp = await provider.connect();
    walletPubkey = resp.publicKey.toString();
    walletType = 'Phantom';
    document.getElementById('walletAddr').textContent = walletType + ': ' + walletPubkey.slice(0,4) + '...' + walletPubkey.slice(-4);
    document.getElementById('btnPhantom').classList.add('connected');
    alert('Phantom 連接成功！\\n' + walletPubkey);
  } catch(e) { alert('連接失敗: ' + e.message); }
}

async function connectSolflare() {
  try {
    const provider = window.solflare;
    if (!provider) { alert('請先安裝 Solflare 錢包\\nhttps://solflare.com/'); return; }
    const resp = await provider.connect();
    walletPubkey = resp.toString();
    walletType = 'Solflare';
    document.getElementById('walletAddr').textContent = walletType + ': ' + walletPubkey.slice(0,4) + '...' + walletPubkey.slice(-4);
    document.getElementById('btnSolflare').classList.add('connected');
    alert('Solflare 連接成功！\\n' + walletPubkey);
  } catch(e) { alert('連接失敗: ' + e.message); }
}

async function connectMetaMask() {
  try {
    if (!window.ethereum) { alert('請先安裝 MetaMask\\nhttps://metamask.io/'); return; }
    const accounts = await window.ethereum.request({ method: 'eth_requestAccounts' });
    walletPubkey = accounts[0];
    walletType = 'MetaMask';
    document.getElementById('walletAddr').textContent = walletType + ': ' + walletPubkey.slice(0,6) + '...' + walletPubkey.slice(-4);
    document.getElementById('btnMetaMask').classList.add('connected');
    alert('MetaMask 連接成功！\\n' + walletPubkey);
  } catch(e) { alert('連接失敗: ' + e.message); }
}
"""

c = c.replace("</script>", wallet_js + "</script>")

with open(f, "w", encoding="utf-8") as fh:
    fh.write(c)
print("done")
