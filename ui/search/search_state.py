from dataclasses import dataclass


@dataclass
class SearchState:
    """保存搜索过程中的界面状态。"""

    stage: str = "book"
    selected_book: str | None = None
    converted_book: bool = False
    space_mode: bool = False
    formatting: bool = False
    confirming: bool = False
