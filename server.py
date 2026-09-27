"""迷因幣雷達 - 含模擬交易 + 真實鏈上交易 (Solana Jupiter)"""
import requests, time, json, base64, os, subprocess
from datetime import datetime, timezone, timedelta
from flask import Flask, jsonify, send_file, Response, request

app = Flask(__name__)
try:
    with open("notify_pref.json") as _f: MEME_NOTIFY_ENABLED = json.load(_f).get("tg", True)
except: MEME_NOTIFY_ENABLED = True
UTC8 = timezone(timedelta(hours=8))
CACHE = {"data": None, "ts": 0}
GMGN_CACHE = {"data": {}, "ts": 0}
GMGN_KEY = "gmgn_solbscbaseethmonadtron"
GMGN_ENABLED = True

def fetch_gmgn_trending():
    """呼叫 gmgn-cli 取得 trending 資料，回傳 {address: data} dict"""
    if not GMGN_ENABLED: return GMGN_CACHE["data"]
    if time.time() - GMGN_CACHE["ts"] < 120:
        return GMGN_CACHE["data"]
    try:
        env = dict(os.environ, GMGN_API_KEY=GMGN_KEY)
        out = subprocess.run(["/root/.local/share/mise/installs/node/24.21.0/bin/node", "/root/.local/share/mise/installs/node/24.21.0/lib/node_modules/gmgn-cli/dist/index.js", "market", "trending", "--chain", "sol",
                              "--interval", "1h", "--limit", "50", "--raw"],
                             capture_output=True, text=True, timeout=20, env=env)
        data = json.loads(out.stdout)
        ranks = data.get("data", {}).get("rank", [])
        gm = {}
        for r in ranks:
            addr = r.get("address", "")
            if addr:
                gm[addr] = {
                    "holders": r.get("holder_count", 0),
                    "top10_rate": r.get("top_10_holder_rate", 0),
                    "smart_degen": r.get("smart_degen_count", 0),
                    "sniper": r.get("sniper_count", 0),
                    "bundler": r.get("bundler_rate", 0),
                    "entrapment": r.get("entrapment_ratio", 0),
                    "rug_ratio": r.get("rug_ratio", 0),
                    "wash": r.get("is_wash_trading", False),
                }
        GMGN_CACHE["data"] = gm
        GMGN_CACHE["ts"] = time.time()
        print(f"[GMGN] 載入 {len(gm)} 個 trending 幣")
    except Exception as e:
        print(f"[GMGN] 失敗: {e}")
    return GMGN_CACHE["data"]
PORTFOLIO_FILE = 'portfolio.json'
SIM_PORTFOLIO_FILE = 'sim_portfolio.json'
REC_FILE = r'C:\Users\ANGEL\Doubao\chats\2026-09-12\new-chat\dex_scanner\rec_tracker.json'
PRIVKEY_FILE = r'C:\Users\ANGEL\Doubao\chats\2026-09-12\new-chat\dex_scanner\privkey.json'
WsolMint = "So11111111111111111111111111111111111111112"

# ============ Solana 鏈上交易 ============
def load_keypair():
    try:
        with open(PRIVKEY_FILE, "r") as f:
            d = json.load(f)
        pk = d.get("privkey", "")
        if not pk: return None
        from solders.keypair import Keypair
        from base58 import b58decode
        return Keypair.from_bytes(b58decode(pk))
    except Exception as e:
        print(f"[KEYPAIR] error: {e}", flush=True)
        return None

def jupiter_swap(keypair, input_mint, output_mint, amount_lamports, slippage_bps=100):
    try:
        quote_r = requests.get("https://quote-api.jup.ag/v6/quote", params={
            "inputMint": input_mint, "outputMint": output_mint,
            "amount": str(int(amount_lamports)), "slippageBps": str(slippage_bps),
        }, timeout=15)
        quote = quote_r.json()
        if "error" in quote: return False, f"quote: {quote['error']}"
        swap_r = requests.post("https://quote-api.jup.ag/v6/swap", json={
            "quoteResponse": quote, "userPublicKey": str(keypair.pubkey()),
            "wrapAndUnwrapSol": True,
        }, timeout=15)
        swap_data = swap_r.json()
        if "swapTransaction" not in swap_data: return False, f"swap: {swap_data.get('error','?')}"
        from solders.transaction import VersionedTransaction
        tx = VersionedTransaction.from_bytes(base64.b64decode(swap_data["swapTransaction"]))
        tx.sign([keypair])
        from solana.rpc.api import Client
        rpc = Client("https://api.mainnet-beta.solana.com")
        sig = rpc.send_raw_transaction(bytes(tx), opts={"skipPreflight": True}).value
        rpc.confirm_transaction(sig, commitment="confirmed")
        return True, str(sig)
    except Exception as e:
        return False, str(e)


def check_honeypot(token_mint, buy_sol=0.1):
    """買入前測試：模擬賣出報價，如果回傳過低就是 honeypot"""
    try:
        # 先測買入報價 SOL->token
        buy_q = requests.get("https://quote-api.jup.ag/v6/quote", params={
            "inputMint": WsolMint, "outputMint": token_mint,
            "amount": str(int(buy_sol * 1e9)), "slippageBps": "500",
        }, timeout=10).json()
        if "error" in buy_q or not buy_q.get("outAmount"):
            return False, "買入報價失敗"
        bought_tokens = int(buy_q["outAmount"])
        if bought_tokens < 1000:
            return False, "買入數量異常"
        # 再測賣出報價 token->SOL
        sell_q = requests.get("https://quote-api.jup.ag/v6/quote", params={
            "inputMint": token_mint, "outputMint": WsolMint,
            "amount": str(bought_tokens), "slippageBps": "500",
        }, timeout=10).json()
        if "error" in sell_q:
            return False, f"賣出報價失敗(可能honeypot): {sell_q.get('error','?')}"
        out_sol = int(sell_q.get("outAmount", 0))
        in_sol = int(buy_sol * 1e9)
        # 如果賣出回傳不到買入的10%，判定為 honeypot
        if out_sol < in_sol * 0.1:
            return False, f"HONEYPOT: 買{buy_sol}SOL→賣出僅{out_sol/1e9:.4f}SOL"
        return True, f"安全(賣出回報{out_sol/in_sol*100:.0f}%)"
    except Exception as e:
        return False, f"檢查異常: {e}"

def get_real_buy_price(token_mint, ref_price=0, buy_sol=0.1):
    try:
        q = requests.get("https://quote-api.jup.ag/v6/quote", params={
            "inputMint": WsolMint, "outputMint": token_mint,
            "amount": str(int(buy_sol * 1e9)), "slippageBps": "500",
        }, timeout=10).json()
        if "outAmount" not in q or int(q["outAmount"]) < 1000:
            return ref_price
        tokens = int(q["outAmount"]) / (10 ** q.get("outputDecimals", 9))
        sol_price_usd = 150.0
        token_usd = (buy_sol * sol_price_usd) / tokens if tokens > 0 else ref_price
        print(f"[JUP PRICE] real=${token_usd:.8f} vs dex=${ref_price:.8f}", flush=True)
        return token_usd
    except Exception as e:
        print(f"[JUP PRICE FAIL] {e}", flush=True)
        return ref_price

def get_sol_balance(pubkey):
    try:
        r = requests.post("https://api.mainnet-beta.solana.com",
            json={"jsonrpc":"2.0","id":1,"method":"getBalance","params":[pubkey]}, timeout=10)
        return r.json()["result"]["value"] / 1e9
    except: return 0.0

# ============ 投資組合存取 ============
def load_portfolio():
    try:
        with open(PORTFOLIO_FILE, "r") as f: return json.load(f)
    except: return {"positions": [], "trades": [], "capital": 1000, "cash": 1000}

def save_portfolio(p):
    with open(PORTFOLIO_FILE, "w") as f: json.dump(p, f, ensure_ascii=False, indent=2)

def load_sim_portfolio():
    try:
        with open(SIM_PORTFOLIO_FILE, "r") as f: return json.load(f)
    except: return {"positions": [], "trades": [], "capital": 1000, "cash": 1000}

def save_sim_portfolio(p):
    with open(SIM_PORTFOLIO_FILE, "w") as f: json.dump(p, f, ensure_ascii=False, indent=2)

IMG_CACHE = {}
def fetch_image(url):
    if url in IMG_CACHE: return IMG_CACHE[url]
    try:
        pair_addr = url.rstrip("/").split("/")[-1]
        r = requests.get(f"https://api.dexscreener.com/latest/dex/pairs/solana/{pair_addr}", timeout=8)
        pairs = r.json().get("pairs",[])
        if pairs:
            img = (pairs[0].get("info",{}) or {}).get("imageUrl","")
            IMG_CACHE[url] = img; return img
    except Exception as e: print(f"[IMG] error: {e}", flush=True)
    IMG_CACHE[url] = ""; return ""

def score_token(t):
    score = 0; reasons = []
    h1, h24 = t.get("change_1h",0), t.get("change_24h",0)
    vol, liq, br = t.get("volume_24h",0), t.get("liquidity",0), t.get("buy_ratio",50)
    if h1 > 50: score -= 2; reasons.append("追高風險")
    elif h1 > 30: score += 1; reasons.append("1h強勢")
    elif h1 > 10: score += 1; reasons.append("1h上漲")
    elif h1 < -10: score -= 2; reasons.append("1h暴跌")
    elif h1 < -30: score -= 3; reasons.append("1h崩盤")
    if 10 < h24 <= 50: score += 2; reasons.append("健康上漲")
    elif 50 < h24 <= 150: score += 1; reasons.append("強勢噴發")
    elif h24 > 200: score -= 1; reasons.append("高位追風險")
    elif h24 < -30: score -= 3; reasons.append("死亡螺旋")
    elif h24 < -50: score -= 5; reasons.append("已崩盤")
    if vol > 200000: score += 1.5; reasons.append("大量")
    elif vol > 50000: score += 0.5
    if liq > 50000: score += 1.5; reasons.append("流動性極足")
    elif liq > 30000: score += 1; reasons.append("流動性足")
    elif liq < 10000: score -= 2; reasons.append("流動性低易RUG")
    elif liq < 5000: score -= 3; reasons.append("高風險RUG")
    if br > 70: score += 1.5; reasons.append("買盤極強")
    elif br < 40: score -= 1.5; reasons.append("賣壓大")
    # 反洗盤：量/流動比 > 5 代表人氣造假
    # 反拉盤：1h 暴漲 >80% 且 24h 暴漲 >300% = 典型拉盤砸盤
    if h1 > 80 and h24 > 300: score -= 3; reasons.append("拉盤陷阱")
    # 反洗盤：交易筆數太少 = 只有幾個地址在刷
    txns = t.get("txns_24h", 999)
    avg_t = t.get("avg_trade", 0)
    if txns < 30: score -= 3; reasons.append("交易筆數極少")
    elif txns < 80: score -= 1; reasons.append("交易冷清")
    # 平均每筆金額過大 = 大戶自買自賣
    if avg_t > 5000 and txns < 100: score -= 2; reasons.append("大戶對敲洗盤")
    if avg_t < 50 and txns > 200: score -= 2; reasons.append(f"散戶洗盤均${int(avg_t)}")
    buyers = t.get("buyers", 0)
    if buyers > 0:
        if buyers < 10: score -= 3; reasons.append(f"人少{buyers}人刷單")
        elif buyers < 30: score -= 1; reasons.append(f"買家少{buyers}人")
    # GMGN 數據
    if t.get("gm_wash"): score -= 5; reasons.append("GMGN洗盤")
    if t.get("gm_smart",0) >= 5: score += 2; reasons.append(f"聰明錢{t['gm_smart']}人")
    elif t.get("gm_smart",0) >= 2: score += 1; reasons.append(f"聰明錢{t['gm_smart']}人")
    if t.get("gm_holders",0) >= 200: score += 1; reasons.append(f"持幣{t['gm_holders']}人")
    if t.get("gm_top10",0) > 0.3: score -= 2; reasons.append(f"前10大持幣{int(t['gm_top10']*100)}%集中")
    # 買賣次數接近 50/50 且筆數少 = 典型對敲
    if txns > 0 and txns < 50:
        b_ratio = t.get("buy_ratio", 50)
        if 40 < b_ratio < 60: score -= 1; reasons.append("買賣對敲")
    rating = "🔥強推薦" if score>=4 else "✅可關注" if score>=2 else "⚪觀望" if score>=0 else "⚠️危險" if score>=-2 else "❌避開"
    return round(score,1), rating, reasons

first_seen_map = {}
try:
    with open("notify_pref.json") as _f: NOTIFY_ENABLED = json.load(_f).get("tg", True)
except: NOTIFY_ENABLED = MEME_NOTIFY_ENABLED  # symbol -> 首次掃描到的時間戳

def fetch_meme_coins():
    if CACHE["data"] and time.time() - CACHE["ts"] < 15:
        return CACHE["data"]
    all_tokens = []
    try:
        r = requests.get("https://api.dexscreener.com/token-profiles/latest/v1", timeout=10)
        for prof in r.json():
            chain, addr = prof.get("chainId",""), prof.get("tokenAddress","")
            if not addr or chain not in ("solana","base"): continue
            try:
                pr = requests.get(f"https://api.dexscreener.com/token-pairs/v1/{chain}/{addr}", timeout=8)
                for p in pr.json():
                    if p.get("baseToken",{}).get("address","").lower() != addr.lower(): continue
                    base = p.get("baseToken",{}).get("symbol","?")
                    name = p.get("baseToken",{}).get("name","")
                    try: price=float(p.get("priceUsd",0) or 0)
                    except: price=0
                    try: h24=float(p.get("priceChange",{}).get("h24",0) or 0)
                    except: h24=0
                    try: h1=float(p.get("priceChange",{}).get("h1",0) or 0)
                    except: h1=0
                    try: vol=float(p.get("volume",{}).get("h24",0) or 0)
                    except: vol=0
                    try: liq=float(p.get("liquidity",{}).get("usd",0) or 0)
                    except: liq=0
                    try: buys=p.get("txns",{}).get("h24",{}).get("buys",0)
                    except: buys=0
                    try: sells=p.get("txns",{}).get("h24",{}).get("sells",0)
                    except: sells=0
                    try: buyers=p.get("buyers",0)
                    except: buyers=0
                    if liq < 10000: continue
                    br = round(buys/(buys+sells)*100) if (buys+sells)>0 else 50
                    txns_24h = buys + sells
                    avg_trade = vol / txns_24h if txns_24h > 0 else 0
                    t = {"symbol":f"{base}/SOL","name":name,"price":price,"change_1h":round(h1,1),"change_24h":round(h24,1),"volume_24h":round(vol),"liquidity":round(liq),"chain":chain,"url":p.get("url",""),"buy_ratio":br,"address":addr,"image":(p.get("info",{}) or {}).get("imageUrl",""),"txns_24h":txns_24h,"avg_trade":round(avg_trade),"buyers":buyers,"pair_created":p.get("pairCreatedAt",0)}
                    gm = fetch_gmgn_trending()
                    g = gm.get(addr)
                    if g:
                        t["gm_holders"]=g["holders"]; t["gm_smart"]=g["smart_degen"]
                        t["gm_top10"]=g["top10_rate"]; t["gm_wash"]=g["wash"]
                    sc, rating, reasons = score_token(t)
                    t["score"], t["rating"], t["reasons"] = sc, rating, reasons
                    if t["symbol"] not in first_seen_map: first_seen_map[t["symbol"]] = time.time()
                    all_tokens.append(t); break
            except: pass
    except: pass
    # GMGN trending 直接加入候選
    if GMGN_ENABLED:
        try:
            env = dict(os.environ, GMGN_API_KEY=GMGN_KEY)
            out = subprocess.run(["/root/.local/share/mise/installs/node/24.21.0/bin/node", "/root/.local/share/mise/installs/node/24.21.0/lib/node_modules/gmgn-cli/dist/index.js", "market", "trending", "--chain", "sol",
                                  "--interval", "1h", "--limit", "30", "--raw"],
                                 capture_output=True, text=True, timeout=15, env=env)
            gm_data = json.loads(out.stdout).get("data", {}).get("rank", [])
            existing = {t["address"] for t in all_tokens}
            for g in gm_data:
                addr = g.get("address","")
                if not addr or addr in existing: continue
                liq = g.get("liquidity", 0) or 0
                if liq < 10000: continue
                sym = g.get("symbol","?")
                h1 = g.get("price_change_percent1h", 0) or 0
                h24 = g.get("price_change_percent", 0) or 0
                vol = g.get("volume", 0) or 0
                buys = g.get("buys", 0) or 0
                sells = g.get("sells", 0) or 0
                br = round(buys/(buys+sells)*100) if (buys+sells)>0 else 50
                txns = buys + sells
                avg = vol/txns if txns>0 else 0
                t = {"symbol":f"{sym}/SOL","name":g.get("name",""),"price":g.get("price",0),
                     "change_1h":round(h1,1),"change_24h":round(h24,1),
                     "volume_24h":round(vol),"liquidity":round(liq),"chain":"solana",
                     "url":f"https://gmgn.ai/sol/token/{addr}","buy_ratio":br,
                     "address":addr,"image":g.get("logo",""),
                     "txns_24h":txns,"avg_trade":round(avg),"buyers":0,
                     "gm_holders":g.get("holder_count",0),"gm_smart":g.get("smart_degen_count",0),
                     "gm_top10":g.get("top_10_holder_rate",0),"gm_wash":g.get("is_wash_trading",False)}
                sc, rating, reasons = score_token(t)
                t["score"], t["rating"], t["reasons"] = sc, rating, reasons
                all_tokens.append(t)
            print(f"[GMGN] 直接加入 {len(gm_data)} 個 trending 幣")
        except Exception as e:
            print(f"[GMGN] trending 加入失敗: {e}")
    all_tokens.sort(key=lambda x: x["score"], reverse=True)

    # === 正式交易（鏈上真實交易，每筆單位 SOL） ===
    pf = load_portfolio()
    pf.setdefault("trades", [])
    pf.setdefault("positions", [])
    pf.setdefault("cooldown", {})
    now_str = datetime.now(UTC8).strftime("%m-%d %H:%M")
    now_ts = time.time()
    PF_BUY_SOL = pf.get("trade_amount_sol", 0.1)  # 每筆投入 SOL
    PF_MAX = 10
    PF_TP = 30.0
    PF_SL = -30.0
    PF_COOLDOWN = 360
    PF_MAX_HOLD = 14400  # 最長持有4小時（gainzfeldt風格）
    pf.setdefault("blacklist", [])  # 虧錢賣出過的幣不再買
    pf["cooldown"] = {sym: ts for sym, ts in pf["cooldown"].items() if now_ts - ts < PF_COOLDOWN}

    # 讀取錢包餘額
    kp = load_keypair()
    pf["last_error"] = ""
    if not kp:
        pf["last_error"] = "未設定私鑰"
    wallet_balance_sol = get_sol_balance(str(kp.pubkey())) if kp else 0
    pf["wallet_sol"] = wallet_balance_sol

    for pos in pf["positions"]:
        current = next((t for t in all_tokens if t["symbol"] == pos["symbol"]), None)
        if current:
            pos["current_price"] = current["price"]
            if current.get("image"): pos["image"] = current["image"]
        else:
            pos["current_price"] = pos.get("current_price", pos["buy_price"])
            pos["_delisted"] = True
        if "buy_ts" not in pos: pos["buy_ts"] = now_ts - 3600
        pos["current_value"] = pos["shares"] * pos["current_price"]
        invested = pos.get("invested_usd", pos.get("invested", 0))
        pos["pnl"] = pos["current_value"] - invested
        pos["pnl_pct"] = round((pos["pnl"] / invested) * 100, 1) if invested > 0 else 0
        if pos["pnl_pct"] > pos.get("peak_pct", -999): pos["peak_pct"] = pos["pnl_pct"]

    # 停利停損 → 鏈上賣出 token->SOL
    pf_kept = []
    for pos in pf["positions"]:
        sell_reason = None
        if pos.get("_delisted"): sell_reason = "下架死幣"
        elif pos["pnl_pct"] >= PF_TP: sell_reason = f"停利+{pos['pnl_pct']}%"
        elif pos["pnl_pct"] <= PF_SL: sell_reason = f"停損{pos['pnl_pct']}%"
        else:
            held_secs = now_ts - pos.get("buy_ts", now_ts)
            if held_secs > PF_MAX_HOLD: sell_reason = f"久未動{int(held_secs/60)}分鐘"
        if sell_reason and kp:
            # 真實鏈上賣出
            token_mint = pos.get("address","")
            if token_mint:
                token_amount = int(pos["shares"] * 1e6)  # 假設 6 位小數
                ok, sig = jupiter_swap(kp, token_mint, WsolMint, token_amount)
                if ok:
                    print(f"[ONCHAIN SELL] {pos['symbol']} tx: {sig[:20]}...", flush=True)
                    fee_sol = round(PF_BUY_SOL * 0.003 + 0.000005, 6)
                    pf["trades"].append({
                        "time": now_str, "symbol": pos["symbol"], "action": "SELL",
                        "buy_price": pos["buy_price"], "sell_price": pos["current_price"],
                        "pnl": round(pos["pnl"],2), "pnl_pct": pos["pnl_pct"],
                        "held_min": int((now_ts - pos.get("buy_ts", now_ts))/60),
                        "buy_score": pos.get("buy_score",0),
                        "entry_liq": pos.get("entry_liq",0),
                        "tx": sig, "fee_sol": fee_sol,
                        "url": pos.get("url",""), "address": pos.get("address",""),
                        "reason": f"{sell_reason} 鏈上成交"
                    })
                else:
                    err = f"賣出 {pos['symbol']} 失敗: {sig}"
                    print(f"[ONCHAIN SELL FAIL] {err}", flush=True)
                    pf["last_error"] = err
                    pf_kept.append(pos)
                    continue
            pf["cooldown"][pos["symbol"]] = now_ts + 360 if pos["pnl"] < 0 else now_ts
            # 虧錢不永久黑名單，只冷卻5分鐘
        else:
            pf_kept.append(pos)

    # 自動買入（按下開始交易後才啟用）→ 鏈上 SOL->token
    if pf.get("trading_enabled", False) and kp:
        pf_held = [p["symbol"] for p in pf_kept]
        pf_fresh = [t for t in all_tokens if t["symbol"] not in pf_held and t["symbol"] not in pf["cooldown"] and t["symbol"] not in pf["blacklist"] and t["symbol"] not in PERM_BLACKLIST and t["score"] >= 4.5 and t["price"] > 0]
        for t in pf_fresh:
            if len(pf_kept) >= PF_MAX: break
            if wallet_balance_sol < PF_BUY_SOL:
                err = f"餘額不足: {wallet_balance_sol:.4f} SOL < {PF_BUY_SOL} SOL"
                print(f"[ONCHAIN BUY SKIP] {err}", flush=True)
                pf["last_error"] = err
                break
            # HONEYPOT 檢查：先測試能不能賣出
            safe, hmsg = check_honeypot(t["address"], PF_BUY_SOL)
            if not safe:
                print(f"[HONEYPOT SKIP] {t['symbol']} {hmsg}", flush=True)
                pf["blacklist"].append(t["symbol"])
                pf["last_error"] = f"跳過 {t['symbol']}: {hmsg}"
                break
            print(f"[HONEYPOT OK] {t['symbol']} {hmsg}", flush=True)
            # 買入前價格合理性檢查：Jupiter報價 vs DexScreener
            try:
                pre_q = requests.get("https://quote-api.jup.ag/v6/quote", params={
                    "inputMint": WsolMint, "outputMint": t["address"],
                    "amount": str(int(PF_BUY_SOL * 1e9)), "slippageBps": "500",
                }, timeout=10).json()
                if "outAmount" in pre_q and int(pre_q["outAmount"]) > 1000:
                    decimals = pre_q.get("outputDecimals", 9)
                    tok_count = int(pre_q["outAmount"]) / (10 ** decimals)
                    jup_price = (PF_BUY_SOL * 150) / tok_count if tok_count > 0 else 0
                    dex_price = t["price"]
                    if dex_price > 0 and (jup_price > dex_price * 3 or jup_price < dex_price / 3):
                        err = f"價格異常 Jupiter=${jup_price:.8f} vs Dex=${dex_price:.8f}"
                        print(f"[PRICE MISMATCH SKIP] {t['symbol']} {err}", flush=True)
                        pf["blacklist"].append(t["symbol"])
                        pf["last_error"] = f"跳過 {t['symbol']}: {err}"
                        break
                    print(f"[PRICE OK] {t['symbol']} jup=${jup_price:.8f} dex=${dex_price:.8f}", flush=True)
            except Exception as e:
                print(f"[PRICE CHECK FAIL] {t['symbol']} {e}", flush=True)
            # 真實鏈上買入
            sol_lamports = int(PF_BUY_SOL * 1e9)
            real_price = get_real_buy_price(t["address"], t["price"])
            ok, sig = jupiter_swap(kp, WsolMint, t["address"], sol_lamports)
            if ok:
                print(f"[ONCHAIN BUY] {t['symbol']} {PF_BUY_SOL} SOL tx: {sig[:20]}...", flush=True)
                invested_usd = PF_BUY_SOL * 150  # 估計 USD (SOL~$150)
                pf_kept.append({
                    "symbol": t["symbol"], "buy_price": real_price, "buy_time": now_str,
                    "buy_ts": now_ts,
                    "invested_sol": PF_BUY_SOL, "invested_usd": invested_usd,
                    "shares": invested_usd/real_price,
                    "url": t["url"], "buy_score": t["score"],
                    "address": t.get("address",""), "chain": t.get("chain",""),
                    "image": t.get("image","")
                })
                wallet_balance_sol -= PF_BUY_SOL
                fee_sol = round(PF_BUY_SOL * 0.003 + 0.000005, 6)
                pf["trades"].append({
                    "time": now_str, "symbol": t["symbol"], "action": "BUY",
                    "buy_price": t["price"], "sell_price": 0, "pnl": 0, "pnl_pct": 0,
                    "tx": sig, "fee_sol": fee_sol,
                    "url": t["url"], "address": t.get("address",""),
                    "reason": f"鏈上買入 {PF_BUY_SOL} SOL"
                })
            else:
                err = f"買入 {t['symbol']} 失敗: {sig}"
                print(f"[ONCHAIN BUY FAIL] {err}", flush=True)
                pf["last_error"] = err
                break
    pf["positions"] = pf_kept

    all_sells = [t for t in pf.get("trades",[]) if t["action"]=="SELL"]
    wins = [t for t in all_sells if t["pnl"]>0]
    losses = [t for t in all_sells if t["pnl"]<=0]
    rugs = [t for t in all_sells if t.get("pnl_pct",0)<=-51]
    buys = [t for t in pf.get("trades",[]) if t["action"]=="BUY"]
    pf["stats"] = {"wins": len(wins), "losses": len(losses), "rugs": len(rugs),
        "win_amount": round(sum(t["pnl"] for t in wins),2),
        "loss_amount": round(sum(t["pnl"] for t in losses),2),
        "total_sells": len(all_sells), "unique_bought": len(set(t["symbol"] for t in buys))}
    save_portfolio(pf)
    pf["total_value"] = sum(p.get("current_value", p.get("invested_usd", p.get("invested",0))) for p in pf["positions"])
    pf["total_invested"] = sum(p.get("invested_usd", p.get("invested",0)) for p in pf["positions"])
    pf["total_pnl"] = pf["total_value"] - pf["total_invested"]
    pf["total_pnl_pct"] = round((pf["total_pnl"] / max(pf["total_invested"],1)) * 100, 1)

    # === 模擬交易組合（自動，$1000本金） ===
    spf = load_sim_portfolio()
    spf.setdefault("trades", [])
    spf.setdefault("capital", 1000)
    spf.setdefault("cash", 1000)
    spf.setdefault("positions", [])
    spf.setdefault("cooldown", {})
    SIM_BUY = 75; SIM_MAX = 8; PERM_BLACKLIST = {"DEBT/SOL"}; SIM_TP = 999.0; SIM_SL = -20.0; SIM_CD = 0
    spf.setdefault("blacklist", [])
    spf["cooldown"] = {sym: ts for sym, ts in spf["cooldown"].items() if now_ts - ts < SIM_CD}
    for pos in spf["positions"]:
        current = next((t for t in all_tokens if t["symbol"] == pos["symbol"]), None)
        if current:
            pos["current_price"] = current["price"]
            pos["miss_count"] = 0
            if current.get("image"): pos["image"] = current["image"]
        else:
            # 幣不在熱門榜 → 直接查真實價格（不在榜 ≠ 死了）
            real_price = None
            try:
                chain = pos.get("chain","") or "sol"; addr = pos.get("address","")
                if addr:
                    pr = requests.get(f"https://api.dexscreener.com/token-pairs/v1/{chain}/{addr}", timeout=5)
                    pairs = pr.json()
                    if pairs:
                        best = max(pairs, key=lambda x: float(x.get("liquidity",{}).get("usd",0) or 0))
                        real_price = float(best.get("priceUsd",0) or 0)
                        if real_price > 0:
                            pos["current_price"] = real_price
            except: pass
            if real_price is None or real_price <= 0:
                pos["current_price"] = pos.get("current_price", pos["buy_price"])
                pos["miss_count"] = pos.get("miss_count", 0) + 1
                if pos["miss_count"] >= 8:  # 改 8 次查不到才算下架
                    pos["_delisted"] = True
            else:
                pos["miss_count"] = 0  # 查得到價格 = 還活著
        if "buy_ts" not in pos: pos["buy_ts"] = now_ts - 3600
        bp = pos["buy_price"]; cp = pos["current_price"]
        if bp > 0 and cp > bp * 5: pos["current_price"] = bp * 5
        elif bp > 0 and cp < bp / 5: pos["current_price"] = bp / 5
        pos["current_value"] = pos["shares"] * pos["current_price"]
        pos["pnl"] = pos["current_value"] - pos["invested"]
        pos["pnl_pct"] = round((pos["pnl"] / pos["invested"]) * 100, 1)
    kept = []
    for pos in spf["positions"]:
        sr = None
        held_secs = now_ts - pos.get("buy_ts", now_ts)
        if pos.get("_delisted"): sr = "下架死幣"
        elif pos["pnl_pct"] >= SIM_TP: sr = f"停利+{pos['pnl_pct']}%"
        elif pos["pnl_pct"] <= SIM_SL: sr = f"停損{pos['pnl_pct']}%"
        elif pos.get("peak_pct",0) >= 50 and pos["pnl_pct"] < pos["peak_pct"] * 0.60: sr = f"移動停利{pos['pnl_pct']}%(峰{pos['peak_pct']}%)"
        else:
            # RUG 偵測：入場流動性流失 >40%
            entry_liq = pos.get("entry_liq", 0)
            cur_tok = next((t for t in all_tokens if t["symbol"] == pos["symbol"]), None)
            if cur_tok and entry_liq > 0 and cur_tok.get("liquidity",0) < entry_liq * 0.6:
                sr = f"流動性逃離{RUG}"
            elif held_secs > 1800 and pos["pnl_pct"] < 2: sr = f"死幣不動{int(held_secs/60)}分"
            elif held_secs > PF_MAX_HOLD: sr = f"久未動{int(held_secs/60)}分鐘"
        if sr:
            spf["cash"] += pos["current_value"]
            held_min = int(held_secs/60)
            spf["trades"].append({"time": now_str, "symbol": pos["symbol"], "action": "SELL",
                "buy_price": pos["buy_price"], "sell_price": pos["current_price"],
                "pnl": round(pos["pnl"],2), "pnl_pct": pos["pnl_pct"],
                "held_min": held_min, "buy_score": pos.get("buy_score",0),
                "entry_liq": pos.get("entry_liq",0),
                "url": pos.get("url",""), "address": pos.get("address",""), "reason": sr})
            spf["cooldown"][pos["symbol"]] = now_ts + 0 if pos["pnl"] < 0 else now_ts  # 公海不冷卻
            # 虧錢不永久黑名單，只冷卻5分鐘
        else: kept.append(pos)
    held = [p["symbol"] for p in kept]
    fresh = [t for t in all_tokens if t["symbol"] not in held and t["symbol"] not in spf["cooldown"] and t["symbol"] not in spf.get("blacklist",[]) and t["symbol"] not in PERM_BLACKLIST and t["score"] >= 3.5 and t["price"] > 0 and t.get("buy_ratio",50) >= 40 and t.get("liquidity",0) > 30000 and (time.time() - first_seen_map.get(t["symbol"], 0)) > 900]
    bought_syms = set(held)
    for t in fresh:
        if t["symbol"] in bought_syms: continue
        if len(kept) >= SIM_MAX: break
        if spf["cash"] < SIM_BUY: break
        pair_addr = t.get("url","").rstrip("/").split("/")[-1]
        if pair_addr and len(pair_addr) > 32:
            ok_w, wmsg = check_wash_addresses(pair_addr)
            if not ok_w:
                print(f"[WASH SKIP] {t['symbol']} {wmsg}", flush=True)
                bought_syms.add(t["symbol"])
                continue
        real_p = get_real_buy_price(t["address"], t["price"])
        buy_amt = SIM_BUY  # 取消加碼，固定倉位避免追高
        if spf["cash"] < buy_amt: continue
        bought_syms.add(t["symbol"])
        kept.append({"symbol": t["symbol"], "buy_price": real_p, "buy_time": now_str,
            "buy_ts": now_ts, "entry_liq": t.get("liquidity",0),
            "invested": buy_amt, "shares": buy_amt/real_p, "url": t["url"],
            "buy_score": t["score"], "address": t.get("address",""), "chain": t.get("chain",""),
            "image": t.get("image","")})
        spf["cash"] -= buy_amt
        spf["trades"].append({"time": now_str, "symbol": t["symbol"], "action": "BUY",
            "buy_price": t["price"], "sell_price": 0, "pnl": 0, "pnl_pct": 0,
            "url": t["url"], "address": t.get("address",""), "reason": f"score={t['score']}"})
    spf["positions"] = kept
    ss = [t for t in spf["trades"] if t["action"]=="SELL"]
    sw = [t for t in ss if t["pnl"]>0]; sl = [t for t in ss if t["pnl"]<=0]
    sr2 = [t for t in ss if t.get("pnl_pct",0)<=-51]
    sb = [t for t in spf["trades"] if t["action"]=="BUY"]
    spf["stats"] = {"wins": len(sw), "losses": len(sl), "rugs": len(sr2),
        "win_amount": round(sum(t["pnl"] for t in sw),2),
        "loss_amount": round(sum(t["pnl"] for t in sl),2),
        "total_sells": len(ss), "unique_bought": len(set(t["symbol"] for t in sb))}
    spf["total_value"] = sum(p.get("current_value", p["invested"]) for p in spf["positions"])
    spf["total_invested"] = sum(p["invested"] for p in spf["positions"])
    spf["total_pnl"] = spf["total_value"] + spf["cash"] - spf["capital"]
    spf["total_pnl_pct"] = round((spf["total_pnl"] / spf["capital"]) * 100, 1)
    save_sim_portfolio(spf)

    potential = [t for t in all_tokens
        if t["symbol"] not in [p["symbol"] for p in pf["positions"]]
        and t["liquidity"] > 3000 and t["buy_ratio"] >= 50
        and -20 < t["change_1h"] < 20 and -20 < t["change_24h"] < 50
        and t["volume_24h"] > 5000]
    potential.sort(key=lambda x: x["buy_ratio"], reverse=True)

    # Telegram 新幣通知
    TOKEN, CHAT_ID = "", ""
    try:
        envf = open(r"C:\Users\ANGEL\Doubao\chats\2026-09-12\new-chat\stonkfly\.env", encoding="utf-8").read()
        for line in envf.splitlines():
            if line.startswith("TELEGRAM_BOT_TOKEN="): TOKEN = line.split("=",1)[1].strip()
            if line.startswith("TELEGRAM_CHAT_ID="): CHAT_ID = line.split("=",1)[1].strip()
    except: pass
    SEEN_FILE = r'C:\Users\ANGEL\Doubao\chats\2026-09-12\new-chat\dex_scanner\seen_coins.json'
    try:
        with open(SEEN_FILE, "r") as f: seen = set(json.load(f))
    except: seen = set()
    hot_tokens = [t for t in all_tokens if t["score"] >= 4]
    new_coins = [t for t in hot_tokens + potential if t["symbol"] not in seen]
    for t in new_coins: seen.add(t["symbol"])
    if new_coins and TOKEN and CHAT_ID:
        if NOTIFY_ENABLED:
         for t in new_coins[:3]:
            emoji = "🔥" if t["score"] >= 4 else "🌱"
            p_str = f"${t['price']:.8f}" if t['price'] < 0.01 else f"${t['price']:.4f}"
            msg = f"{emoji} 新幣警報\n\n幣種: {t['symbol']}\n名稱: {t['name']}\n價格: {p_str}\n1h: {t['change_1h']:+.1f}%\n24h: {t['change_24h']:+.1f}%\n買盤: {t['buy_ratio']}%\n流動性: ${t['liquidity']:,.0f}\n\n{t['url']}"
            try:
                if MEME_NOTIFY_ENABLED:
                    if False: requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                        data={"chat_id": CHAT_ID, "text": msg}, timeout=10)
            except: pass
    try:
        with open(SEEN_FILE, "w") as f: json.dump(list(seen), f)
    except: pass

    trending = []
    try:
        tr = requests.get("https://api.coingecko.com/api/v3/search/trending", timeout=8)
        for c in tr.json().get("coins", [])[:10]:
            trending.append({"rank": c["item"]["score"]+1, "name": c["item"]["name"],
                "symbol": c["item"]["symbol"].upper(), "thumb": c["item"].get("thumb","")})
    except: pass

    try:
        with open(REC_FILE, "r") as rf: rec_tracker = json.load(rf)
    except: rec_tracker = {}
    rec_symbols = {t["symbol"]: t for t in all_tokens if t["score"] >= 4}
    for sym, t in rec_symbols.items():
        if sym not in rec_tracker:
            rec_tracker[sym] = {"buy_price": t["price"], "buy_time": datetime.now(UTC8).strftime("%H:%M"),
                "image": t.get("image",""), "url": t["url"]}
        rec_tracker[sym]["current_price"] = t["price"]
        rec_tracker[sym]["pnl"] = round((t["price"]-rec_tracker[sym]["buy_price"])/rec_tracker[sym]["buy_price"]*100,1) if rec_tracker[sym]["buy_price"]>0 else 0
    rec_tracker = {k:v for k,v in rec_tracker.items() if k in rec_symbols}
    with open(REC_FILE, "w") as rf: json.dump(rec_tracker, rf, ensure_ascii=False)

    # === 下架幣偵測（永久歷史） ===
    SEEN_FILE = os.path.join(os.path.dirname(__file__), "seen_tokens.json")
    DELISTED_FILE = os.path.join(os.path.dirname(__file__), "delisted_history.json")
    try:
        with open(SEEN_FILE, "r", encoding="utf-8") as sf: prev_seen = json.load(sf)
    except: prev_seen = {}
    try:
        with open(DELISTED_FILE, "r", encoding="utf-8") as df: delisted_hist = json.load(df)
    except: delisted_hist = []
    curr_symbols = {t["symbol"] for t in all_tokens}
    # 更新 seen_tokens 並記錄最高價
    new_seen = {}
    for t in all_tokens:
        old = prev_seen.get(t["symbol"], {})
        peak = max(old.get("peak", t["price"]), t["price"])
        new_seen[t["symbol"]] = {"price": t["price"], "peak": peak,
            "image": t.get("image",""), "url": t["url"], "score": t["score"],
            "address": t.get("address",""), "chain": t.get("chain","")}
    # 消失的幣 → 存入永久歷史（只記錄曾持倉/曾買賣的，避免 GMGN 輪動噪音）
    existing_delisted = {d["symbol"] for d in delisted_hist}
    held_syms = set()
    for p in pf.get("positions", []): held_syms.add(p["symbol"])
    for p in spf.get("positions", []): held_syms.add(p["symbol"])
    for tr in pf.get("trades", []): held_syms.add(tr.get("symbol",""))
    for tr in spf.get("trades", []): held_syms.add(tr.get("symbol",""))
    for sym, info in prev_seen.items():
        if sym not in curr_symbols and sym not in existing_delisted and sym in held_syms:
            last_price = info.get("price", 0)
            peak = info.get("peak", last_price)
            crash_pct = round((last_price - peak) / peak * 100, 1) if peak > 0 else 0
            delisted_hist.append({
                "symbol": sym, "last_price": last_price, "peak_price": peak,
                "crash_pct": crash_pct, "last_score": info.get("score", 0),
                "image": info.get("image",""), "url": info.get("url",""),
                "address": info.get("address",""), "delist_time": datetime.now(UTC8).strftime("%m-%d %H:%M")
            })
    delisted_hist = delisted_hist[-50:]  # 最多保留50筆
    with open(SEEN_FILE, "w", encoding="utf-8") as sf: json.dump(new_seen, sf, ensure_ascii=False)
    with open(DELISTED_FILE, "w", encoding="utf-8") as df: json.dump(delisted_hist, df, ensure_ascii=False, indent=2)

    result = {"scanned_at": datetime.now(UTC8).strftime("%H:%M:%S"), "total": len(all_tokens),
              "tokens": all_tokens[:25], "portfolio": pf, "sim_portfolio": spf,
              "potential": potential[:8], "trending": trending, "rec_tracker": rec_tracker,
              "delisted": list(reversed(delisted_hist[-20:]))}
    CACHE["data"] = result; CACHE["ts"] = time.time()
    return result

@app.route("/api/dex")
def api_dex(): return jsonify(fetch_meme_coins())

@app.route("/api/toggle_notify", methods=["POST"])
def toggle_notify():
    global NOTIFY_ENABLED
    global NOTIFY_ENABLED
    NOTIFY_ENABLED = not NOTIFY_ENABLED
    with open("notify_pref.json","w") as _f: json.dump({"tg": NOTIFY_ENABLED}, _f)
    return jsonify({"enabled": NOTIFY_ENABLED})

@app.route("/api/clear_delisted", methods=["POST"])
def clear_delisted():
    DELISTED_FILE = os.path.join(os.path.dirname(__file__), "delisted_history.json")
    with open(DELISTED_FILE, "w", encoding="utf-8") as df: json.dump([], df)
    return jsonify({"ok": True})

@app.route("/app.js")
def app_js(): return send_file("app.js", mimetype="application/javascript")
@app.route("/alert.mp3")
def alert(): return send_file("alert.mp3")

@app.route("/api/balance/<pubkey>")
def api_balance(pubkey):
    try:
        sol = get_sol_balance(pubkey)
        return jsonify({"ok": True, "sol": sol})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

@app.route("/api/notify_toggle", methods=["POST"])
def api_notify_toggle():
    global MEME_NOTIFY_ENABLED
    MEME_NOTIFY_ENABLED = request.json.get("enabled", True)
    with open("notify_pref.json","w") as _f: json.dump({"tg": MEME_NOTIFY_ENABLED}, _f)
    try:
        TOKEN = CHAT_ID = ""
        import os
        envf = r'C:\Users\ANGEL\Doubao\chats\2026-09-12\new-chat\stonkfly\.env'
        if os.path.exists(envf):
            for line in open(envf, encoding="utf-8").read().splitlines():
                if line.startswith("TELEGRAM_BOT_TOKEN="): TOKEN = line.split("=",1)[1].strip()
                if line.startswith("TELEGRAM_CHAT_ID="): CHAT_ID = line.split("=",1)[1].strip()
        if TOKEN and CHAT_ID:
            msg = "🚀 迷因幣雷達通知已開啟" if MEME_NOTIFY_ENABLED else "🔕 迷因幣雷達通知已關閉"
            if False: requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                data={"chat_id": CHAT_ID, "text": msg}, timeout=10)
    except Exception as e: print(f"notify toggle: {e}")
    return jsonify({"ok": True, "enabled": MEME_NOTIFY_ENABLED})

@app.route("/api/save_privkey", methods=["POST"])
def api_save_privkey():
    pk = request.json.get("privkey", "").strip()
    pub = request.json.get("pubkey", "").strip()
    with open(PRIVKEY_FILE, "w") as f: json.dump({"privkey": pk, "pubkey": pub}, f)
    return jsonify({"ok": True})

@app.route("/api/get_privkey")
def api_get_privkey():
    try:
        with open(PRIVKEY_FILE, "r") as f: d = json.load(f)
        return jsonify({"ok": True, "pubkey": d.get("pubkey",""), "has_privkey": bool(d.get("privkey"))})
    except: return jsonify({"ok": True, "pubkey": "", "has_privkey": False})

@app.route("/api/toggle_trading", methods=["POST"])
def api_toggle_trading():
    pf = load_portfolio()
    pf["trading_enabled"] = not pf.get("trading_enabled", False)
    save_portfolio(pf)
    return jsonify({"ok": True, "enabled": pf["trading_enabled"]})

@app.route("/api/save_trade_amount", methods=["POST"])
def api_save_trade_amount():
    amt = float(request.json.get("amount", 0.1))
    pf = load_portfolio()
    pf["trade_amount_sol"] = amt
    save_portfolio(pf)
    return jsonify({"ok": True, "amount": amt})

@app.route("/")
def index():
    with open("dashboard.html", "r", encoding="utf-8") as f:
        return Response(f.read(), mimetype="text/html")

def check_wash_addresses(pair_address, limit=20):
    try:
        r = requests.post("https://api.mainnet-beta.solana.com", json={
            "jsonrpc":"2.0","id":1,"method":"getSignaturesForAddress",
            "params":[pair_address, {"limit": limit}]
        }, timeout=8).json()
        sigs = [s["signature"] for s in r.get("result",[])]
        if len(sigs) < 10: return True, "交易筆數不足"
        from collections import Counter
        signers = []
        for sig in sigs[:10]:
            tx = requests.post("https://api.mainnet-beta.solana.com", json={
                "jsonrpc":"2.0","id":1,"method":"getTransaction",
                "params":[sig, {"maxSupportedTransactionVersion":0}]
            }, timeout=8).json()
            msg = tx.get("result",{}).get("transaction",{}).get("message",{})
            if msg: signers.append(msg["accountKeys"][0])
        if len(signers) < 8: return True, "無法讀取交易"
        unique = len(set(signers))
        repeat_ratio = 1 - unique/len(signers)
        if repeat_ratio > 0.5:
            return False, f"洗盤:{unique}/{len(signers)}地址"
        return True, f"正常:{unique}/{len(signers)}地址"
    except Exception as e:
        return True, f"檢查失敗:{e}"


if __name__ == "__main__":
    print("迷因幣雷達: http://127.0.0.1:8770")
    app.run(host="0.0.0.0", port=int(__import__("os").environ.get("PORT", 8080)), debug=False, threaded=True)


