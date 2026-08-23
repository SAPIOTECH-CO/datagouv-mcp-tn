"""Pagination metadata for uData list responses.

uData paginated payloads look like::

    {"total": 231, "page": 2, "page_size": 20, "data": [...]}
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class PaginationInfo:
    page: int
    page_size: int
    total: int

    @classmethod
    def from_udata(cls, data: dict, default_page: int = 1, default_page_size: int = 20) -> PaginationInfo:
        return cls(
            page=int(data.get("page") or default_page),
            page_size=int(data.get("page_size") or default_page_size),
            total=int(data.get("total") or 0),
        )

    @property
    def total_pages(self) -> int | None:
        if self.total == 0:
            return 0
        return max(1, math.ceil(self.total / self.page_size)) if self.page_size else None

    def describe(self) -> str:
        """One-line human-readable pagination summary for tool output."""
        pages = f"/{self.total_pages}" if self.total_pages is not None else ""
        plural = "" if self.total == 1 else "s"
        return f"Page {self.page}{pages} · {self.total} result{plural}"
