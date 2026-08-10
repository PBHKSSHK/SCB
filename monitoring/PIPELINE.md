# SCHKM 輿情 Pipeline 全紀錄（rules / crawling / 平台 / API）

> 截至 2026-08-10。呢份係「實際做緊乜」嘅權威紀錄——同 code 有出入以 code 為準，發現出入請更新呢份。
> 配套：`RUBRIC.md`（分類規則詳細版）、`HANDOFF.md`（項目狀態）、`README.md`（操作手冊）。

## 1. 平台 × 抓取方式總表

| 平台 | 發現（discovery） | 留言抽取 | Nested | API/工具 | Key |
|---|---|---|---|---|---|
| **Threads** | Apify `futurizerush~meta-threads-scraper` 關鍵詞搜尋（top+recent、可設日期；~30日窗口）＋ TikHub watchlist 帳號掃描 | TikHub `threads/web/fetch_post_detail_v2`（頂層）＋逐條 reply 用自己 URL 再 detail（nested） | ✅ pipeline 內建，call 上限＋時間預算 | TikHub + Apify | `TIKHUB_API_KEY` `APIFY_TOKEN` |
| **Instagram** | TikHub hashtag（渣馬/渣打香港馬拉松/渣馬2027/schkm）＋ watchlist 帳號 | TikHub `instagram/v2/fetch_post_comments`（頂層）＋ `fetch_comment_replies`（nested） | ✅ 同上 | TikHub | `TIKHUB_API_KEY` |
| **FB 專頁** | Apify `facebook-posts-scraper`（**冇關鍵詞搜尋 API**——只能逐專頁掃＋日期窗口 `onlyPostsNewerThan/OlderThan`） | Apify `facebook-comments-scraper`（`includeNestedComments:true`, `RANKED_UNFILTERED`） | ✅ actor 內建（depth 0-2） | Apify | `APIFY_TOKEN` |
| **FB 公開 group** | ❌ 冇 API 發現途徑——靠**人手/Meta 內部 search** 畀 link | 同上 comments scraper，URL 直入 | ✅ | Apify | `APIFY_TOKEN` |
| **FB closed group** | ❌ | ❌ 「Empty or private data」——**冇任何 API 途徑**，組員人手 copy | — | — | — |
| **LIHKG** | config `forum_discovery` site: 搜尋 | 直接 fetch（經 agent proxy 200 OK） | 平面結構 | curl | 冇 |
| **香討 HKDiscuss** | site: 搜尋 | Bright Data unlocker `data_format:"markdown"`——**只有 `redirect.php?goto=findpost&pid=…` 或正確 tid 嘅 viewthread 先 render**，普通 URL 回 cookie/JS shell；Discuz markdown 自家 parser（~70% 帖率，引用/刪帖走失） | 平面 | Bright Data `/request` | BD token |
| **小紅書** | TikHub MCP 有（未用於渣馬） | — | — | — | — |

## 2. API 細節 & 陷阱（實戰驗證）

### TikHub（`api.tikhub.io/api/v1`）
- **冇 Facebook module**（985 個端點全掃確認）——FB 只能行 Apify
- 端點間歇性 flaky：`lib/clients.py` 有 25s timeout × 2 retry × 全域時間預算三重限制
- Threads nested：每條 reply 本身係 post，`direct_reply_count>0` 先值得 walk；回覆數會 run 同 run 之間有浮動
- IG 頂層有分頁（第一頁 ~10-15 條），`child_comment_count>0` 先 call replies

### Apify（`api.apify.com/v2`，run-sync-get-dataset-items）
- FB comments scraper 收 `posts/`、`share/p/`、`photo/?fbid=` 三種 URL 形式都得
- **`likesCount` 回字串**——入庫前必須 coerce int（曾經冧咗成個 deck build）
- closed group 回 `{"error":"no_items","errorDescription":"Empty or private data"}`
- FB 歷史帖必須用日期窗口收窄，唔設窗口只回近期

### Bright Data（`api.brightdata.com/request`，zone `mcp_unlocker`，unblocker type）
- `data_format:"screenshot"` → PNG（有 JS 渲染）：LIHKG/Threads/FB ✅，**IG 回空白**（人手截）
- `data_format:"markdown"` → 文字抽取：香討得（正確 URL 前提下）
- 逐 request 收費（~$1.5/req trial rate）——唔好 probe/loop

### 本機環境限制
- **Chromium/Playwright 完全出唔到網**（sandbox 封咗，連 example.com 都 reset）——所有截圖行 Bright Data
- 香討直 curl 403；LIHKG 直 curl 200

## 3. Pipeline 層（`sweep.py` L1-L5）

```
L1 發現   關鍵詞/hashtag/watchlist/引用鏈/回訪 → candidates
L2 抽取   pull_threads_comments / pull_ig_comments（含 nested walk）
L3 分類   noise filter（bank_terms 等）→ issue labels → relevance
L4 報告   diff report（reports/run_*.md）→ 人手核對
L5 出deck apply_deck.py（approved only）→ pptx
```

**人手補漏**：`add_link.py <url>`——平台自動判別，Threads/IG/FB 自動抽留言（含 nested），標 `source_channel=human-add`（統計 crawler miss 率）。**Meta 內部 search（用戶側）係 FB 發現嘅最強渠道**——crawler 對 FB share-form links 同 group 帖係盲嘅，靠恆常人手對數。

## 4. 分類規則（詳見 `RUBRIC.md`）

- **R1/R2/S/U** 證據分級，**speaker-based**（同 thread 同一人升級埋一齊）
- Stance 五級＋**反串警覺**（誇張讚美+😆 唔可以照字面判 support）
- Argument tag 有封閉清單；**「海外先例」教訓**：一個 tag 唔可以揹多過一個方向嘅意思
- 流程：N 個並行分類 agent（寫 JSON 檔，唔用 StructuredOutput——長輸出會 fail）→ 嚴格 audit 複核全部 R1/R2 → 人手抽查 → 錯 tag 回寫 rubric

## 5. 安全閘

1. `apply_deck.py` 預設只出 `review_status=approved`；pending 唔入 deck
2. 每頁 footer「Auto-generated, verify before circulation」
3. API keys 只經環境變數（`.env`，已 gitignore）——**歷來 commit 零 token**（每次 commit 前 grep 驗證）
4. 改 config 後必跑 `backtest.py`
5. 週期過濾：預設只出 `cycle=2027`

## 6. 數據資產（data/）

| 檔 | 內容 |
|---|---|
| `master.json` | 145 帖（帖層真相來源；88 approved + 56 pending + 新增） |
| `phase0_twoday_corpus.json` | 18 個源帖 + 全部留言原文 |
| `twoday_community_read.json` | **841 條留言逐條 label**（tier/stance/argument/rationale/src/audit_note）+ 17 源帖 meta |
| `watchlist_learned.json` | 雪球學到嘅帳號 |
| `raw/<run_id>/` | 原始 API 回應（審計） |
| `out/screencaps/` | 14 張源帖網頁截圖（S1-S15,S17；IG 3張欠奉） |

## 7. 已知缺口（誠實清單）

- FB closed group（渣打馬拉松2015-2099 兩帖 ~49 條）——組員人手 copy 先有
- IG 源帖截圖 ×3——人手截
- 香討 parser 帖率 ~70%（引用only/刪帖走失）
- IG 頂層留言分頁未行盡（第一頁後嘅頂層留言可能有 child 未 walk）
- S10（fitz FB）帖日期 TBC
- 56 條 pending 未人手核對
- Threads 30 日搜尋窗口以外嘅舊帖——靠人手補
