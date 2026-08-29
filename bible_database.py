import os
import re
import sqlite3


class BibleDatabase:
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
        self.verse_table = "Titles" if any(r[0] == "Titles" for r in tables) else tables[0][0]
        columns = [r[1] for r in self.conn.execute(f'PRAGMA table_info("{self.verse_table}")').fetchall()]

        def find(names):
            lower = {c.lower(): c for c in columns}
            for name in names:
                if name.lower() in lower:
                    return lower[name.lower()]
            return None

        self.book_col = find(["Book", "book", "书卷", "书名"])
        self.chapter_col = find(["Chapter", "chapter", "章节", "章"])
        self.verse_col = find(["Verse", "verse", "节号", "节"])
        self.text_col = find(["Scripture", "scripture", "text", "content", "verse_text", "经文", "经文内容"])
        if not all([self.book_col, self.chapter_col, self.verse_col, self.text_col]):
            raise RuntimeError(f"无法识别和合本.db字段：当前表 {self.verse_table} 字段为：{', '.join(columns)}")

    def _quote(self, name):
        return '"' + name.replace('"', '""') + '"'

    def _build_book_index(self):
        rows = self.conn.execute(
            f"SELECT {self._quote(self.book_col)} AS book, MIN(rowid) AS first_row "
            f"FROM {self._quote(self.verse_table)} "
            f"WHERE {self._quote(self.book_col)} IS NOT NULL "
            f"GROUP BY {self._quote(self.book_col)} "
            f"ORDER BY first_row"
        ).fetchall()
        self.book_names = [str(r["book"]) for r in rows]

        codes = [
            "CSJ","CFJ","LWSJ","MSJ","SMJ","YSJ","SSM","LSJ","SWSJ","WSJ","DLSJ","DLZ","NLSJ","SL","NJ","STJ","YB","SJ","PS","PY","CDS","YGG","YSY","JLM","JLA","YZXJ","DNYL","HXS","YEL","AM","ESDY","YL","MH","NH","HB","HGY","MLJ","MJFY","MKFY","LJFY","YHFY","SHXS","LMS","GLLQ","YFS","FLB","GLX","TQ","TXQ","TSL","TSL","TQMS","TMD","TD","FLM","XLYS","YGS","YQ","BDE","BDH","YDS","JDS","JDYS","YD","QL"
        ]
        self.book_codes = {}
        for i, book in enumerate(self.book_names[:66], 1):
            self.book_codes[str(i)] = book
            if i <= len(codes):
                self.book_codes[codes[i - 1].lower()] = book

        self.short_names = {
            "创":"创世记","出":"出埃及记","利":"利未记","民":"民数记","申":"申命记","书":"约书亚记","士":"士师记","得":"路得记","撒上":"撒母耳记上","撒下":"撒母耳记下","王上":"列王纪上","王下":"列王纪下","代上":"历代志上","代下":"历代志下","拉":"以斯拉记","尼":"尼希米记","斯":"以斯帖记","伯":"约伯记","诗":"诗篇","箴":"箴言","传":"传道书","歌":"雅歌","赛":"以赛亚书","耶":"耶利米书","哀":"耶利米哀歌","结":"以西结书","但":"但以理书","何":"何西阿书","珥":"约珥书","摩":"阿摩司书","俄":"俄巴底亚书","拿":"约拿书","弥":"弥迦书","鸿":"那鸿书","哈":"哈巴谷书","番":"西番雅书","该":"哈该书","亚":"撒迦利亚书","玛":"玛拉基书","太":"马太福音","可":"马可福音","路":"路加福音","约":"约翰福音","徒":"使徒行传","罗":"罗马书","林前":"哥林多前书","林后":"哥林多后书","加":"加拉太书","弗":"以弗所书","腓":"腓立比书","西":"歌罗西书","帖前":"帖撒罗尼迦前书","帖后":"帖撒罗尼迦后书","提前":"提摩太前书","提后":"提摩太后书","多":"提多书","门":"腓利门书","来":"希伯来书","雅":"雅各书","彼前":"彼得前书","彼后":"彼得后书","约一":"约翰一书","约二":"约翰二书","约三":"约翰三书","犹":"犹大书","启":"启示录"
        }
        for short, full in self.short_names.items():
            if full in self.book_names:
                self.book_codes[short.lower()] = full

    def _normalize_code(self, value):
        return str(value).strip().lower().replace(" ", "")

    def _short_name(self, book):
        for short, full in self.short_names.items():
            if full == book:
                return short
        return book[:1]

    def search_books(self, query):
        q = self._normalize_code(query)
        if not q:
            return []
        if q in self.book_codes:
            return [self.book_codes[q]]
        results = []
        for book in self.book_names:
            codes = [code for code, target in self.book_codes.items() if target == book]
            if q in book.lower() or q in self._short_name(book).lower() or any(q in code for code in codes):
                if book not in results:
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
        row = self.conn.execute(f"SELECT MAX({self._quote(self.chapter_col)}) AS n FROM {self._quote(self.verse_table)} WHERE {self._quote(self.book_col)}=?", (book_name,)).fetchone()
        return int(row["n"] or 0)

    def get_verse_count(self, book_name, chapter):
        row = self.conn.execute(f"SELECT MAX({self._quote(self.verse_col)}) AS n FROM {self._quote(self.verse_table)} WHERE {self._quote(self.book_col)}=? AND {self._quote(self.chapter_col)}=?", (book_name, chapter)).fetchone()
        return int(row["n"] or 0)

    def get_verses(self, book_name, chapter, start_verse=None, end_verse=None):
        params = [book_name, chapter]
        sql = f"SELECT {self._quote(self.verse_col)} AS verse, {self._quote(self.text_col)} AS text FROM {self._quote(self.verse_table)} WHERE {self._quote(self.book_col)}=? AND {self._quote(self.chapter_col)}=?"
        if start_verse is not None:
            sql += f" AND {self._quote(self.verse_col)}>=?"
            params.append(start_verse)
        if end_verse is not None:
            sql += f" AND {self._quote(self.verse_col)}<=?"
            params.append(end_verse)
        sql += f" ORDER BY {self._quote(self.verse_col)}"
        return [(int(r["verse"]), str(r["text"])) for r in self.conn.execute(sql, params).fetchall()]

    def parse_reference(self, text):
        raw = str(text).strip().replace("：", ":").replace("．", ".").replace("。", ".")
        if not raw:
            return None

        # 小键盘：1.1.2.12 = 创世记1:2-12
        m = re.fullmatch(r"(\d{1,2})[.\s]+(\d+)[.\s]+(\d+)[.\s]+(\d+)", raw)
        if m:
            book, ch, start, end = m.groups()
            b = self.find_book(book)
            return (b, int(ch), int(start), int(end)) if b else None

        # 小键盘：1.1.2 = 创世记1:2
        m = re.fullmatch(r"(\d{1,2})[.\s]+(\d+)[.\s]+(\d+)", raw)
        if m:
            book, ch, verse = m.groups()
            b = self.find_book(book)
            return (b, int(ch), int(verse), int(verse)) if b else None

        # 创世记1:2-12 / CSJ1.2-12 / 创 1 2-12
        m = re.fullmatch(r"(.+?)[\s]*(\d+)(?::|[.\s]+)(\d+)(?:\s*-\s*(\d*))?", raw)
        if m:
            book_query, ch, start, end = m.groups()
            b = self.find_book(book_query)
            if b:
                return (b, int(ch), int(start), int(end) if end else (None if "-" in raw else int(start)))

        # 书卷 + 章节
        m = re.fullmatch(r"(.+?)[\s]*(\d+)", raw)
        if m:
            b = self.find_book(m.group(1))
            if b:
                return b, int(m.group(2)), None, None

        b = self.find_book(raw)
        return (b, 1, None, None) if b else None

    def close(self):
        self.conn.close()
