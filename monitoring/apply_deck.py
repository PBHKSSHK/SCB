#!/usr/bin/env python3
"""L5 —— 由已核對嘅 master.json 生成 annex pptx（跟 deck 14/15 頁格式）。

安全閘：預設只輸出 review_status == "approved" 嘅條目。
未核對（pending）嘅唔會入 deck，除非 --include-pending（會喺 deck 標紅）。

用法:
    python monitoring/apply_deck.py                     # 只出 approved
    python monitoring/apply_deck.py --approve-run 20260807_1930   # 批准某次 run 嘅新帖
    python monitoring/apply_deck.py --include-pending   # 連未核對都出（標紅）
"""
import argparse
import json
import os
import subprocess
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import store  # noqa: E402

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "out")

PLATFORM_LABEL = {
    "threads": "Threads",
    "instagram": "Instagram",
    "facebook": "Facebook",
    "lihkg": "LIHKG",
    "hkdiscuss": "HKDiscuss",
    "news": "News",
}


def build_js(rows_by_group, as_of, pending_n):
    """生成 pptxgenjs script。"""
    groups_json = json.dumps(rows_by_group, ensure_ascii=False)
    return f"""
const pptxgen = require("pptxgenjs");
const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE";
const NAVY="1E2761", ICE="CADCFC", LINEC="D9D9D9", RED="B3261E";
const GROUPS = {groups_json};
const AS_OF = {json.dumps(as_of)};
const PENDING = {pending_n};

const HEAD = ["Topic","Platform","No. of comments","Link","Community / Note"];
const COLW = [4.9, 1.35, 1.25, 3.6, 1.5];

function titleSlide() {{
  const s = pres.addSlide();
  s.background = {{ color: NAVY }};
  s.addText("Annex — Sentiment tracking on 2-day race", {{
    x:0.7, y:2.3, w:12, h:1.0, fontSize:32, bold:true, color:"FFFFFF", fontFace:"Arial" }});
  s.addText(`Auto-generated from monitoring database\\nData as of ${{AS_OF}}`, {{
    x:0.7, y:3.5, w:12, h:0.9, fontSize:15, color:ICE, fontFace:"Arial", lineSpacing:22 }});
  if (PENDING > 0) {{
    s.addText(`⚠ ${{PENDING}} item(s) pending human review — excluded from this deck`, {{
      x:0.7, y:4.6, w:12, h:0.4, fontSize:13, color:"FFD166", fontFace:"Arial" }});
  }}
}}

function tableSlides(groupName, rows) {{
  const PER = 6;
  for (let i=0; i<rows.length; i+=PER) {{
    const chunk = rows.slice(i, i+PER);
    const s = pres.addSlide();
    s.background = {{ color:"FFFFFF" }};
    const part = rows.length>PER ? ` (${{Math.floor(i/PER)+1}}/${{Math.ceil(rows.length/PER)}})` : "";
    s.addText(`Annex — ${{groupName}}${{part}}`, {{
      x:0.35, y:0.18, w:12.6, h:0.45, fontSize:19, bold:true, color:NAVY, fontFace:"Arial" }});
    const tr = [HEAD.map(h=>({{ text:h, options:{{ bold:true, color:"FFFFFF", fill:{{color:NAVY}}, fontSize:9.5, valign:"middle" }} }}))];
    chunk.forEach(r=>{{
      const isNew = r.is_new;
      tr.push([
        {{ text:r.topic, options:{{ fontSize:8.4, valign:"top", color: isNew?RED:"222222", bold: isNew }} }},
        {{ text:r.platform, options:{{ fontSize:8.6, valign:"top" }} }},
        {{ text:String(r.comments), options:{{ fontSize:8.6, valign:"top", align:"center" }} }},
        {{ text:r.link, options:{{ fontSize:7.2, valign:"top", color:"1155CC" }} }},
        {{ text:r.note, options:{{ fontSize:8, valign:"top" }} }},
      ]);
    }});
    s.addTable(tr, {{ x:0.35, y:0.72, w:12.6, colW:COLW,
      border:{{ type:"solid", color:LINEC, pt:0.75 }}, margin:0.04,
      fontFace:"Arial", color:"222222", autoPage:false }});
    s.addText("紅色 = 本次新增，須人手覆核｜Auto-generated, verify before circulation", {{
      x:0.35, y:7.02, w:12.6, h:0.3, fontSize:8, italic:true, color:"5A5A5A", fontFace:"Arial" }});
  }}
}}

titleSlide();
for (const [g, rows] of Object.entries(GROUPS)) {{ tableSlides(g, rows); }}
pres.writeFile({{ fileName: {json.dumps(os.path.join(OUT, "SCHKM_Annex_auto.pptx"))} }})
  .then(()=>console.log("written"));
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--include-pending", action="store_true")
    ap.add_argument("--approve-run", help="將某次 run 嘅 pending 條目標記為 approved")
    ap.add_argument("--approve-all", action="store_true", help="批准全部 pending（慎用）")
    args = ap.parse_args()

    master = store.load_master()
    items = master.get("items", {})

    if args.approve_run or args.approve_all:
        n = 0
        for it in items.values():
            if it.get("review_status") != "pending":
                continue
            if args.approve_all or it.get("first_seen"):
                it["review_status"] = "approved"
                n += 1
        store.save_master(master)
        print(f"已批准 {n} 條")

    approved, pending = [], []
    for it in items.values():
        (approved if it.get("review_status") == "approved" else pending).append(it)

    use = approved + (pending if args.include_pending else [])
    if not use:
        print("冇 approved 條目。先核對報告，再行 --approve-run 或 --approve-all")
        return

    groups = defaultdict(list)
    for it in sorted(use, key=lambda x: (x.get("date") or ""), reverse=True):
        rel = it.get("relevance") or "background"
        g = {
            "direct": "Direct 2-day / quota discussion",
            "adjacent": "Adjacent (route / medical / fees / economy)",
        }.get(rel, "Background & noise samples")
        groups[g].append(
            {
                "topic": (it.get("text") or "")[:180].replace("\n", " ") or "(no text)",
                "platform": PLATFORM_LABEL.get(it.get("platform"), it.get("platform") or "?"),
                "comments": it.get("comments_pulled") or it.get("replies") or 0,
                "link": it.get("url"),
                "note": " / ".join((it.get("issue_labels") or [])[:2]),
                "is_new": it.get("review_status") != "approved",
            }
        )

    os.makedirs(OUT, exist_ok=True)
    js = build_js(dict(groups), store.today_str(), 0 if args.include_pending else len(pending))
    jsp = os.path.join(OUT, "_build_annex.js")
    with open(jsp, "w", encoding="utf-8") as f:
        f.write(js)

    env = dict(os.environ)
    r = subprocess.run(["node", jsp], capture_output=True, text=True, cwd=OUT, env=env)
    if r.returncode != 0:
        print("pptxgenjs 失敗：", r.stderr[:400])
        print("提示：喺 monitoring/out 行 `npm install pptxgenjs`")
        return
    print(f"已生成: {os.path.join(OUT, 'SCHKM_Annex_auto.pptx')}")
    print(f"  approved {len(approved)} 條 | pending {len(pending)} 條"
          f"{'（已包含，標紅）' if args.include_pending else '（未包含）'}")
    for g, rows in groups.items():
        print(f"  - {g}: {len(rows)} 條")


if __name__ == "__main__":
    main()
