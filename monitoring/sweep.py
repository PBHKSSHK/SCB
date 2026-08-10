#!/usr/bin/env python3
"""SCHKM 輿情掃描 —— L1 發現 + L2 抽取 + L3 分類 + L4 diff 報告。

用法:
    python monitoring/sweep.py                 # 全渠道深掃（每7日）
    python monitoring/sweep.py --light         # 輕掃（每日，只行 Threads recent）
    python monitoring/sweep.py --no-comments   # 唔抽留言（快速試跑）
    python monitoring/sweep.py --dry-run       # 唔寫 master，只出報告

呢個 script 唔會掂 deck。要更新 deck 見 apply_deck.py。
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import classify, store  # noqa: E402
from lib.clients import Apify, ApiError, TikHub  # noqa: E402

ROOT = os.path.dirname(os.path.abspath(__file__))


def load_cfg():
    with open(os.path.join(ROOT, "config.json"), encoding="utf-8") as f:
        return json.load(f)


def ts_to_date(ts):
    if not ts:
        return None
    try:
        return datetime.utcfromtimestamp(int(ts)).strftime("%Y-%m-%d")
    except Exception:  # noqa: BLE001
        return None


# ---------------- L1: 發現 ----------------

def discover_threads_search(apify, cfg, light, log):
    """Apify Threads 關鍵詞搜尋。回傳候選 dict list。"""
    out = []
    sc = cfg["threads_search"]
    orders = ["recent"] if light else sc["sort_orders"]
    for order in orders:
        try:
            items = apify.threads_search(
                sc["keywords"], sort_order=order, max_posts=sc["max_posts_per_keyword"]
            )
        except ApiError as e:
            log(f"  !! Threads search ({order}) 失敗: {e}", warn=True)
            continue
        log(f"  Threads search [{order}]: {len(items)} 條原始")
        for it in items:
            out.append(
                {
                    "url": it.get("post_url"),
                    "platform": "threads",
                    "author": it.get("username"),
                    "date": ts_to_date(it.get("created_at_timestamp")),
                    "text": (it.get("text_content") or "").strip(),
                    "likes": it.get("like_count"),
                    "replies": it.get("reply_count"),
                    "source_channel": f"threads-search-{order}",
                    "quoted": it.get("quoted_post_url"),
                    "reposted": it.get("reposted_post_url"),
                }
            )
    return out


def discover_threads_watchlist(tik, cfg, learned, log, budget_s=420):
    """逐個 watchlist 帳號拉最新帖 —— 補搜尋窗口盲點。

    TikHub 端點間歇性失敗，所以設全階段時間預算：跑到時限就停，
    並喺報告出警報（覆蓋唔完整好過整個 sweep 掛住幾個鐘）。
    """
    import time as _t

    out = []
    names = list(dict.fromkeys(cfg["watchlist_threads"] + learned.get("threads", [])))
    ok = fail = 0
    t0 = _t.time()
    skipped = []
    for idx, name in enumerate(names):
        if _t.time() - t0 > budget_s:
            skipped = names[idx:]
            log(
                f"  !! watchlist 時間預算 {budget_s}s 用完，跳過剩餘 {len(skipped)} 個帳號："
                f"{', '.join(skipped[:8])}{'...' if len(skipped) > 8 else ''}",
                warn=True,
            )
            break
        ui = tik.threads_user_info(name)
        pk = ((ui or {}).get("data") or {}).get("user", {}).get("pk") if ui else None
        if not pk:
            fail += 1
            continue
        fp = tik.threads_user_posts(pk)
        md = ((fp or {}).get("data") or {}).get("mediaData") or {}
        n = 0
        for e in md.get("edges", []):
            for ti in e.get("node", {}).get("thread_items", []):
                p = ti.get("post") or {}
                cap = (p.get("caption") or {}).get("text") or ""
                code = p.get("code")
                if not code:
                    continue
                out.append(
                    {
                        "url": f"https://www.threads.com/@{name}/post/{code}",
                        "platform": "threads",
                        "author": name,
                        "date": ts_to_date(p.get("taken_at")),
                        "text": cap.strip(),
                        "likes": p.get("like_count"),
                        "replies": (p.get("text_post_app_info") or {}).get(
                            "direct_reply_count"
                        ),
                        "source_channel": "threads-watchlist",
                    }
                )
                n += 1
        ok += 1
    elapsed = int(_t.time() - t0)
    log(
        f"  Threads watchlist: {ok} 成功 / {fail} 失敗 / {len(skipped)} 跳過"
        f"，收 {len(out)} 條帖（{elapsed}s）"
    )
    if fail > ok:
        log("  !! 過半帳號抽取失敗（TikHub flaky）—— 本次覆蓋可能唔完整", warn=True)
    return out


def discover_instagram(tik, cfg, log):
    out = []
    for tag in cfg.get("instagram_hashtags", []):
        d = tik.ig_hashtag_posts(tag)
        if not d:
            log(f"  !! IG hashtag #{tag} 抽唔到", warn=True)
            continue
        items = _dig_ig_items(d)
        log(f"  IG #{tag}: {len(items)} 條")
        out.extend(items)
    return out


def _dig_ig_items(payload):
    """IG 回應結構浮動，遞歸搵有 code/caption 嘅節點。"""
    found = []

    def walk(o):
        if isinstance(o, dict):
            code = o.get("code") or o.get("shortcode")
            if code and ("caption" in o or "user" in o):
                cap = o.get("caption")
                text = ""
                if isinstance(cap, dict):
                    text = cap.get("text") or ""
                elif isinstance(cap, str):
                    text = cap
                user = o.get("user") or {}
                found.append(
                    {
                        "url": f"https://www.instagram.com/p/{code}/",
                        "platform": "instagram",
                        "author": user.get("username") if isinstance(user, dict) else None,
                        "date": ts_to_date(o.get("taken_at")),
                        "text": text.strip(),
                        "likes": o.get("like_count"),
                        "replies": o.get("comment_count"),
                        "source_channel": "ig-hashtag",
                    }
                )
                return
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(payload.get("data", payload))
    return found


# ---------------- L2: 抽取留言 ----------------

def _threads_caption(p):
    cap = p.get("caption")
    if isinstance(cap, dict):
        return (cap.get("text") or "").strip()
    return (cap or "").strip() if isinstance(cap, str) else ""


def pull_threads_comments(tik, url, log, max_child_walks=15):
    """Threads 留言，包括 nested replies。

    fetch_post_detail_v2 只回頂層；每條 reply 本身係一個 post，
    有 direct_reply_count 就要用佢自己嘅 URL 再 detail 一次先攞到下層
    （2026-08 人手對數發現：淨頂層會漏 ~1/3 留言，而且 nested 層
    跑手密度最高）。max_child_walks 限 API 開支，drc 大嗰啲行先。
    """
    d = tik.threads_post_detail(url)
    posts = ((d or {}).get("data") or {}).get("posts") or []
    if not posts:
        return None, []
    root = posts[0]
    root_code = root.get("code")
    detail = {
        "text": _threads_caption(root),
        "likes": root.get("like_count"),
        "date": ts_to_date(root.get("taken_at")),
        "author": (root.get("user") or {}).get("username"),
    }

    comments = []
    seen_codes = {root_code}

    def add_post(p, depth):
        code = p.get("code")
        if not code or code in seen_codes:
            return
        seen_codes.add(code)
        txt = _threads_caption(p)
        if not txt:
            return
        comments.append(
            {
                "author": (p.get("user") or {}).get("username"),
                "text": txt,
                "likes": p.get("like_count"),
                "depth": depth,
                "speaker": classify.speaker_type(txt),
                "labels": classify.label_text(txt),
            }
        )

    tops = posts[1:]
    for p in tops:
        add_post(p, 0)

    walkable = sorted(
        (p for p in tops if p.get("direct_reply_count")),
        key=lambda p: -(p.get("direct_reply_count") or 0),
    )
    skipped = len(walkable) - max_child_walks if len(walkable) > max_child_walks else 0
    for p in walkable[:max_child_walks]:
        if tik.budget_exhausted():
            log(f"   （nested walk 中止：TikHub 時間預算用完，剩 {len(walkable)} 條未行）")
            break
        u = (p.get("user") or {}).get("username")
        code = p.get("code")
        if not u or not code:
            continue
        d2 = tik.threads_post_detail(f"https://www.threads.com/@{u}/post/{code}")
        for q in ((d2 or {}).get("data") or {}).get("posts") or []:
            add_post(q, 1)
    if skipped:
        log(f"   （nested walk 上限 {max_child_walks}，跳過咗 {skipped} 條低回覆數嘅）")
    return detail, comments


def pull_ig_comments(tik, url, log, max_child_walks=10):
    """IG 留言，包括 nested replies。

    fetch_post_comments 只回頂層；child_comment_count > 0 嘅要另 call
    fetch_comment_replies 先攞到下層。max_child_walks 限 API 開支。
    """
    m = re.search(r"/p/([A-Za-z0-9_-]+)", url)
    if not m:
        return []
    code = m.group(1)
    d = tik.ig_comments(code)
    if not d:
        return []
    inner = (d.get("data") or {})
    inner = inner.get("data", inner)
    items = inner.get("items") or inner.get("comments") or []
    out = []

    def add_item(c, depth):
        txt = (c.get("text") or "").strip()
        if not txt:
            return
        u = c.get("user") or {}
        out.append(
            {
                "author": u.get("username") if isinstance(u, dict) else c.get("username"),
                "text": txt,
                "likes": c.get("comment_like_count") or c.get("like_count"),
                "depth": depth,
                "speaker": classify.speaker_type(txt),
                "labels": classify.label_text(txt),
            }
        )

    for c in items:
        add_item(c, 0)

    walkable = sorted(
        (c for c in items if (c.get("child_comment_count") or 0) > 0),
        key=lambda c: -(c.get("child_comment_count") or 0),
    )
    for c in walkable[:max_child_walks]:
        if tik.budget_exhausted():
            log("   （IG nested walk 中止：TikHub 時間預算用完）")
            break
        cid = c.get("pk") or c.get("id")
        if not cid:
            continue
        d2 = tik.ig_comment_replies(code, cid)
        inner2 = ((d2 or {}).get("data") or {})
        inner2 = inner2.get("data", inner2)
        for q in inner2.get("items") or []:
            add_item(q, 1)
    if len(walkable) > max_child_walks:
        log(f"   （IG nested walk 上限 {max_child_walks}，跳過 {len(walkable)-max_child_walks} 條）")
    return out


# ---------------- 主流程 ----------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--light", action="store_true", help="輕掃：只行 Threads recent 搜尋")
    ap.add_argument("--no-comments", action="store_true", help="唔抽留言")
    ap.add_argument("--dry-run", action="store_true", help="唔寫 master")
    ap.add_argument("--max-comment-pulls", type=int, default=25)
    args = ap.parse_args()

    cfg = load_cfg()
    store.ensure_dirs()
    run_id = store.now_hkt().strftime("%Y%m%d_%H%M")
    logs = []
    warns = []

    def log(msg, warn=False):
        print(msg)
        logs.append(msg)
        if warn:
            warns.append(msg)

    log(f"=== SCHKM sweep {run_id} ({'light' if args.light else 'full'}) ===")

    tik = TikHub()
    apify = Apify()
    master = store.load_master()
    learned = store.load_learned_watchlist()
    before = set(master.get("items", {}).keys())

    # --- L1 發現 ---
    log("[L1] 發現層")
    cands = []
    cands += discover_threads_search(apify, cfg, args.light, log)
    if not args.light:
        cands += discover_threads_watchlist(tik, cfg, learned, log)
        cands += discover_instagram(tik, cfg, log)

    # 引用鏈：quoted/reposted 自動變候選
    extra = []
    for c in cands:
        for k in ("quoted", "reposted"):
            u = c.get(k)
            if u:
                extra.append(
                    {
                        "url": u,
                        "platform": "threads",
                        "source_channel": "quote-chain",
                        "text": "",
                    }
                )
    if extra:
        log(f"  引用鏈: {len(extra)} 條候選")
        cands += extra

    log(f"  候選合計（未去重）: {len(cands)}")
    store.save_raw(run_id, "candidates_raw", cands)

    # --- L3 過濾分類 ---
    log("[L3] 過濾分類")
    seen = {}
    noise_n = 0
    bank_n = 0
    for c in cands:
        u = store.canon_url(c.get("url"))
        if not u:
            continue
        txt = c.get("text") or ""
        if txt and classify.is_noise(txt, cfg):
            if classify.is_bank_line(txt):
                bank_n += 1
            noise_n += 1
            continue
        if u in seen:
            # 保留資料較全嗰個
            if len(txt) > len(seen[u].get("text") or ""):
                seen[u].update({k: v for k, v in c.items() if v})
            continue
        c["url"] = u
        c["issue_labels"] = classify.label_text(txt) if txt else []
        c["relevance"] = classify.relevance(txt) if txt else "unknown"
        c["cycle"] = classify.cycle_of(c, cfg)
        seen[u] = c
    log(f"  剔走噪音 {noise_n} 條（其中銀行線 {bank_n}）；保留 {len(seen)} 條唯一")

    # --- L2 抽留言（只抽新帖 + 高互動）---
    new_urls = [u for u in seen if u not in before]
    log(f"[L2] 新帖 {len(new_urls)} 條")
    if not args.no_comments:
        targets = sorted(
            new_urls,
            key=lambda u: -(seen[u].get("replies") or 0),
        )[: args.max_comment_pulls]
        log(f"  抽留言 target: {len(targets)} 條（按回覆數排序）")
        for u in targets:
            item = seen[u]
            if item["platform"] == "threads":
                detail, comments = pull_threads_comments(tik, u, log)
                if detail:
                    for k, v in detail.items():
                        if v:
                            item[k] = v
                    item["issue_labels"] = classify.label_text(item.get("text", ""))
                    item["relevance"] = classify.relevance(item.get("text", ""))
                item["comments"] = comments
                item["comments_pulled"] = len(comments)
            elif item["platform"] == "instagram":
                comments = pull_ig_comments(tik, u, log)
                item["comments"] = comments
                item["comments_pulled"] = len(comments)

    # --- 雪球：新相關帖作者入 watchlist ---
    added = []
    for u in new_urls:
        it = seen[u]
        if it.get("relevance") in ("direct", "adjacent") and it.get("author"):
            a = it["author"]
            if a not in cfg["watchlist_threads"] and a not in learned.get("threads", []):
                learned.setdefault("threads", []).append(a)
                added.append(a)
    if added:
        log(f"  雪球新增 watchlist: {', '.join(added)}")

    # --- L4 diff + 報告 ---
    stats = {"new": 0, "updated": 0, "same": 0}
    for u, it in seen.items():
        st, _ = store.upsert(master, it)
        if st in stats:
            stats[st] += 1

    master.setdefault("runs", []).append(
        {
            "run_id": run_id,
            "mode": "light" if args.light else "full",
            "candidates": len(cands),
            "unique": len(seen),
            "new": stats["new"],
            "tikhub_calls": tik.calls,
            "warnings": len(warns),
        }
    )

    if not args.dry_run:
        store.save_master(master)
        store.save_learned_watchlist(learned)

    report = build_report(run_id, args, seen, new_urls, master, stats, cfg, logs, warns, tik, apify)
    rp = os.path.join(ROOT, "reports", f"run_{run_id}.md")
    with open(rp, "w", encoding="utf-8") as f:
        f.write(report)
    log(f"\n報告已寫入: {rp}")
    print("\n" + "=" * 60)
    print(f"新帖 {stats['new']} 條 | 更新 {stats['updated']} | 警告 {len(warns)} 個")
    print(f"下一步：人手核對 {rp}，剔完 checklist 後行 apply_deck.py")


def build_report(run_id, args, seen, new_urls, master, stats, cfg, logs, warns, tik, apify):
    L = []
    A = L.append
    A(f"# SCHKM 輿情掃描報告 — {run_id}")
    A("")
    A(f"- 模式：{'輕掃 (light)' if args.light else '全渠道深掃 (full)'}")
    A(f"- 唯一候選：{len(seen)}｜**新帖：{stats['new']}**｜更新：{stats['updated']}")
    A(f"- 資料庫累計：{len(master.get('items', {}))} 條")

    # --- 齊全度指標：fresh vs backfill ---
    # fresh = 30日窗內發佈（新內容，執到係系統正常運作）
    # backfill = 30日窗外發佈（舊帖補漏——呢個數連續兩個 run 歸零，
    #            就係「歷史覆蓋已收斂」嘅可驗證證據）
    import datetime as _dt

    win = (_dt.date.today() - _dt.timedelta(days=30)).isoformat()
    fresh_n = sum(1 for u in new_urls if (seen[u].get("date") or "") >= win)
    backfill_n = len(new_urls) - fresh_n
    A(f"- **齊全度指標**：新帖中 fresh（30日內發佈）{fresh_n} 條｜"
      f"backfill（舊帖補漏）{backfill_n} 條")
    if backfill_n > 5:
        A(f"  - ⚠️ backfill 偏高——渠道/關鍵詞有變動，或上次覆蓋有洞；"
          f"下次同一設定重跑，此數應大幅回落")
    elif backfill_n == 0:
        A("  - ✅ backfill = 0：歷史覆蓋喺現有渠道設定下已收斂")
    cyc_counter = {}
    for u in new_urls:
        cyc_counter[seen[u].get("cycle", "?")] = cyc_counter.get(seen[u].get("cycle", "?"), 0) + 1
    A(f"- 週期分佈（新帖）：{'｜'.join(f'{k}: {v}' for k, v in sorted(cyc_counter.items(), reverse=True))}"
      f"（focus = {cfg.get('focus_cycle', '2027')}）")
    bal = tik.balance()
    if bal is not None:
        A(f"- TikHub 餘額：${bal:.3f}（本次 {tik.calls} calls）")
    usage = apify.month_usage_usd()
    if usage is not None:
        A(f"- Apify 本月用量：${usage:.2f}")
    A("")

    if warns:
        A("## ⚠️ 渠道健康警報")
        A("")
        A("> 「靜」唔等於「冇嘢」——以下渠道本次有問題，覆蓋可能唔完整：")
        A("")
        for w in warns:
            A(f"- {w}")
        A("")

    # 議題分佈
    from collections import Counter

    lab_counter = Counter()
    for u in new_urls:
        for lab in seen[u].get("issue_labels") or []:
            lab_counter[lab] += 1
    if lab_counter:
        A("## 議題標籤分佈（本次新帖）")
        A("")
        A("| 議題 | 條數 |")
        A("|---|---|")
        for lab, n in lab_counter.most_common():
            flag = " ⚠️新議題" if lab == "other" and n >= 3 else ""
            A(f"| {lab}{flag} | {n} |")
        A("")

    # 新帖清單 —— focus 週期行先，舊週期收埋做背景
    focus = cfg.get("focus_cycle", "2027")
    focus_urls = [u for u in new_urls if seen[u].get("cycle") == focus]
    other_urls = [u for u in new_urls if seen[u].get("cycle") != focus]

    A(f"## 本次新帖（渣馬{focus}週期，待核對）")
    A("")
    if not focus_urls:
        A("_（無新帖）_")
        A("")
    else:
        rows = sorted(focus_urls, key=lambda u: (seen[u].get("date") or ""), reverse=True)
        for u in rows:
            it = seen[u]
            A(f"### [ ] {it.get('date') or '?'} @{it.get('author') or '?'} ({it['platform']})")
            A("")
            A(f"- 連結：{u}")
            A(
                f"- 相關度：`{it.get('relevance')}`｜標籤：`{', '.join(it.get('issue_labels') or [])}`"
                f"｜♥{it.get('likes')}｜帖面回覆 {it.get('replies')}｜實抽留言 {it.get('comments_pulled', 0)}"
            )
            A(f"- 渠道：`{it.get('source_channel')}`")
            txt = (it.get("text") or "").replace("\n", " ")
            A(f"- 內文：{txt[:200]}")
            cs = it.get("comments") or []
            if cs:
                A("- 留言樣本：")
                for c in cs[:5]:
                    A(
                        f"    - `{c.get('speaker')}` @{c.get('author')}: "
                        f"{(c.get('text') or '')[:120]}".replace("\n", " ")
                    )
            A("")

    if other_urls:
        A(f"## 舊週期背景（{len(other_urls)} 條，唔入 {focus} annex，只作歷史脈絡）")
        A("")
        for u in sorted(other_urls, key=lambda x: (seen[x].get("date") or ""), reverse=True):
            it = seen[u]
            A(
                f"- `{it.get('cycle')}` {it.get('date')} @{it.get('author')} "
                f"[{it.get('relevance')}] ♥{it.get('likes')} — {u}"
            )
        A("")

    A("## 人手核對清單")
    A("")
    A("逐項剔，全部剔晒先好行 `apply_deck.py`：")
    A("")
    A("- [ ] 每條新帖連結開得到、內容對版")
    A("- [ ] 相關度／議題標籤分類正確（錯就改 master.json 嘅 `issue_labels_confirmed`）")
    A("- [ ] 發言人分類（runner / spectator）抽樣核對過")
    A("- [ ] 渠道健康警報已處理（如有）")
    A("- [ ] 「other」標籤帖檢視過——有冇新議題要開新 row？")
    A("- [ ] 反爬平台（LIHKG / HKDiscuss）已人手開過")
    A("- [ ] eyeball 抽查：本週你哋見到但系統冇執到嘅帖 → `/schkm-add <url>` 補入，並記錄為 miss")
    A("")
    A("### 反爬平台待人手開")
    A("")
    for s in cfg.get("forum_discovery", {}).get("site_searches", []):
        A(f"- [ ] `{s}`")
    A("")
    A("## 運行日誌")
    A("")
    A("```")
    for line in logs:
        A(line)
    A("```")
    return "\n".join(L)


if __name__ == "__main__":
    main()
