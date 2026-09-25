f = r"C:\Users\ANGEL\Doubao\chats\2026-09-12\new-chat\dex_scanner\dashboard.html"
with open(f, "r", encoding="utf-8") as fh:
    c = fh.read()

# Remove wallet JS block (from // ===== 錢包連接 to </script>)
import re
# Remove the wallet JS between the audio unlock and the second script tag
c = c.replace('''
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
}''', '')

with open(f, "w", encoding="utf-8") as fh:
    fh.write(c)
print("done")
