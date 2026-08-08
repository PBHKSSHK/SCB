"""LIHKG 討論串抓取 —— 免費，無需第三方 API。

關鍵：api_v2 端點對 datacenter IP 會回 403，但只要帶
`Referer: https://lihkg.com/thread/<tid>` 就通（實測 200）。
HTML 頁面係 SPA 殼（__PRELOADED_STATE__，無留言內文），唔可以靠佢。

HKDiscuss 係 Cloudflare JS 挑戰（「Just a moment...」），curl 破唔到，
要 headless browser——見 forum_discovery，維持人手或另開 Playwright 通路。
"""
import json
import re
import subprocess
import time

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


def _strip(html):
    return re.sub(r"<[^>]+>", "", html or "").replace("\r", " ").strip()


def _curl(url, tid):
    cmd = [
        "curl", "-sS", "--max-time", "25",
        "-H", f"User-Agent: {UA}",
        "-H", f"Referer: https://lihkg.com/thread/{tid}",
        "-H", "Accept: application/json",
        url,
    ]
    return subprocess.run(cmd, capture_output=True, text=True).stdout


def thread_id_from_url(url):
    m = re.search(r"/thread/(\d+)", url or "")
    return m.group(1) if m else None


def fetch_thread(tid, max_pages=20):
    """回傳 (meta, comments[])。comments 每條含 author/text/like/dislike/msg_num。"""
    meta = {}
    comments = []
    page = 1
    while page <= max_pages:
        raw = _curl(
            f"https://lihkg.com/api_v2/thread/{tid}/page/{page}?order=reply_time",
            tid,
        )
        try:
            d = json.loads(raw)
        except Exception:  # noqa: BLE001
            break
        if not d.get("success"):
            break
        r = d.get("response", {})
        if page == 1:
            meta = {
                "tid": tid,
                "title": r.get("title"),
                "cat": (r.get("category") or {}).get("name"),
                "total_page": r.get("total_page", 1),
                "no_of_reply": r.get("no_of_reply"),
                "like_count": r.get("like_count"),
                "dislike_count": r.get("dislike_count"),
            }
        for p in r.get("item_data", []):
            comments.append(
                {
                    "author": (p.get("user") or {}).get("nickname"),
                    "text": _strip(p.get("msg")),
                    "like": p.get("like_count"),
                    "dislike": p.get("dislike_count"),
                    "msg_num": p.get("msg_num"),
                }
            )
        if page >= r.get("total_page", 1):
            break
        page += 1
        time.sleep(0.4)
    # 去重（同一 msg_num）
    seen, uniq = set(), []
    for c in comments:
        k = c.get("msg_num")
        if k in seen:
            continue
        seen.add(k)
        uniq.append(c)
    return meta, uniq


def health_check():
    """回傳 (ok: bool, detail: str) —— 畀 sweep 渠道健康警報用。"""
    raw = _curl("https://lihkg.com/api_v2/thread/4063805/page/1", "4063805")
    try:
        d = json.loads(raw)
        if d.get("success"):
            return True, "LIHKG api_v2 OK"
        return False, f"LIHKG 回應 success!=1：{str(d)[:80]}"
    except Exception as e:  # noqa: BLE001
        return False, f"LIHKG 抓取失敗（可能 IP 被封或改咗防護）：{str(e)[:80]}"
