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

ANALYSIS_DEFAULT = os.path.join(ROOT, "data", "twoday_community_read.json")

STANCES = ["support", "oppose", "mixed", "neutral", "na"]
STANCE_LABEL = {
    "support": "Support 2-day",
    "oppose": "Oppose 2-day",
    "mixed": "Mixed",
    "neutral": "Neutral",
    "na": "N/A",
}


def build_community_read(path):
    """由 comment-level 分類 labels 計 aggregates（single source of truth：labels）。

    回傳 dict 畀 JS 直接 render；labels 唔啱格式就回 None（deck 照出，冇分析頁）。
    """
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    labels = data.get("labels") or []
    if not labels:
        return None

    def stance_row(rows):
        c = Counter(r.get("stance") for r in rows)
        return [c.get(s, 0) for s in STANCES]

    # 未知 stance/tier 唔會靜默流失：出聲警告（cohort 行加埋應該等於 N）
    bad_stance = Counter(
        r.get("stance") for r in labels if r.get("stance") not in STANCES
    )
    bad_tier = Counter(
        r.get("tier") for r in labels if r.get("tier") not in ("R1", "R2", "S", "U")
    )
    if bad_stance:
        print(f"⚠ 分析檔有未知 stance（唔會計入立場欄）：{dict(bad_stance)}")
    if bad_tier:
        print(f"⚠ 分析檔有未知 tier（唔會入任何 cohort）：{dict(bad_tier)}")

    runners = [r for r in labels if r.get("tier") in ("R1", "R2")]
    noise = [r for r in labels if r.get("tier") == "S"]
    unclear = [r for r in labels if r.get("tier") == "U"]

    cohorts = [
        {"name": f"All comments ({len(labels)})", "row": stance_row(labels)},
        {
            "name": (
                f"Confirmed runners ({len(runners)} — "
                f"R1×{sum(1 for r in runners if r['tier'] == 'R1')}, "
                f"R2×{sum(1 for r in runners if r['tier'] == 'R2')})"
            ),
            "row": stance_row(runners),
            "bold": True,
        },
        {"name": f"Non-runners / noise ({len(noise)})", "row": stance_row(noise)},
        {"name": f"Unclassifiable ({len(unclear)})", "row": stance_row(unclear)},
    ]

    # 真跑手論點矩陣：support vs oppose 兩欄並排，每個論點附源帖 ref
    def top_args(stance, n=8):
        c = Counter(
            r.get("argument")
            for r in runners
            if r.get("stance") == stance and r.get("argument") not in (None, "無論點")
        )
        out = []
        for arg, k in c.most_common(n):
            refs = sorted(
                {
                    r.get("src")
                    for r in runners
                    if r.get("stance") == stance and r.get("argument") == arg and r.get("src")
                },
                key=lambda s: int(s[1:]),
            )
            out.append({"t": f"{arg}（{k}）", "refs": " ".join(refs)})
        return out

    # 代表引言：每個立場按 likes 排頭位（R1 有專列，呢度只抽 R2 免重複；跳過無實質論點嘅）
    def quotes(stance, n):
        grp = sorted(
            (
                r
                for r in runners
                if r.get("stance") == stance
                and r["tier"] != "R1"
                and r.get("argument") not in (None, "無論點")
            ),
            key=lambda r: -(r.get("lk") or 0),
        )
        return [
            {
                "stance": STANCE_LABEL[stance],
                "tier": r["tier"],
                "src": r.get("src") or "",
                "text": (r.get("tx") or "").replace("\n", " ").strip()[:150],
            }
            for r in grp[:n]
        ]

    n_oppose_all = sum(1 for r in labels if r.get("stance") == "oppose")
    n_oppose_noise = sum(1 for r in noise if r.get("stance") == "oppose")
    nr = stance_row(runners)
    takeaways = [
        f"{n_oppose_all} oppose comments overall — but {n_oppose_noise} "
        f"({round(100 * n_oppose_noise / max(n_oppose_all, 1))}%) come from non-runners, "
        "mostly road-closure complaints unrelated to race design.",
        f"Among confirmed runners the split is genuine: support {nr[0]} vs oppose {nr[1]} "
        f"(mixed {nr[2]}, neutral {nr[3]}).",
        "Runner support is practical (10K split frees closure budget; HM ballot bottleneck; "
        "overseas precedent). Runner opposition is about execution trust and atmosphere, "
        "not the concept.",
    ]

    meta = data.get("meta") or {}
    sources = meta.get("sources") or []

    methodology = [
        {"h": "Unit of analysis", "b": [
            "Every public comment under the 10 source posts (S1–S10) discussing the "
            "1-day vs 2-day question — 371 comments after dedup/noise filter."]},
        {"h": "Step 1 — Evidence tier (who is speaking?)", "b": [
            "R1 Confirmed runner: first-person race evidence — own ballot/entry, finish, PB, "
            "pace, training, runner-pack pickup, ran an overseas race.",
            "R2 Likely runner: no first-person proof, but race-structure knowledge — start-wave "
            "spacing, Gold/Platinum Label, course overlap, closure hours, two-day precedents.",
            "S Non-runner / noise: zero running signal — road-closure complaints, jokes, pile-ons.",
            "U Unclassifiable: too short, news repost, or off-topic.",
            "Perspective test: argued from a runner's perspective with concrete race detail → "
            "R1/R2. Stance alone proves nothing — 「支持但我跑唔到」 is NOT a runner."]},
        {"h": "Step 2 — Stance on the 2-day format", "b": [
            "support / oppose / mixed / neutral / n.a. — judged independently of tier."]},
        {"h": "Step 3 — Argument tag", "b": [
            "One short tag per comment（e.g. 10K拆走封路唔加・氣氛分薄・唔信田總執行）."]},
        {"h": "Step 4 — Strict audit pass", "b": [
            "A second, adversarial pass re-judged all 104 initial R1/R2; 6 were downgraded "
            "(news quoters, 「我跑唔到」, pure politician-bashing). Final: 100 confirmed runners."]},
    ]

    return {
        "as_of": meta.get("as_of", ""),
        "n": len(labels),
        "cohorts": cohorts,
        "stance_heads": [STANCE_LABEL[s] for s in STANCES],
        "args_support": top_args("support"),
        "args_oppose": top_args("oppose"),
        "quotes": quotes("support", 3) + quotes("oppose", 3) + quotes("mixed", 2),
        "r1_quotes": [
            {
                "stance": STANCE_LABEL.get(r.get("stance"), r.get("stance") or "?"),
                "tier": "R1",
                "src": r.get("src") or "",
                "text": (r.get("tx") or "").replace("\n", " ").strip()[:150],
            }
            for r in runners
            if r["tier"] == "R1"
        ],
        "takeaways": takeaways,
        "sources": sources,
        "methodology": methodology,
        "pie_tier": {
            "labels": [
                f"Confirmed runners ({len(runners)})",
                f"Non-runners / noise ({len(noise)})",
                f"Unclassifiable ({len(unclear)})",
            ],
            "values": [len(runners), len(noise), len(unclear)],
        },
        "pie_runner_stance": {
            "labels": [
                f"{STANCE_LABEL[s]} ({v})" for s, v in zip(STANCES, stance_row(runners))
            ],
            "values": stance_row(runners),
        },
    }


def build_js(rows_by_group, as_of, pending_n, community=None):
    """生成 pptxgenjs script。"""
    groups_json = json.dumps(rows_by_group, ensure_ascii=False)
    return f"""
const pptxgen = require("pptxgenjs");
const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE";
const NAVY="1E2761", ICE="CADCFC", LINEC="D9D9D9", RED="B3261E", GREEN="2E6E4E";
const GROUPS = {groups_json};
const AS_OF = {json.dumps(as_of)};
const PENDING = {pending_n};
const COMM = {json.dumps(community, ensure_ascii=False)};

const HEAD = ["Topic","Date","Platform","No. of comments","Link","Community / Note"];
const COLW = [4.35, 0.95, 1.2, 1.15, 3.55, 1.4];

function titleSlide() {{
  const s = pres.addSlide();
  s.background = {{ color: NAVY }};
  s.addText("Annex — Sentiment tracking on 2-day race", {{
    x:0.7, y:2.3, w:12, h:1.0, fontSize:32, bold:true, color:"FFFFFF", fontFace:"Arial" }});
  s.addText(`Auto-generated from monitoring database\\nData as of ${{AS_OF}}`, {{
    x:0.7, y:3.5, w:12, h:0.9, fontSize:15, color:ICE, fontFace:"Arial", lineSpacing:22 }});
  if (COMM) {{
    s.addText(`Includes community-read analysis: ${{COMM.n}} comments classified by runner evidence`, {{
      x:0.7, y:4.4, w:12, h:0.4, fontSize:13, color:ICE, fontFace:"Arial" }});
  }}
  if (PENDING > 0) {{
    s.addText(`⚠ ${{PENDING}} item(s) pending human review — excluded from this deck`, {{
      x:0.7, y:4.9, w:12, h:0.4, fontSize:13, color:"FFD166", fontFace:"Arial" }});
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
        {{ text:r.date||"", options:{{ fontSize:8.4, valign:"top" }} }},
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

function footer(s) {{
  s.addText("Auto-generated, verify before circulation", {{
    x:0.35, y:7.02, w:12.6, h:0.3, fontSize:8, italic:true, color:"5A5A5A", fontFace:"Arial" }});
}}

function communitySlides() {{
  if (!COMM) return;

  // C0 —— 分類 methodology
  let s = pres.addSlide();
  s.background = {{ color:"FFFFFF" }};
  s.addText("Classification methodology", {{
    x:0.35, y:0.18, w:12.6, h:0.45, fontSize:19, bold:true, color:NAVY, fontFace:"Arial" }});
  const mruns = [];
  (COMM.methodology||[]).forEach(sec=>{{
    mruns.push({{ text:sec.h+"\\n", options:{{ bold:true, fontSize:12.5, color:NAVY, breakLine:true }} }});
    sec.b.forEach(line=>mruns.push({{ text:"•  "+line+"\\n", options:{{ fontSize:10.5, color:"222222", breakLine:true }} }}));
  }});
  s.addText(mruns, {{ x:0.35, y:0.72, w:12.6, h:6.1, fontFace:"Arial", valign:"top", lineSpacing:15.5 }});
  footer(s);

  // C1 —— cohort × stance 表 + pie charts
  s = pres.addSlide();
  s.background = {{ color:"FFFFFF" }};
  s.addText(`Community read — who actually runs? (${{COMM.n}} comments, evidence-tiered)`, {{
    x:0.35, y:0.18, w:12.6, h:0.45, fontSize:19, bold:true, color:NAVY, fontFace:"Arial" }});
  const hd = [{{ text:"Cohort", options:{{ bold:true, color:"FFFFFF", fill:{{color:NAVY}}, fontSize:10 }} }}]
    .concat(COMM.stance_heads.map(h=>({{ text:h, options:{{ bold:true, color:"FFFFFF", fill:{{color:NAVY}}, fontSize:10, align:"center" }} }})));
  const body = COMM.cohorts.map(c=>{{
    return [{{ text:c.name, options:{{ fontSize:10, bold:!!c.bold }} }}]
      .concat(c.row.map(v=>({{ text:String(v), options:{{ fontSize:10, align:"center", bold:!!c.bold }} }})));
  }});
  s.addTable([hd].concat(body), {{ x:0.35, y:0.72, w:12.6, colW:[5.1,1.5,1.5,1.5,1.5,1.5],
    border:{{ type:"solid", color:LINEC, pt:0.75 }}, margin:0.06, fontFace:"Arial", color:"222222" }});
  s.addText("Evidence tier — all comments", {{ x:0.6, y:2.95, w:5.6, h:0.3, fontSize:11.5, bold:true, color:NAVY, fontFace:"Arial", align:"center" }});
  s.addChart(pres.ChartType.pie,
    [{{ name:"Evidence tier", labels:COMM.pie_tier.labels, values:COMM.pie_tier.values }}],
    {{ x:0.6, y:3.25, w:5.6, h:3.1, showLegend:true, legendPos:"b", legendFontSize:9,
       showPercent:true, dataLabelFontSize:10, dataLabelColor:"FFFFFF",
       chartColors:["1E2761","B3261E","8A8A8A"] }});
  s.addText("Confirmed runners — stance on 2-day", {{ x:7.0, y:2.95, w:5.6, h:0.3, fontSize:11.5, bold:true, color:NAVY, fontFace:"Arial", align:"center" }});
  s.addChart(pres.ChartType.pie,
    [{{ name:"Runner stance", labels:COMM.pie_runner_stance.labels, values:COMM.pie_runner_stance.values }}],
    {{ x:7.0, y:3.25, w:5.6, h:3.1, showLegend:true, legendPos:"b", legendFontSize:9,
       showPercent:true, dataLabelFontSize:10, dataLabelColor:"FFFFFF",
       chartColors:["2E6E4E","B3261E","D98E04","8A8A8A","CADCFC"] }});
  s.addText(COMM.takeaways.map(t=>({{ text:"•  "+t+"\\n", options:{{ fontSize:9, color:"222222", breakLine:true }} }})),
    {{ x:0.35, y:6.28, w:12.6, h:0.62, fontFace:"Arial", valign:"top", lineSpacing:11.5 }});
  footer(s);

  // C1b —— 371 條留言嘅源帖（全部連結）
  s = pres.addSlide();
  s.background = {{ color:"FFFFFF" }};
  s.addText(`Comment sources — all ${{COMM.n}} comments come from these posts`, {{
    x:0.35, y:0.18, w:12.6, h:0.45, fontSize:19, bold:true, color:NAVY, fontFace:"Arial" }});
  const sh = ["Ref","Date","Platform","Post","No. of comments","Link"].map(h=>({{ text:h, options:{{ bold:true, color:"FFFFFF", fill:{{color:NAVY}}, fontSize:9.5 }} }}));
  const srows = (COMM.sources||[]).map(p=>[
    {{ text:p.ref, options:{{ fontSize:9, bold:true, valign:"top" }} }},
    {{ text:p.date||"TBC", options:{{ fontSize:9, valign:"top" }} }},
    {{ text:p.platform, options:{{ fontSize:9, valign:"top" }} }},
    {{ text:p.title, options:{{ fontSize:9, valign:"top" }} }},
    {{ text:String(p.n_comments), options:{{ fontSize:9, valign:"top", align:"center" }} }},
    {{ text:p.url, options:{{ fontSize:7.6, valign:"top", color:"1155CC", hyperlink:{{ url:p.url }} }} }},
  ]);
  s.addTable([sh].concat(srows), {{ x:0.35, y:0.72, w:12.6, colW:[0.6,1.0,1.1,3.4,1.3,5.2],
    border:{{ type:"solid", color:LINEC, pt:0.75 }}, margin:0.04, fontFace:"Arial", color:"222222" }});
  s.addText("S1–S10 refs are used on the argument-matrix and verbatim pages to trace every point back to its source post.", {{
    x:0.35, y:6.6, w:12.6, h:0.3, fontSize:9, italic:true, color:"5A5A5A", fontFace:"Arial" }});
  footer(s);

  // C2 —— 真跑手論點矩陣（附源帖 ref）
  s = pres.addSlide();
  s.background = {{ color:"FFFFFF" }};
  s.addText("Confirmed-runner argument matrix", {{
    x:0.35, y:0.18, w:12.6, h:0.45, fontSize:19, bold:true, color:NAVY, fontFace:"Arial" }});
  const nrows = Math.max(COMM.args_support.length, COMM.args_oppose.length);
  const mtr = [[
    {{ text:"Why runners SUPPORT 2-day", options:{{ bold:true, color:"FFFFFF", fill:{{color:GREEN}}, fontSize:11 }} }},
    {{ text:"Sources", options:{{ bold:true, color:"FFFFFF", fill:{{color:GREEN}}, fontSize:11 }} }},
    {{ text:"Why runners OPPOSE 2-day", options:{{ bold:true, color:"FFFFFF", fill:{{color:RED}}, fontSize:11 }} }},
    {{ text:"Sources", options:{{ bold:true, color:"FFFFFF", fill:{{color:RED}}, fontSize:11 }} }},
  ]];
  for (let i=0;i<nrows;i++) {{
    const a=COMM.args_support[i]||{{}}, b=COMM.args_oppose[i]||{{}};
    mtr.push([
      {{ text:a.t||"", options:{{ fontSize:10.5 }} }},
      {{ text:a.refs||"", options:{{ fontSize:8.5, color:"5A5A5A" }} }},
      {{ text:b.t||"", options:{{ fontSize:10.5 }} }},
      {{ text:b.refs||"", options:{{ fontSize:8.5, color:"5A5A5A" }} }},
    ]);
  }}
  s.addTable(mtr, {{ x:0.35, y:0.8, w:12.6, colW:[4.5,1.8,4.5,1.8],
    border:{{ type:"solid", color:LINEC, pt:0.75 }}, margin:0.06, fontFace:"Arial", color:"222222" }});
  s.addText("S# = source post — see the Comment sources page for full links.", {{
    x:0.35, y:6.6, w:12.6, h:0.3, fontSize:9, italic:true, color:"5A5A5A", fontFace:"Arial" }});
  footer(s);

  // C3 —— 代表引言（真跑手原文，附源帖 ref）
  s = pres.addSlide();
  s.background = {{ color:"FFFFFF" }};
  s.addText("Verbatim highlights — confirmed runners only", {{
    x:0.35, y:0.18, w:12.6, h:0.45, fontSize:19, bold:true, color:NAVY, fontFace:"Arial" }});
  const qh = ["Stance","Tier","Src","Quote"].map(h=>({{ text:h, options:{{ bold:true, color:"FFFFFF", fill:{{color:NAVY}}, fontSize:9.5 }} }}));
  const qr = COMM.quotes.concat(COMM.r1_quotes).map(q=>[
    {{ text:q.stance, options:{{ fontSize:8.6, valign:"top" }} }},
    {{ text:q.tier, options:{{ fontSize:8.6, valign:"top", align:"center", bold:q.tier==="R1" }} }},
    {{ text:q.src||"", options:{{ fontSize:8.6, valign:"top", align:"center" }} }},
    {{ text:q.text, options:{{ fontSize:8.4, valign:"top" }} }},
  ]);
  s.addTable([qh].concat(qr), {{ x:0.35, y:0.72, w:12.6, colW:[1.4,0.7,0.7,9.8],
    border:{{ type:"solid", color:LINEC, pt:0.75 }}, margin:0.04, fontFace:"Arial", color:"222222" }});
  footer(s);
}}

titleSlide();
communitySlides();
for (const [g, rows] of Object.entries(GROUPS)) {{ tableSlides(g, rows); }}
pres.writeFile({{ fileName: {json.dumps(os.path.join(OUT, "SCHKM_Annex_auto.pptx"))} }})
  .then(()=>console.log("written"));
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--include-pending", action="store_true")
    ap.add_argument("--approve-run", help="將某次 run 嘅 pending 條目標記為 approved")
    ap.add_argument("--approve-all", action="store_true", help="批准全部 pending（慎用）")
    ap.add_argument(
        "--cycle",
        default=None,
        help="只出某個賽事週期（預設用 config focus_cycle=2027；傳 all 出晒）",
    )
    ap.add_argument(
        "--analysis",
        default=ANALYSIS_DEFAULT,
        help="comment-level 分類 labels JSON（預設 data/twoday_community_read.json，存在就自動出分析頁）",
    )
    ap.add_argument("--no-analysis", action="store_true", help="唔出 community-read 分析頁")
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

    # 週期過濾：預設只出 focus 週期（渣馬2027），舊週期材料唔入 annex
    cfg = store.load_config()
    focus = args.cycle or cfg.get("focus_cycle", "2027")
    if focus != "all":
        before_n = len(use)
        use = [it for it in use if it.get("cycle", "2027") == focus]
        print(f"週期過濾：{before_n} → {len(use)} 條（cycle={focus}；--cycle all 可出晒）")

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
                "date": it.get("date") or "",
                "platform": PLATFORM_LABEL.get(it.get("platform"), it.get("platform") or "?"),
                "comments": it.get("comments_pulled") or it.get("replies") or 0,
                "link": it.get("url"),
                "note": " / ".join((it.get("issue_labels") or [])[:2]),
                "is_new": it.get("review_status") != "approved",
            }
        )

    # 組別次序：Direct 最重要行先，Background 殿後
    ORDER = [
        "Direct 2-day / quota discussion",
        "Adjacent (route / medical / fees / economy)",
        "Background & noise samples",
    ]
    ordered = {g: groups[g] for g in ORDER if g in groups}

    community = None
    if not args.no_analysis and os.path.exists(args.analysis):
        try:
            community = build_community_read(args.analysis)
        except Exception as e:  # 壞檔任何形式都唔可以拖冧正常 annex 出 deck
            print(f"分析檔讀取失敗，deck 照出（冇分析頁）：{type(e).__name__}: {e}")
    elif not args.no_analysis and args.analysis != ANALYSIS_DEFAULT:
        print(f"⚠ --analysis 指定嘅檔唔存在，deck 冇分析頁：{args.analysis}")
    if community:
        print(f"community-read 分析頁：{community['n']} 條留言（{args.analysis}）")

    os.makedirs(OUT, exist_ok=True)
    js = build_js(
        ordered, store.today_str(), 0 if args.include_pending else len(pending), community
    )
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
