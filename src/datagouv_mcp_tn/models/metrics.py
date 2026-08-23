"""Pydantic models for uData metrics payloads.

uData exposes metrics either as a dict (``{"views": 12, ...}``) or as a
comma-separated string of ``key:value`` pairs; both shapes normalize here.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class Metrics(BaseModel):
    """Common visitation/engagement counters; unknown keys are preserved."""

    model_config = {"extra": "allow"}

    views: int | None = Field(default=None, ge=0)
    followers: int | None = Field(default=None, ge=0)
    reuses: int | None = Field(default=None, ge=0)
    datasets: int | None = Field(default=None, ge=0)

    @classmethod
    def from_api(cls, data: Any) -> Metrics:
        if data is None:
            return cls()
        if isinstance(data, str):
            parsed: dict[str, int] = {}
            for chunk in data.split(","):
                key, _, value = chunk.partition(":")
                if value.strip().isdigit():
                    parsed[key.strip()] = int(value.strip())
            return cls.model_validate(parsed)
        if isinstance(data, dict):
            return cls.model_validate(data)
        return cls()


class DatasetMetrics(Metrics):
    """Metrics attached to a dataset."""


class OrganizationMetrics(Metrics):
    """Metrics attached to an organization (adds member count)."""

    members: int | None = Field(default=None, ge=0)


class ResourceMetrics(Metrics):
    """Download metrics attached to a resource."""
