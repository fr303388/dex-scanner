"""迷因幣策略 — 決策日誌分析器

用法（在 dex-scanner 資料夾內執行）：
    python analyze.py                # 全部報告
    python analyze.py --horizon 30   # 指定前瞻分鐘數
    python analyze.py --min-n 10     # 低於此樣本數的分群標為「不足」

輸出：主控台摘要 + 報告檔案 analysis_report.md

設計原則（針對迷因幣的肥尾分佈）：
  1. 一律用「中位數」而非平均數 —— 這個宇宙的平均值由少數 10 倍幣主導
  2. 分群一律與「無條件基準」比較，而非與 0 比較 —— 否則上漲行情會讓
     每個分群都看起來顯著
  3. 樣本數不足時明說「不足」，不給出看起來像結論的數字
  4. 抽樣不重疊 —— 同一地址每 HORIZON 內只取一點，降低自相關
"""
import csv, json, os, sys, collections, statistics
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
DECISIONS = os.path.join(HERE, "decisions.csv")
PORTFOLIO = os.path.join(HERE, "sim_portfolio.json")
OUT_MD = os.path.join(HERE, "analysis_report.md")

HORIZON_MIN = 15
MIN_N = 8
SINCE = 0          # 0 = 用全部資料；可填 epoch 秒數只看某個時間點之後

L = []             # 報告輸出的行


def out(s=""):
    print(s)
    L.append(s)


def fwd_stats(vals):
    v = sorted(vals)
    n = len(v)
    med = v[n // 2]
    win = 100.0 * sum(1 for x in v if x > 0) / n
    return n, med, win


# ---------- 載入 ----------
def load():
    if not os.path.exists(DECISIONS):
        sys.exit("找不到 decisions.csv —— 請在 dex-scanner 資料夾內執行")
    rows = list(csv.DictReader(open(DECISIONS, encoding="utf-8")))
    rows = [r for r in rows if SINCE == 0 or int(r["ts"]) >= SINCE]
    # 過濾不合理的時間戳（例如測試殘留的 ts=1），否則會讓觀察窗算成天文數字
    rows = [r for r in rows if 1_500_000_000 < int(r["ts"]) < 4_000_000_000]
    rows.sort(key=lambda r: int(r["ts"]))
    if not rows:
        sys.exit("沒有可用資料列")

    series = collections.defaultdict(list)
    for r in rows:
        try:
            series[r["address"]].append({
                "ts": int(r["ts"]), "px": float(r["price"]),
                "score": float(r["score"]), "liq": float(r["liquidity"]),
                "buy": float(r["buy_ratio"]), "h1": float(r["h1"]),
                "h24": float(r["h24"]), "vol": float(r["volume"]),
                "sym": r["symbol"], "dec": r["decision"], "reason": r["reason"],
            })
        except (ValueError, KeyError):
            pass
    return rows, series


# ---------- 抽樣：非重疊前瞻報酬 ----------
def build_samples(series, horizon_sec):
    def px_after(addr, t):
        for p in series[addr]:
            if p["ts"] >= t:
                return p
        return None

    samples, last = [], {}
    for addr, v in series.items():
        for p in v:
            if addr in last and p["ts"] - last[addr] < horizon_sec:
                continue
            f = px_after(addr, p["ts"] + horizon_sec)
            if not f or f["ts"] > p["ts"] + horizon_sec + 300:
                continue
            samples.append({
                "addr": addr, "sym": p["sym"], "dec": p["dec"],
                "fwd": (f["px"] / p["px"] - 1) * 100,
                "score": p["score"], "liq": p["liq"], "buy": p["buy"],
                "h1": p["h1"], "vol": p["vol"],
            })
            last[addr] = p["ts"]
    return samples


# ---------- 報告主體 ----------
def report(rows, series, samples, portfolio):
    span = (int(rows[-1]["ts"]) - int(rows[0]["ts"])) / 60.0
    out("# 迷因幣策略 — 決策日誌分析報告")
    out()
    out("產生時間：%s" % datetime.now().strftime("%Y-%m-%d %H:%M"))
    out("資料來源：decisions.csv（%d 列）／sim_portfolio.json" % len(rows))
    out("前瞻窗口：+%d 分鐘　最小樣本門檻：n >= %d" % (HORIZON_MIN, MIN_N))
    out()
    out("---")
    out()

    # ===== 1. 基準 =====
    out("## 1. 無條件基準（這段期間的市場水位）")
    out()
    if not samples:
        out("樣本不足，還無法計算前瞻報酬。需要累積更多時間。")
        out()
    else:
        n, med, win = fwd_stats([s["fwd"] for s in samples])
        sd = statistics.pstdev([s["fwd"] for s in samples])
        out("| 項目 | 值 |")
        out("|---|---|")
        out("| 觀察窗 | %.0f 分鐘 |" % span)
        out("| 唯一地址 | %d |" % len(series))
        out("| 非重疊抽樣點 | %d |" % n)
        out("| **中位前瞻報酬** | **%+.2f%%** |" % med)
        out("| 平均前瞻報酬 | %+.2f%% |" % (sum(s["fwd"] for s in samples) / n))
        out("| 標準差 | %.1f%% |" % sd)
        out("| 勝率 | %.0f%% |" % win)
        out()
        if sd > 30:
            out("> ⚠️ 標準差 %.0f%% — 這是極高波動的宇宙。任何分群的差異都必須"
                "遠大於這個數量級才值得相信。" % sd)
            out()

        base_med = med

        # ===== 2. 分群 =====
        def table(title, groups, key_desc):
            out("## %s" % title)
            out()
            out("| %s | n | 中位前瞻 | 勝率 | 超額(vs 基準) | 判讀 |" % key_desc)
            out("|---|---|---|---|---|---|")
            for name, pred in groups:
                grp = [s for s in samples if pred(s)]
                if len(grp) < 3:
                    out("| %s | %d | — | — | — | ★ 樣本不足 |" % (name, len(grp)))
                    continue
                gn, gmed, gwin = fwd_stats([s["fwd"] for s in grp])
                exc = gmed - base_med
                if gn < MIN_N:
                    verdict = "★ 樣本不足"
                elif abs(exc) >= 15:
                    verdict = "差異明顯，值得追蹤"
                elif abs(exc) >= 5:
                    verdict = "略有意義，繼續累積"
                else:
                    verdict = "與基準無明顯差異"
                out("| %s | %d | %+.2f%% | %.0f%% | %+.2f%% | %s |"
                    % (name, gn, gmed, gwin, exc, verdict))
            out()

        out("## 2. 分群前瞻報酬 vs 基準")
        out()
        out("**「超額」= 該群中位數 − 基準中位數。** 與 0 比會被行情方向污染。")
        out()

        table("2.1 評分門檻（直接回答「放寬評分有沒有用」）", [
            ("score >= 8", lambda s: s["score"] >= 8),
            ("score 6~8　（可進場）", lambda s: 6 <= s["score"] < 8),
            ("score 5~6　（可進場）", lambda s: 5 <= s["score"] < 6),
            ("score 4~5　（被擋）", lambda s: 4 <= s["score"] < 5),
            ("score 3~4　（被擋）", lambda s: 3 <= s["score"] < 4),
            ("score < 3　　（被擋）", lambda s: s["score"] < 3),
        ], "分數區間")

        table("2.2 流動性門檻", [
            ("liq >= 75k　（大池）", lambda s: s["liq"] >= 75000),
            ("liq 35k~75k（小池）", lambda s: 35000 <= s["liq"] < 75000),
            ("liq 20k~35k（被擋）", lambda s: 20000 <= s["liq"] < 35000),
            ("liq < 20k　 （被擋）", lambda s: s["liq"] < 20000),
        ], "流動性區間")

        table("2.3 買盤比門檻", [
            ("buy >= 60%", lambda s: s["buy"] >= 60),
            ("buy 52~60%　（可進場）", lambda s: 52 <= s["buy"] < 60),
            ("buy 45~52%　（被擋）", lambda s: 45 <= s["buy"] < 52),
            ("buy < 45%　 （被擋）", lambda s: s["buy"] < 45),
        ], "買盤比區間")

        table("2.4 1h 漲幅（檢驗「追高扣分」有沒有道理）", [
            ("h1 > 50%（被判追高扣分）", lambda s: s["h1"] > 50),
            ("h1 10~50%", lambda s: 10 <= s["h1"] <= 50),
            ("h1 < 10%（沒加分）", lambda s: s["h1"] < 10),
        ], "1h 漲幅區間")

        table("2.5 量能（絕對值門檻的對照）", [
            ("vol >= 200k", lambda s: s["vol"] >= 200000),
            ("vol 50k~200k", lambda s: 50000 <= s["vol"] < 200000),
            ("vol < 50k", lambda s: s["vol"] < 50000),
        ], "量能區間")

    # ===== 3. 進場漏斗 =====
    out("## 3. 進場漏斗")
    out()
    c = collections.Counter(r["decision"] for r in rows)
    for k, v in c.most_common():
        out("- %s：%d 列" % (k, v))
    out()
    rc = collections.Counter()
    for r in rows:
        x = r["reason"]
        if not x:
            continue
        for name, pat in [("幣齡過舊", "過舊"), ("幣齡未知(退回觀察)", "幣齡未知"),
                          ("幣齡太新", "幣齡"), ("流動性不足", "流動性"),
                          ("分數不足", "分數"), ("買盤不足", "買盤"),
                          ("PENDING 兩階段", "確認"), ("觸發未放行", "觸發"),
                          ("冷卻中", "冷卻"), ("熔斷暫停", "熔斷"),
                          ("Jupiter 無報價", "Jupiter"), ("出場衝擊過高", "衝擊")]:
            if pat in x:
                rc[name] += 1
                break
        else:
            rc["其他"] += 1
    if rc:
        out("| 淘汰原因 | 列數 | 佔比 |")
        out("|---|---|---|")
        for k, v in rc.most_common():
            out("| %s | %d | %.1f%% |" % (k, v, 100.0 * v / len(rows)))
    out()

    # ===== 4. 已平倉交易 / 出場規則診斷 =====
    out("## 4. 已平倉交易與出場規則診斷")
    out()
    if not portfolio:
        out("讀不到 sim_portfolio.json")
        out()
    else:
        sells = [t for t in portfolio.get("trades", []) if t.get("action") == "SELL"]
        st = portfolio.get("stats", {})
        out("- 現金：$%.2f　部位：%d　總交易：%d　已平倉：%d"
            % (portfolio.get("cash", 0), len(portfolio.get("positions", [])),
               len(portfolio.get("trades", [])), len(sells)))
        out("- 勝 %d / 負 %d　累計損益 $%.2f"
            % (st.get("wins", 0), st.get("losses", 0), st.get("total_pnl", 0)))
        out()
        if not sells:
            out("尚無已平倉交易 —— 出場規則還沒有樣本可用來校準。")
            out()
        else:
            out("| 時間 | 幣 | 入場分數 | 持有(分) | MFE | MAE | 出場 | 損益% | **回吐** |")
            out("|---|---|---|---|---|---|---|---|---|")
            givebacks = []
            reasons = collections.Counter()
            for t in sells:
                mfe = t.get("mfe")
                pnl = t.get("pnl_pct")
                gb = (float(mfe) - float(pnl)) if (mfe is not None and pnl is not None) else None
                if gb is not None:
                    givebacks.append(gb)
                r = t.get("reason", "")
                reasons[r.split("-")[0] if r else "?"] += 1
                out("| %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
                    t.get("time", ""), t.get("symbol", ""), t.get("buy_score", "-"),
                    t.get("held_min", "-"),
                    ("%+.1f%%" % mfe) if mfe is not None else "-",
                    ("%+.1f%%" % t.get("mae")) if t.get("mae") is not None else "-",
                    r, pnl,
                    ("%+.1fpp" % gb) if gb is not None else "-"))
            out()
            if givebacks:
                n, med, _ = fwd_stats(givebacks)
                out("**回吐統計（每筆：MFE − 實際出場%）**")
                out()
                out("- 樣本 %d 筆，中位回吐 **%.1f 個百分點**，最大 %.1fpp"
                    % (n, med, max(givebacks)))
                wasted = [g for g in givebacks if g >= 15]
                if wasted:
                    out("- 有 **%d 筆曾經浮盈 ≥15pp 卻回吐 ≥15pp**" % len(wasted))
                    out()
                    out("> 🔴 這是移動停利門檻過高造成的：規則要 `peak >= 30%` 才啟動，")
                    out("> 所以在 +15% ~ +30% 區間見頂的部位完全沒有保護，")
                    out("> 會一路持有到 −12% 停損。")
                    out()
                out("- 出場原因佔比：" + "　".join("%s %d" % (k, v) for k, v in reasons.most_common()))
                out()
                out("> **校準建議**：把移動停利啟動門檻降到 +15%，並改用波動率相對的回撤")
                out("> （用持倉的 `hist` 算 ATR 或滾動分位數），不要用固定百分點。")
                out("> 有了 %d 筆以上樣本後再看這裡的數字調整。" % (2 * MIN_N))
                out()

    out("---")
    out()
    out("## 如何解讀這份報告")
    out()
    out("1. **看超額，不看絕對值。** 行情本身可能整體往上，所有分群都會看起來很好。")
    out("2. **樣本不足就別信。** 這份報告會明確標示 `★ 樣本不足` 的分群 ——")
    out("   那些格子裡的數字不構成證據。")
    out("3. **中位數，不是平均數。** 這個宇宙肥尾極重，平均值會被少數暴漲幣帶偏。")
    out("4. **一次只改一個參數。** 同時改兩三個，之後就分不清是哪個生效。")


def main():
    global HORIZON_MIN, MIN_N, SINCE
    for i, a in enumerate(sys.argv):
        if a == "--horizon" and i + 1 < len(sys.argv):
            HORIZON_MIN = int(sys.argv[i + 1])
        if a == "--min-n" and i + 1 < len(sys.argv):
            MIN_N = int(sys.argv[i + 1])
        if a == "--since" and i + 1 < len(sys.argv):
            SINCE = int(sys.argv[i + 1])

    rows, series = load()
    samples = build_samples(series, HORIZON_MIN * 60)
    portfolio = None
    if os.path.exists(PORTFOLIO):
        try:
            portfolio = json.load(open(PORTFOLIO, encoding="utf-8"))
        except Exception:
            portfolio = None
    report(rows, series, samples, portfolio)

    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    print()
    print("報告已寫入：%s" % OUT_MD)


if __name__ == "__main__":
    main()
