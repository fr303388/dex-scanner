# 迷因幣雷達 (dex_scanner)

Solana 迷因幣自動掃描與模擬交易系統。

## 啟動方式

```powershell
cd dex_scanner
C:\Users\ANGEL\AppData\Local\Programs\Python\Python312\python.exe -u server.py
```

瀏覽器開啟 http://127.0.0.1:8770/

## 當前交易規則（模擬）

| 項目 | 設定 |
|---|---|
| 本金 | $1,000 |
| 每筆投入 | $100 |
| 最大持倉 | 10 |
| 買入門檻 | score ≥ 4.0 |
| 加碼 | score ≥ 6 時 1.5 倍 |
| 最低流動性 | > $50,000 |
| 上線時間 | > 15 分鐘才買 |
| 買盤比例 | ≥ 45% |
| 1h 漲幅 | > 40% 不買（追高風險） |
| 停利 | +25% |
| 停損 | -8% |
| 虧損後冷卻 | 30 分鐘（同一幣） |
| 獲利後冷卻 | 立即解除 |
| 死幣不動 | 5 分鐘且 |pnl| < 2% 賣出 |
| 最長持有 | 1.5 小時 |
| 下架判定 | 連續 3 次掃描不到才賣 |
| 永久黑名單 | DEBT/SOL |
| 虧損 >20% | 自動加入黑名單 |

## 評分規則

- +2 1h 漲 >30%（強勢）· +1 1h 漲 10-30%
- +2 24h 漲 10-50%（健康）· +1 50-150% · -1 >200%（高位）
- +1.5 交易量 >$200K · +0.5 >$50K
- +1.5 流動性 >$50K · +1 >$30K · -2 <$10K · -3 <$5K
- +1.5 買盤 >70% · -1.5 買盤 <40%
- +3 買家 <10 人（刷單）· -1 買家 <30 人
- -2 量/流動 >5（洗盤）· -3 1h>80% 且 24h>300%（拉盤陷阱）
- -3 交易 <30 筆 · -1 <80 筆 · -2 大戶對敲
- score ≥7 額外扣 1.5 分（追高風險）

## 檔案說明

- `server.py` — 主伺服器（Flask）
- `dashboard.html` — 前端頁面
- `app.js` — 前端邏輯（15 秒輪詢）
- `sim_portfolio.json` — 模擬組合（$1000 本金）
- `portfolio.json` — 正式交易組合
- `notify_pref.json` — Telegram 通知開關
- `privkey.json` — Solana 錢包私鑰
- `seen_tokens.json` — 已見過的幣（避免重複通知）
- `delisted_history.json` — 已下架幣種歷史

## API

- `GET /api/dex` — 所有資料
- `POST /api/toggle_trading` — 開關正式交易
- `POST /api/save_trade_amount` — 設定每筆金額
- `POST /api/save_privkey` — 儲存錢包
- `POST /api/toggle_notify` — 切換 Telegram 通知
- `POST /api/clear_delisted` — 清除下架列表
