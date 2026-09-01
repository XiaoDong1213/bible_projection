"""解析书卷与同章经文范围（跨章/跳节改由左侧导航处理）。"""

from __future__ import annotations

import re

from ..selection import ScriptureSelection, VerseSpan


class SearchParser:
    """解析书卷简拼后的同章章节/节范围。"""

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

    def parse(
        self,
        text,
        selected_book,
        exact_book,
        chapter_count,
        verse_count,
        book_names=None,
    ):
        """解析搜索内容，返回同章 ScriptureSelection 或 None。"""
        value = self.normalize(text)
        if not value:
            return None

        book = None
        suffix = value

        if selected_book and value.startswith(selected_book):
            book = selected_book
            suffix = value[len(selected_book):].strip()
        else:
            match = re.match(r"^([A-Za-z]+)", value)
            if match:
                book = exact_book(match.group(1))
                if book:
                    suffix = value[len(match.group(1)):].strip()
            if not book and book_names:
                for name in sorted(book_names, key=len, reverse=True):
                    if value.startswith(name):
                        book = name
                        suffix = value[len(name):].strip()
                        break
            if not book and selected_book:
                book = selected_book
                suffix = value

        if not book or not suffix:
            return None

        return self.parse_suffix(book, suffix, chapter_count, verse_count)

    def parse_suffix(self, book, suffix, chapter_count, verse_count):
        """仅解析同章：整章 / 单节 / 连续节。未写完的「节-」返回 None。"""
        value = self.normalize(suffix).strip()
        if not value:
            return None

        max_chapter = int(chapter_count(book) or 0)
        if max_chapter <= 0:
            return None

        if re.fullmatch(r"\d+", value):
            chapter = int(value)
            if not 1 <= chapter <= max_chapter:
                return None
            max_v = int(verse_count(book, chapter) or 0)
            if max_v <= 0:
                return None
            return ScriptureSelection.single_chapter(
                book, chapter, 1, max_v, max_verse=max_v
            )

        match = re.fullmatch(
            r"(\d+)\s*[:.]\s*(\d+)(?:\s*-\s*(\d+))?",
            value,
        )
        if not match:
            return None

        chapter, verse, end = match.groups()
        chapter = int(chapter)
        verse = int(verse)
        if not 1 <= chapter <= max_chapter:
            return None
        max_v = int(verse_count(book, chapter) or 0)
        if not 1 <= verse <= max_v:
            return None

        if end is None:
            return ScriptureSelection.single_chapter(book, chapter, verse, verse)

        end_v = int(end)
        if not verse <= end_v <= max_v:
            return None
        return ScriptureSelection.single_chapter(book, chapter, verse, end_v)

    @staticmethod
    def parse_reference(value):
        """解析纯章节预览。"""
        value = SearchParser.normalize(value)
        # 未完成的「3:16-」不当作完整引用
        if re.search(r"-\s*$", value):
            return None
        match = re.fullmatch(
            r"(\d+)(?:\s*[:.]\s*(\d+)(?:\s*-\s*(\d+))?)?",
            value,
        )
        return match.groups() if match else None
