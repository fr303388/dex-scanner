let seenSymbols = new Set();
load(); setInterval(load, 5000);
async function toggleTrading() {
  try {
    const r = await fetch('/api/toggle_trading', {method:'POST'});
    const d = await r.json();
    updateTradeBtn(d.enabled);
    alert(d.enabled ? '正式交易已開始' : '正式交易已停止');
  } catch(e) { alert('錯誤: ' + e.message); }
}
function updateTradeBtn(enabled) {
  const btn = document.getElementById('tradeToggleBtn');
  const st = document.getElementById('tradeStatus');
  if (enabled) {
    btn.textContent = '⏸ 停止交易';
    btn.style.background = '#da3633';
    st.textContent = '🟢 交易中';
    st.style.color = '#3fb950';
  } else {
    btn.textContent = '▶ 開始交易';
    btn.style.background = '#238636';
    st.textContent = '⚪ 未啟動';
    st.style.color = '#8b949e';
  }
}
async function saveTradeAmount() {
  const amt = parseFloat(document.getElementById('tradeAmountInput').value) || 100;
  try {
    await fetch('/api/save_trade_amount', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({amount: amt})
    });
    alert('每筆投入金額已設為 $' + amt);
  } catch(e) { alert('錯誤: ' + e.message); }
}
async function fetchBalance(pubkey) {
  if (!pubkey) return;
  try {
    const r = await fetch('/api/balance/' + pubkey);
    const d = await r.json();
    if (d.ok) {
      document.getElementById('walletBalDisplay').textContent = d.sol.toFixed(4) + ' SOL';
    } else {
      document.getElementById('walletBalDisplay').textContent = '讀取失敗';
    }
  } catch(e) {
    document.getElementById('walletBalDisplay').textContent = '讀取失敗';
  }
}
async function savePrivKey() {
  const pk = document.getElementById('privKeyInput').value.trim();
  const pub = document.getElementById('pubKeyInput').value.trim();
  if (!pk) { alert('請輸入私鑰'); return; }
  try {
    await fetch('/api/save_privkey', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({privkey: pk, pubkey: pub})
    });
    document.getElementById('pkStatus').textContent = '✅ 已儲存';
    document.getElementById('privKeyInput').value = '';
    if (pub) {
      document.getElementById('walletAddrDisplay').textContent = pub.slice(0,6) + '...' + pub.slice(-4);
      fetchBalance(pub);
    }
  } catch(e) { alert('儲存失敗: ' + e.message); }
}
async function loadSavedKey() {
  try {
    const r = await fetch('/api/get_privkey');
    const d = await r.json();
    if (d.has_privkey) {
      document.getElementById('pkStatus').textContent = '✅ 已設定';
      if (d.pubkey) {
        document.getElementById('pubKeyInput').value = d.pubkey;
        document.getElementById('walletAddrDisplay').textContent = d.pubkey.slice(0,6) + '...' + d.pubkey.slice(-4);
        fetchBalance(d.pubkey);
      }
    }
  } catch(e) {}
  // 載入每筆金額
  try {
    const r = await fetch('/api/dex');
    const d = await r.json();
    if (d.portfolio && d.portfolio.trade_amount_sol) {
      document.getElementById('tradeAmountInput').value = d.portfolio.trade_amount_sol;
    }
  } catch(e) {}
}

function fmtPrice(p) {
  p = Number(p) || 0;
  if (p >= 1000) return '$' + p.toFixed(0);
  if (p >= 100) return '$' + p.toFixed(2);
  if (p >= 1) return '$' + p.toFixed(4);
  if (p >= 0.0001) return '$' + p.toFixed(6);
  if (p > 0) return '$' + p.toPrecision(4);
  return '$0';
}


function holdStr(ts) {
  if (!ts) return '--';
  const s = Math.floor(Date.now()/1000 - ts);
  if (s < 60) return s + '秒';
  const m = Math.floor(s/60);
  if (m < 60) return m + '分' + (s%60) + '秒';
  return Math.floor(m/60) + '時' + (m%60) + '分';
}

function renderPositions(positions, containerId) {
  document.getElementById(containerId).innerHTML = positions.map(p=>{
    const pnlCls = (p.pnl||0)>=0?'up':'down';
    const img = p.image ? `<img src="${p.image}" style="width:40px;height:40px;border-radius:50%;flex-shrink:0" onerror="this.style.display='none'">` : '<div style="width:40px;height:40px;border-radius:50%;background:#21262d;flex-shrink:0"></div>';
    return `<div class="pf-pos" style="display:flex;align-items:center;gap:10px">
      ${img}
      <div style="flex:1">
        <div class="sym"><a href="${p.url}" target="_blank">${p.symbol}</a></div>
        <div class="detail" style="font-size:10px;color:#8b949e">買 ${fmtPrice(p.buy_price||0)} | 現 ${fmtPrice(p.current_price||0)}</div>
        <div class="pnl ${pnlCls}" style="font-size:12px">${(p.pnl||0)>=0?'+':''}$${(p.pnl||0).toFixed(2)} (${(p.pnl_pct||0)>=0?'+':''}${(p.pnl_pct||0)}%) <span style="color:#666;font-size:10px">持 ${holdStr(p.buy_ts)}</span></div>
      </div>
    </div>`;
  }).join('') || '<div style="color:#666;font-size:12px;grid-column:1/-1">尚無持倉</div>';
}

function renderTrades(trades, containerId) {
  document.getElementById(containerId).innerHTML = trades.slice(-20).reverse().map(t=>{
    const cls = t.action==="BUY"?"up":"down";
    const pnlStr = t.action==="SELL" ? `<span class="${t.pnl>=0?"up":"down"}">${t.pnl>=0?"+":""}$${t.pnl} (${t.pnl_pct>=0?"+":""}${t.pnl_pct}%)</span>` : `<span style="color:#8b949e">持有中</span>`;
    const feeStr = t.fee_sol ? `<span style="color:#8b949e;font-size:10px">手續費 ${t.fee_sol} SOL</span>` : "";
    const txStr = t.tx ? `<a href="https://solscan.io/tx/${t.tx}" target="_blank" style="color:#f0b429;font-size:10px">鏈上</a>` : "";
    return `<div style="padding:3px 0;border-bottom:1px solid #21262d;display:flex;gap:8px;align-items:center;flex-wrap:wrap">
      <span style="color:#666">${t.time}</span>
      <span class="${cls}" style="font-weight:bold">${t.action}</span>
      ${(t.url || t.address) ? `<a href="${t.url || `https://dexscreener.com/solana/${t.address}`}" target="_blank" style="color:#58a6ff">${t.symbol}</a>` : `<span>${t.symbol}</span>`}
      <span style="color:#8b949e">@ ${fmtPrice(t.action==="BUY"?t.buy_price:t.sell_price||0)}</span>
      ${pnlStr}
      ${feeStr}
      ${txStr}
      <span style="color:#666;margin-left:auto">${t.reason||""}</span>
    </div>`;
  }).join("") || "<div style='color:#666'>尚無交易紀錄</div>";
}

async function load() {
  try {
    const r = await fetch('/api/dex');
    const d = await r.json();
    document.getElementById('refresh').textContent = '更新於 ' + d.scanned_at;
    const pf = d.portfolio || {};
    pf.positions = pf.positions || [];
    pf.trades = pf.trades || [];
    updateTradeBtn(pf.trading_enabled === true);
    const errEl = document.getElementById('tradeError');
    if (errEl) errEl.textContent = pf.last_error || '';

    // 正式交易 - 跟模擬一樣版面
    const pInvested = pf.total_invested||0;
    const pValue = pf.total_value||0;
    const pPnl = pValue - pInvested;
    const pPnlPct = pInvested > 0 ? (pPnl/pInvested*100) : 0;
    const pEquity = pValue + (pf.cash||0);
    const pEquityPnl = pEquity - (pf.capital||1000);
    document.getElementById('pfInvested').textContent = '$' + pInvested.toFixed(0);
    document.getElementById('pfValue').textContent = '$' + pValue.toFixed(2);
    const pnlEl = document.getElementById('pfPnl');
    pnlEl.textContent = '$' + (pPnl>=0?'+':'') + pPnl.toFixed(2) + ' (' + (pPnlPct>=0?'+':'') + pPnlPct.toFixed(1) + '%)';
    pnlEl.className = 'num ' + (pPnl>=0?'up':'down');
    const pEqEl = document.getElementById('pfEquity');
    if (pEqEl) {
      const sol = pf.wallet_sol || 0;
      pEqEl.textContent = sol.toFixed(4) + ' SOL';
      pEqEl.className = 'num up';
    const sugEl = document.getElementById('suggestedAmount');
    if (sugEl) { const sug = (pf.wallet_sol||0)*0.8/10; sugEl.textContent = sug.toFixed(4) + ' SOL'; }
    }
    const st = pf.stats || {};
    document.getElementById('stWins').textContent = st.wins||0;
    document.getElementById('stLosses').textContent = st.losses||0;
    document.getElementById('stRugs').textContent = st.rugs||0;
    document.getElementById('stCoins').textContent = st.unique_bought||0;
    const wr = (st.wins||0)+(st.losses||0)>0 ? Math.round((st.wins||0)/((st.wins||0)+(st.losses||0))*100) : 0;
    document.getElementById('stWinRate').textContent = wr+'%';
    document.getElementById('stWinAmt').textContent = '$'+((st.win_amount||0).toFixed(2));
    document.getElementById('stLossAmt').textContent = '$'+((st.loss_amount||0).toFixed(2));

    renderPositions(pf.positions, 'pfPositions');
    renderTrades(pf.trades, 'pfTrades');

    // === 模擬交易 ===
    const spf = d.sim_portfolio || {};
    spf.positions = spf.positions || [];
    spf.trades = spf.trades || [];
    const sInvested = spf.total_invested||0;
    const sValue = spf.total_value||0;
    const sPnl = sValue - sInvested;
    const sPnlPct = sInvested > 0 ? (sPnl/sInvested*100) : 0;
    const sEquity = sValue + (spf.cash||0);
    const sEquityPnl = sEquity - (spf.capital||1000);
    document.getElementById('simInvested').textContent = '$' + sInvested.toFixed(0);
    document.getElementById('simValue').textContent = '$' + sValue.toFixed(2);
    const spnlEl = document.getElementById('simPnl');
    spnlEl.textContent = '$' + (sPnl>=0?'+':'') + sPnl.toFixed(2) + ' (' + (sPnlPct>=0?'+':'') + sPnlPct.toFixed(1) + '%)';
    spnlEl.className = 'num ' + (sPnl>=0?'up':'down');
    const seqEl = document.getElementById('simEquity');
    seqEl.textContent = '$' + sEquity.toFixed(2) + ' (' + (sEquityPnl>=0?'+':'') + sEquityPnl.toFixed(0) + ')';
    seqEl.className = 'num ' + (sEquityPnl>=0?'up':'down');
    const sst = spf.stats || {};
    document.getElementById('sWins').textContent = sst.wins||0;
    document.getElementById('sLosses').textContent = sst.losses||0;
    document.getElementById('sRugs').textContent = sst.rugs||0;
    document.getElementById('sCoins').textContent = sst.unique_bought||0;
    const swr = (sst.wins||0)+(sst.losses||0)>0 ? Math.round((sst.wins||0)/((sst.wins||0)+(sst.losses||0))*100) : 0;
    document.getElementById('sWinRate').textContent = swr+'%';
    document.getElementById('sWinAmt').textContent = '$'+((sst.win_amount||0).toFixed(2));
    document.getElementById('sLossAmt').textContent = '$'+((sst.loss_amount||0).toFixed(2));

    renderPositions(spf.positions, 'simPositions');
    renderTrades(spf.trades, 'simTrades');

    // 推薦
    document.getElementById('recommend').innerHTML = d.tokens.filter(t=>t.score>=4).slice(0,5).map((t,i)=>{
      const img = t.image ? `<img src="${t.image}" style="width:24px;height:24px;border-radius:50%;flex-shrink:0" onerror="this.style.display='none'">` : '';
      return `<div class="rec-item" style="display:flex;align-items:center;gap:6px">
        <span class="rec-rank" style="color:#f0b429">#${i+1}</span>
        ${img}
        <span class="rec-name"><a href="${t.url}" target="_blank">${t.symbol}</a></span>
        <span class="rec-score">${t.score}分</span>
        <div style="display:flex;flex-wrap:wrap;gap:2px;flex:1">${renderTags(t.reasons)}</div>
        <span class="${t.change_24h>=0?'up':'down'}">${t.change_24h>=0?'+':''}${t.change_24h}%</span>
      </div>`;
    }).join('') || '<div style="color:#8b949e;font-size:12px">目前沒有強推薦</div>';

    // 潛力新股
    document.getElementById('potential').innerHTML = (d.potential||[]).map(t=>{
      const pimg = t.image ? `<img src="${t.image}" style="width:24px;height:24px;border-radius:50%;flex-shrink:0" onerror="this.style.display='none'">` : '';
      return `<div class="rec-item" style="display:flex;align-items:center;gap:6px">
        <span class="rec-rank" style="color:#f0b429">🌱</span>
        ${pimg}
        <span class="rec-name"><a href="${t.url}" target="_blank">${t.symbol}</a></span>
        <span class="rec-score" style="background:#f0b42922">買盤${t.buy_ratio}%</span>
        <div style="display:flex;flex-wrap:wrap;gap:2px;flex:1;align-items:center"><span style="color:#8b949e;font-size:11px">${fmtPrice(t.price)} | 1h:${t.change_1h}% | 24h:${t.change_24h}% | 流動:$${(t.liquidity/1000).toFixed(1)}K</span>${renderTags(t.reasons)}</div>
      </div>`;
    }).join('') || '<div style="color:#8b949e;font-size:12px">目前沒有符合條件的潛力股</div>';

    // 新幣提醒音效
    const currentSymbols = new Set();
    d.tokens.filter(t=>t.score>=4).forEach(t=>currentSymbols.add(t.symbol));
    (d.potential||[]).forEach(t=>currentSymbols.add(t.symbol));
    let isFirst = seenSymbols.size === 0;
    let newOnes = [];
    currentSymbols.forEach(s => { if (!seenSymbols.has(s)) newOnes.push(s); });
    if (!isFirst && newOnes.length > 0) {
      document.getElementById('alertSound').play().catch(()=>{});
    }
    currentSymbols.forEach(s => seenSymbols.add(s));

    // 社群熱門
    document.getElementById('trending').innerHTML = (d.trending||[]).map(t=>{
      return `<div style="background:#161b22;border-radius:6px;padding:6px 12px;display:flex;align-items:center;gap:6px;font-size:12px">
        <b style="color:#a371f7">#${t.rank}</b>
        <img src="${t.thumb}" style="width:18px;height:18px;border-radius:50%" onerror="this.style.display='none'">
        <span>${t.name}</span>
        <span style="color:#8b949e">${t.symbol}</span>
      </div>`;
    }).join('') || '<span style="color:#8b949e;font-size:12px">載入中...</span>';
    // 下架幣種
    document.getElementById("delisted").innerHTML = (d.delisted||[]).map(t=>{
      const crash = t.crash_pct || 0;
      const crashColor = crash < -50 ? '#f85149' : crash < -20 ? '#d29922' : '#8b949e';
      let tag = '';
      if (t.type === 'honeypot') tag = '<span style="background:#f85149;color:#fff;padding:1px 5px;border-radius:3px;font-size:10px">🍬蜜糖罐頭</span>';
      else if (crash <= -90) tag = '<span style="background:#6f0808;color:#fff;padding:1px 5px;border-radius:3px;font-size:10px">🕸️螺旋死亡</span>';
      else if (crash <= -70) tag = '<span style="background:#b62324;color:#fff;padding:1px 5px;border-radius:3px;font-size:10px">💀崩盤Rug</span>';
      else if (crash <= -50) tag = '<span style="background:#d29922;color:#000;padding:1px 5px;border-radius:3px;font-size:10px">📉暴跌</span>';
      else if (crash <= -30) tag = '<span style="background:#8b949e;color:#fff;padding:1px 5px;border-radius:3px;font-size:10px">💧淡出</span>';
      const link = t.url || (t.address ? `https://dexscreener.com/solana/${t.address}` : '#');
      const timeShort = (t.delist_time||"").slice(-5);
      return `<div style="background:#da363311;border:1px solid #da363344;border-radius:6px;padding:4px 10px;display:flex;align-items:center;gap:6px;font-size:11px;flex-wrap:wrap">
        <img src="${t.image}" style="width:16px;height:16px;border-radius:50%" onerror="this.style.display='none'">
        <a href="${link}" target="_blank" style="color:#f85149;font-weight:bold;text-decoration:none">💀 ${t.symbol}</a>
        ${tag}
        <span style="color:${crashColor};font-weight:bold">${crash}%</span>
        <span style="color:#666;margin-left:auto">${timeShort}</span>
      </div>`;
    }).join('') || '<span style="color:#8b949e;font-size:12px">目前無下架幣種</span>';

    // 表格
    document.getElementById('tbody').innerHTML = d.tokens.map((t,i)=>{
      const c24 = t.change_24h>=0?'up':'down';
      const scColor = t.score>=4?'#3fb950':t.score>=2?'#58a6ff':t.score>=0?'#8b949e':'#f85149';
      const timg = t.image ? `<img src="${t.image}" style="width:20px;height:20px;border-radius:50%;vertical-align:middle" onerror="this.style.display='none'">` : '';
      return `<tr>
        <td><b style="color:${scColor}">${t.score}</b></td>
        <td>${timg} <a href="${t.url}" target="_blank">${t.symbol}</a></td>
        <td style="color:#8b949e">${t.name}</td>
        <td>${fmtPrice(t.price)}</td>
        <td class="${t.change_1h>=0?'up':'down'}">${t.change_1h>=0?'+':''}${t.change_1h}%</td>
        <td class="${c24}">${t.change_24h>=0?'+':''}${t.change_24h}%</td>
        <td>$${(t.volume_24h/1000).toFixed(0)}K</td>
        <td style="font-size:11px">${renderTags(t.reasons.slice(0,6))}</td>
      </tr>`;
    }).join('');
  } catch(e){ console.error(e); }
}
// 分析理由轉 TAG 標籤
const POS_TAGS = ["1h強勢","1h上漲","健康上漲","強勢噴發","大量","流動性極足","流動性足","買盤極強"];
const NEG_TAGS = ["1h暴跌","1h崩盤","高位追風險","死亡螺旋","已崩盤","流動性低易RUG","高風險RUG","賣壓大","疑似洗盤量假","拉盤陷阱","交易筆數極少","交易冷清","大戶對敲洗盤","買賣對敲"];
function renderTags(reasons) {
  const tagColors = {
    "1h強勢":"#238636","強勢噴發":"#238636","健康上漲":"#2ea043","1h上漲":"#3fb950",
    "大量":"#1f6feb",
    "流動性極足":"#0598bc","流動性足":"#39c5cf",
    "買盤極強":"#8957e5",
    "1h暴跌":"#da3633","1h崩盤":"#b62324","死亡螺旋":"#8b080f","已崩盤":"#6f0808",
    "高位追風險":"#d29922","流動性低易RUG":"#db6d28","高風險RUG":"#f85149","賣壓大":"#e3b341",
    "疑似洗盤量假":"#da3633","拉盤陷阱":"#a371f7","大戶對敲洗盤":"#6e7681","買賣對敲":"#6e7681",
    "交易筆數極少":"#484f58","交易冷清":"#484f58"
  };
  const icons = {"1h強勢":"🚀","1h上漲":"📈","健康上漲":"📈","強勢噴發":"🚀","大量":"💎","流動性極足":"💧","流動性足":"💧","買盤極強":"🛒","1h暴跌":"📉","1h崩盤":"💀","高位追風險":"⚠️","死亡螺旋":"🕸️","已崩盤":"💀","流動性低易RUG":"🩸","高風險RUG":"🩸","賣壓大":"🔻","疑似洗盤量假":"🧻","拉盤陷阱":"🪤","交易筆數極少":"👻","交易冷清":"🥶","大戶對敲洗盤":"🎭","買賣對敲":"🎭"};
  return (reasons||[]).map(r => {
    const bg = tagColors[r] || "#30363d";
    return `<span style="display:inline-block;padding:1px 6px;border-radius:8px;font-size:10px;margin:1px;background:${bg};color:#fff">${icons[r]||""} ${r}</span>`;
  }).join("");
}
loadSavedKey();
load(); setInterval(load, 5000);

async function clearDelisted() { if(confirm('清除所有下架幣種記錄？')) { await fetch('/api/clear_delisted',{method:'POST'}); load(); } }
