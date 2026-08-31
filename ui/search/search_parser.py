import re


class SearchParser:
    """解析书卷、章节和节范围。"""

    SEPARATOR_RE = re.compile(r"\s*[:.]\s*")
    RANGE_RE = re.compile(r"\s*-\s*")

    @staticmethod
    def normalize(value):
        return (
            str(value or "")
            .strip()
            .replace("：", ":")
            .replace("．", ".")
            .replace("。", ".")
        )

    def parse(self, text, selected_book, exact_book, chapter_count, verse_count):
        value = self.normalize(text)
        book = selected_book

        if not book:
            match = re.match(r"^([A-Za-z]+)", value)
            book = exact_book(match.group(1)) if match else None

        if not book:
            return None

        suffix = value[len(book):].strip() if value.startswith(book) else value

        match = re.fullmatch(r"(\d+)", suffix)
        if match:
            chapter = int(match.group(1))
            return (book, chapter, None, None) if 1 <= chapter <= chapter_count(book) else None

        match = re.fullmatch(r"(\d+)\s*[:.]\s*(\d+)(?:\s*-\s*(\d+))?", suffix)
        if not match:
            return None

        chapter, verse, end = match.groups()
        chapter = int(chapter)
        verse = int(verse)
        end = int(end) if end else verse
        max_verse = verse_count(book, chapter)

        if 1 <= chapter <= chapter_count(book) and 1 <= verse <= end <= max_verse:
            return book, chapter, verse, end
        return None

    @staticmethod
    def parse_reference(value):
        value = SearchParser.normalize(value)
        match = re.fullmatch(r"(\d+)(?:\s*[:.]\s*(\d+)(?:\s*-\s*(\d*))?)?", value)
        return match.groups() if match else None
