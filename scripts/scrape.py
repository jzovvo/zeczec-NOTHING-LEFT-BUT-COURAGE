"""抓取嘖嘖專案各方案的「已被贊助 N 次」，輸出到 data/rewards.json。
只用 Python 標準函式庫，GitHub Actions 內建即可執行。"""
import html
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timezone, timedelta
from urllib.parse import unquote

SLUG = os.environ.get("PROJECT_SLUG", "NOTHING-LEFT-BUT-COURAGE")
TARGET = f"https://www.zeczec.com/projects/{SLUG}"
OUT = os.path.join(os.path.dirname(__file__), "..", "data", "rewards.json")
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")


def get(url, headers=None):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "zh-TW,zh;q=0.9",
        **(headers or {}),
    })
    with urllib.request.urlopen(req, timeout=40) as r:
        return r.read().decode("utf-8", "replace")


SOURCES = [
    ("direct", lambda: get(TARGET)),
    ("jina", lambda: get("https://r.jina.ai/" + TARGET,
                         {"X-Return-Format": "html", "X-No-Cache": "true"})),
]


def fetch_rewards():
    # 依序嘗試每個來源，第一個能解析出方案的就採用
    for name, fn in SOURCES:
        try:
            page = fn()
        except Exception as e:
            print(f"[{name}] 請求失敗: {e}")
            continue
        rewards = parse(page)
        title = re.search(r"<title>(.*?)</title>", page, re.S)
        print(f"[{name}] 長度 {len(page)}，標題 {title.group(1).strip()[:60] if title else '(無)'}，"
              f"解析到 {len(rewards)} 個方案")
        if rewards:
            return rewards, name
        print(f"[{name}] 開頭內容: {page[:300]!r}")
    return None, None


def text_of(fragment):
    t = re.sub(r"<[^>]+>", " ", fragment)
    return re.sub(r"\s+", " ", html.unescape(t)).strip()


def parse(page):
    rewards = []
    for m in re.finditer(r'<a\b[^>]*href="([^"]*selected_reward[^"]*)"[^>]*>(.*?)</a>', page, re.S):
        href, body = unquote(html.unescape(m.group(1))), m.group(2)
        rid = re.search(r"selected_reward=(\d+)", href)
        title = re.search(r'<div class="[^"]*font-bold[^"]*mt-4[^"]*">(.*?)</div>', body, re.S)
        t = text_of(body)
        price = re.search(r"NT\$\s*([\d,]+)", t)
        backers = re.search(r"已被贊助\s*(\d+)\s*次", t)
        remaining = re.search(r"剩餘\s*(\d+)\s*份", t)
        rewards.append({
            "id": rid.group(1) if rid else None,
            "title": text_of(title.group(1)) if title else t.split(" NT$")[0][:40],
            "price": int(price.group(1).replace(",", "")) if price else None,
            "backers": int(backers.group(1)) if backers else 0,
            "remaining": int(remaining.group(1)) if remaining else None,
        })
    return rewards


def main():
    rewards, source = fetch_rewards()
    if not rewards:
        sys.exit("所有來源都沒有解析到方案，可能被擋或嘖嘖改版了；保留舊資料不覆寫。")

    # 只有數字有變才更新時間戳，避免每次都產生 commit
    old = {}
    if os.path.exists(OUT):
        with open(OUT, encoding="utf-8") as f:
            old = json.load(f)
    if old.get("rewards") == rewards:
        print("no change")
        return

    tw = timezone(timedelta(hours=8))
    data = {
        "project": SLUG,
        "source": source,
        "updated_at": datetime.now(tw).isoformat(timespec="seconds"),
        "total_backers": sum(r["backers"] for r in rewards),
        "rewards": rewards,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"updated {len(rewards)} rewards via {source}")


if __name__ == "__main__":
    main()
