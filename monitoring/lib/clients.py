"""TikHub / Apify 客戶端。全部經 curl subprocess（呢個環境嘅 agent proxy 唔認 urllib）。"""
import json
import os
import subprocess
import time
import urllib.parse

TIKHUB_BASE = "https://api.tikhub.io/api/v1"
APIFY_BASE = "https://api.apify.com/v2"


class ApiError(Exception):
    pass


def _curl(url, headers=None, method="GET", body=None, timeout=120):
    cmd = ["curl", "-sS", "--max-time", str(timeout)]
    for k, v in (headers or {}).items():
        cmd += ["-H", f"{k}: {v}"]
    if method != "GET":
        cmd += ["-X", method]
    if body is not None:
        cmd += ["-d", body]
    cmd.append(url)
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise ApiError(f"curl failed: {r.stderr[:200]}")
    return r.stdout


def _token(env_name, label):
    tok = os.environ.get(env_name, "").strip()
    if not tok:
        raise ApiError(
            f"環境變數 {env_name} 未設定。請 export {env_name}=... 再運行（{label}）"
        )
    return tok


# ---------------- TikHub ----------------

class TikHub:
    """Threads + Instagram 抽取。端點間歇性 flaky，全部有 retry。"""

    # 端點間歇性 400，但重試太狠會令整個 watchlist 階段跑幾個鐘。
    # 用「單次呼叫短 timeout + 少重試 + 全域時間預算」三重限制。
    CALL_TIMEOUT = 25
    DEFAULT_TRIES = 2

    def __init__(self, budget_seconds=None):
        self.token = _token("TIKHUB_API_KEY", "TikHub")
        self.calls = 0
        self.failures = 0
        self._budget = budget_seconds
        self._start = time.time()

    def budget_exhausted(self):
        return self._budget is not None and (time.time() - self._start) > self._budget

    def get(self, path, tries=None, **params):
        tries = tries or self.DEFAULT_TRIES
        url = f"{TIKHUB_BASE}/{path}?" + urllib.parse.urlencode(params)
        last = None
        for i in range(tries):
            if self.budget_exhausted():
                raise ApiError(f"TikHub 時間預算用完，跳過 {path}")
            self.calls += 1
            try:
                out = _curl(
                    url,
                    {"Authorization": f"Bearer {self.token}"},
                    timeout=self.CALL_TIMEOUT,
                )
                d = json.loads(out)
            except Exception as e:  # noqa: BLE001
                last = str(e)[:120]
                if i < tries - 1:
                    time.sleep(1.0)
                continue
            if "detail" not in d:
                return d
            last = (d.get("detail") or {}).get("message", "")[:120]
            if i < tries - 1:
                time.sleep(1.0)
        self.failures += 1
        raise ApiError(f"TikHub {path} failed after {tries} tries: {last}")

    def try_get(self, path, **params):
        """失敗返 None 而唔係拋錯 —— 用於可容忍缺失嘅呼叫。"""
        try:
            return self.get(path, **params)
        except ApiError:
            return None

    # -- Threads --
    def threads_post_detail(self, url):
        return self.try_get("threads/web/fetch_post_detail_v2", url=url)

    def threads_comments(self, post_id):
        return self.try_get("threads/web/fetch_post_comments", post_id=post_id)

    def threads_user_info(self, username):
        return self.try_get("threads/web/fetch_user_info", username=username)

    def threads_user_posts(self, user_id):
        return self.try_get("threads/web/fetch_user_posts", user_id=user_id)

    # -- Instagram --
    def ig_shortcode_to_media_id(self, shortcode):
        return self.try_get("instagram/v1/shortcode_to_media_id", shortcode=shortcode)

    def ig_comments(self, code_or_url, pagination_token=None):
        p = {"code_or_url": code_or_url}
        if pagination_token:
            p["pagination_token"] = pagination_token
        return self.try_get("instagram/v2/fetch_post_comments", **p)

    def ig_hashtag_posts(self, hashtag, end_cursor=None):
        p = {"hashtag": hashtag}
        if end_cursor:
            p["end_cursor"] = end_cursor
        return self.try_get("instagram/v1/fetch_hashtag_posts", **p)

    def ig_user_posts(self, username):
        return self.try_get("instagram/v1/fetch_user_posts", username=username)

    def balance(self):
        d = self.try_get("tikhub/user/get_user_info")
        if not d:
            return None
        return (d.get("user_data") or {}).get("balance")


# ---------------- Apify ----------------

class Apify:
    """Threads 關鍵詞搜尋（有日期範圍）＋ Facebook。"""

    THREADS_ACTOR = "futurizerush~meta-threads-scraper"

    def __init__(self):
        self.token = _token("APIFY_TOKEN", "Apify")
        self.runs = []

    def run_actor_sync(self, actor, payload, timeout_s=280):
        url = (
            f"{APIFY_BASE}/acts/{actor}/run-sync-get-dataset-items"
            f"?timeout={timeout_s}&format=json"
        )
        out = _curl(
            url,
            {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"},
            method="POST",
            body=json.dumps(payload, ensure_ascii=False),
            timeout=timeout_s + 30,
        )
        try:
            data = json.loads(out)
        except Exception as e:  # noqa: BLE001
            raise ApiError(f"Apify {actor} bad JSON: {out[:200]}") from e
        if isinstance(data, dict) and data.get("error"):
            raise ApiError(f"Apify {actor}: {data['error'].get('message','')[:200]}")
        return data

    def threads_search(self, keywords, sort_order="recent", max_posts=100, start_date=None):
        payload = {
            "mode": "search",
            "keywords": keywords,
            "max_posts": max_posts,
            "search_filter": sort_order,  # 必須小寫 top / recent
        }
        if start_date:
            payload["start_date"] = start_date
        return self.run_actor_sync(self.THREADS_ACTOR, payload)

    def threads_user_posts(self, usernames, max_posts=50):
        return self.run_actor_sync(
            self.THREADS_ACTOR,
            {"mode": "user", "usernames": usernames, "max_posts": max_posts},
        )

    def month_usage_usd(self):
        try:
            out = _curl(
                f"{APIFY_BASE}/users/me/usage/monthly",
                {"Authorization": f"Bearer {self.token}"},
                timeout=30,
            )
            d = json.loads(out).get("data", {})
            return d.get("totalUsageCreditsUsdAfterVolumeDiscount") or d.get(
                "totalUsageCreditsUsd"
            )
        except Exception:  # noqa: BLE001
            return None
