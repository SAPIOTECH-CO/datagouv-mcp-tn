"""Pydantic models for uData datasets."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel

from datagouv_mcp_tn.models.resource import Resource


class OrganizationRef(BaseModel):
    """Lightweight organization reference embedded in datasets/dataservices."""

    id: str | None = None
    name: str | None = None
    acronym: str | None = None
    logo: str | None = None
    page: str | None = None


class LicenseRef(BaseModel):
    """License info; uData sends either an object or a plain string id."""

    id: str | None = None
    title: str | None = None
    url: str | None = None

    @classmethod
    def from_api(cls, data: Any) -> LicenseRef:
        if data is None:
            return cls()
        if isinstance(data, str):
            return cls(id=data)
        return cls.model_validate(data)


class Dataset(BaseModel):
    """A dataset on the portal, tolerant to partial payloads."""

    id: str
    title: str | None = None
    slug: str | None = None
    description: str | None = None
    tags: list[str] = []
    license: LicenseRef | None = None
    organization: OrganizationRef | None = None
    resources: list[Resource] = []
    created_at: datetime | None = None
    last_update: datetime | None = None
    page: str | None = None

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> Dataset:
        payload = dict(data)
        payload["license"] = LicenseRef.from_api(payload.get("license"))
        # Parse resources individually so one malformed entry doesn't fail
        # the whole dataset (preserves the pre-models skip-and-continue UX).
        payload["resources"] = Resource.from_api_list(payload.get("resources"))
        return cls.model_validate(payload)

    @property
    def display_title(self) -> str:
        return self.title or self.id

    @property
    def portal_url(self) -> str | None:
        if self.page:
            return f"https://data.gouv.tn{self.page}" if self.page.startswith("/") else self.page
        if self.slug:
            return f"https://data.gouv.tn/fr/datasets/{self.slug}"
        return None
