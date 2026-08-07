"""資料庫層：master.json 係唯一真相來源，raw/ 存原始 API 回應（審計用，永不刪）。"""
import json
import os
import re
from datetime import datetime, timezone, timedelta

HKT = timezone(timedelta(hours=8))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
RAW = os.path.join(DATA, "raw")
MASTER = os.path.join(DATA, "master.json")
WATCH = os.path.join(DATA, "watchlist_learned.json")


def now_hkt():
    return datetime.now(HKT)


def today_str():
    return now_hkt().strftime("%Y-%m-%d")


def ensure_dirs():
    os.makedirs(RAW, exist_ok=True)
    os.makedirs(os.path.join(ROOT, "reports"), exist_ok=True)
    os.makedirs(os.path.join(ROOT, "out"), exist_ok=True)


def canon_url(u):
    """統一 URL 形式，避免同一帖因 www/尾斜線/query 被當兩條。"""
    if not u:
        return ""
    u = u.strip().split("?")[0].rstrip("/")
    u = u.replace("threads.net", "threads.com")
    u = re.sub(r"^http://", "https://", u)
    return u


def load_master():
    if not os.path.exists(MASTER):
        return {"items": {}, "runs": []}
    with open(MASTER, encoding="utf-8") as f:
        return json.load(f)


def save_master(m):
    ensure_dirs()
    with open(MASTER, "w", encoding="utf-8") as f:
        json.dump(m, f, ensure_ascii=False, indent=1, sort_keys=True)


def load_learned_watchlist():
    if not os.path.exists(WATCH):
        return {"threads": [], "instagram": []}
    with open(WATCH, encoding="utf-8") as f:
        return json.load(f)


def save_learned_watchlist(w):
    ensure_dirs()
    with open(WATCH, "w", encoding="utf-8") as f:
        json.dump(w, f, ensure_ascii=False, indent=1, sort_keys=True)


def save_raw(run_id, name, obj):
    ensure_dirs()
    d = os.path.join(RAW, run_id)
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, f"{name}.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False)
    return p


def upsert(master, item):
    """插入或更新一條帖。回傳 ('new'|'updated'|'same', 舊留言數)。"""
    u = canon_url(item.get("url"))
    if not u:
        return ("skip", 0)
    item["url"] = u
    items = master.setdefault("items", {})
    old = items.get(u)
    if old is None:
        item.setdefault("first_seen", today_str())
        item.setdefault("review_status", "pending")
        items[u] = item
        return ("new", 0)

    old_n = old.get("comments_pulled") or 0
    new_n = item.get("comments_pulled") or 0
    changed = False
    # 只補資料、唔覆蓋人手核對過嘅欄位
    for k, v in item.items():
        if k in ("first_seen", "review_status", "human_notes", "issue_labels_confirmed"):
            continue
        if v in (None, "", [], {}):
            continue
        if old.get(k) != v:
            old[k] = v
            changed = True
    old["last_seen"] = today_str()
    if new_n > old_n:
        old["comments_delta"] = new_n - old_n
        return ("updated", old_n)
    return ("updated" if changed else "same", old_n)
