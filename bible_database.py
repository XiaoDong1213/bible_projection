# bible_database.py
# SQLite 圣经数据库接口层：直接读取项目根目录“和合本.db”
import os
import sqlite3


class BibleDatabase:
    def __init__(self, db_path=None):
        self.db_path = db_path or os.path.join(os.path.dirname(os.path.abspath(__file__)), "和合本.db")
        if not os.path.exists(self.db_path):
            raise FileNotFoundError(f"找不到圣经数据库：{self.db_path}")

        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self._inspect_database()
        self._build_book_index()

    def _inspect_database(self):
        tables = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        self.tables = [row["name"] for row in tables]
        if not self.tables:
            raise RuntimeError("和合本.db 中没有可用的数据表")

        # 自动识别最可能的经文表，避免把数据库表名写死
        candidates = []
        for table in self.tables:
            cols = [r["name"] for r in self.conn.execute(
                f'PRAGMA table_info("{table.replace(chr(34), chr(34)*2)}")'
            ).fetchall()]
            low = {c.lower(): c for c in cols}
            score = 0
            if any(x in low for x in ("book", "book_name", "书卷", "卷")): score += 3
            if any(x in low for x in ("chapter", "chapter_num", "章")): score += 3
            if any(x in low for x in ("verse", "verse_num", "节")): score += 3
            if any(x in low for x in ("text", "content", "verse_text", "经文", "经文内容")): score += 3
            candidates.append((score, table, cols))

        candidates.sort(reverse=True)
        self.verse_table = candidates[0][1]
        self.verse_columns = candidates[0][2]
        self.book_col = self._pick_column(("book", "book_name", "书卷", "卷", "bookname"))
        self.chapter_col = self._pick_column(("chapter", "chapter_num", "章", "chap"))
        self.verse_col = self._pick_column(("verse", "verse_num", "节", "verse_number"))
        self.text_col = self._pick_column(("text", "content", "verse_text", "经文", "经文内容", "content_text"))

        missing = [name for name, col in (
            ("书卷", self.book_col), ("章节", self.chapter_col),
            ("节号", self.verse_col), ("经文", self.text_col)
        ) if col is None]
        if missing:
            raise RuntimeError(
                f"无法识别和合本.db字段：缺少{'、'.join(missing)}。"
                f"当前表 {self.verse_table} 字段为：{', '.join(self.verse_columns)}"
            )

    def _pick_column(self, names):
        lowered = {c.lower(): c for c in self.verse_columns}
        for name in names:
            if name.lower() in lowered:
                return lowered[name.lower()]
        for col in self.verse_columns:
            if any(name.lower() in col.lower() for name in names):
                return col
        return None

    def _quote(self, name):
        return '"' + name.replace('"', '""') + '"'

    def _build_book_index(self):
        rows = self.conn.execute(
            f"SELECT DISTINCT {self._quote(self.book_col)} AS book "
            f"FROM {self._quote(self.verse_table)} "
            f"WHERE {self._quote(self.book_col)} IS NOT NULL "
            f"ORDER BY rowid"
        ).fetchall()

        self.book_names = [str(r["book"]) for r in rows]
        self.short_names = {
            "创": "创世记", "出": "出埃及记", "利": "利未记", "民": "民数记", "申": "申命记",
            "书": "约书亚记", "士": "士师记", "得": "路得记", "撒上": "撒母耳记上", "撒下": "撒母耳记下",
            "王上": "列王纪上", "王下": "列王纪下", "代上": "历代志上", "代下": "历代志下",
            "拉": "以斯拉记", "尼": "尼希米记", "斯": "以斯帖记", "伯": "约伯记", "诗": "诗篇",
            "箴": "箴言", "传": "传道书", "歌": "雅歌", "赛": "以赛亚书", "耶": "耶利米书",
            "哀": "耶利米哀歌", "结": "以西结书", "但": "但以理书", "何": "何西阿书", "珥": "约珥书",
            "摩": "阿摩司书", "俄": "俄巴底亚书", "拿": "约拿书", "弥": "弥迦书", "鸿": "那鸿书",
            "哈": "哈巴谷书", "番": "西番雅书", "该": "哈该书", "亚": "撒迦利亚书", "玛": "玛拉基书",
            "太": "马太福音", "可": "马可福音", "路": "路加福音", "约": "约翰福音", "徒": "使徒行传",
            "罗": "罗马书", "林前": "哥林多前书", "林后": "哥林多后书", "加": "加拉太书", "弗": "以弗所书",
            "腓": "腓立比书", "西": "歌罗西书", "帖前": "帖撒罗尼迦前书", "帖后": "帖撒罗尼迦后书",
            "提前": "提摩太前书", "提后": "提摩太后书", "多": "提多书", "门": "腓利门书",
            "来": "希伯来书", "雅": "雅各书", "彼前": "彼得前书", "彼后": "彼得后书",
            "约一": "约翰一书", "约二": "约翰二书", "约三": "约翰三书", "犹": "犹大书", "启": "启示录"
        }

    def get_books(self, category="all"):
        old_count = 39
        if category == "old":
            return [(b, self._short_name(b)) for b in self.book_names[:old_count]]
        if category == "new":
            return [(b, self._short_name(b)) for b in self.book_names[old_count:]]
        return [(b, self._short_name(b)) for b in self.book_names]

    def _short_name(self, book):
        for short, full in self.short_names.items():
            if full == book:
                return short
        return book[:1]

    def search_books(self, query):
        query = str(query).lower().strip()
        if not query:
            return []

        # 先处理简称，再做书名模糊匹配
        if query in self.short_names and self.short_names[query] in self.book_names:
            return [self.short_names[query]]

        results = []
        for book in self.book_names:
            if query in book.lower():
                results.append(book)
        return results

    def get_chapter_count(self, book_name):
        row = self.conn.execute(
            f"SELECT MAX(CAST({self._quote(self.chapter_col)} AS INTEGER)) AS n "
            f"FROM {self._quote(self.verse_table)} WHERE {self._quote(self.book_col)} = ?",
            (book_name,)
        ).fetchone()
        return int(row["n"] or 0)

    def get_verse_count(self, book_name, chapter):
        row = self.conn.execute(
            f"SELECT COUNT(*) AS n FROM {self._quote(self.verse_table)} "
            f"WHERE {self._quote(self.book_col)} = ? AND "
            f"CAST({self._quote(self.chapter_col)} AS INTEGER) = ?",
            (book_name, chapter)
        ).fetchone()
        return int(row["n"] or 0)

    def get_verse_text(self, book_name, chapter, verse):
        row = self.conn.execute(
            f"SELECT {self._quote(self.text_col)} AS text FROM {self._quote(self.verse_table)} "
            f"WHERE {self._quote(self.book_col)} = ? AND "
            f"CAST({self._quote(self.chapter_col)} AS INTEGER) = ? AND "
            f"CAST({self._quote(self.verse_col)} AS INTEGER) = ? LIMIT 1",
            (book_name, chapter, verse)
        ).fetchone()
        return str(row["text"]) if row else ""

    def get_verse_range(self, book_name, chapter, start_verse, end_verse=None):
        max_verse = self.get_verse_count(book_name, chapter)
        if max_verse <= 0:
            return []

        end_verse = max_verse if end_verse is None or end_verse > max_verse else end_verse
        start_verse = max(1, int(start_verse))

        rows = self.conn.execute(
            f"SELECT {self._quote(self.verse_col)} AS verse, {self._quote(self.text_col)} AS text "
            f"FROM {self._quote(self.verse_table)} "
            f"WHERE {self._quote(self.book_col)} = ? AND "
            f"CAST({self._quote(self.chapter_col)} AS INTEGER) = ? AND "
            f"CAST({self._quote(self.verse_col)} AS INTEGER) BETWEEN ? AND ? "
            f"ORDER BY CAST({self._quote(self.verse_col)} AS INTEGER)",
            (book_name, chapter, start_verse, end_verse)
        ).fetchall()

        return [(int(r["verse"]), str(r["text"])) for r in rows]

    def parse_reference(self, text):
        text = str(text).strip().replace("：", ":").replace("．", ".").replace("。", ".")
        if not text:
            return None

        parts = text.split()
        if not parts:
            return None

        # 支持“约3:16”“约 3:16”两种输入
        if len(parts) == 1:
            import re
            m = re.match(r"^(.+?)(d+)(?::|\.)(.+)$", parts[0])
            if m:
                parts = [m.group(1), m.group(2) + ":" + m.group(3)]
            else:
                m = re.match(r"^(.+?)(d+)$", parts[0])
                if m:
                    parts = [m.group(1), m.group(2)]

        books = self.search_books(parts[0])
        if not books:
            return None
        book_name = books[0]

        if len(parts) == 1:
            return (book_name, 1, None, None)

        chapter_part = parts[1]
        if ":" in chapter_part:
            ch, ver = chapter_part.split(":", 1)
        elif "." in chapter_part:
            ch, ver = chapter_part.split(".", 1)
        else:
            ch, ver = chapter_part, None

        try:
            chapter = int(ch)
        except ValueError:
            return None

        start_verse, end_verse = None, None
        if ver:
            if "-" in ver:
                s, e = ver.split("-", 1)
                try:
                    start_verse = int(s) if s else 1
                    end_verse = int(e) if e else None
                except ValueError:
                    return None
            else:
                try:
                    start_verse = int(ver)
                    end_verse = start_verse
                except ValueError:
                    return None

        return (book_name, chapter, start_verse, end_verse)

    def close(self):
        if getattr(self, "conn", None):
            self.conn.close()
            self.conn = None
