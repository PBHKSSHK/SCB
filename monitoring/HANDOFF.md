# SCHKM 監察項目 —— Session Handoff

> 畀新 Claude session（或另一個 account）接手用。閱讀次序：呢份 → `PIPELINE.md`（全部平台/API/rules）→ `RUBRIC.md`（分類規則）→ `README.md`（操作）。唔使歷史對話都可以繼續做嘢。

## 項目係乜

渣打香港馬拉松（SCHKM）「一日 vs 兩日」議題嘅社交輿情監察，恆常更新 Neutralization deck 嘅 annex。
Repo 唯一 branch：`claude/hong-kong-marathon-one-two-day-ejweky`。

## 而家去到邊（2026-08-10 最新）

1. **監察系統**（`monitoring/`）行緊：sweep → 人手核對 → apply_deck 出 pptx。
   - `master.json`：145 帖（88 approved + 56 **pending 未核對** + human-add）
2. **語料**：`data/phase0_twoday_corpus.json` —— **18 個源帖（S1–S17）+ 841 條留言**
   （Threads×5 / IG×3 / FB專頁×4 / FB公開group×2 / LIHKG×2 / 香討×1；含 nested replies）
3. **留言分類**（`data/twoday_community_read.json`）：841 條逐條 label，經 audit + 用戶QC retag
   - R1 實錘 11 / R2 疑似 171 / S 抽水 515 / U 判唔到 144 → **真跑手 182**
   - 核心發現：**反對聲 ~83% 嚟自唔跑步嘅人（主因封路擾民）；真跑手 43 支持 vs 42 反對——真・五五波**
   - 跑手支持論點：10K拆走封路唔加/半馬樽頸/海外分兩日先例
   - 跑手反對論點：氣氛分薄/唔信田總執行/連一日都未搞好/星期六返工/凌晨起步
4. **Annex deck**（`out/SCHKM_Annex_auto.pptx`，27 頁）：
   title → methodology → cohort×stance+兩pie → sources(S1-S17連結) → 論點矩陣(帶S#) → 引言 → source evidence 附錄×6 → annex 表(Date欄)
5. **源帖網頁截圖**：`out/screencaps/` 14 張（Bright Data；IG 3 張要人手）

## 未完成 / 等緊人

- [ ] **56 條 pending** 未人手核對（`reports/run_20260808_*.md`）→ 核對完行 `apply_deck.py --approve-run <run_id>`
- [ ] **S10 源帖日期 TBC**（fitz FB 帖唔喺 master，人手補：`data/twoday_community_read.json` meta.sources）
- [ ] 用戶提供咗一份 **FB 跑步 groups Excel**（26 groups × ~140 帳號 R/V 矩陣）——**未入庫**，同 monitoring DB 係兩件事
- [ ] Deck 出街前：人手開 pptx 覆核 + 抽查 3-5 條連結
- [ ] 用戶想試 **FB 關鍵詞直搜**（Apify，唔靠 Google site:）掃漏網 FB 帖/group——未跑，等確認
- [ ] **人手先攞到**嘅留言：渣打馬拉松2015-2099 closed group 兩帖（~49條）＋香討 thread（42條，403反爬）——要組員/人手 copy，然後 add_link 入庫
- [ ] IG 源帖截圖 3 張（S3/S4/S16）——Bright Data 影 IG 空白，人手截

## 2026-08-10 更新（二）：Meta 內部 search 對數 + S13–S16

用戶用 Meta 內部 search 畀咗 19 帖對數（`1D_vs_2D_discussion.xlsx`）：12 帖已有（S1–S12），
7 帖漏網。已抽 4 帖：S13 跑步關注組舊帖（96）、S14 獨媒議員倡FB（142，第二大source）、
S15 HKDiscuss FB（14）、S16 Fitz IG（7，TikHub）。分類+audit 後總量 **765 條、真跑手 142**。
**跑手立場變咗：37 支持 vs 38 反對（五五波）**——S14 帶入跑手反對聲（星期六返工/分法唔可行/
義工通宵/凌晨起步）。反對聲 83% 仍係非跑手。
源帖截圖 13/16 張已存 `out/screencaps/`（Bright Data unlocker zone `mcp_unlocker`）。

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
