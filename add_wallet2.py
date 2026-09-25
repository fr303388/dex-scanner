f = r"C:\Users\ANGEL\Doubao\chats\2026-09-12\new-chat\dex_scanner\dashboard.html"
with open(f, "r", encoding="utf-8") as fh:
    c = fh.read()

# Add wallet buttons after h1
old_h1 = '<h1>🚀 迷因幣雷達 <span class="refresh" id="refresh">--</span></h1>'
new_h1 = '''<h1>🚀 迷因幣雷達 <span class="refresh" id="refresh">--</span></h1>
<div style="display:flex;gap:8px;align-items:center;margin-bottom:12px;flex-wrap:wrap">
  <span style="font-size:12px;color:#8b949e">連接錢包:</span>
  <button onclick="connectPhantom()" style="background:#161b22;border:1px solid #30363d;color:#e6edf3;padding:6px 14px;border-radius:6px;cursor:pointer;font-size:12px">👻 Phantom</button>
  <button onclick="connectSolflare()" style="background:#161b22;border:1px solid #30363d;color:#e6edf3;padding:6px 14px;border-radius:6px;cursor:pointer;font-size:12px">☀️ Solflare</button>
  <button onclick="connectMetaMask()" style="background:#161b22;border:1px solid #30363d;color:#e6edf3;padding:6px 14px;border-radius:6px;cursor:pointer;font-size:12px">🦊 MetaMask</button>
  <span id="walletAddr" style="font-size:12px;color:#3fb950"></span>
</div>'''
c = c.replace(old_h1, new_h1, 1)

# Add wallet JS after unlockAudio section
old_audio = "document.addEventListener('keydown', unlockAudio);"
new_audio = '''document.addEventListener('keydown', unlockAudio);

// ===== 錢包連接 =====
let walletType = null, walletPubkey = null;
async function connectPhantom() {
  try {
    if (!window.solana) { alert('請先安裝 Phantom: https://phantom.app/'); return; }
    const r = await window.solana.connect();
    walletPubkey = r.publicKey.toString(); walletType = 'Phantom';
    document.getElementById('walletAddr').textContent = walletType + ': ' + walletPubkey.slice(0,4) + '...' + walletPubkey.slice(-4);
    alert('Phantom 已連接: ' + walletPubkey);
  } catch(e) { alert('連接失敗: ' + e.message); }
}
async function connectSolflare() {
  try {
    if (!window.solflare) { alert('請先安裝 Solflare: https://solflare.com/'); return; }
    const r = await window.solflare.connect();
    walletPubkey = r.toString(); walletType = 'Solflare';
    document.getElementById('walletAddr').textContent = walletType + ': ' + walletPubkey.slice(0,4) + '...' + walletPubkey.slice(-4);
    alert('Solflare 已連接: ' + walletPubkey);
  } catch(e) { alert('連接失敗: ' + e.message); }
}
async function connectMetaMask() {
  try {
    if (!window.ethereum) { alert('請先安裝 MetaMask: https://metamask.io/'); return; }
    const a = await window.ethereum.request({ method: 'eth_requestAccounts' });
    walletPubkey = a[0]; walletType = 'MetaMask';
    document.getElementById('walletAddr').textContent = walletType + ': ' + walletPubkey.slice(0,6) + '...' + walletPubkey.slice(-4);
    alert('MetaMask 已連接: ' + walletPubkey);
  } catch(e) { alert('連接失敗: ' + e.message); }
}'''
c = c.replace(old_audio, new_audio, 1)

with open(f, "w", encoding="utf-8") as fh:
    fh.write(c)
print("done")
