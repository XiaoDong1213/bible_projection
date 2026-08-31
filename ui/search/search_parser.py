import re


class SearchParser:
    """解析书卷、章节和节范围。"""

    @staticmethod
    def normalize(value):
        """统一章节搜索中的标点格式。"""
        return (
            str(value or "")
            .strip()
            .replace("：", ":")
            .replace("．", ".")
            .replace("。", ".")
        )

    def parse(self, text, selected_book, exact_book, chapter_count, verse_count):
        """解析搜索内容并校验章节、节范围。"""
        value = self.normalize(text)
        book = selected_book

        # 未选定书卷时，先从输入内容中识别简拼
        if not book:
            match = re.match(r"^([A-Za-z]+)", value)
            book = exact_book(match.group(1)) if match else None

        if not book:
            return None

        suffix = value[len(book):].strip() if value.startswith(book) else value

        # 只输入章节时，默认选择整章
        match = re.fullmatch(r"(\d+)", suffix)
        if match:
            chapter = int(match.group(1))
            if 1 <= chapter <= chapter_count(book):
                return book, chapter, None, None
            return None

        match = re.fullmatch(
            r"(\d+)\s*[:.]\s*(\d+)(?:\s*-\s*(\d*))?",
            suffix,
        )
        if not match:
            return None

        chapter, verse, end = match.groups()
        chapter = int(chapter)
        verse = int(verse)

        if not 1 <= chapter <= chapter_count(book):
            return None

        max_verse = verse_count(book, chapter)
        if not 1 <= verse <= max_verse:
            return None

        # 省略末节时，范围直接延伸到本章最后一节
        if end is None or end == "":
            end = max_verse
        else:
            end = int(end)

        if verse <= end <= max_verse:
            return book, chapter, verse, end
        return None

    @staticmethod
    def parse_reference(value):
        """解析纯章节或章节节范围。"""
        value = SearchParser.normalize(value)
        match = re.fullmatch(
            r"(\d+)(?:\s*[:.]\s*(\d+)(?:\s*-\s*(\d*))?)?",
            value,
        )
        return match.groups() if match else None
