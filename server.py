"""迷因幣雷達 V3.1 — 背景自主掃描、mint address 管理、Jupiter 可成交報價"""
import requests, time, json, os, subprocess, shutil, threading, csv
DECISION_LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "decisions.csv")
TRAJECTORY_LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "trajectory.csv")
def log_trajectory(pos, now_ts):
    """每個循環記錄持倉狀態"""
    file_exists = os.path.exists(TRAJECTORY_LOG)
    with open(TRAJECTORY_LOG, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if not file_exists:
            w.writerow(["ts","time","address","symbol","price","pnl_pct","mfe","mae",
                        "peak_pct","current_value","sell_impact","held_min"])
        held = (now_ts - pos.get("buy_ts", now_ts)) / 60
        w.writerow([int(now_ts), time.strftime("%m-%d %H:%M:%S"),
                    pos["address"], pos["symbol"], pos.get("current_price",0),
                    pos.get("pnl_pct",0), pos.get("mfe",0), pos.get("mae",0),
                    pos.get("peak_pct",0), pos.get("current_value",0),
                    pos.get("sell_impact",0), round(held,1)])
def log_decisions(tokens, sim, rejected, now_ts, entered):
    """entered = 本輪「實際成交」的 address 集合。

    為什麼不能用 kept 代替：呼叫端在呼叫本函式之前已經執行
    sim["positions"] = kept，兩者是同一個清單物件，所以 kept 的位址集合
    與 held 完全相同，判斷式會永遠先命中 HELD，ENTERED 永遠不會被寫出。
    """
    file_exists = os.path.exists(DECISION_LOG)
    with open(DECISION_LOG, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if not file_exists:
            w.writerow(["ts","time","address","symbol","score","price","h1","h24",
                        "volume","liquidity","buy_ratio","txns_24h","decision","reason"])
        held = {p["address"] for p in sim["positions"]}
        entered = set(entered or ())
        rej_map = {rt["address"]: r for rt, r in rejected}
        for t in tokens:
            addr = t["address"]
            if t.get("liquidity", 0) < 35000: continue
            if addr in entered:
                decision = "ENTERED"          # 本輪成交（同時也會在 held 裡）
            elif addr in held:
                decision = "HELD"
            else:
                decision = "REJECTED"
            if addr in sim.get("cooldown", {}) and addr not in entered:
                decision = "COOLDOWN"
            w.writerow([int(now_ts), time.strftime("%m-%d %H:%M"), addr,
                        t["symbol"], t["score"], t["price"],
                        t.get("change_1h",0), t.get("change_24h",0),
                        t.get("volume_24h",0), t.get("liquidity",0),
                        t.get("buy_ratio",0), t.get("txns_24h",0),
                        decision, rej_map.get(addr,"")])
from datetime import datetime, timezone, timedelta
from flask import Flask, jsonify, send_file, Response, request

app = Flask(__name__)
UTC8 = timezone(timedelta(hours=8))
LOCK = threading.Lock()

# ============ 設定 ============
SIM_CAPITAL = 1000
SIM_BUY_USD = 75
SIM_MAX_POS = 3
# 分級流動性門檻
LIQ_TIER1 = 75000   # 大池：score>=5, buy>=52%, impact<=2%
LIQ_TIER2 = 35000   # 小池：score>=6, buy>=55%, impact<=1.5%
SIM_SL_PCT = -12.0
SIM_MAX_HOLD = 2 * 3600
SIM_DEAD_SECS = 2700          # 45 分未延續
SIM_COOLDOWN = 24 * 3600      # 同 mint 當日不進
SOL_USD = 150
def get_sol_price():
    global SOL_USD
    try:
        r = requests.get("https://api.jup.ag/price/v2?ids=So11111111111111111111111111111111111111112", timeout=5)
        SOL_USD = float(r.json()["data"]["So11111111111111111111111111111111111111112"]["price"])
    except: pass
SCAN_INTERVAL = 15

WSOL = "So11111111111111111111111111111111111111112"
import os
JUP_API_KEY = os.environ.get("JUP_API_KEY", "")
if not JUP_API_KEY:
    try:
        for line in open(".env", encoding="utf-8"):
            if line.startswith("JUP_API_KEY="):
                JUP_API_KEY = line.strip().split("=",1)[1]
    except: pass
SIM_FILE = "sim_portfolio.json"
FIRST_SEEN_FILE = "first_seen.json"

GMGN_KEY = os.environ.get("GMGN_API_KEY", "")
if not GMGN_KEY:
    try:
        for line in open(".env", encoding="utf-8"):
            if line.startswith("GMGN_API_KEY="): GMGN_KEY = line.strip().split("=",1)[1]
    except: pass
GMGN_NODE = r"C:\Users\ANGEL\AppData\Local\Doubao\User Data\sandbox_runtime\bases\c98c5042338ed152c6f10ecd8591889f\node\node.exe"
GMGN_CLI = r"C:\Users\ANGEL\AppData\Local\Doubao\User Data\sandbox_runtime\bases\c98c5042338ed152c6f10ecd8591889f\node\node_modules\gmgn-cli\dist\index.js"

# ============ 全域狀態 ============
STATE = {
    "tokens": [],
    "scanned_at": "",
    "sim": None,
}

# ============ 持久化 ============
def load_sim():
    try:
        with open(SIM_FILE, "r", encoding="utf-8") as f:
            d = json.load(f)
        d.setdefault("cash", SIM_CAPITAL)
        d.setdefault("positions", [])
        d.setdefault("trades", [])
        d.setdefault("cooldown", {})
        d.setdefault("blacklist", [])
        return d
    except json.JSONDecodeError:
        bak = f"{SIM_FILE}.corrupt-{int(time.time())}"
        shutil.copyfile(SIM_FILE, bak)
        print(f"[SIM] corrupt, backed up to {bak}", flush=True)
    except: pass
    return {"cash": SIM_CAPITAL, "positions": [], "trades": [], "cooldown": {}, "blacklist": []}

def save_sim(sim):
    save_circuit(sim)
    tmp = SIM_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(sim, f, ensure_ascii=False, indent=2)
    os.replace(tmp, SIM_FILE)

def load_first_seen():
    try:
        with open(FIRST_SEEN_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except: return {}

def save_first_seen(d):
    with open(FIRST_SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(d, f)

# ============ Jupiter 報價 ============
def jup_quote(input_mint, output_mint, amount_lamports, slippage_bps=500):
    """回傳 quote dict，失敗回傳 None"""
    try:
        r = requests.get("https://api.jup.ag/swap/v1/quote", headers={"x-api-key": JUP_API_KEY}, params={
            "inputMint": input_mint, "outputMint": output_mint,
            "amount": str(int(amount_lamports)), "slippageBps": str(slippage_bps),
        }, timeout=10)
        q = r.json()
        if "error" in q or "outAmount" not in q:
            return None
        return q
    except Exception as e:
        print(f"[JUP] quote fail: {e}", flush=True)
        return None

PENDING = {}
TRIGGER_TRACK = {}  # addr -> list of (ts, price, volume) snapshots
def update_trigger_history(tokens, now_ts):
    for t in tokens:
        addr = t["address"]
        if not addr: continue
        hist = TRIGGER_TRACK.setdefault(addr, [])
        hist.append((now_ts, t["price"], t.get("volume_24h", 0)))
        cutoff = now_ts - 1800
        while hist and hist[0][0] < cutoff: hist.pop(0)

def check_trigger(addr, t, now_ts):
    """排名與觸發分離：score 通過後，等突破或回踩再起才進場"""
    hist = TRIGGER_TRACK.setdefault(addr, [])
    hist.append((now_ts, t["price"], t.get("volume_24h", 0)))
    # 只留最近 30 分鐘（120 個 15 秒點）
    cutoff = now_ts - 1800
    while hist and hist[0][0] < cutoff: hist.pop(0)
    if len(hist) < 8:  # 至少收集 2 分鐘
        return False, "收集走勢中"
    prices = [h[1] for h in hist]
    recent = prices[-8:]   # 最近 2 分鐘
    prior = prices[:-8]    # 之前
    if not prior: return False, "資料不足"
    hi_prior = max(prior)
    lo_prior = min(prior)
    cur = prices[-1]
    # 模式1：突破 — 現價突破前高，且不在追高區
    if cur > hi_prior * 1.01 and t.get("change_1h", 0) < 50:
        return True, "突破"
    # 模式2：回踩再起 — 從高點回撤10-25%後重新站回近期均價
    peak = max(prices)
    if peak > 0:
        pullback = (peak - cur) / peak
        avg_recent = sum(recent) / len(recent)
        if 0.10 <= pullback <= 0.25 and cur >= avg_recent:
            return True, "回踩再起"
    return False, "等待觸發"

CIRCUIT = {"consecutive_losses": 0, "paused_until": 0, "day_pnl": 0, "day_date": ""}
def save_circuit(sim):
    sim["circuit"] = CIRCUIT
def load_circuit(sim):
    global CIRCUIT
    if "circuit" in sim: CIRCUIT = sim["circuit"]  # addr -> first pass timestamp
DECIMALS_CACHE = {}
def get_token_decimals(mint):
    if mint in DECIMALS_CACHE: return DECIMALS_CACHE[mint]
    try:
        r = requests.post("https://api.mainnet-beta.solana.com", json={
            "jsonrpc": "2.0", "id": 1, "method": "getAccountInfo",
            "params": [mint, {"encoding": "jsonParsed"}]
        }, timeout=8)
        dec = r.json()["result"]["value"]["data"]["parsed"]["info"]["decimals"]
        DECIMALS_CACHE[mint] = dec
        return dec
    except Exception as e:
        print(f"[DEC] fail {mint[:8]}: {e}", flush=True)
        return None

def get_buy_quote(token_mint, usd_amount=SIM_BUY_USD):
    """取得買入報價，回傳 (有效價格USD, priceImpact%, inLamports, outAmount)"""
    sol_in = usd_amount / SOL_USD
    lamports = int(sol_in * 1e9)
    q = jup_quote(WSOL, token_mint, lamports)
    if not q: return None
    out_amount = int(q["outAmount"])
    decimals = get_token_decimals(token_mint)
    tokens = out_amount / (10 ** decimals)
    if tokens <= 0: return None
    eff_price = usd_amount / tokens
    impact = float(q.get("priceImpactPct", 0) or 0) * 100
    return {"price_usd": eff_price, "impact_pct": round(impact, 3),
            "in_lamports": lamports, "out_amount": out_amount,
            "decimals": decimals, "tokens": tokens}

def get_sell_value_usd(token_mint, token_amount, decimals=6):
    """取得完整賣出報價，回傳可拿回 USD"""
    raw = int(token_amount * (10 ** decimals))
    if raw <= 0: return None
    q = jup_quote(token_mint, WSOL, raw)
    if not q: return None
    out_lamports = int(q["outAmount"])
    sol_out = out_lamports / 1e9
    impact = float(q.get("priceImpactPct", 0) or 0) * 100
    return {"usd": sol_out * SOL_USD, "sol": sol_out, "impact_pct": round(impact, 3)}

# ============ GMGN ============
GMGN_CACHE = {"data": {}, "ts": 0}
def fetch_gmgn():
    if time.time() - GMGN_CACHE["ts"] < 120:
        return GMGN_CACHE["data"]
    try:
        env = dict(os.environ, GMGN_API_KEY=GMGN_KEY)
        out = subprocess.run([GMGN_NODE, GMGN_CLI, "market", "trending",
                              "--chain", "sol", "--interval", "1h",
                              "--limit", "50", "--raw"],
                             capture_output=True, text=True,
                             encoding="utf-8", errors="replace",
                             timeout=20, env=env)
        ranks = json.loads(out.stdout).get("data", {}).get("rank", [])
        gm = {}
        for r in ranks:
            a = r.get("address", "")
            if a: gm[a] = r
        GMGN_CACHE["data"] = gm
        GMGN_CACHE["ts"] = time.time()
        print(f"[GMGN] {len(gm)} trending", flush=True)
    except Exception as e:
        print(f"[GMGN] fail: {e}", flush=True)
    return GMGN_CACHE["data"]

# ============ 掃描 ============
def safe_float(v, default=0):
    try: return float(v)
    except: return default

def check_onchain_risk(addr):
    """檢查 mint authority、freeze authority、持倉集中度。回傳 (ok, reason)"""
    try:
        # Mint info
        r = requests.post("https://api.mainnet-beta.solana.com", json={
            "jsonrpc":"2.0","id":1,"method":"getAccountInfo",
            "params":[addr,{"encoding":"jsonParsed"}]
        }, timeout=8)
        info = r.json()["result"]["value"]["data"]["parsed"]["info"]
        if info.get("mintAuthority"):
            return False, "mint權限未撤"
        if info.get("freezeAuthority"):
            return False, "freeze權限未撤"
        # Top holders concentration
        r2 = requests.post("https://api.mainnet-beta.solana.com", json={
            "jsonrpc":"2.0","id":1,"method":"getTokenLargestAccounts",
            "params":[addr]
        }, timeout=8)
        accounts = r2.json()["result"]["value"]
        total_supply = float(info["supply"])
        if total_supply > 0 and accounts:
            top1 = float(accounts[0]["amount"]) / total_supply
            if top1 > 0.30:
                return False, f"最大持倉{top1*100:.0f}%"
        return True, ""
    except Exception as e:
        return True, ""

def score_token(t):
    s = 0; reasons = []
    h1 = t.get("change_1h", 0); h24 = t.get("change_24h", 0)
    vol = t.get("volume_24h", 0); liq = t.get("liquidity", 0)
    br = t.get("buy_ratio", 50)

    if h1 > 50: s -= 2; reasons.append("追高")
    elif h1 > 30: s -= 1; reasons.append("1h追高")
    elif h1 > 10: s += 1; reasons.append("1h漲")
    elif h1 < -30: s -= 3; reasons.append("1h崩")
    elif h1 < -10: s -= 2; reasons.append("1h跌")

    if 10 < h24 <= 50: s += 2; reasons.append("健康漲")
    elif 50 < h24 <= 150: s += 1; reasons.append("強勢")
    elif h24 > 200: s -= 1; reasons.append("高位")
    elif h24 < -50: s -= 5; reasons.append("已崩")
    elif h24 < -30: s -= 3; reasons.append("死亡螺旋")

    if vol > 200000: s += 1.5; reasons.append("大量")
    elif vol > 50000: s += 0.5

    if liq > 50000: s += 1.5; reasons.append("流動足")
    elif liq > 30000: s += 1
    elif liq < 10000: s -= 2; reasons.append("流動低")

    if br > 70: s += 1.5; reasons.append("買盤強")
    elif br < 40: s -= 1.5; reasons.append("賣壓")

    if h1 > 80 and h24 > 300: s -= 3; reasons.append("拉盤陷阱")

    txns = t.get("txns_24h", 999)
    if txns < 30: s -= 3; reasons.append("筆數少")
    elif txns < 80: s -= 1

    if t.get("gm_wash"): s -= 5; reasons.append("GMGN洗盤")
    smart = t.get("gm_smart", 0)
    if smart >= 5: s += 2; reasons.append(f"聰明錢{smart}")
    elif smart >= 2: s += 1; reasons.append(f"聰明錢{smart}")

    return round(s, 1), reasons

def fetch_tokens():
    """掃描 DexScreener 新幣 + GMGN trending，回傳 tokens list"""
    tokens = []
    seen_addr = set()
    gm = fetch_gmgn()

    # DexScreener token profiles → 批次查詢
    try:
        r = requests.get("https://api.dexscreener.com/token-profiles/latest/v1", timeout=10)
        addrs = []
        for prof in r.json():
            chain = prof.get("chainId", "")
            addr = prof.get("tokenAddress", "")
            if addr and chain == "solana" and addr not in seen_addr:
                addrs.append(addr)
        # 批次查詢（最多30個）
        for i in range(0, min(len(addrs), 60), 30):
            batch = addrs[i:i+30]
            pr = requests.get(
                f"https://api.dexscreener.com/latest/dex/tokens/{','.join(batch)}",
                timeout=10)
            pairs = pr.json().get("pairs", [])
            if not pairs: continue
            # 每個 addr 取流動性最大的 pair
            best = {}
            for p in pairs:
                bt = p.get("baseToken", {})
                a = bt.get("address", "")
                liq = safe_float(p.get("liquidity", {}).get("usd"))
                if liq < 10000: continue
                if a not in best or liq > best[a][0]:
                    best[a] = (liq, p)
            for addr, (liq, p) in best.items():
                try:
                    buys = p.get("txns", {}).get("h24", {}).get("buys", 0)
                    sells = p.get("txns", {}).get("h24", {}).get("sells", 0)
                    vol = safe_float(p.get("volume", {}).get("h24"))
                    txns = buys + sells
                    br = round(buys / txns * 100) if txns else 50
                    g = gm.get(addr, {})
                    bt = p.get("baseToken", {})
                    t = {
                        "address": addr,
                        "symbol": bt.get("symbol", "?"),
                        "name": bt.get("name", ""),
                        "price": safe_float(p.get("priceUsd")),
                        "change_1h": safe_float(p.get("priceChange", {}).get("h1")),
                        "change_24h": safe_float(p.get("priceChange", {}).get("h24")),
                        "volume_24h": round(vol),
                        "liquidity": round(liq),
                        "buy_ratio": br,
                        "txns_24h": txns,
                        "image": (p.get("info", {}) or {}).get("imageUrl", ""),
                        "url": p.get("url", f"https://dexscreener.com/solana/{addr}"),
                        "gm_smart": g.get("smart_degen_count", 0),
                        "gm_wash": g.get("is_wash_trading", False),
                        "pair_created": p.get("pairCreatedAt", 0),
                    }
                    t["score"], t["reasons"] = score_token(t)
                    tokens.append(t)
                    seen_addr.add(addr)
                except: pass
    except Exception as e:
        print(f"[SCAN] dex fail: {e}", flush=True)

    # GMGN trending 補充
    try:
        for addr, g in gm.items():
            if addr in seen_addr: continue
            liq = safe_float(g.get("liquidity"))
            if liq < 10000: continue
            buys = safe_float(g.get("buys")); sells = safe_float(g.get("sells"))
            txns = int(buys + sells)
            br = round(buys / txns * 100) if txns else 50
            vol = safe_float(g.get("volume"))
            t = {
                "address": addr,
                "symbol": g.get("symbol", "?"),
                "name": g.get("name", ""),
                "price": safe_float(g.get("price")),
                "change_1h": safe_float(g.get("price_change_percent1h")),
                "change_24h": safe_float(g.get("price_change_percent")),
                "volume_24h": round(vol),
                "liquidity": round(liq),
                "buy_ratio": br,
                "txns_24h": txns,
                "image": g.get("logo", ""),
                "url": f"https://gmgn.ai/sol/token/{addr}",
                "gm_smart": g.get("smart_degen_count", 0),
                "gm_wash": g.get("is_wash_trading", False),
                "pair_created": 0,
            }
            t["score"], t["reasons"] = score_token(t)
            tokens.append(t)
            seen_addr.add(addr)
    except Exception as e:
        print(f"[SCAN] gmgn fail: {e}", flush=True)

    tokens.sort(key=lambda x: x["score"], reverse=True)
    return tokens

# ============ 模擬交易 ============
def run_sim(tokens, now_ts, now_str, first_seen):
    sim = STATE["sim"]
    token_by_addr = {t["address"]: t for t in tokens if t.get("address")}

    # 清理過期 cooldown
    sim["cooldown"] = {a: exp for a, exp in sim["cooldown"].items() if exp > now_ts}

    # 更新持倉
    for pos in sim["positions"]:
        addr = pos["address"]
        t = token_by_addr.get(addr)
        decimals = pos.get("decimals", 6)

        sell_quote = None
        if t:
            pos["current_price"] = t["price"]
            pos["miss_count"] = 0
        else:
            # 不在榜 → 直接查 DexScreener
            try:
                r = requests.get(
                    f"https://api.dexscreener.com/latest/dex/tokens/{addr}", timeout=5)
                pairs = r.json().get("pairs", [])
                if pairs:
                    best = max(pairs, key=lambda x: safe_float(
                        x.get("liquidity", {}).get("usd")))
                    p = safe_float(best.get("priceUsd"))
                    if p > 0:
                        pos["current_price"] = p
                        pos["miss_count"] = 0
                    else:
                        _handle_miss(pos, now_ts)
                else:
                    _handle_miss(pos, now_ts)
            except:
                _handle_miss(pos, now_ts)

        # Jupiter 賣出報價算市值（decimals 已修正）
        dec = get_token_decimals(addr)
        sq = get_sell_value_usd(addr, pos["tokens"], dec)
        if sq and sq["usd"] > 0:
            pos["current_value"] = sq["usd"]
            pos["sell_impact"] = sq["impact_pct"]
            pos["current_price"] = sq["usd"] / pos["tokens"]
        else:
            pos["current_value"] = pos["tokens"] * pos["current_price"]
        pos["sell_quote_usd"] = round(pos["current_value"], 2)

        # Jupiter 賣出報價已含衝擊，只扣約 0.5% 網路/優先費
        cost = pos["invested"] * 0.005
        pos["pnl"] = pos["current_value"] - pos["invested"] - cost
        pos["pnl_pct"] = round(pos["pnl"] / pos["invested"] * 100, 1)
        pos["peak_pct"] = max(pos.get("peak_pct", pos["pnl_pct"]), pos["pnl_pct"])
        # MFE/MAE tracking
        pos["mfe"] = max(pos.get("mfe", pos["pnl_pct"]), pos["pnl_pct"])
        pos["mae"] = min(pos.get("mae", 0), pos["pnl_pct"])
        log_trajectory(pos, now_ts)
        # 記錄價格走勢（最多30點）
        if "hist" not in pos: pos["hist"] = []
        pos["hist"].append(round(pos["current_price"], 8))
        if len(pos["hist"]) > 30: pos["hist"] = pos["hist"][-30:]

    # 出場判斷
    kept = []
    for pos in sim["positions"]:
        held = now_ts - pos["buy_ts"]
        reason = None

        if pos.get("delisted"):
            reason = "下架無報價"
        elif pos["pnl_pct"] <= SIM_SL_PCT:
            reason = f"停損{pos['pnl_pct']}%"
        elif pos.get("peak_pct", 0) >= 50 and pos["pnl_pct"] < 20:
            reason = f"鎖利{pos['pnl_pct']}%(峰{pos['peak_pct']}%)"
        elif pos.get("peak_pct", 0) >= 15 and pos["pnl_pct"] <= pos["peak_pct"] - 10:
            reason = f"移動停利{pos['pnl_pct']}%(峰{pos['peak_pct']}%)"
        else:
            # 流動性流失
            t = token_by_addr.get(pos["address"])
            if t and pos.get("entry_liq", 0) > 0 and t["liquidity"] < pos["entry_liq"] * 0.6:
                reason = f"流動性流失"
            elif held > SIM_DEAD_SECS and pos["pnl_pct"] < 3:
                reason = f"45分未延續{pos['pnl_pct']}%"
            elif held > SIM_MAX_HOLD:
                reason = f"最長持有{int(held/60)}分"

        if reason:
            sim["cash"] += pos["current_value"]
            sim["trades"].append({
                "time": now_str, "symbol": pos["symbol"],
                "action": "SELL", "address": pos["address"],
                "buy_price": pos["buy_price"],
                "sell_price": pos["current_price"],
                "pnl": round(pos["pnl"], 2),
                "pnl_pct": pos["pnl_pct"],
                "held_min": int(held / 60),
                "buy_score": pos.get("buy_score", 0),
                "buy_impact": pos.get("buy_impact", 0),
                "sell_impact": pos.get("sell_impact", 0),
                "mfe": round(pos.get("mfe", 0), 1),
                "mae": round(pos.get("mae", 0), 1),
                "url": pos.get("url", ""),
                "reason": f"{reason} (最高{pos.get('mfe',0):+.1f}%)",
            })
            # 下架/rug → 永久黑名單；其他出場 → 24小時冷卻
            if "下架" in reason or "rug" in reason.lower() or "流動性流失" in reason:
                if pos["address"] not in sim["blacklist"]:
                    sim["blacklist"].append(pos["address"])
            else:
                sim["cooldown"][pos["address"]] = now_ts + SIM_COOLDOWN
            # 更新熔斷
            if pos["pnl"] < 0:
                CIRCUIT["consecutive_losses"] += 1
                CIRCUIT["day_pnl"] += pos["pnl"]
                if CIRCUIT["consecutive_losses"] >= 5:
                    CIRCUIT["paused_until"] = now_ts + 3600
                    CIRCUIT["consecutive_losses"] = 0
            else:
                CIRCUIT["consecutive_losses"] = 0
                CIRCUIT["day_pnl"] += pos["pnl"]
            if CIRCUIT["day_pnl"] < -150:
                CIRCUIT["paused_until"] = now_ts + 86400
            print(f"[SELL] {pos['symbol']} {reason}", flush=True)
        else:
            kept.append(pos)

    # 進場
    held_addr = {p["address"] for p in kept}
    candidates = []
    rejected = []
    for t in tokens:
        addr = t["address"]
        if not addr: continue
        if addr in held_addr: continue
        if addr in sim["cooldown"] or addr in sim.get("blacklist", []):
            rejected.append((t, "冷卻中/黑名單")); continue
        # 幣齡檢查
        pc = t.get("pair_created", 0)
        if pc > 1e11: age_sec = now_ts - pc / 1000
        elif pc > 0: age_sec = now_ts - pc
        else: age_sec = None
        if age_sec is None:
            if addr not in first_seen: first_seen[addr] = now_ts
            age_sec = now_ts - first_seen[addr]
            if age_sec < 180:
                rejected.append((t, f"幣齡未知{int(age_sec)}s")); continue
        else:
            if age_sec < 180:
                rejected.append((t, f"幣齡{int(age_sec)}s")); continue
            if age_sec > 86400:
                rejected.append((t, f"幣齡過舊{int(age_sec/3600)}h")); continue

        liq = t["liquidity"]
        if liq >= LIQ_TIER1:
            min_score, min_br, max_impact = 5.0, 52, 2.0
        elif liq >= LIQ_TIER2:
            min_score, min_br, max_impact = 5.0, 52, 1.5
        else:
            rejected.append((t, f"流動性${int(liq/1000)}K<$35K")); continue

        if t["score"] < min_score:
            rejected.append((t, f"分數{t['score']}<{min_score}")); continue
        if t["buy_ratio"] < min_br:
            rejected.append((t, f"買盤{t['buy_ratio']}%<{min_br}%")); continue

        # 兩階段確認：連續2次掃描(30秒)都通過才進
        now_cycle = now_ts
        if addr not in PENDING:
            PENDING[addr] = now_cycle
            rejected.append((t, "首次通過，待確認")); continue
        if now_cycle - PENDING[addr] < 15:
            rejected.append((t, "確認中")); continue

        # 熔斷檢查（最前面，省RPC）
        today = time.strftime("%Y-%m-%d")
        if CIRCUIT["day_date"] != today:
            CIRCUIT["day_date"] = today; CIRCUIT["day_pnl"] = 0
        if now_ts < CIRCUIT["paused_until"]:
            rejected.append((t, "熔斷暫停")); continue

        # 鏈上風險檢查
        ok, risk_reason = check_onchain_risk(addr)
        if not ok:
            rejected.append((t, risk_reason)); continue
        # 排名與觸發分離
        triggered, trig_reason = check_trigger(addr, t, now_ts)
        if not triggered:
            rejected.append((t, trig_reason)); continue
        t["_max_impact"] = max_impact
        candidates.append(t)

    candidates.sort(key=lambda x: (x["score"], x["liquidity"]), reverse=True)

    entered_this_cycle = set()   # 本輪實際成交（給 log_decisions 用）
    for t in candidates:
        if len(kept) >= SIM_MAX_POS: break
        buy_usd = min(SIM_BUY_USD, t["liquidity"] * 0.0015)
        if sim["cash"] < buy_usd: break
        addr = t["address"]

        # 部位大小：min($75, 流動性×0.5%)
        buy_usd = min(SIM_BUY_USD, t["liquidity"] * 0.0015)
        # Jupiter 買入報價
        bq = get_buy_quote(addr, buy_usd)
        if not bq:
            t["reject_reason"] = "Jupiter無報價"
            rejected.append((t, "Jupiter無報價"))   # 進場後才失敗 — 也要進日誌
            print(f"[SKIP] {t['symbol']} 無買入報價", flush=True)
            continue
        max_imp = t.get("_max_impact", 2.0)
        if bq["impact_pct"] > max_imp:
            t["reject_reason"] = f"衝擊{bq['impact_pct']}%>{max_imp}%"
            rejected.append((t, t["reject_reason"]))
            print(f"[SKIP] {t['symbol']} 衝擊{bq['impact_pct']}%>{max_imp}%", flush=True)
            continue

        # 用 Jupiter 實際成交價（decimals 已由 Solana RPC 修正）
        eff_price = bq["price_usd"] if bq["price_usd"] > 0 else t["price"]
        tokens_bought = buy_usd / eff_price
        sim["cash"] -= buy_usd
        entered_this_cycle.add(addr)
        kept.append({
            "address": addr,
            "symbol": t["symbol"],
            "buy_price": eff_price,
            "current_price": eff_price,
            "buy_ts": now_ts,
            "buy_time": now_str,
            "invested": round(buy_usd, 2),
            "tokens": tokens_bought,
            "decimals": bq["decimals"],
            "buy_score": t["score"],
            "entry_liq": t["liquidity"],
            "buy_impact": bq["impact_pct"],
            "jup_buy_price": bq["price_usd"],
            "url": t.get("url", ""),
            "image": t.get("image", ""),
            "miss_count": 0,
            "peak_pct": 0,  # set on first update
        })
        sim["trades"].append({
            "time": now_str, "symbol": t["symbol"],
            "action": "BUY", "address": addr,
            "buy_price": eff_price, "sell_price": 0,
            "pnl": 0, "pnl_pct": 0,
            "buy_impact": bq["impact_pct"],
            "jup_buy_price": bq["price_usd"],
            "url": t.get("url", ""),
            "reason": f"score={t['score']} 衝擊{bq['impact_pct']}% [Jup原始${bq['price_usd']:.6f}]",
        })
        print(f"[BUY] {t['symbol']} score={t['score']} impact={bq['impact_pct']}%", flush=True)

    sim["positions"] = kept
    sim["rejected"] = [{"symbol": t["symbol"], "address": t["address"], "reason": r,
                        "score": t["score"], "liq": t["liquidity"], "buy": t["buy_ratio"]}
                       for t, r in rejected[:20]]

    # 統計
    sells = [t for t in sim["trades"] if t["action"] == "SELL"]
    wins = [t for t in sells if t["pnl"] > 0]
    losses = [t for t in sells if t["pnl"] <= 0]
    total_value = sum(p["current_value"] for p in kept)
    sim["stats"] = {
        "wins": len(wins), "losses": len(losses),
        "win_amount": round(sum(t["pnl"] for t in wins), 2),
        "loss_amount": round(sum(t["pnl"] for t in losses), 2),
        "total_sells": len(sells),
        "total_value": round(total_value, 2),
        "total_invested": round(sum(p["invested"] for p in kept), 2),
        "total_pnl": round(total_value + sim["cash"] - SIM_CAPITAL, 2),
    }
    # 前端讀頂層
    bought_addrs = set(t["address"] for t in sim["trades"] if t["action"] == "BUY")
    sim["unique_bought"] = len(bought_addrs)
    sim["total_invested"] = round(sum(p["invested"] for p in kept), 2)
    sim["total_value"] = round(total_value, 2)
    sim["capital"] = SIM_CAPITAL
    log_decisions(tokens, sim, rejected, now_ts, entered_this_cycle)

def _handle_miss(pos, now_ts):
    held = now_ts - pos.get("buy_ts", now_ts)
    if held > 300:  # 5 分鐘寬限
        pos["miss_count"] = pos.get("miss_count", 0) + 1
        if pos["miss_count"] >= 8:
            pos["delisted"] = True

# ============ 背景迴圈 ============
def scan_cycle():
    try:
        now_ts = time.time()
        tokens = fetch_tokens()
        update_trigger_history(tokens, now_ts)
        now_str = datetime.now(UTC8).strftime("%m-%d %H:%M")
        first_seen = load_first_seen()
        run_sim(tokens, now_ts, now_str, first_seen)
        save_first_seen(first_seen)
        save_sim(STATE["sim"])
        STATE["tokens"] = tokens[:25]
        STATE["scanned_at"] = datetime.now(UTC8).strftime("%H:%M:%S")
    except Exception as e:
        import traceback
        print(f"[BG] error: {e}\n{traceback.format_exc()}", flush=True)

def bg_loop():
    get_sol_price()
    sol_counter = 0
    while True:
        try:
            with LOCK:
                scan_cycle()
        except Exception as e:
            print(f"[BG] error: {e}", flush=True)
        time.sleep(SCAN_INTERVAL)

# ============ Routes ============
@app.route("/api/dex")
def api_dex():
    with LOCK:
        return jsonify({
            "scanned_at": STATE["scanned_at"],
            "tokens": STATE["tokens"],
            "portfolio": {
                "positions": [], "trades": [], "cash": 0,
            },
            "sim_portfolio": STATE["sim"],
            "delisted": [],
        })

@app.route("/app.js")
def app_js():
    return send_file("app.js", mimetype="application/javascript")

@app.route("/")
def index():
    with open("dashboard.html", "r", encoding="utf-8") as f:
        return Response(f.read(), mimetype="text/html")

@app.route("/api/clear_sim", methods=["POST"])
def clear_sim():
    with LOCK:
        STATE["sim"] = {"cash": SIM_CAPITAL, "positions": [], "trades": [],
                        "cooldown": {}, "blacklist": []}
        save_sim(STATE["sim"])
    return jsonify({"ok": True})

@app.route("/api/sell/<address>", methods=["POST"])
def sell_one(address):
    with LOCK:
        sim = STATE["sim"]
        now_ts = time.time()
        now_str = datetime.now(UTC8).strftime("%m-%d %H:%M")
        kept = []
        for pos in sim["positions"]:
            if pos["address"] == address:
                sim["cash"] += pos["current_value"]
                sim["trades"].append({
                    "time": now_str, "symbol": pos["symbol"],
                    "action": "SELL", "address": address,
                    "buy_price": pos["buy_price"],
                    "sell_price": pos["current_price"],
                    "pnl": round(pos["pnl"], 2),
                    "pnl_pct": pos["pnl_pct"],
                    "held_min": int((now_ts - pos["buy_ts"])/60),
                    "url": pos.get("url", ""),
                    "reason": "手動賣出" + (f" [買衝擊{pos.get('buy_impact',0)}%]" if pos.get('buy_impact') else ""),
                })
                sim["cooldown"][address] = now_ts + SIM_COOLDOWN
                print(f"[MANUAL SELL] {pos['symbol']} {pos['pnl_pct']}%", flush=True)
            else:
                kept.append(pos)
        sim["positions"] = kept
        save_sim(sim)
    return jsonify({"ok": True})

# ============ 啟動 ============
if __name__ == "__main__":
    STATE["sim"] = load_sim()
    load_circuit(STATE["sim"])
    t = threading.Thread(target=bg_loop, daemon=True)
    t.start()
    print("V3.1 background scanner started", flush=True)
    port = int(os.environ.get("PORT", 8080))
    app.run(host="127.0.0.1", port=port, debug=False, threaded=True)
