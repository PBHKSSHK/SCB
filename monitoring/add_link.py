#!/usr/bin/env python3
"""人手補漏 —— 將 eyeball 見到但 crawler 漏咗嘅連結入庫，並自動抽留言。

用法:
    python monitoring/add_link.py <url> [<url2> ...]
    python monitoring/add_link.py <url> --note "點解要加"

會記錄 source_channel="human-add"，方便日後統計 crawler 漏咗幾多、漏喺邊。
"""
import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import classify, store  # noqa: E402
from lib.clients import TikHub  # noqa: E402


def detect_platform(url):
    if "threads." in url:
        return "threads"
    if "instagram.com" in url:
        return "instagram"
    if "facebook.com" in url:
        return "facebook"
    if "lihkg.com" in url:
        return "lihkg"
    if "discuss.com.hk" in url:
        return "hkdiscuss"
    return "news"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("urls", nargs="+")
    ap.add_argument("--note", default="")
    ap.add_argument("--no-comments", action="store_true")
    args = ap.parse_args()

    master = store.load_master()
    tik = None
    if not args.no_comments:
        try:
            tik = TikHub()
        except Exception as e:  # noqa: BLE001
            print(f"（無法抽留言：{e}）")

    import sweep

    for url in args.urls:
        u = store.canon_url(url)
        plat = detect_platform(u)
        item = {
            "url": u,
            "platform": plat,
            "source_channel": "human-add",
            "origin": "human-add",
            "human_notes": args.note,
            "review_status": "approved",  # 人手加入 = 已核實
        }

        if tik and plat == "threads":
            detail, comments = sweep.pull_threads_comments(tik, u, lambda *a, **k: None)
            if detail:
                for k, v in detail.items():
                    if v:
                        item[k] = v
            item["comments"] = comments
            item["comments_pulled"] = len(comments)
        elif tik and plat == "instagram":
            item["comments"] = sweep.pull_ig_comments(tik, u, lambda *a, **k: None)
            item["comments_pulled"] = len(item["comments"])

        txt = item.get("text") or ""
        item["issue_labels"] = classify.label_text(txt) if txt else []
        item["relevance"] = classify.relevance(txt) if txt else "unknown"

        st, _ = store.upsert(master, item)
        print(f"[{st}] {plat} {u}")
        if item.get("text"):
            print(f"   內文: {item['text'][:100]}")
        print(f"   標籤: {', '.join(item['issue_labels'])} | 留言 {item.get('comments_pulled', 0)} 條")

        # 作者自動入 watchlist
        a = item.get("author")
        if a and plat == "threads":
            w = store.load_learned_watchlist()
            if a not in w.get("threads", []):
                w.setdefault("threads", []).append(a)
                store.save_learned_watchlist(w)
                print(f"   → @{a} 已加入 watchlist")

    store.save_master(master)
    n_miss = sum(
        1 for it in master["items"].values() if it.get("source_channel") == "human-add"
    )
    print(f"\n完成。資料庫 {len(master['items'])} 條，其中人手補入 {n_miss} 條")
    if n_miss >= 5:
        print("⚠️ 人手補入已達 5+ 條 —— 建議檢視 config.json 嘅關鍵詞/watchlist 有冇要加")


if __name__ == "__main__":
    main()
