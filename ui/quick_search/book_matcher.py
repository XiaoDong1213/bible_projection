class BookMatcher:
    """负责书卷简拼匹配。"""

    def __init__(self, db):
        self.db = db
        self._cache = {}

    @staticmethod
    def normalize(value):
        """统一搜索编码格式。"""
        return str(value or "").strip().lower().replace(" ", "").replace(".", "").replace("_", "").replace("-", "")

    def code(self, book):
        """获取指定书卷的简拼编码。"""
        meta = self.db.book_meta.get(book, {})
        return self.normalize(meta.get("pinyin", ""))

    def aliases(self, book):
        """书卷的全部可匹配别名：拼音码 / 简称 / 书卷名（均归一化）。

        中文库：拼音码 + 中文 书卷名；英文库：拼音列（常含英文缩写）+
        英文缩写 + 英文全名。多语言译本通用。
        """
        meta = self.db.book_meta.get(book, {})
        aliases = [self.code(book), self.normalize(meta.get("short", "")), self.normalize(book)]
        return [a for a in aliases if a]

    def candidates(self, query):
        """返回符合当前前缀的书卷（拼音码 / 简称 / 书卷名前缀）。"""
        query = self.normalize(query)
        if query in self._cache:
            return self._cache[query]
        if query:
            result = [
                book for book in self.db.book_names
                if any(a.startswith(query) for a in self.aliases(book))
            ]
        else:
            result = []
        self._cache[query] = result
        return result

    def exact(self, query):
        """查找完全匹配的书卷。"""
        query = self.normalize(query)
        for book in self.db.book_names:
            if query in self.aliases(book):
                return book
        return None

