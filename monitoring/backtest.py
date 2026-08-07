#!/usr/bin/env python3
"""驗收測試 —— 證明 crawler 覆蓋到 deck annex 嘅內容。

兩部分：
  A. 過濾器回歸測試：deck annex + 已知帖嘅文字要通過過濾（唔可以被當噪音剔走）
     台灣/銀行噪音樣本要被剔走。
  B. 覆蓋度報告：deck annex 12 條喺 master.json 嘅狀態。

用法: python monitoring/backtest.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import classify, store  # noqa: E402

ROOT = os.path.dirname(os.path.abspath(__file__))

# --- A. 必須保留（真實 deck annex / 已核實帖嘅內文）---
MUST_KEEP = [
    ("deck annex #2 martin3388",
     "香港渣馬其實係現有賽道下，最大問題係半馬要就全馬加唔到位，所以半馬同全馬要分開星期六日搞"),
    ("deck annex #3 kk30gsw",
     "有人提出渣馬分兩日舉行，我分析一下：最多人參加是最短的10k，其次是半馬"),
    ("deck annex #4 ericchan326",
     "其實渣馬會唔會學吓其他地方，考慮將breakfast run同真正馬拉松分開兩日搞"),
    ("deck annex #5 sunnychan1987（低互動，最易漏）",
     "而家討論緊香港渣馬分唔分兩日搞 其實瑞士同澳洲都做緊 日內瓦同黃金海岸馬拉松星期六傍晚跑小型嘅"),
    ("deck annex #6 fitz 北都",
     "渣馬分兩日搞? 霍啟剛倡一日市區一日北都 田總: 成立特別小組研究新路線"),
    ("Gap1 保證名額",
     "半日就FULL左，夠出席率有保證渣馬購買額 報名成功"),
    ("Gap2 內部渠道",
     "屬會報名有問題報唔到，公眾抽籤兩輪都唔中，慈善位癲價放棄，有背後有勢力人士通知我有方法可以去跑"),
    ("Gap3 雙重身份",
     "好多人用香港身份證報名和外國護照報名，2次抽籤機會，田總你們知道嗎"),
    ("Gap4 技術反駁",
     "10K同半全馬賽道係冇重疊，兩日加埋封嘅路係唔會多咗"),
    ("跑手第一身",
     "大目標：2027年渣馬 sub 3 訓練日記 今晚玩90分鐘跑"),
    ("香港語境泛詞（無「渣」字）",
     "香港馬拉松今年封路安排點呀？維園終點會唔會好逼"),
    ("渣馬賽道回憶（短句）",
     "是咪跑過渣馬嘅人都會揀海底隧道"),
    ("香港跑手國際數據分析",
     "Boston Marathon官方數據，香港女跑手中位完成時間3:26:25，170位香港完成者中有60位女跑手"),
]

# --- B. 必須剔走（噪音樣本）---
MUST_DROP = [
    ("台灣蔬食活動", "彰化15家蔬食馬拉松 大佛盤子實體有夠可愛質感超好 彰化人都去給我換起來喔"),
    ("銀行活期產品", "月尾一出糧就做渣打馬拉松活期 港元年利率介於 2.6% ~ 3.1% 以活期存款回報十分不錯"),
    ("銀行派息投訴", "渣打銀行定期竟然派少咗息！原來定期派息都要自己計吓先知啱唔啱，出少咗44美金"),
    ("台北馬（無香港訊號）", "黑仔如我竟然有首抽運，台北馬正取！中選後才知道全馬正取只有4393人"),
    ("台灣粗口哏", "馬的怎麼會有人花錢買這種東西？？"),
    ("賽馬", "今日雨戰加水馬日戒賭一天 R3淨係鍾意三隻馬"),
    ("完全無關", "想買比寧咸波衫，應該買皇馬定英格蘭好？"),
    # --- 以下係第一次真實掃描漏網、之後修正嘅樣本（回歸保護）---
    ("台灣半馬無港訊號", "八月開跑🏃 秋天的第一隻半馬"),
    ("富士山線上馬", "有人參加富士山夏季線上馬拉松嗎？我覺得我跑不完半馬了"),
    ("東馬報名", "2027東馬拉松報名完成 連續2年，明年又正好是東馬20週年"),
    ("銀行債券轉存（含渣馬字眼）",
     "機管局債券今日到期 連本帶利收回$30,000 即刻將新資金轉去渣打馬拉松活期存款 繼續跑賺高息"),
    ("虛銀比較（含渣馬字眼）", "做 Mox Flexiboost 都好過今個月渣馬"),
    ("台灣新手提問", "今天一樣來跑步 跑到第3k就想放棄了 這樣真的可以去報名10k馬拉松嗎"),
]


def main():
    with open(os.path.join(ROOT, "config.json"), encoding="utf-8") as f:
        cfg = json.load(f)

    print("=" * 66)
    print("A. 過濾器回歸測試")
    print("=" * 66)
    fails = []

    print("\n[必須保留]")
    for name, txt in MUST_KEEP:
        noise = classify.is_noise(txt, cfg)
        rel = classify.relevance(txt)
        labs = classify.label_text(txt)
        ok = not noise
        print(f"  {'✅' if ok else '❌'} {name}")
        print(f"      relevance={rel} labels={','.join(labs[:3])}")
        if not ok:
            fails.append(f"錯殺: {name}")

    print("\n[必須剔走]")
    for name, txt in MUST_DROP:
        noise = classify.is_noise(txt, cfg)
        print(f"  {'✅' if noise else '❌'} {name}")
        if not noise:
            fails.append(f"漏網: {name}")

    print("\n" + "=" * 66)
    print("B. Deck annex 覆蓋度")
    print("=" * 66)
    master = store.load_master()
    items = master.get("items", {})
    annex = [
        (u, it) for u, it in items.items() if (it.get("origin") == "deck-annex")
    ]
    print(f"\ndeck-annex 種子：{len(annex)}/12 條在庫")
    by_plat = {}
    for u, it in annex:
        by_plat.setdefault(it["platform"], []).append(it)
    for plat, rows in sorted(by_plat.items()):
        auto = plat in ("threads", "instagram", "facebook")
        mark = "✅ 全自動覆蓋" if auto else "⚠️ 半自動（發現自動／內容人手）"
        print(f"  {plat:10s} {len(rows)} 條  {mark}")

    total = len(items)
    pending = sum(1 for it in items.values() if it.get("review_status") == "pending")
    print(f"\n資料庫總計：{total} 條（pending 待核對 {pending} 條）")

    print("\n" + "=" * 66)
    if fails:
        print(f"❌ 回歸測試失敗 {len(fails)} 項：")
        for f in fails:
            print(f"   - {f}")
        sys.exit(1)
    print("✅ 全部通過")
    print("=" * 66)


if __name__ == "__main__":
    main()
