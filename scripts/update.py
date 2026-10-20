"""把每日抓到的原始數字整理成 data/rewards.json，並追加到 data/history.json。

用法：python3 scripts/update.py input.json

input.json 範例（數字照頁面抄，次數沒顯示的方案寫 null）：
{
  "raised": 251184, "goal": 3800000, "backers": 95, "unique_backers": 91,
  "rewards": [
    {"id": 190227, "title": "1 張交換券｜一路相挺", "price": 1680, "backed": 22, "remaining": null},
    {"id": 190232, "title": "比媽手繪似顏繪", "price": 25000, "backed": null, "remaining": 10}
  ]
}

驗證不通過時不寫入任何檔案，並以非 0 結束。
"""
import json
import os
import sys
from datetime import datetime, timezone, timedelta

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
OUT = os.path.join(ROOT, "data", "rewards.json")
HISTORY = os.path.join(ROOT, "data", "history.json")
TZ = timezone(timedelta(hours=8))

# 限量方案的總份數（頁面只顯示剩餘份數，次數 = 總量 - 剩餘）
LIMITS = {190232: 10}

PROJECT = {
    "slug": "NOTHING-LEFT-BUT-COURAGE",
    "title": "《我只剩下勇敢》紀錄片電影上映集資計畫",
    "url": "https://www.zeczec.com/projects/NOTHING-LEFT-BUT-COURAGE",
    "starts_at": "2026-10-13T20:00:00+08:00",
    "ends_at": "2026-12-13T23:59:00+08:00",
}


def fail(msg):
    print(f"驗證失敗，未寫入：{msg}")
    sys.exit(1)


def main(path):
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)

    for key in ("raised", "goal", "backers"):
        if not isinstance(raw.get(key), int):
            fail(f"缺少或格式錯誤：{key}")
    if not raw.get("rewards"):
        fail("沒有任何方案")

    rewards = []
    for r in raw["rewards"]:
        rid = int(r["id"])
        limit = LIMITS.get(rid)
        remaining = r.get("remaining")
        backed = r.get("backed")
        if backed is None:
            backed = limit - remaining if (limit is not None and remaining is not None) else 0
        if not isinstance(backed, int) or backed < 0:
            fail(f"方案 {rid} 次數不合理：{backed}")
        rewards.append({
            "id": rid,
            "title": r["title"],
            "price": int(r["price"]),
            "backers": backed,
            "limit": limit,
            "remaining": remaining,
        })

    total = sum(r["backers"] for r in rewards)
    if total != raw["backers"]:
        fail(f"各方案次數加總 {total} ≠ 頁面贊助人數 {raw['backers']}")

    # 不得比上次少太多（贊助次數理論上只增不減，退款可能少量減少）
    if os.path.exists(OUT):
        with open(OUT, encoding="utf-8") as f:
            prev = json.load(f)
        if total < prev.get("total_backers", 0) * 0.9:
            fail(f"總次數從 {prev['total_backers']} 驟降到 {total}，疑似抓錯")

    now = datetime.now(TZ).replace(microsecond=0)
    data = {
        **PROJECT,
        "updated_at": now.isoformat(),
        "raised": raw["raised"],
        "goal": raw["goal"],
        "progress": round(raw["raised"] / raw["goal"], 4),
        "total_backers": total,
        "unique_backers": raw.get("unique_backers"),
        "rewards": rewards,
    }

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")

    # 每日歷史：同一天只保留最後一筆
    history = []
    if os.path.exists(HISTORY):
        with open(HISTORY, encoding="utf-8") as f:
            history = json.load(f)
    today = now.date().isoformat()
    history = [h for h in history if h["date"] != today]
    history.append({
        "date": today,
        "raised": raw["raised"],
        "total_backers": total,
        "rewards": {str(r["id"]): r["backers"] for r in rewards},
    })
    history.sort(key=lambda h: h["date"])
    with open(HISTORY, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"已更新：總次數 {total}，集資 NT$ {raw['raised']:,}，{len(rewards)} 個方案")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    main(sys.argv[1])
