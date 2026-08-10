# SCHKM 監察項目 —— Session Handoff

> 畀新 Claude session（或另一個 account）接手用。讀完呢份 + `README.md`，唔使歷史對話都可以繼續做嘢。

## 項目係乜

渣打香港馬拉松（SCHKM）「一日 vs 兩日」議題嘅社交輿情監察，恆常更新 Neutralization deck 嘅 annex。
Repo 唯一 branch：`claude/hong-kong-marathon-one-two-day-ejweky`。

## 而家去到邊（2026-08-10）

1. **監察系統**（`monitoring/`）行緊：sweep → 人手核對 → apply_deck 出 pptx。
   - `master.json`：138 帖（82 approved / 56 **pending 未核對**）
2. **Phase 0 語料**：`data/phase0_twoday_corpus.json` —— 10 個「一日vs兩日」帖 + 371 條留言
3. **留言分類**（`data/twoday_community_read.json`）：371 條逐條分級
   - R1 實錘跑手 5 / R2 疑似跑手 95 / S 唔跑抽水 195 / U 判唔到 76
   - 核心發現：**反對聲 74% 嚟自唔跑步嘅人；真跑手 support 32 vs oppose 27，意見分裂**
   - 方法：10 個並行分類 agent + 1 個嚴格 audit（降級 6 條假陽性）
4. **Annex deck**（`out/SCHKM_Annex_auto.pptx`，17 頁）：
   title → methodology → cohort×stance+pies → sources(S1-S10) → 論點矩陣 → 引言 → annex 表(有 Date 欄)

## 未完成 / 等緊人

- [ ] **56 條 pending** 未人手核對（`reports/run_20260808_*.md`）→ 核對完行 `apply_deck.py --approve-run <run_id>`
- [ ] **S10 源帖日期 TBC**（fitz FB 帖唔喺 master，人手補：`data/twoday_community_read.json` meta.sources）
- [ ] 用戶提供咗一份 **FB 跑步 groups Excel**（26 groups × ~140 帳號 R/V 矩陣）——**未入庫**，同 monitoring DB 係兩件事
- [ ] Deck 出街前：人手開 pptx 覆核 + 抽查 3-5 條連結
- [ ] 用戶想試 **FB 關鍵詞直搜**（Apify，唔靠 Google site:）掃漏網 FB 帖/group——未跑，等確認
- [ ] 源帖**網頁截圖**：本機瀏覽器出網被封；用戶考慮加 Bright Data MCP（見對話）

## 2026-08-10 更新：FB 補漏

用戶指出 crawler 漏咗 FB：獨媒 FB 帖（S11，108 條留言）+ 香港跑步關注組 group 帖（S12，27 條）。
已用 Apify（`APIFY_TOKEN`，見 `.env.example`）抽取、分類、audit、併入 corpus/labels/master。
發現：FB 噪音率 84%（獨媒 FB 108 條僅 4 個真跑手）。合併後 506 條、跑手 112、
反對聲 79% 係非跑手。`add_link.py` 而家識自動抽 FB 留言（公開帖；closed group 會警告）。
TikHub **冇** FB 端點（985 個端點確認過）——FB 只能行 Apify。

## 新 session 點接手

1. Clone repo，checkout `claude/hong-kong-marathon-one-two-day-ejweky`
2. 讀 `monitoring/README.md`（pipeline）+ 呢份（狀態）
3. Skills 喺 `.claude/skills/`（schkm-sweep / schkm-apply / schkm-add）——repo 自帶，新 account 有 repo 就有 skills
4. 要重跑 sweep：需要 TikHub MCP connector（account 級設定，要喺新 account 重新接）
5. 分類 labels 更新後：`python3 monitoring/apply_deck.py` 即重出 deck（aggregates 由 labels 即場計）

## 重要注意

- `apply_deck.py` 預設只出 approved 條目（安全閘）——唔好用 `--approve-all` 跳過人手核對
- LibreOffice 預覽 CJK 會有重影/emoji 空格——係 render artifact，PowerPoint 開正常
- Deck 頁腳「Auto-generated, verify before circulation」係故意嘅，唔好刪
