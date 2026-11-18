"""抓取万有真原圣咏集篇标题并导入思高本.db 的 Titles 表。

数据源：万有真原圣咏目录页（任一篇页面左侧目录含全部 150 篇标题）。
用法：python tools/fetch_sigao_psalm_titles.py [--db 路径]
幂等：重复执行会先清除圣咏卷已导入的「第N篇」标题再插入，
保留原有分卷标题（卷一~卷五）与 119 篇子题。
"""

from __future__ import annotations

import argparse
import re
import sqlite3
import sys
import time
from pathlib import Path
from urllib.request import Request, urlopen

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = REPO_ROOT / "resources" / "思高本.db"
URL = "https://www.wanyouzhenyuan.cn/index.php?m=bible&version=sigao&template=23&chapter=1"
RETRIES = 5
TIMEOUT = 30
# 目录条目：当前篇带 active class；chapter=0 是圣咏集引言，不导入
LI_RE = re.compile(
    r'<li class="col(?: active)?"><a href="[^"]*chapter=(\d+)">([^<]+)</a></li>'
)


def fetch_titles() -> dict[int, str]:
    last_err: Exception | None = None
    for attempt in range(1, RETRIES + 1):
        try:
            req = Request(URL, headers={"User-Agent": "Mozilla/5.0 (BiblePro)"})
            with urlopen(req, timeout=TIMEOUT) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
            break
        except Exception as exc:  # noqa: BLE001——网络阵发失败需重试
            last_err = exc
            print(f"第 {attempt} 次抓取失败：{exc}，重试…")
            time.sleep(2)
    else:
        raise SystemExit(f"抓取失败（已重试 {RETRIES} 次）：{last_err}")

    items: dict[int, str] = {}
    for num, title in LI_RE.findall(html):
        n = int(num)
        if n < 1:
            continue  # 引言
        cleaned = re.sub(r"\s+", " ", title).strip()
        if n in items:
            raise SystemExit(f"第 {n} 篇出现多条：{items[n]!r} / {cleaned!r}")
        items[n] = cleaned
    missing = [i for i in range(1, 151) if i not in items]
    if missing:
        raise SystemExit(f"圣咏目录缺篇：{missing[:10]}…共缺 {len(missing)} 条")
    return items


def psalm_book_id(con: sqlite3.Connection) -> int:
    row = con.execute(
        "SELECT id FROM Books WHERE LongName LIKE '%圣咏%'"
    ).fetchone()
    if row is None:
        raise SystemExit("Books 表中未找到圣咏卷")
    return int(row[0])


def import_titles(db_path: Path, items: dict[int, str]) -> None:
    con = sqlite3.connect(str(db_path))
    try:
        book_id = psalm_book_id(con)
        # 只清已导入的篇标题行，保留「卷一~卷五」与 119 篇子题
        removed = con.execute(
            "DELETE FROM Titles WHERE Book=? AND Verse=1 AND Scripture LIKE '第%篇'",
            (book_id,),
        ).rowcount
        con.executemany(
            "INSERT INTO Titles (Book, Chapter, Verse, Scripture) VALUES (?, ?, 1, ?)",
            [(book_id, n, title) for n, title in sorted(items.items())],
        )
        con.commit()
        print(f"导入 {len(items)} 条篇标题到 {db_path.name}（清理旧导入 {removed} 条）")
        # 自检：第 10 篇应含思高本原文关键词
        row = con.execute(
            "SELECT Scripture FROM Titles WHERE Book=? AND Chapter=10 AND Verse=1",
            (book_id,),
        ).fetchone()
        assert row and "求主铲除恶霸" in row[0], f"第 10 篇标题异常：{row}"
        print(f"抽查第 10 篇：{row[0]}")
    finally:
        con.close()


def main() -> int:
    ap = argparse.ArgumentParser(description="导入圣咏集篇标题到思高本.db")
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = ap.parse_args()
    if not args.db.is_file():
        raise SystemExit(f"找不到数据库：{args.db}")
    items = fetch_titles()
    print(f"抓取到 {len(items)} 篇标题（1-150 齐全）")
    import_titles(args.db, items)
    return 0


if __name__ == "__main__":
    sys.exit(main())
