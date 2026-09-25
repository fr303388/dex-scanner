"""迷因幣雷達 - 含模擬交易 + 真實鏈上交易 (Solana Jupiter)"""
import requests, time, json, base64, os
from datetime import datetime, timezone, timedelta
from flask import Flask, jsonify, send_file, Response, request

app = Flask(__name__)
MEME_NOTIFY_ENABLED = True
UTC8 = timezone(timedelta(hours=8))
CACHE = {"data": None, "ts": 0}
PORTFOLIO_FILE = r'C:\Users\ANGEL\Doubao\chats\2026-09-12\new-chat\dex_scanner\portfolio.json'
SIM_PORTFOLIO_FILE = r'C:\Users\ANGEL\Doubao\chats\2026-09-12\new-chat\dex_scanner\sim_portfolio.json'
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
    if h1 > 30: score += 2; reasons.append("1h強勢")
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
    if liq > 0 and vol/liq > 5: score -= 2; reasons.append("疑似洗盤量假")
    # 反拉盤：1h 暴漲 >80% 且 24h 暴漲 >300% = 典型拉盤砸盤
    if h1 > 80 and h24 > 300: score -= 3; reasons.append("拉盤陷阱")
    # 反洗盤：交易筆數太少 = 只有幾個地址在刷
    txns = t.get("txns_24h", 999)
    avg_t = t.get("avg_trade", 0)
    if txns < 30: score -= 3; reasons.append("交易筆數極少")
    elif txns < 80: score -= 1; reasons.append("交易冷清")
    # 平均每筆金額過大 = 大戶自買自賣
    if avg_t > 5000 and txns < 100: score -= 2; reasons.append("大戶對敲洗盤")
    # 買賣次數接近 50/50 且筆數少 = 典型對敲
    if txns > 0 and txns < 50:
        b_ratio = t.get("buy_ratio", 50)
        if 40 < b_ratio < 60: score -= 1; reasons.append("買賣對敲")
    rating = "🔥強推薦" if score>=4 else "✅可關注" if score>=2 else "⚪觀望" if score>=0 else "⚠️危險" if score>=-2 else "❌避開"
    return round(score,1), rating, reasons

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
                    if liq < 10000: continue
                    br = round(buys/(buys+sells)*100) if (buys+sells)>0 else 50
                    txns_24h = buys + sells
                    avg_trade = vol / txns_24h if txns_24h > 0 else 0
                    t = {"symbol":f"{base}/SOL","name":name,"price":price,"change_1h":round(h1,1),"change_24h":round(h24,1),"volume_24h":round(vol),"liquidity":round(liq),"chain":chain,"url":p.get("url",""),"buy_ratio":br,"address":addr,"image":(p.get("info",{}) or {}).get("imageUrl",""),"txns_24h":txns_24h,"avg_trade":round(avg_trade)}
                    sc, rating, reasons = score_token(t)
                    t["score"], t["rating"], t["reasons"] = sc, rating, reasons
                    all_tokens.append(t); break
            except: pass
    except: pass
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
    PF_TP = 20.0
    PF_SL = -10.0
    PF_COOLDOWN = 30
    PF_MAX_HOLD = 7200  # 持倉超過2小時則賣出（久未動）
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
                        "tx": sig, "fee_sol": fee_sol,
                        "reason": f"{sell_reason} 鏈上成交"
                    })
                else:
                    err = f"賣出 {pos['symbol']} 失敗: {sig}"
                    print(f"[ONCHAIN SELL FAIL] {err}", flush=True)
                    pf["last_error"] = err
                    pf_kept.append(pos)
                    continue
            pf["cooldown"][pos["symbol"]] = now_ts
            # 虧錢賣出 → 加入黑名單不再買
            if pos["pnl"] < 0 and pos["symbol"] not in pf["blacklist"]:
                pf["blacklist"].append(pos["symbol"])
                print(f"[BLACKLIST] {pos['symbol']} 虧錢賣出，不再買入", flush=True)
        else:
            pf_kept.append(pos)

    # 自動買入（按下開始交易後才啟用）→ 鏈上 SOL->token
    if pf.get("trading_enabled", False) and kp:
        pf_held = [p["symbol"] for p in pf_kept]
        pf_fresh = [t for t in all_tokens if t["symbol"] not in pf_held and t["symbol"] not in pf["cooldown"] and t["symbol"] not in pf["blacklist"] and t["score"] >= 4 and t["price"] > 0]
        for t in pf_fresh:
            if len(pf_kept) >= PF_MAX: break
            if wallet_balance_sol < PF_BUY_SOL:
                err = f"餘額不足: {wallet_balance_sol:.4f} SOL < {PF_BUY_SOL} SOL"
                print(f"[ONCHAIN BUY SKIP] {err}", flush=True)
                pf["last_error"] = err
                break
            # 真實鏈上買入
            sol_lamports = int(PF_BUY_SOL * 1e9)
            ok, sig = jupiter_swap(kp, WsolMint, t["address"], sol_lamports)
            if ok:
                print(f"[ONCHAIN BUY] {t['symbol']} {PF_BUY_SOL} SOL tx: {sig[:20]}...", flush=True)
                invested_usd = PF_BUY_SOL * 150  # 估計 USD (SOL~$150)
                pf_kept.append({
                    "symbol": t["symbol"], "buy_price": t["price"], "buy_time": now_str,
                    "buy_ts": now_ts,
                    "invested_sol": PF_BUY_SOL, "invested_usd": invested_usd,
                    "shares": invested_usd/t["price"],
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
    rugs = [t for t in all_sells if t.get("pnl_pct",0)<=-70]
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
    SIM_BUY = 100; SIM_MAX = 10; SIM_TP = 20.0; SIM_SL = -10.0; SIM_CD = 30
    spf.setdefault("blacklist", [])
    spf["cooldown"] = {sym: ts for sym, ts in spf["cooldown"].items() if now_ts - ts < SIM_CD}
    for pos in spf["positions"]:
        current = next((t for t in all_tokens if t["symbol"] == pos["symbol"]), None)
        if current:
            pos["current_price"] = current["price"]
            if current.get("image"): pos["image"] = current["image"]
        else:
            pos["current_price"] = pos.get("current_price", pos["buy_price"])
            # 幣種已從 DexScreener 下架 → 視為死幣，標記賣出
            pos["_delisted"] = True
        if "buy_ts" not in pos: pos["buy_ts"] = now_ts - 3600  # 舊持倉預設1小時前
        pos["current_value"] = pos["shares"] * pos["current_price"]
        pos["pnl"] = pos["current_value"] - pos["invested"]
        pos["pnl_pct"] = round((pos["pnl"] / pos["invested"]) * 100, 1)
    kept = []
    for pos in spf["positions"]:
        sr = None
        held_secs = now_ts - pos.get("buy_ts", now_ts)
        if pos.get("_delisted"): sr = "下架死幣"
        elif pos["pnl_pct"] >= SIM_TP: sr = f"停利+{pos['pnl_pct']}%"
        elif pos["pnl_pct"] <= -5 and held_secs < 300: sr = f"早期止損{pos['pnl_pct']}%"
        elif pos["pnl_pct"] <= SIM_SL: sr = f"停損{pos['pnl_pct']}%"
        else:
            # RUG 偵測：入場流動性流失 >40%
            entry_liq = pos.get("entry_liq", 0)
            cur_tok = next((t for t in all_tokens if t["symbol"] == pos["symbol"]), None)
            if cur_tok and entry_liq > 0 and cur_tok.get("liquidity",0) < entry_liq * 0.6:
                sr = f"流動性逃離{RUG}"
            elif held_secs > PF_MAX_HOLD: sr = f"久未動{int(held_secs/60)}分鐘"
        if sr:
            spf["cash"] += pos["current_value"]
            spf["trades"].append({"time": now_str, "symbol": pos["symbol"], "action": "SELL",
                "buy_price": pos["buy_price"], "sell_price": pos["current_price"],
                "pnl": round(pos["pnl"],2), "pnl_pct": pos["pnl_pct"], "reason": sr})
            spf["cooldown"][pos["symbol"]] = now_ts
            if pos["pnl"] < 0 and pos["symbol"] not in spf["blacklist"]:
                spf["blacklist"].append(pos["symbol"])
        else: kept.append(pos)
    held = [p["symbol"] for p in kept]
    fresh = [t for t in all_tokens if t["symbol"] not in held and t["symbol"] not in spf["cooldown"] and t["symbol"] not in spf.get("blacklist",[]) and t["score"] >= 4 and t["price"] > 0]
    for t in fresh:
        if len(kept) >= SIM_MAX: break
        if spf["cash"] < SIM_BUY: break
        kept.append({"symbol": t["symbol"], "buy_price": t["price"], "buy_time": now_str,
            "buy_ts": now_ts, "entry_liq": t.get("liquidity",0),
            "invested": SIM_BUY, "shares": SIM_BUY/t["price"], "url": t["url"],
            "buy_score": t["score"], "address": t.get("address",""), "chain": t.get("chain",""),
            "image": t.get("image","")})
        spf["cash"] -= SIM_BUY
        spf["trades"].append({"time": now_str, "symbol": t["symbol"], "action": "BUY",
            "buy_price": t["price"], "sell_price": 0, "pnl": 0, "pnl_pct": 0, "reason": f"score={t['score']}"})
    spf["positions"] = kept
    ss = [t for t in spf["trades"] if t["action"]=="SELL"]
    sw = [t for t in ss if t["pnl"]>0]; sl = [t for t in ss if t["pnl"]<=0]
    sr2 = [t for t in ss if t.get("pnl_pct",0)<=-70]
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
        for t in new_coins[:3]:
            emoji = "🔥" if t["score"] >= 4 else "🌱"
            p_str = f"${t['price']:.8f}" if t['price'] < 0.01 else f"${t['price']:.4f}"
            msg = f"{emoji} 新幣警報\n\n幣種: {t['symbol']}\n名稱: {t['name']}\n價格: {p_str}\n1h: {t['change_1h']:+.1f}%\n24h: {t['change_24h']:+.1f}%\n買盤: {t['buy_ratio']}%\n流動性: ${t['liquidity']:,.0f}\n\n{t['url']}"
            try:
                if MEME_NOTIFY_ENABLED:
                    requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
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

    # === 下架幣偵測 ===
    SEEN_FILE = os.path.join(os.path.dirname(__file__), "seen_tokens.json")
    try:
        with open(SEEN_FILE, "r", encoding="utf-8") as sf: prev_seen = json.load(sf)
    except: prev_seen = {}
    curr_symbols = {t["symbol"] for t in all_tokens}
    delisted = []
    for sym, info in prev_seen.items():
        if sym not in curr_symbols:
            delisted.append({"symbol": sym, "price": info.get("price",0), "image": info.get("image",""), "url": info.get("url",""), "last_score": info.get("score",0)})
    # 更新 seen_tokens
    new_seen = {}
    for t in all_tokens:
        new_seen[t["symbol"]] = {"price": t["price"], "image": t.get("image",""), "url": t["url"], "score": t["score"]}
    with open(SEEN_FILE, "w", encoding="utf-8") as sf: json.dump(new_seen, sf, ensure_ascii=False)

    result = {"scanned_at": datetime.now(UTC8).strftime("%H:%M:%S"), "total": len(all_tokens),
              "tokens": all_tokens[:25], "portfolio": pf, "sim_portfolio": spf,
              "potential": potential[:8], "trending": trending, "rec_tracker": rec_tracker,
              "delisted": delisted[:10]}
    CACHE["data"] = result; CACHE["ts"] = time.time()
    return result

@app.route("/api/dex")
def api_dex(): return jsonify(fetch_meme_coins())

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
            requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
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

if __name__ == "__main__":
    print("迷因幣雷達: http://127.0.0.1:8770")
    app.run(host="127.0.0.1", port=8770, debug=False, threaded=True)
