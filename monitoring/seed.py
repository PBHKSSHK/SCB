#!/usr/bin/env python3
"""種子入庫 —— 將 deck annex 已有連結 + 已核實嘅歷史帖一次過入 master.json。

呢批係「開機之前」嘅歷史資料，Threads 30日搜尋窗口追唔返，
所以用人手核實過嘅清單封存做基線。之後靠 sweep.py 向前保底。

用法: python monitoring/seed.py [--pull-comments]
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import classify, store  # noqa: E402

ROOT = os.path.dirname(os.path.abspath(__file__))

# ---- 你哋 deck annex 14/15 頁嘅 12 條（origin=deck-annex）----
DECK_ANNEX = [
    ("https://www.instagram.com/p/DTkSKqPgcpc/", "instagram", "sportsroad.hk", "2026-01-16",
     "渣馬｜報名人數再創新高 田總稱考慮未來分兩日舉辦", 72),
    ("https://www.threads.com/@martin3388/post/DTs9Cu5k93b", "threads", "martin3388", "2026-01-19",
     "香港渣馬其實係現有賽道下，最大問題係半馬要就全馬加唔到位，所以半馬同全馬要分開星期六日搞", 20),
    ("https://www.threads.com/@kk30gsw/post/DTsVTMIEkiG", "threads", "kk30gsw", "2026-01-19",
     "有人提出渣馬分兩日舉行，我分析一下：最合理係星期六跑10k，星期日跑半馬+全馬", 37),
    ("https://www.threads.com/@ericchan326/post/DPXiGLhkkyd", "threads", "ericchan326", "2025-10-04",
     "其實渣馬會唔會學吓其他地方，考慮將breakfast run同真正馬拉松分開兩日搞", 35),
    ("https://www.threads.com/@sunnychan1987/post/DTxnQkgiCTn", "threads", "sunnychan1987", "2026-01-21",
     "而家討論緊香港渣馬分唔分兩日搞 其實瑞士同澳洲都做緊 日內瓦同黃金海岸馬拉松星期六傍晚跑小型嘅", 0),
    ("https://www.threads.com/@fitz.hk/post/DTrQQPIjz9D", "threads", "fitz.hk", "2026-01-19",
     "渣馬分兩日搞? | 霍啟剛倡一日市區一日北都 田總: 成立特別小組研究新路線", 43),
    ("https://www.facebook.com/share/p/1EJQtS3aXn/", "facebook", "fitz.hk", "2026-01-19",
     "渣馬分兩日搞? | 霍啟剛倡一日市區一日北都（FB版）", 150),
    ("https://www.instagram.com/p/DUXJsL1DNl8/", "instagram", "inmediahk", "2026-01",
     "議員倡分兩日舉行 一日專業賽事一日與眾同樂", 172),
    ("https://lihkg.com/thread/4063805/page/1", "lihkg", None, "2026-01",
     "【渣打馬拉松】議員倡分兩日舉行 一日專業賽事一日與眾同樂", 23),
    ("https://lihkg.com/thread/4056286/page/2", "lihkg", None, "2026-01",
     "霍啟剛倡：渣打馬拉松分兩日舉行 有助宣傳北都", 29),
    ("https://www.facebook.com/photo/?fbid=1392561962908593&set=a.551884776976320", "facebook", "DiscussHK", "2026-04-15",
     "渣馬考慮分兩日跑！跑手反應兩極", 15),
    ("https://www.discuss.com.hk/redirect.php?goto=findpost&pid=576343357&ptid=32200587", "hkdiscuss", None, "2026-04",
     "大棋盤︱渣馬研分兩日舉行 封路安排費思量", 42),
]

# ---- 我今次核實、deck 未有嘅（origin=claude-verified）----
EXTRA = [
    ("https://www.threads.com/@martin3388/post/DPZIbptD4Ht", "threads", "martin3388", "2025-10-04",
     "下年第八度挑戰香港渣馬最終失敗! 雖然有問過慈善位,但係價錢非常瘋狂", 1),
    ("https://www.threads.com/@martin3388/post/DTnCeWZD-56", "threads", "martin3388", "2026-01-17",
     "屬會報名有問題報唔到，公眾抽籤兩輪都唔中，再望慈善位既癲價都已經放棄。十月…有背後有勢力人士通知我有方法可以去跑", 0),
    ("https://www.threads.com/@ericchan326/post/DOjvx9dkoi9", "threads", "ericchan326", "2025-09-13",
     "啱啱先留意到原來中九龍幹線嘅上落幅度恐怖過西隧好多", 0),
    ("https://www.threads.com/@steveyu.rdcoach/post/DbnuvzIAfpE", "threads", "steveyu.rdcoach", "2026-08-04",
     "半日就FULL左，夠出席率有保證渣馬購買額 報名成功", 10),
    ("https://www.threads.com/@fitz.hk/post/DXa2X7nACBR", "threads", "fitz.hk", "2026-04-22",
     "田總委託理大賽後問卷：逾10,000跑手、85%滿意、經濟效益3.38億", 0),
    ("https://www.threads.com/@cheerfulsuen/post/DT9F3ZMkorq", "threads", "cheerfulsuen", "2026-01-26",
     "渣馬10K限時2小時，最困難應該係塞人，唔係完成", 0),
    ("https://www.threads.com/@kong.news/post/DTpm9SOEr3v", "threads", "kong.news", "2026-01-18",
     "渣馬2026：1,517人需治理、59送院、2危殆", 1),
    ("https://www.threads.com/@harbourdailyuk/post/DZzfjVwjA8S", "threads", "harbourdailyuk", "2026-06-20",
     "倫敦馬拉松擴規模 史上首次連跑兩日", 1),
    ("https://www.threads.com/@hkeverydayrunners/post/Da1UIwpE9WV", "threads", "hkeverydayrunners", "2026-07-16",
     "倫敦馬兩日賽制中籤率仍極低，不如轉戰愛丁堡", 2),
    ("https://www.threads.com/@lan.shua/post/DbubzFaE_4Y", "threads", "lan.shua", "2026-08-07",
     "為查渣馬2027報名日期發現Abbott分齡世界排名", 8),
    ("https://www.threads.com/@wannarun__ro/post/Da4Jx5Xj6QV", "threads", "wannarun__ro", "2026-07-17",
     "26-27跑步比賽行程：27 1.17 渣打馬拉松(半/全)", 17),
    ("https://www.threads.com/@isme_kkkkk/post/DbBOSBLk7Yf", "threads", "isme_kkkkk", "2026-07-20",
     "我想報10k渣馬", 12),
    ("https://www.threads.com/@thisissyss/post/DbqW6rIDx25", "threads", "thisissyss", "2026-08-05",
     "希望抽到2027渣打馬拉松全馬", 9),
    ("https://www.threads.com/@tszyiu1999/post/DbilPNOkwoo", "threads", "tszyiu1999", "2026-08-02",
     "大目標：2027年渣馬 sub 3 訓練日記#421", 0),
    ("https://www.facebook.com/hkmarathon/posts/1827627874537502/", "facebook", "hkmarathon", "2025-10-02",
     "渣馬2026第二輪公眾抽籤結果（留言區大量抽唔中怨氣）", 8),
    ("https://www.facebook.com/hkmarathon/posts/1829264571040499/", "facebook", "hkmarathon", "2025-10-04",
     "報名近12萬公布帖", 4),
    ("https://www.facebook.com/100063811579149/posts/1388317133305326/", "facebook", "sportsroad", "2026-01-16",
     "體路FB：如果分開兩日搞，相信可以畀更多跑手報到名", 9),
    ("https://www.facebook.com/stheadlinehk/posts/1386223580211620/", "facebook", "stheadlinehk", "2026-04-14",
     "星島：分兩日搞，順手帶動埋旅遊業喎（留言區反對為主）", 9),
    ("https://www.instagram.com/p/DO70qXnk555/", "instagram", "schkmarathon", "2025-09-22",
     "渣馬2026第一輪抽籤結果（IG）", 8),
    ("https://www.instagram.com/p/DTh19M_D5LE/", "instagram", "walkwithtsui", "2026-01-15",
     "渣馬2026史上最難抽！120,000人爭74,000位", 0),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pull-comments", action="store_true",
                    help="順便抽 Threads/IG 留言（需 TIKHUB_API_KEY）")
    args = ap.parse_args()

    store.ensure_dirs()
    master = store.load_master()
    tik = None
    if args.pull_comments:
        from lib.clients import TikHub
        tik = TikHub()

    n_new = 0
    for origin, rows in (("deck-annex", DECK_ANNEX), ("claude-verified", EXTRA)):
        for url, plat, author, date, text, claimed in rows:
            item = {
                "url": url,
                "platform": plat,
                "author": author,
                "date": date,
                "text": text,
                "replies": claimed,
                "source_channel": f"seed:{origin}",
                "origin": origin,
                "issue_labels": classify.label_text(text),
                "relevance": classify.relevance(text),
                "review_status": "approved",  # 種子已人手核實
            }
            if tik and plat == "threads":
                import sweep
                detail, comments = sweep.pull_threads_comments(tik, url, lambda *a, **k: None)
                if detail:
                    for k, v in detail.items():
                        if v:
                            item[k] = v
                item["comments"] = comments
                item["comments_pulled"] = len(comments)
            st, _ = store.upsert(master, item)
            if st == "new":
                n_new += 1
            print(f"  [{st}] {plat:10s} {url[:70]}")

    store.save_master(master)
    print(f"\n種子入庫完成：新增 {n_new} 條，資料庫合計 {len(master['items'])} 條")
    print("其中 deck-annex 12 條 = 完工驗收嘅歷史對齊基線")


if __name__ == "__main__":
    main()
