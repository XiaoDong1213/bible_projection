"""经文选择模型：支持同章连续、跨章连续与跳节多段。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence


@dataclass(frozen=True)
class VerseSpan:
    """同一章内的连续节区间（含端点）。"""

    chapter: int
    start: int
    end: int

    def __post_init__(self):
        if self.end < self.start:
            start, end = self.end, self.start
            object.__setattr__(self, "start", start)
            object.__setattr__(self, "end", end)

    def contains(self, chapter: int, verse: int) -> bool:
        return self.chapter == chapter and self.start <= verse <= self.end

    def label(self, show_chapter: bool = True) -> str:
        if self.start == self.end:
            body = str(self.start)
        else:
            body = f"{self.start}-{self.end}"
        return f"{self.chapter}:{body}" if show_chapter else body


@dataclass(frozen=True)
class ScriptureSelection:
    """一次投影/搜索选中的经文集合。"""

    book: str
    spans: tuple[VerseSpan, ...]

    def __post_init__(self):
        if not self.book:
            raise ValueError("book is required")
        if not self.spans:
            raise ValueError("spans must not be empty")
        object.__setattr__(self, "spans", tuple(self.spans))

    @classmethod
    def single_chapter(
        cls,
        book: str,
        chapter: int,
        start: int | None = None,
        end: int | None = None,
        *,
        max_verse: int | None = None,
    ) -> "ScriptureSelection":
        s = 1 if start is None else int(start)
        if end is None:
            e = int(max_verse) if max_verse is not None else s
        else:
            e = int(end)
        return cls(book=str(book), spans=(VerseSpan(int(chapter), s, e),))

    @classmethod
    def from_legacy(cls, book, chapter, start, end) -> "ScriptureSelection":
        return cls.single_chapter(book, chapter, start, end)

    @property
    def is_simple(self) -> bool:
        return len(self.spans) == 1

    @property
    def is_multi_chapter(self) -> bool:
        chapters = {span.chapter for span in self.spans}
        return len(chapters) > 1

    @property
    def primary_chapter(self) -> int:
        return self.spans[0].chapter

    @property
    def primary_start(self) -> int:
        return self.spans[0].start

    @property
    def primary_end(self) -> int:
        return self.spans[-1].end if self.is_simple else self.spans[0].end

    def to_legacy(self) -> tuple[str, int, int, int] | None:
        """仅单章单段时可转回旧四元组。"""
        if not self.is_simple:
            return None
        span = self.spans[0]
        return self.book, span.chapter, span.start, span.end

    def label(self) -> str:
        if self.is_simple and not self.is_multi_chapter:
            span = self.spans[0]
            if span.start == span.end:
                return f"{self.book} {span.chapter}:{span.start}"
            return f"{self.book} {span.chapter}:{span.start}-{span.end}"

        # 同章多段：约翰福音 3:16,18,20
        if not self.is_multi_chapter:
            chapter = self.spans[0].chapter
            bodies = []
            for span in self.spans:
                if span.start == span.end:
                    bodies.append(str(span.start))
                else:
                    bodies.append(f"{span.start}-{span.end}")
            return f"{self.book} {chapter}:" + ",".join(bodies)

        # 连续跨章：优先显示 3:16-4:2
        if self._is_contiguous_cross():
            first, last = self.spans[0], self.spans[-1]
            return (
                f"{self.book} {first.chapter}:{first.start}"
                f"-{last.chapter}:{last.end}"
            )

        parts = [span.label(show_chapter=True) for span in self.spans]
        return f"{self.book} " + ",".join(parts)

    def _is_contiguous_cross(self) -> bool:
        if len(self.spans) < 2:
            return False
        chapters = [span.chapter for span in self.spans]
        if chapters != list(range(chapters[0], chapters[-1] + 1)):
            return False
        # 中间章必须是整段展开后的形态，此处只要求章连续
        return True

    def title(self) -> str:
        """投影标题文案。"""
        unit = "篇" if self.book == "诗篇" else "章"
        if self.is_simple and not self.is_multi_chapter:
            span = self.spans[0]
            if span.start == span.end:
                return f"{self.book}{span.chapter}{unit}{span.start}节"
            return f"{self.book}{span.chapter}{unit}{span.start}-{span.end}节"
        return self.label()

    def to_history_entry(self) -> dict:
        return {
            "book": self.book,
            "spans": [
                {"c": span.chapter, "s": span.start, "e": span.end}
                for span in self.spans
            ],
        }

    @classmethod
    def from_history_entry(cls, entry) -> "ScriptureSelection | None":
        try:
            if isinstance(entry, dict):
                book = str(entry["book"])
                spans = tuple(
                    VerseSpan(int(item["c"]), int(item["s"]), int(item["e"]))
                    for item in entry.get("spans") or []
                )
                if not spans:
                    return None
                return cls(book=book, spans=spans)
            if isinstance(entry, (list, tuple)) and len(entry) == 4:
                return cls.from_legacy(entry[0], entry[1], entry[2], entry[3])
        except (KeyError, TypeError, ValueError):
            return None
        return None

    @staticmethod
    def expand_cross_chapter(
        book: str,
        start_chapter: int,
        start_verse: int,
        end_chapter: int,
        end_verse: int,
        verse_count,
    ) -> "ScriptureSelection":
        """把跨章连续范围展开为多段同章区间。"""
        if end_chapter < start_chapter or (
            end_chapter == start_chapter and end_verse < start_verse
        ):
            start_chapter, end_chapter = end_chapter, start_chapter
            start_verse, end_verse = end_verse, start_verse

        spans: list[VerseSpan] = []
        for chapter in range(start_chapter, end_chapter + 1):
            max_v = int(verse_count(book, chapter) or 0)
            if max_v <= 0:
                continue
            if chapter == start_chapter and chapter == end_chapter:
                s, e = start_verse, end_verse
            elif chapter == start_chapter:
                s, e = start_verse, max_v
            elif chapter == end_chapter:
                s, e = 1, end_verse
            else:
                s, e = 1, max_v
            s = max(1, min(s, max_v))
            e = max(1, min(e, max_v))
            if e < s:
                continue
            spans.append(VerseSpan(chapter, s, e))
        if not spans:
            raise ValueError("empty cross-chapter range")
        return ScriptureSelection(book=book, spans=tuple(spans))

    @staticmethod
    def merge_spans(spans: Sequence[VerseSpan]) -> tuple[VerseSpan, ...]:
        """合并同章相邻/重叠区间，保持章序。"""
        ordered = sorted(spans, key=lambda sp: (sp.chapter, sp.start, sp.end))
        merged: list[VerseSpan] = []
        for span in ordered:
            if not merged:
                merged.append(span)
                continue
            last = merged[-1]
            if span.chapter == last.chapter and span.start <= last.end + 1:
                merged[-1] = VerseSpan(last.chapter, last.start, max(last.end, span.end))
            else:
                merged.append(span)
        return tuple(merged)

    @classmethod
    def from_spans(cls, book: str, spans: Iterable[VerseSpan]) -> "ScriptureSelection":
        merged = cls.merge_spans(tuple(spans))
        return cls(book=book, spans=merged)

    @classmethod
    def from_space_verses(
        cls,
        book: str,
        chapter: int,
        text: str,
        max_verse: int,
    ) -> "ScriptureSelection | None":
        """解析同章空格分隔节号，支持 16-18 20 22-25。"""
        import re

        raw = str(text or "").strip()
        if not raw:
            return None
        tokens = [t for t in re.split(r"[\s,，;；]+", raw) if t]
        if not tokens:
            return None
        spans: list[VerseSpan] = []
        for token in tokens:
            token = token.strip()
            m = re.fullmatch(r"(\d+)(?:\s*-\s*(\d+))?", token)
            if not m:
                return None
            start = int(m.group(1))
            end = int(m.group(2)) if m.group(2) else start
            if end < start:
                start, end = end, start
            if not (1 <= start <= max_verse and 1 <= end <= max_verse):
                return None
            spans.append(VerseSpan(int(chapter), start, end))
        if not spans:
            return None
        return cls.from_spans(book, spans)

    def space_verse_text(self) -> str:
        """同章多段时还原为空格分隔文本。"""
        if self.is_multi_chapter:
            return ""
        parts = []
        for span in self.spans:
            if span.start == span.end:
                parts.append(str(span.start))
            else:
                parts.append(f"{span.start}-{span.end}")
        return " ".join(parts)
