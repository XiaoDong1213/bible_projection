"""微读圣经格式 bible_*.db → 经文投影应用格式 转换工具。

源格式（微读）:
    bible              bid/bn/bnm/cid/vid/txt/content（content 为富文本块 JSON）
    bible_catalog      id/name/name_min/chapter_count/chapters
    bible_summary      title（版本名）
转换规则（复刻 resources/和合本.db 与 NIV.db 的既有惯例）:
    f:2 小标题        → Titles 表（英文版整块 <m> 包裹的标题是古抄本注，丢弃）
    题注表 Captions   → f:4 篇首注（大卫的诗…）、说话人标签（〔新郎〕/He/She/Friends）、
                        细拉（（细拉）/（細拉）/Selah 从正文抽出）——应用单独显示，不混入正文
    f:3 串引用        → 并入同节最后一个标题「标题（引用）」；无标题时单独成行
    f:4 英文正文后    → 牌铭类（出 28:36「HOLY TO THE LORD」）仍属经文
    段中配对 <m> 块   → ESV 是段中小标题，进 Titles；NIV 是脚注，删除
    <m> 行内          → NIV 为脚注删除；ESV 为古抄本存疑经文，保留内容仅去标签
    空经文            → 英文写「-」占位（对齐现有 NIV.db，如太 17:21），应用会并入前节
    cid=0 书卷简介    → 跳过
    Books.Pinyin      → 中文照抄和合本；英文追加英文缩写（如 "CSJ Gen"）
用法:
    python tools/convert_bible_db.py <源.db> [输出.db|输出目录] [--lang zh|en]
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from core.bible_versions import _probe_bible_name  # noqa: E402

# 和合本.db 的书卷拼音码，按 Books.id 对照（转换时中文直接抄，英文追加缩写）
DEFAULT_BIBLE = REPO_ROOT / "resources" / "和合本.db"

# 桌面文件的元信息：文件名 → (输出文件名, 显示名, id码, lang, langcode, 简繁, ESV式保留<m>)
KNOWN_FILES = {
    "bible_cuv_simple.db": ("和合本.db", "和合本", "CUV1", "简体中文", "zh-CN", "zh", True),
    "bible_cuv_traditional.db": ("和合本繁体.db", "新標點和合本", "CUVT1", "繁体中文", "zh-TW", "zh", True),
    "bible_cuhwv_simple.db": ("文理和合译本.db", "文理和合译本", "CUHWV1", "简体中文", "zh-CN", "zh", True),
    "bible_cuhwv_traditional.db": ("文理和合译本繁体.db", "文理和合譯本", "CUHWVT1", "繁体中文", "zh-TW", "zh", True),
    "bible_english_standard_version.db": ("ESV.db", "ESV", "ESV1", "English", "en", "en", True),
    "bible_new_international_version.db": ("NIV微读.db", "NIV", "NIV2", "English", "en", "en", False),
}

NIV_COPYRIGHT = (
    "NIV(R). Copyright (C) 1973, 1978, 1984, 2011 by Biblica, Inc.(TM) "
    "Scripture taken from the Holy Bible, New International Version(R)."
)

FOOTNOTE_RE = re.compile(r"<m>.*?</m>", re.S)          # 行内脚注
M_WRAP_RE = re.compile(r"^<m>(.*?)</m>$", re.S)        # 整块 <m> 包裹
TAG_RE = re.compile(r"</?[a-zA-Z][^>]*>")
REF_TEXT_RE = re.compile(r"<l>.*?\}\}([^<]*)</l>", re.S)
SPEAKER_RE = re.compile(r"^(?:〔[^〔〕]*〕)+$")         # 中文说话人标签（〔新郎〕…）
EN_SPEAKERS = {"He", "She", "Others", "Friends"}        # 英文雅歌说话人标签
SELAH_ZH_RE = re.compile(r"（[细細]拉）")                # 和合本细拉（精确括注形态，不会误伤人名「雅希细拉」）
SELAH_EN_RE = re.compile(r"\s*\bSelah\b[.,;:!？”\"']*")  # 英文 Selah（区分大小写，Methuselah 等小写不会误伤）
# 英文篇首注开头形态（NIV 把篇首注编码成 f:2，以 A psalm/Of David/For the director 等开头；
# 诗119 希伯来字母标题「א Aleph」与 Book/Psalms 范围标题均不匹配，保留为小标题）
SUP_RE = re.compile(
    r'^["“”]?\s*(A psalm|A prayer|A song|A shiggaion|A miktam|A maskil|'
    r'For the director|Of David|Of Solomon|Of Asaph|Of Korah|Of the Son)'
)


def strip_quotes(text: str) -> str:
    return text.strip().strip("“”\"‘’'")


def load_pinyin_map() -> dict[int, tuple[str, int]]:
    """读和合本.db 的 Books：(id → (pinyin, chapter_count))。"""
    con = sqlite3.connect(f"file:{DEFAULT_BIBLE.as_posix()}?mode=ro", uri=True)
    rows = con.execute("SELECT id, Pinyin, ChapterCount FROM Books").fetchall()
    con.close()
    return {int(r[0]): (str(r[1] or ""), int(r[2] or 0)) for r in rows}


def clean_title(text: str, lang: str, keep_m: bool = False) -> str:
    """标题清理：剥标签留字；NIV（keep_m=False）标题内嵌 <m> 脚注删除。"""
    text = text.strip()
    if not keep_m:
        text = FOOTNOTE_RE.sub("", text)
    text = re.sub(r"</?m>", "", text)
    text = TAG_RE.sub("", text)
    if lang == "en":
        text = re.sub(r"\s{2,}", " ", text)
        text = text.strip("“”\"")  # NIV 标题/篇首注的 stray quotes
    return text.strip()


def clean_body(text: str, lang: str, keep_m: bool) -> str:
    """正文清理：keep_m=True（ESV）<m> 是存疑经文，保留内容；False（NIV）是脚注，删除。"""
    text = text.strip()
    if keep_m:
        text = re.sub(r"</?m>", "", text)
    else:
        text = FOOTNOTE_RE.sub("", text)
        text = re.sub(r"</?m>", "", text)  # 残留散标签（如 <m><m>… 无闭合）
    text = TAG_RE.sub("", text)
    if lang == "en":
        text = re.sub(r"\s{2,}", " ", text)
    return text.strip()


def join_blocks(parts: list[str], lang: str) -> str:
    """块拼接：中文直接相连（微读 txt 同款），英文按词补空格；
    含 \\n 的段（内联标签）两侧不加分隔符。"""
    out = ""
    for p in parts:
        if not p:
            continue
        if not out:
            out = p
        elif out.endswith("\n") or p.startswith("\n"):
            out += p
        elif lang == "en":
            out += " " + p
        else:
            out += p
    return out


def convert_verse_row(bid: int, cid: int, vid: int, content: str,
                      lang: str, keep_m: bool) -> tuple[str, list[tuple], list[tuple]]:
    """解析一节 content JSON，返回 (经文文本, 标题行列表, 题注行列表)。"""
    blocks = json.loads(content)
    titles: list[str] = []
    captions: list[str] = []
    refs: list[str] = []
    body: list[str] = []
    seen_body = False
    for blk in blocks:
        f = blk.get("f")
        d = str(blk.get("d") or "").strip()
        if f == 2:
            if lang == "en" and M_WRAP_RE.match(d):
                continue  # 古抄本注伪装成标题（如「Some of the earliest manuscripts…」）
            if lang == "zh" and SPEAKER_RE.match(d):
                # 说话人标签：节首 → 题注（上方）；节中 → 原位独立成行
                #（\n 标记，显示层按题注样式渲染，不并入正文行内）
                if seen_body:
                    body.append("\n" + d + "\n")
                else:
                    captions.append(d)
                continue
            if lang == "en" and bid == 22 and strip_quotes(d) in EN_SPEAKERS:
                captions.append(strip_quotes(d))  # 英文雅歌说话人标签（f:2）→ 题注
                continue
            if lang == "en" and SUP_RE.match(d):
                captions.append(d)  # NIV 篇首注（A psalm of David… 式 f:2）→ 题注
                continue
            titles.append(d)
        elif f == 3:
            m = REF_TEXT_RE.search(d)
            ref = m.group(1).strip() if m else TAG_RE.sub("", d).strip("（）() ")
            if ref:
                refs.append(ref.replace("·", ":"))  # 繁体「1·1—4」→「1:1—4」，应用清理规则只认「1:1」
        elif f == 4:
            if lang == "zh":
                # 篇首注/说话人标签：节首 → 题注（上方）；节中 → 原位独立成行
                if seen_body:
                    body.append("\n" + d + "\n")
                else:
                    captions.append(d)
            else:
                if bid == 22 and strip_quotes(d) in EN_SPEAKERS:
                    captions.append(strip_quotes(d))
                    continue
                mw = M_WRAP_RE.match(d)
                if mw:
                    d = mw.group(1).strip()
                if not d:
                    continue
                if seen_body:
                    body.append(d)      # 正文后的注（如「HOLY TO THE LORD」牌铭）属于经文
                else:
                    captions.append(d)  # 篇首注 → 题注
        else:
            mw = M_WRAP_RE.match(d)
            if lang == "en" and mw:
                inner = strip_quotes(mw.group(1).strip())
                if bid == 22 and inner in EN_SPEAKERS:
                    captions.append(inner)  # 雅歌说话人标签 → 题注
                    continue
                if keep_m and inner:
                    titles.append(inner)  # ESV：段中配对 <m> 是小标题
                # NIV：整块脚注，丢弃
                continue
            text = clean_body(d, lang, keep_m)
            if lang == "en" and bid == 22 and strip_quotes(text) in EN_SPEAKERS:
                captions.append(strip_quotes(text))  # NIV 独立说话人块（f:0/f:1）→ 题注
                continue
            if text:
                body.append(text)
                seen_body = True

    text = join_blocks(body, lang)
    # 细拉 / Selah 从正文抽出为题注（保留括号形态：简「（细拉）」/ 繁「（細拉）」）
    selah_re = SELAH_ZH_RE if lang == "zh" else SELAH_EN_RE
    if lang == "zh":
        selah_hits = [m.group(0) for m in selah_re.finditer(text)]
    else:
        selah_hits = ["Selah"] * len(selah_re.findall(text))
    if selah_hits:
        captions.extend(selah_hits)
        text = selah_re.sub("", text)
    text = text.rstrip("\n")  # 节末说话人标签的尾换行不留在正文里
    if lang == "en":
        text = re.sub(r"\s{2,}", " ", text)
    if lang == "en" and not text.strip():
        text = "-"  # 空经文占位（对齐现有 NIV.db），应用会并入前一逻辑节
    if refs:
        ref_part = "（" + "；".join(refs) + "）"
        if titles:
            titles[-1] += ref_part
        else:
            titles.append(ref_part)
    title_rows = []
    for t in titles:
        t = clean_title(t, lang, keep_m)
        if t:
            title_rows.append((bid, cid, vid, t))
    caption_rows = []
    for c in captions:
        c = clean_title(c, lang, keep_m)
        if c:
            caption_rows.append((bid, cid, vid, c))
    return text, title_rows, caption_rows


def convert(source: Path, dest: Path, name: str, ver_id: str, lang_name: str,
            langcode: str, lang: str, keep_m: bool, pinyin_map: dict) -> dict:
    src = sqlite3.connect(f"file:{source.as_posix()}?mode=ro", uri=True)

    summary = src.execute("SELECT title FROM bible_summary LIMIT 1").fetchone()
    catalog = src.execute(
        "SELECT id, name, name_min, chapter_count FROM bible_catalog ORDER BY id"
    ).fetchall()

    verses, titles, captions = [], [], []
    for bid, cid, vid, content in src.execute(
        "SELECT bid, cid, vid, content FROM bible WHERE cid>=1 ORDER BY bid, cid, vid"
    ):
        text, t_rows, c_rows = convert_verse_row(bid, cid, vid, content, lang, keep_m)
        verses.append((bid, cid, vid, text))
        titles.extend(t_rows)
        captions.extend(c_rows)
    src.close()

    # ---- 写目标库 ----
    if dest.exists():
        dest.unlink()
    out = sqlite3.connect(str(dest))
    out.executescript(
        """
        CREATE TABLE Bible (id INTEGER PRIMARY KEY, Book INT, Chapter INT, Verse INT, Scripture TEXT);
        CREATE TABLE Books (id INTEGER, ShortName TEXT, LongName TEXT, ChapterCount INTEGER, Pinyin TEXT,
                            PRIMARY KEY (id));
        CREATE TABLE Titles (id INTEGER PRIMARY KEY, Book INT, Chapter INT, Verse INT, Scripture TEXT);
        CREATE TABLE Captions (id INTEGER PRIMARY KEY, Book INT, Chapter INT, Verse INT, Caption TEXT);
        CREATE TABLE metadata (id INTEGER PRIMARY KEY, name UNIQUE NOT NULL, value TEXT);
        CREATE INDEX bible_lookup_index ON Bible(Book, Chapter);
        CREATE INDEX titles_lookup_index ON Titles(Book, Chapter);
        CREATE INDEX captions_lookup_index ON Captions(Book, Chapter);
        """
    )
    out.executemany("INSERT INTO Bible(Book, Chapter, Verse, Scripture) VALUES (?,?,?,?)", verses)
    out.executemany(
        "INSERT INTO Titles(Book, Chapter, Verse, Scripture) VALUES (?,?,?,?)", titles
    )
    out.executemany(
        "INSERT INTO Captions(Book, Chapter, Verse, Caption) VALUES (?,?,?,?)", captions
    )
    books = []
    for bid, name_full, name_short, ch_count in catalog:
        base_pinyin, _ = pinyin_map.get(int(bid), ("", 0))
        if lang == "en":
            pinyin = f"{base_pinyin} {name_short}".strip()
        else:
            pinyin = base_pinyin
        books.append((bid, name_short, name_full, int(ch_count), pinyin))
    out.executemany(
        "INSERT INTO Books(id, ShortName, LongName, ChapterCount, Pinyin) VALUES (?,?,?,?,?)",
        books,
    )
    edition = str(summary[0] or name) if summary else name
    copyright = NIV_COPYRIGHT if ver_id == "NIV2" else edition
    meta = [
        ("id", ver_id),
        ("date", "20261110"),
        ("lang", lang_name),
        ("langcode", langcode),
        ("name", name),
        ("shortname", name),
        ("copyright", copyright),
        ("source", f"微读圣经格式文件 {source.name}"),
    ]
    out.executemany("INSERT INTO metadata(name, value) VALUES (?,?)", meta)
    out.commit()
    out.close()

    return {
        "verses": len(verses),
        "titles": len(titles),
        "captions": len(captions),
        "books": len(books),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("source", type=Path)
    ap.add_argument("dest", nargs="?", type=Path, default=None)
    ap.add_argument("--lang", choices=["zh", "en"], default=None)
    args = ap.parse_args()

    source = args.source.resolve()
    meta = KNOWN_FILES.get(source.name)
    if meta is None:
        print(f"未知文件 {source.name}：请手动指定输出路径与 --lang zh|en")
        return 1
    out_name, display_name, ver_id, lang_name, langcode, lang, keep_m = meta
    if args.lang:
        lang = args.lang
    dest = args.dest or Path.cwd()
    if dest.is_dir():
        dest = dest / out_name
    dest = dest.resolve()

    stats = convert(source, dest, display_name, ver_id, lang_name, langcode, lang,
                    keep_m, load_pinyin_map())
    # 自检：能用应用的 BibleDatabase 打开、显示名正确
    from core.database import BibleDatabase
    db = BibleDatabase(str(dest))
    assert _probe_bible_name(dest) == display_name, "metadata 显示名不符"
    print(
        f"{source.name} → {dest.name}  经文 {stats['verses']}  标题 {stats['titles']}  "
        f"题注 {stats['captions']}  书卷 {stats['books']}  "
        f"显示名「{display_name}」 书卷数 {len(db.book_names)}"
    )
    db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
