---
name: schkm-add
description: 將人手發現（eyeball 見到）但 crawler 漏咗嘅社交帖連結補入 SCHKM 監察資料庫，並自動抽取留言。當用戶貼出渣馬相關嘅 Threads/IG/FB 連結、或講「呢條你冇執到」「加呢條入去」時使用。
---

# SCHKM 人手補漏

## 用途

Crawler 一定有漏（尤其 Threads 30 日窗口以外嘅舊帖）。呢個 skill 令人手發現嘅嘢 30 秒入庫，並且**記錄低係人手補入**，方便統計 crawler 嘅 miss 率同調整方向。

## 執行

```bash
export TIKHUB_API_KEY=...

python3 monitoring/add_link.py "https://www.threads.com/@user/post/XXXX"

# 多條一次過
python3 monitoring/add_link.py "url1" "url2" "url3"

# 加註解（記低點解要人手補，日後分析用）
python3 monitoring/add_link.py "url" --note "1月舊帖，超出搜尋窗口"

# 唔抽留言（快）
python3 monitoring/add_link.py "url" --no-comments
```

## 自動做嘅嘢

- 判別平台（threads / instagram / facebook / lihkg / hkdiscuss）
- Threads / IG：自動抽帖文全文 + 留言（連 handle）—— 需要 `TIKHUB_API_KEY`
- FB（專頁帖 + **公開** group 帖）：自動抽留言 —— 需要 `APIFY_TOKEN`；closed group 冇 API 途徑，會警告叫你人手處理
- 打議題標籤、判斷相關度
- **作者自動加入 watchlist** —— 下次掃描會覆蓋佢
- 標記 `review_status = approved`（人手加入視為已核實）
- 標記 `source_channel = human-add`（miss 率統計用）

## 用完之後

如果人手補入累積到 5 條以上，script 會提示檢視 `monitoring/config.json`：

- 呢啲 miss 有冇共通關鍵詞？→ 加入 `threads_search.keywords`
- 係咪同一批帳號？→ 加入 `watchlist_threads`
- 改完 config **必須行 `python3 monitoring/backtest.py`** 確認冇錯殺

## 點解要記錄 miss

呢個係系統改善嘅唯一根據。每次你哋 eyeball 贏過 crawler，都應該問：

1. 係窗口問題（帖太舊）→ 冇得救，正常，繼續人手補
2. 係關鍵詞問題（用詞冇覆蓋）→ 加詞
3. 係帳號問題（新帳號未入 watchlist）→ 加帳號（或者等雪球自動學到）
4. 係過濾器錯殺 → **最嚴重**，要即刻加入 `backtest.py` 嘅 MUST_KEEP 並修 `classify.py`
