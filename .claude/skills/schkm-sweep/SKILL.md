---
name: schkm-sweep
description: 執行 SCHKM（渣打香港馬拉松）輿情掃描，抓取 Threads / Instagram / Facebook 上關於渣馬一日定兩日、名額、抽籤、封路等討論，輸出 diff 報告供人手核對。用於恆常更新 Neutralization deck 嘅 annex。當用戶提到「渣馬掃描」「schkm sweep」「更新輿情」「跑一次監察」時使用。
---

# SCHKM 輿情掃描

## 用途

抓取渣打香港馬拉松「一日 vs 兩日」議題嘅社交輿情，出 diff 報告。**唔會自動更新 deck** —— 報告要人手核對，之後行 `schkm-apply` 先入 deck。

## 前置：API keys

需要兩個環境變數：

```bash
export TIKHUB_API_KEY=...   # Threads/IG 抽帖文+留言
export APIFY_TOKEN=...      # Threads 關鍵詞搜尋（TikHub 搜尋端點壞咗）
```

如果未設定，script 會報錯並提示。查 `monitoring/README.md` 有 key 嘅存放建議。

## 執行

```bash
cd <repo root>

# 全渠道深掃（建議每 7 日；報名季每 3 日）
python3 monitoring/sweep.py

# 輕掃（每日，只行 Threads recent 搜尋，成本 ~$0.3）
python3 monitoring/sweep.py --light

# 快速試跑（唔抽留言、唔寫入資料庫）
python3 monitoring/sweep.py --light --no-comments --dry-run
```

跑完會喺 `monitoring/reports/run_YYYYMMDD_HHMM.md` 出報告。

## 讀報告時要留意

按呢個次序睇：

1. **⚠️ 渠道健康警報** —— 最重要。「靜」唔等於「冇嘢」；如果某渠道 fail，本次覆蓋唔完整，要重跑或標記
2. **議題標籤分佈** —— `other` 標籤數量突升＝可能有新議題，要人手睇係咪要開新 deck row
3. **本次新帖清單** —— 逐條核對連結、分類、留言樣本
4. **人手核對清單** —— 逐項剔

## 跟進動作

核對完之後：

- 分類錯 → 直接改 `monitoring/data/master.json` 該條目嘅 `issue_labels_confirmed` / `review_status`
- 你 eyeball 見到但系統漏咗 → 用 `schkm-add` skill 補入，並喺報告記低（呢啲 miss 係調整關鍵詞/watchlist 嘅根據）
- 確認無誤 → 行 `schkm-apply` 生成 annex pptx

## 加減監察範圍

改 `monitoring/config.json`（唔使改 code）：

- `threads_search.keywords` —— 搜尋關鍵詞
- `watchlist_threads` / `watchlist_instagram` —— 監察帳號（系統會自動雪球擴張，學到嘅存喺 `data/watchlist_learned.json`）
- `facebook_pages` —— FB 專頁
- `noise_filters` —— 噪音過濾詞

改完必須行 `python3 monitoring/backtest.py` 確認冇錯殺已知重要內容。

## 已知限制（老實講）

- **Threads 搜尋只能回溯約 30 日**（平台限制）—— 所以要恆常運行，開機之前嘅歷史帖追唔返
- **Threads 留言只攞到第一頁** —— 報告會標「帖面回覆數 vs 實抽留言數」
- **LIHKG / HKDiscuss 反爬** —— 只做發現（site: 搜尋），內容要人手開，報告有清單
- **FB 私人群組、IG 私人帳號** 爬唔到
- TikHub 端點間歇性 flaky，已有 retry；若過半帳號失敗，報告會出警報
