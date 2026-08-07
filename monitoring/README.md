# SCHKM 輿情監察系統

渣打香港馬拉松「一日 vs 兩日」議題嘅社交輿情自動監察，用於恆常更新 Neutralization deck 嘅 annex。

## 設計原則

**唔追歷史，只保證向前唔漏。** Threads 搜尋只能回溯約 30 日（平台限制），所以：
- 「開機之前」嘅歷史帖 → 靠 `seed.py` 一次過封存（deck annex 12 條 + 已核實 20 條）
- 「開機之後」嘅嘢 → 靠每 7 日運行，30 日窗口 ÷ 4 倍安全系數，數學上冚得住

**冇嘢自動入 deck。** sweep 出報告 → 人手核對 → apply 先生成 pptx。

## 快速開始

```bash
# 1. 設定 API keys
export TIKHUB_API_KEY=...
export APIFY_TOKEN=...

# 2. 首次：種子入庫（只需一次）
python3 monitoring/seed.py

# 3. 掃描
python3 monitoring/sweep.py              # 全渠道深掃
python3 monitoring/sweep.py --light      # 輕掃（每日用）

# 4. 人手核對 monitoring/reports/run_*.md

# 5. 生成 annex pptx
python3 monitoring/apply_deck.py --approve-run <run_id>
```

## 檔案結構

```
monitoring/
├── config.json           ← 關鍵詞/帳號/專頁/過濾詞（改呢個，唔使改 code）
├── sweep.py              ← L1發現 + L2抽取 + L3分類 + L4報告
├── apply_deck.py         ← L5 生成 annex pptx
├── seed.py               ← 種子入庫（歷史基線）
├── add_link.py           ← 人手補漏
├── backtest.py           ← 回歸測試（改 config 後必跑）
├── lib/
│   ├── clients.py        ← TikHub / Apify 客戶端（含 retry）
│   ├── store.py          ← master.json 讀寫、URL 正規化、diff
│   └── classify.py       ← 噪音過濾、議題標籤、發言人分類
├── data/
│   ├── master.json       ← 唯一真相來源（git 追蹤，有版本史）
│   ├── watchlist_learned.json  ← 雪球學到嘅帳號
│   └── raw/<run_id>/     ← 原始 API 回應（審計用）
├── reports/run_*.md      ← 每次掃描嘅 diff 報告
└── out/                  ← 生成嘅 pptx
```

## 八條補漏機制

單靠關鍵詞搜尋一定漏，所以內建：

1. **雪球名單** —— 新相關帖作者自動入 watchlist
2. **引用鏈** —— `quoted_post_url` / `reposted_post_url` 自動變候選
3. **回訪** —— 已知帖 re-poll 留言增量
4. **帳號時間軸** —— 補搜尋窗口盲點（發帖疏嘅帳號單頁可翻幾個月）
5. **IG hashtag** —— 獨立於 Threads 嘅發現渠道
6. **渠道健康警報** —— 某渠道回 0 或 fail 會標紅，「靜」唔會被當「冇嘢」
7. **人手回路** —— `add_link.py` 30 秒補入，並統計 miss 率
8. **反爬平台發現** —— LIHKG/HKDiscuss 出 site: 搜尋清單畀人手開

## API keys 存放

**唔好 commit 入 repo。** 三個選擇（由好到差）：

1. 環境變數（建議）：加入 `~/.bashrc` 或 CI secrets
2. 本地 `.env`（已喺 `.gitignore`）：`source monitoring/.env`
3. 每次執行時 export

## 成本

| 模式 | 每次 | 頻率建議 |
|---|---|---|
| `--light` | ~$0.3-0.5 | 每日（報名季） |
| 全掃 | ~$1.5-2.5 | 每 7 日（報名季每 3 日） |

平季月費 ~$6-10；報名季混合制 ~$15-25。

## 驗收標準

`python3 monitoring/backtest.py` —— 18 項回歸測試：
- 11 項「必須保留」（deck annex 真實內文 + 6 gap 關鍵留言）
- 7 項「必須剔走」（台灣賽事、銀行產品、賽馬等噪音）

**改 config.json 之後必須重跑**，確保冇錯殺。

## 已知限制

| 限制 | 影響 | 應對 |
|---|---|---|
| Threads 搜尋回溯 ~30 日 | 開機前歷史帖追唔返 | seed.py 封存 + add_link.py 補 |
| Threads 留言只得第一頁 | 帖面 35 回覆可能只抽到 23 | 報告標明兩個數 |
| LIHKG / HKDiscuss 反爬 | 內容爬唔到 | 只做發現，人手開 |
| FB 私人群組 / IG 私人帳號 | 爬唔到 | 維持人手 |
| TikHub 端點 flaky | 部分帳號抽取失敗 | retry + 健康警報 |
