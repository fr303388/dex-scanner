"""DEX 熱門代幣掃描器（獨立運行，不影響 stonkfly）"""
import requests, json, time
from datetime import datetime, timezone, timedelta

UTC8 = timezone(timedelta(hours=8))

def scan_trending():
    """從 DexScreener 抓取熱門代幣"""
    # 1. 最新代幣檔案
    profiles = requests.get("https://api.dexscreener.com/token-profiles/latest/v1", timeout=10).json()
    
    # 2. 熱門搜索
    search = requests.get("https://api.dexscreener.com/latest/dex/search?q=trending", timeout=10).json()
    pairs = search.get("pairs", [])
    
    results = []
    seen = set()
    for p in pairs:
        base = p.get("baseToken", {}).get("symbol", "?")
        quote = p.get("quoteToken", {}).get("symbol", "?")
        sym = f"{base}/{quote}"
        if sym in seen: continue
        seen.add(sym)
        
        try: price = float(p.get("priceUsd", 0) or 0)
        except: price = 0.0
        try: h24 = float(p.get("priceChange", {}).get("h24", 0) or 0)
        except: h24 = 0.0
        try: vol = float(p.get("volume", {}).get("h24", 0) or 0)
        except: vol = 0.0
        try: liq = float(p.get("liquidity", {}).get("usd", 0) or 0)
        except: liq = 0.0
        chain = p.get("chainId", "?")
        dex = p.get("dexId", "?")
        url = p.get("url", "")
        
        results.append({
            "symbol": sym,
            "price": price,
            "change_24h": round(h24, 1),
            "volume_24h": round(vol, 0),
            "liquidity": round(liq, 0),
            "chain": chain,
            "dex": dex,
            "url": url,
            "signal": "🔥噴發" if h24 > 50 else "📈上漲" if h24 > 10 else "📉下跌" if h24 < -10 else "😐震盪"
        })
    
    # 按成交量排序
    results.sort(key=lambda x: x["volume_24h"], reverse=True)
    
    return {
        "scanned_at": datetime.now(UTC8).strftime("%Y-%m-%d %H:%M:%S"),
        "total": len(results),
        "tokens": results[:15]
    }

if __name__ == "__main__":
    print("=== DEX 熱門代幣掃描 ===")
    data = scan_trending()
    print(f"時間: {data['scanned_at']} | 共 {data['total']} 個交易對\n")
    for i, t in enumerate(data["tokens"], 1):
        price_str = f"${t['price']:.8f}" if t['price'] < 0.01 else f"${t['price']:.4f}"
        print(f"#{i:2d} {t['symbol']:20s} {price_str:15s} 24h:{t['change_24h']:+.1f}%  量:${t['volume_24h']:,.0f}  流動:${t['liquidity']:,.0f}  {t['signal']}")
    
    with open("dex_result.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"\n已儲存到 dex_result.json")
