"""Shared Pydantic models: pagination, sorting and filtering primitives.

Request-side models (:class:`Pagination`, :class:`Sort`, :class:`FieldFilter`)
translate tool arguments into uData query parameters; :class:`PaginationInfo`
describes the pagination metadata returned by uData list endpoints.
"""

from __future__ import annotations

import math
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field

_ARABIC_RESULT_UNITS = {"one": "نتيجة", "many": "نتائج"}


class SortOrder(StrEnum):
    ASCENDING = "asc"
    DESCENDING = "desc"


class Sort(BaseModel):
    """Sort specification rendered as a uData sort parameter.

    uData marks descending order with a leading dash: ``-title``.
    """

    field: str = Field(min_length=1)
    order: SortOrder = SortOrder.ASCENDING

    def to_param(self) -> str:
        if self.order is SortOrder.DESCENDING:
            return f"-{self.field}"
        return self.field


class FieldFilter(BaseModel):
    """A single field filter rendered as ``field=value`` query parameters."""

    field: str = Field(min_length=1)
    value: str
    operator: Literal["exact", "not"] = "exact"

    def to_params(self) -> dict[str, Any]:
        key = self.field if self.operator == "exact" else f"{self.field}__not"
        return {key: self.value}


class Pagination(BaseModel):
    """Request-side pagination constraints shared by all search tools."""

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)

    def to_params(self) -> dict[str, int]:
        return {"page": self.page, "page_size": self.page_size}


class PaginationInfo(BaseModel):
    """Response-side pagination metadata from a uData list payload."""

    page: int = 1
    page_size: int = 20
    total: int = 0

    @classmethod
    def from_udata(
        cls,
        data: dict[str, Any],
        default_page: int = 1,
        default_page_size: int = 20,
    ) -> PaginationInfo:
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

    def describe(self, language: Any = None) -> str:
        """Pagination summary; pass a :class:`~datagouv_mcp_tn.helpers.i18n.Language`
        to localize (defaults to English)."""
        pages = f"/{self.total_pages}" if self.total_pages is not None else ""
        if language is None:
            plural = "" if self.total == 1 else "s"
            return f"Page {self.page}{pages} · {self.total} result{plural}"
        from datagouv_mcp_tn.helpers.i18n import Language, MessageKey, resolve_language, translate

        lang = resolve_language(language)
        kwargs: dict[str, Any] = {
            "page": self.page,
            "pages": pages,
            "count": self.total,
            "plural": "" if self.total == 1 else "s",
            "unit": "",
        }
        if lang is Language.ARABIC:
            kwargs["unit"] = (
                _ARABIC_RESULT_UNITS["one"] if self.total == 1 else _ARABIC_RESULT_UNITS["many"]
            )
        return translate(MessageKey.PAGINATION_LINE, lang, **kwargs)
