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

    def candidates(self, query):
        """返回符合当前简拼前缀的书卷。"""
        query = self.normalize(query)
        if query in self._cache:
            return self._cache[query]
        result = [book for book in self.db.book_names if self.code(book).startswith(query)] if query else []
        self._cache[query] = result
        return result

    def exact(self, query):
        """查找简拼完全匹配的书卷。"""
        query = self.normalize(query)
        for book in self.db.book_names:
            if self.code(book) == query:
                return book
        return None

    def unique_match(self, query):
        """仅在匹配结果唯一时返回书卷。"""
        candidates = self.candidates(query)
        if len(query) == 1 and len(candidates) == 1:
            return candidates[0]
        if len(candidates) == 1 and self.code(candidates[0]) == self.normalize(query):
            return candidates[0]
        return None
