class BookMatcher:
    """负责书卷简拼匹配。"""

    def __init__(self, db):
        self.db = db
        self._cache = {}

    @staticmethod
    def normalize(value):
        return str(value or "").strip().lower().replace(" ", "").replace(".", "").replace("_", "").replace("-", "")

    def code(self, book):
        meta = self.db.book_meta.get(book, {})
        return self.normalize(meta.get("pinyin", ""))

    def candidates(self, query):
        query = self.normalize(query)
        if query in self._cache:
            return self._cache[query]
        result = [book for book in self.db.book_names if self.code(book).startswith(query)] if query else []
        self._cache[query] = result
        return result

    def exact(self, query):
        query = self.normalize(query)
        for book in self.db.book_names:
            if self.code(book) == query:
                return book
        return None

    def unique_match(self, query):
        candidates = self.candidates(query)
        if len(query) == 1 and len(candidates) == 1:
            return candidates[0]
        if len(candidates) == 1 and self.code(candidates[0]) == self.normalize(query):
            return candidates[0]
        return None
