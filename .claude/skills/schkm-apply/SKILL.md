---
name: schkm-apply
description: 將已人手核對嘅 SCHKM 輿情資料生成 annex PowerPoint（跟 Neutralization deck 14/15 頁格式）。當用戶提到「更新 deck」「出 annex」「schkm apply」「生成 pptx」時使用。必須喺 schkm-sweep 報告核對完之後先行。
---

# SCHKM Annex 生成

## 前置條件

**必須先跑 `schkm-sweep` 並人手核對報告。** 呢個 skill 預設只輸出 `review_status == "approved"` 嘅條目 —— 未核對嘅唔會入 deck。

## 執行

```bash
cd <repo root>

# 只出已核對條目（安全預設）
python3 monitoring/apply_deck.py

# 核對完某次 run 之後，批准佢啲新條目
python3 monitoring/apply_deck.py --approve-run 20260808_0330

# 全部批准（慎用 —— 等於跳過人手核對）
python3 monitoring/apply_deck.py --approve-all

# 連未核對都出，會喺 deck 標紅
python3 monitoring/apply_deck.py --include-pending
```

輸出：`monitoring/out/SCHKM_Annex_auto.pptx`

## 輸出格式

跟返主 deck annex 14/15 頁嘅 5 欄表：

| Topic | Platform | No. of comments | Link | Community / Note |

分三組（按相關度）：
- **Direct 2-day / quota discussion** —— 直接討論分兩日、名額、抽籤
- **Adjacent** —— 賽道／醫療／收費／盛事經濟
- **Background & noise samples** —— 背景同噪音樣本

每頁 6 行，超過自動分頁。紅色 = 未核對條目（只喺 `--include-pending` 時出現）。

## 生成後必做

1. 開個 pptx 睇 —— 確認冇文字爆格
2. **抽查連結** —— 隨機開 3-5 條，確認開得到、內容對版
3. 對主 deck：直接 copy table 落你哋原本嘅 annex slide，或者當附件用

## 首次執行

`monitoring/out/` 需要 pptxgenjs：

```bash
cd monitoring/out && npm install pptxgenjs
```

## 注意

生成嘅 deck 頁腳有「Auto-generated, verify before circulation」字樣。呢個係故意嘅 —— 對外發放前要有人睇過。
