import os
import re
import sqlite3


class BibleDatabase:
    """负责数据库连接、书卷索引和经文查询。"""

    def __init__(self, db_path=None):
        if db_path is None:
            db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "和合本.db")
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self._inspect_database()
        self._build_book_index()

    def _inspect_database(self):
        tables = self.conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        if not tables:
            raise RuntimeError("和合本.db中没有可用数据表")
        table_names = [r[0] for r in tables]
        self.verse_table = "Bible" if "Bible" in table_names else table_names[0]
        self.books_table = "Books" if "Books" in table_names else None
        self.titles_table = "Titles" if "Titles" in table_names else None
        self.title_columns = {}
        if self.titles_table:
            self._inspect_titles_table()

        columns = [r[1] for r in self.conn.execute(f'PRAGMA table_info("{self.verse_table}")').fetchall()]

        def find(names):
            lower = {c.lower(): c for c in columns}
            for name in names:
                if name.lower() in lower:
                    return lower[name.lower()]
            return None

        self.book_col = find(["Book", "书卷", "书名"])
        self.chapter_col = find(["Chapter", "章节", "章"])
        self.verse_col = find(["Verse", "节号", "节"])
        self.text_col = find(["Scripture", "text", "content", "verse_text", "经文", "经文内容"])
        if not all([self.book_col, self.chapter_col, self.verse_col, self.text_col]):
            raise RuntimeError(f"无法识别和合本.db字段：当前表 {self.verse_table} 字段为：{', '.join(columns)}")

    def _inspect_titles_table(self):
        """按 Titles 表真实结构识别字段。"""
        columns = [r[1] for r in self.conn.execute(f'PRAGMA table_info("{self.titles_table}")').fetchall()]
        lower = {c.lower(): c for c in columns}

        def find(names):
            for name in names:
                if name.lower() in lower:
                    return lower[name.lower()]
            return None

        self.title_columns = {
            "book": find(["Book", "book_id", "BookID", "书卷", "书名"]),
            "chapter": find(["Chapter", "chapter_id", "ChapterID", "章节", "章"]),
            "verse": find(["Verse", "verse_id", "VerseID", "StartVerse", "start_verse", "节号", "节"]),
            "text": find(["Scripture", "Title", "title", "Text", "text", "Content", "content", "Name", "name", "标题", "小标题"]),
        }
        if not all(self.title_columns.values()):
            self.titles_table = None
            self.title_columns = {}

    @staticmethod
    def _clean_scripture_title(value):
        """删除标题中的经文交叉引用括号，普通括号保留。"""
        text = str(value or "").strip()
        if not text:
            return ""
        reference = re.compile(r"\d{1,3}\s*[:：.]\s*\d{1,3}(?:\s*[-–—]\s*\d{1,3})?")
        pattern = re.compile(r"[（(]([^（）()]*)[）)]")

        def replace(match):
            return "" if reference.search(match.group(1).strip()) else match.group(0)

        text = pattern.sub(replace, text)
        return re.sub(r"\s{2,}", " ", text).strip(" \t-—–，,；;：:")

    def get_chapter_titles(self, book_name, chapter):
        """返回指定章节的小标题，键为标题所属节号。"""
        if not self.titles_table:
            return {}
        cols = self.title_columns
        book_value = self.book_meta.get(book_name, {}).get("id", book_name)
        sql = (
            f"SELECT {self._quote(cols['verse'])} AS verse, {self._quote(cols['text'])} AS title "
            f"FROM {self._quote(self.titles_table)} "
            f"WHERE {self._quote(cols['book'])}=? AND {self._quote(cols['chapter'])}=? "
            f"ORDER BY {self._quote(cols['verse'])}"
        )
        rows = self.conn.execute(sql, (book_value, chapter)).fetchall()
        result = {}
        for row in rows:
            try:
                verse = int(row["verse"])
            except (TypeError, ValueError):
                continue
            title = self._clean_scripture_title(row["title"])
            if title:
                result.setdefault(verse, []).append(title)
        return result

    def _quote(self, name):
        return '"' + name.replace('"', '""') + '"'

    def _build_book_index(self):
        rows = self.conn.execute(
            f"SELECT {self._quote(self.book_col)} AS book, MIN(rowid) AS first_row "
            f"FROM {self._quote(self.verse_table)} "
            f"WHERE {self._quote(self.book_col)} IS NOT NULL "
            f"GROUP BY {self._quote(self.book_col)} ORDER BY first_row"
        ).fetchall()
        bible_names = [str(r["book"]) for r in rows]
        self.book_meta = {}
        if self.books_table:
            cols = [r[1] for r in self.conn.execute(f'PRAGMA table_info("{self.books_table}")').fetchall()]
            lower = {x.lower(): x for x in cols}

            def bc(names):
                for n in names:
                    if n.lower() in lower:
                        return lower[n.lower()]
                return None

            id_col = bc(["id", "ID", "编号"])
            short_col = bc(["ShortName", "short_name", "简称"])
            pinyin_col = bc(["Pinyin", "pinyin", "拼音", "拼音码", "简拼"])
            long_col = bc(["LongName", "long_name", "Book", "书卷", "书名"])
            count_col = bc(["ChapterCount", "chapter_count", "章节数"])
            select_cols = []
            for col in (id_col, short_col, pinyin_col, long_col, count_col):
                if col:
                    select_cols.append(self._quote(col))
            if select_cols:
                for row in self.conn.execute(f'SELECT {", ".join(select_cols)} FROM "{self.books_table}"').fetchall():
                    data = dict(row)
                    name = str(data.get(long_col, "")).strip() if long_col else ""
                    if name:
                        self.book_meta[name] = {
                            "id": data.get(id_col) if id_col else None,
                            "short": str(data.get(short_col, name[:1])).strip() if short_col else name[:1],
                            "pinyin": str(data.get(pinyin_col, "")).strip() if pinyin_col else "",
                            "chapter_count": int(data[count_col]) if count_col and str(data.get(count_col)).isdigit() else None,
                        }
        id_to_name = {str(v.get('id')).strip(): k for k, v in self.book_meta.items() if v.get('id') is not None}
        mapped_names = []
        for raw in bible_names:
            name = id_to_name.get(str(raw).strip(), str(raw).strip())
            if name not in mapped_names:
                mapped_names.append(name)
        self.book_names = [name for name in self.book_meta if name in mapped_names] or mapped_names
        self.book_codes = {}
        for i, book in enumerate(self.book_names[:66], 1):
            self.book_codes[str(i)] = book
            pinyin = self.book_meta.get(book, {}).get("pinyin", "")
            if pinyin:
                self.book_codes[self._normalize_code(pinyin)] = book
        self.short_names = {
            "创":"创世记","出":"出埃及记","利":"利未记","民":"民数记","申":"申命记","书":"约书亚记","士":"士师记","得":"路得记","撒上":"撒母耳记上","撒下":"撒母耳记下","王上":"列王纪上","王下":"列王纪下","代上":"历代志上","代下":"历代志下","拉":"以斯拉记","尼":"尼希米记","斯":"以斯帖记","伯":"约伯记","诗":"诗篇","箴":"箴言","传":"传道书","歌":"雅歌","赛":"以赛亚书","耶":"耶利米书","哀":"耶利米哀歌","结":"以西结书","但":"但以理书","何":"何西阿书","珥":"约珥书","摩":"阿摩司书","俄":"俄巴底亚书","拿":"约拿书","弥":"弥迦书","鸿":"那鸿书","哈":"哈巴谷书","番":"西番雅书","该":"哈该书","亚":"撒迦利亚书","玛":"玛拉基书","太":"马太福音","可":"马可福音","路":"路加福音","约":"约翰福音","徒":"使徒行传","罗":"罗马书","林前":"哥林多前书","林后":"哥林多后书","加":"加拉太书","弗":"以弗所书","腓":"腓立比书","西":"歌罗西书","帖前":"帖撒罗尼迦前书","帖后":"帖撒罗尼迦后书","提前":"提摩太前书","提后":"提摩太后书","多":"提多书","门":"腓利门书","来":"希伯来书","雅":"雅各书","彼前":"彼得前书","彼后":"彼得后书","约一":"约翰一书","约二":"约翰二书","约三":"约翰三书","犹":"犹大书","启":"启示录"
        }

    def _normalize_code(self, value):
        return str(value).strip().lower().replace(" ", "")

    def _short_name(self, book):
        for short, full in self.short_names.items():
            if full == book:
                return short
        return self.book_meta.get(book, {}).get("short", book[:1])

    def search_books(self, query):
        q = self._normalize_code(query)
        if not q or not re.fullmatch(r"[a-z]+", q):
            return []
        results = []
        for book in self.book_names:
            pinyin = self._normalize_code(self.book_meta.get(book, {}).get("pinyin", ""))
            if pinyin and pinyin.startswith(q):
                results.append(book)
        return results

    def find_book(self, query):
        q = self._normalize_code(query)
        if q in self.book_codes:
            return self.book_codes[q]
        results = self.search_books(query)
        return results[0] if results else None

    def get_books(self, category="all"):
        if category == "old":
            books = self.book_names[:39]
        elif category == "new":
            books = self.book_names[39:]
        else:
            books = self.book_names
        return [(b, self._short_name(b)) for b in books]

    def get_chapter_count(self, book_name):
        row = self.conn.execute(
            f"SELECT MAX({self._quote(self.chapter_col)}) AS n FROM {self._quote(self.verse_table)} "
            f"WHERE {self._quote(self.book_col)}=?",
            (self.book_meta.get(book_name, {}).get('id', book_name),),
        ).fetchone()
        return int(row["n"] or 0)

    def get_verse_count(self, book_name, chapter):
        row = self.conn.execute(
            f"SELECT MAX({self._quote(self.verse_col)}) AS n FROM {self._quote(self.verse_table)} "
            f"WHERE {self._quote(self.book_col)}=? AND {self._quote(self.chapter_col)}=?",
            (self.book_meta.get(book_name, {}).get('id', book_name), chapter),
        ).fetchone()
        return int(row["n"] or 0)

    @staticmethod
    def _is_placeholder_verse(text):
        """判断是否为数据库中表示前一节延续关系的纯横线。"""
        return str(text or "").strip() in {"-", "–", "—", "―", "－"}

    def get_logical_verses(self, book_name, chapter, start_verse=None, end_verse=None):
        """读取章节并转换为逻辑经文单位。

        数据库中的结构可能是：
            13 = 完整经文
            14 = —
            15 = 完整经文

        这里 14 不是和 15 连接，而是表示 13 延续到 14。
        因此最终逻辑单位是 13~14，正文取 13；15 仍是独立经文。
        多个连续横线会继续并入前一个逻辑单位。
        """
        book_value = self.book_meta.get(book_name, {}).get("id", book_name)
        sql = (
            f"SELECT {self._quote(self.verse_col)} AS verse, {self._quote(self.text_col)} AS text "
            f"FROM {self._quote(self.verse_table)} "
            f"WHERE {self._quote(self.book_col)}=? AND {self._quote(self.chapter_col)}=? "
            f"ORDER BY {self._quote(self.verse_col)}"
        )
        raw_rows = self.conn.execute(sql, (book_value, chapter)).fetchall()
        rows = [(int(r["verse"]), str(r["text"] or "")) for r in raw_rows]
        result = []

        current = None
        for verse, text in rows:
            if self._is_placeholder_verse(text):
                if current is not None:
                    current["end"] = verse
                else:
                    current = {"start": verse, "end": verse, "text": text, "placeholder": True}
                continue

            if current is not None:
                logical_start = current["start"]
                logical_end = current["end"]
                logical_text = current["text"]
                if not (logical_start == logical_end and current.get("placeholder")):
                    if (start_verse is None or logical_end >= int(start_verse)) and (end_verse is None or logical_start <= int(end_verse)):
                        label = str(logical_start) if logical_start == logical_end else f"{logical_start}~{logical_end}"
                        result.append((label, logical_text, logical_start, logical_end))

            current = {"start": verse, "end": verse, "text": text, "placeholder": False}

        if current is not None:
            logical_start = current["start"]
            logical_end = current["end"]
            logical_text = current["text"]
            if not (logical_start == logical_end and current.get("placeholder")):
                if (start_verse is None or logical_end >= int(start_verse)) and (end_verse is None or logical_start <= int(end_verse)):
                    label = str(logical_start) if logical_start == logical_end else f"{logical_start}~{logical_end}"
                    result.append((label, logical_text, logical_start, logical_end))

        return result

    def get_verse_display_info(self, book_name, chapter, verse):
        """返回指定物理节所属的逻辑节号和正文。"""
        try:
            target = int(verse)
        except (TypeError, ValueError):
            return str(verse), ""
        for label, text, start, end in self.get_logical_verses(book_name, chapter):
            if start <= target <= end:
                return label, text
        return str(target), ""

    def get_verses(self, book_name, chapter, start_verse=None, end_verse=None):
        """读取经文；连接标记归属于前一节并合并为逻辑节号。"""
        return [
            (label, text)
            for label, text, _start, _end in self.get_logical_verses(
                book_name, chapter, start_verse, end_verse
            )
        ]

    def get_selection_verses(self, selection):
        """按多段选择查询经文，返回 (chapter, verse, text, titles) 列表。"""
        rows = []
        for span in selection.spans:
            titles = self.get_chapter_titles(selection.book, span.chapter)
            for label, text, logical_start, logical_end in self.get_logical_verses(
                selection.book, span.chapter, span.start, span.end
            ):
                merged_titles = []
                for verse in range(logical_start, logical_end + 1):
                    merged_titles.extend(titles.get(verse, []))
                rows.append((span.chapter, label, text, merged_titles))
        return rows
