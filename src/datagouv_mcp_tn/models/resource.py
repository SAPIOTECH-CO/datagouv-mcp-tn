"""Pydantic models for uData resources (files and APIs attached to datasets)."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from pydantic import AliasChoices, BaseModel, Field, ValidationError, field_validator

logger = logging.getLogger(__name__)


class Checksum(BaseModel):
    type: str = "sha1"
    value: str

    @classmethod
    def from_api(cls, data: Any) -> Checksum | None:
        if data is None:
            return None
        if isinstance(data, str):
            return cls(value=data)
        return cls.model_validate(data)


class Resource(BaseModel):
    """A single resource of a dataset (file, remote file or API).

    Tolerant by design: uData payloads vary between the portal versions, so
    every optional field defaults to ``None`` instead of failing validation,
    and loosely-typed fields (string sizes, string checksums) are coerced.
    """

    id: str
    title: str | None = Field(default=None, validation_alias=AliasChoices("title", "name"))
    description: str | None = None
    format: str | None = None
    mime: str | None = None
    filesize: int | None = Field(default=None, ge=0)
    url: str | None = None
    checksum: Checksum | None = None
    created_at: datetime | None = None
    last_modified: datetime | None = None

    @field_validator("filesize", mode="before")
    @classmethod
    def _coerce_filesize(cls, value: Any) -> Any:
        if isinstance(value, str):
            cleaned = value.strip().replace(" ", "")
            return int(cleaned) if cleaned.isdigit() else None
        return value

    @field_validator("checksum", mode="before")
    @classmethod
    def _coerce_checksum(cls, value: Any) -> Any:
        return Checksum.from_api(value)

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> Resource:
        return cls.model_validate(data)

    @classmethod
    def from_api_list(cls, items: Any) -> list[Resource]:
        """Parse a list of raw resources, skipping malformed entries."""
        if not isinstance(items, list):
            return []
        parsed: list[Resource] = []
        for item in items:
            if not isinstance(item, dict) or not item.get("id"):
                continue
            try:
                parsed.append(cls.model_validate(item))
            except ValidationError as exc:
                logger.warning("Skipping malformed resource %s: %s", item.get("id"), exc)
        return parsed

    @property
    def display_title(self) -> str:
        return self.title or self.id

    @property
    def human_size(self) -> str | None:
        if self.filesize is None:
            return None
        size = float(self.filesize)
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if size < 1024 or unit == "TB":
                precision = 0 if unit == "B" else 1
                return f"{size:.{precision}f} {unit}"
            size /= 1024
        return None
