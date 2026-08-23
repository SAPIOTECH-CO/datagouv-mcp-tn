"""Pydantic models for uData dataservices (APIs published on the portal)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import AliasChoices, BaseModel, Field

from datagouv_mcp_tn.models.dataset import OrganizationRef
from datagouv_mcp_tn.models.metrics import Metrics


class Endpoint(BaseModel):
    """An endpoint exposed by a dataservice."""

    name: str | None = None
    url: str | None = None
    description: str | None = None


class Dataservice(BaseModel):
    """A dataservice on the portal, tolerant to partial payloads."""

    id: str
    title: str | None = Field(
        default=None, validation_alias=AliasChoices("title", "name")
    )
    description: str | None = None
    base_api_url: str | None = None
    endpoints: list[Endpoint] = []
    organization: OrganizationRef | None = None
    created_at: datetime | None = None
    last_update: datetime | None = None
    page: str | None = None

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> Dataservice:
        return cls.model_validate(data)

    @property
    def display_title(self) -> str:
        return self.title or self.id
