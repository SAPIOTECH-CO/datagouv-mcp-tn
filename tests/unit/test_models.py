from typing import Any

import pytest
from pydantic import ValidationError

from datagouv_mcp_tn.models import (
    Dataservice,
    Dataset,
    DatasetMetrics,
    FieldFilter,
    LicenseRef,
    Metrics,
    OrganizationMetrics,
    Pagination,
    PaginationInfo,
    Resource,
    Sort,
    SortOrder,
)

# --- TASK-018: common primitives ---


def test_sort_to_param_uses_udata_dash_convention():
    assert Sort(field="title").to_param() == "title"
    assert Sort(field="title", order=SortOrder.DESCENDING).to_param() == "-title"


def test_field_filter_to_params_exact_and_not():
    assert FieldFilter(field="organization", value="ministere").to_params() == {
        "organization": "ministere"
    }
    assert FieldFilter(field="format", value="csv", operator="not").to_params() == {
        "format__not": "csv"
    }


def test_pagination_validates_bounds():
    with pytest.raises(ValidationError):
        Pagination(page=0)
    with pytest.raises(ValidationError):
        Pagination(page_size=101)
    assert Pagination(page=2, page_size=50).to_params() == {"page": 2, "page_size": 50}


def test_pagination_from_udata_reads_fields():
    info = PaginationInfo.from_udata({"total": 231, "page": 2, "page_size": 20})
    assert (info.page, info.page_size, info.total) == (2, 20, 231)


def test_pagination_from_udata_applies_defaults_for_missing_fields():
    info = PaginationInfo.from_udata({}, default_page=3, default_page_size=50)
    assert (info.page, info.page_size, info.total) == (3, 50, 0)


@pytest.mark.parametrize(
    "total,page_size,expected",
    [(231, 20, 12), (40, 20, 2), (41, 20, 3), (0, 20, 0), (1, 1, 1)],
)
def test_pagination_total_pages_rounds_up(total, page_size, expected):
    assert PaginationInfo(page=1, page_size=page_size, total=total).total_pages == expected


def test_pagination_describe_formats_summary():
    assert PaginationInfo(page=2, page_size=20, total=231).describe() == "Page 2/12 · 231 results"
    assert PaginationInfo(page=1, page_size=20, total=1).describe() == "Page 1/1 · 1 result"


def test_pagination_describe_localizes():
    info = PaginationInfo(page=2, page_size=20, total=231)
    from datagouv_mcp_tn.helpers.i18n import Language

    assert info.describe(Language.FRENCH) == "Page 2/12 · 231 résultats"
    assert info.describe(Language.ENGLISH) == "Page 2/12 · 231 results"
    arabic = info.describe("ar")
    assert "صفحة 2/12" in arabic and "231" in arabic and "نتائج" in arabic


# --- TASK-015: resource ---


@pytest.fixture
def resource_payload() -> dict[str, Any]:
    return {
        "id": "res-1",
        "title": "Recettes 2024",
        "description": "Budget details",
        "format": "csv",
        "mime": "text/csv",
        "filesize": 2048,
        "url": "https://data.gouv.tn/datasets/recettes.csv",
        "checksum": {"type": "sha1", "value": "abc123"},
        "last_modified": "2024-05-01T00:00:00+00:00",
    }


def test_resource_parses_full_payload(resource_payload):
    resource = Resource.from_api(resource_payload)
    assert resource.display_title == "Recettes 2024"
    assert resource.format == "csv"
    assert resource.human_size == "2.0 KB"
    assert resource.checksum is not None and resource.checksum.value == "abc123"


def test_resource_tolerates_partial_payload_and_name_alias():
    resource = Resource.from_api({"id": "res-2", "name": "fallback-name"})
    assert resource.display_title == "fallback-name"
    assert resource.human_size is None
    assert resource.format is None


def test_resource_human_size_scales():
    assert Resource(id="x", filesize=512).human_size == "512 B"
    assert Resource(id="x", filesize=5 * 1024 * 1024).human_size == "5.0 MB"


def test_resource_skips_malformed_entries_in_list():
    resources = Resource.from_api_list(
        [
            {"id": "ok", "title": "fine.csv"},
            {"title": "no-id.csv"},  # missing id -> skipped
            {"id": 42, "title": "bad-id"},  # wrong id type -> skipped
            "not-a-dict",  # junk entry -> skipped
            None,
        ]
    )
    assert [r.id for r in resources] == ["ok"]


def test_resource_coerces_loose_field_types():
    resource = Resource.from_api({"id": "res-3", "filesize": "2048", "checksum": "abc123"})
    assert resource.filesize == 2048
    assert resource.checksum is not None and resource.checksum.value == "abc123"
    assert resource.checksum.type == "sha1"


# --- TASK-014: dataset ---


def test_dataset_parses_nested_resources_and_refs():
    dataset = Dataset.from_api(
        {
            "id": "ds-1",
            "title": "Population",
            "slug": "population",
            "tags": ["demographie"],
            "license": {"id": "lov2", "title": "Licence Ouverte"},
            "organization": {"id": "org-1", "name": "INS", "acronym": "ins"},
            "resources": [{"id": "res-1", "title": "pop.csv", "format": "csv"}],
            "page": "/fr/datasets/population/",
        }
    )
    assert len(dataset.resources) == 1
    assert dataset.organization is not None and dataset.organization.acronym == "ins"
    assert dataset.license is not None and dataset.license.title == "Licence Ouverte"
    assert dataset.portal_url == "/fr/datasets/population/"


def test_dataset_license_accepts_string_id():
    dataset = Dataset.from_api({"id": "ds-2", "license": "lov2"})
    assert dataset.license == LicenseRef(id="lov2")


def test_dataset_tolerates_one_bad_resource_among_good_ones():
    dataset = Dataset.from_api(
        {
            "id": "ds-9",
            "resources": [
                {"id": "good-1", "title": "a.csv"},
                {"title": "missing-id.csv"},
                {"id": "good-2", "filesize": "not-a-number"},
            ],
        }
    )
    # malformed entry skipped, loosely-typed entry kept with filesize=None
    assert [r.id for r in dataset.resources] == ["good-1", "good-2"]
    assert dataset.resources[1].filesize is None


def test_dataset_defaults_are_safe():
    dataset = Dataset.from_api({"id": "ds-3"})
    assert dataset.resources == []
    assert dataset.portal_url is None
    assert dataset.display_title == "ds-3"


# --- TASK-016: dataservice ---


def test_dataservice_parses_endpoints():
    dataservice = Dataservice.from_api(
        {
            "id": "api-1",
            "name": "API recensement",
            "base_api_url": "https://api.gouv.tn/census",
            "endpoints": [{"url": "https://api.gouv.tn/census/v1"}],
        }
    )
    assert dataservice.display_title == "API recensement"
    assert dataservice.endpoints[0].url == "https://api.gouv.tn/census/v1"


# --- TASK-017: metrics ---


@pytest.mark.parametrize(
    "payload",
    [
        {"views": 12, "followers": 3},
        "views:12,followers:3",
        None,
    ],
)
def test_metrics_normalizes_dict_and_string_shapes(payload):
    metrics = Metrics.from_api(payload)
    if payload is None:
        assert metrics.views is None
    else:
        assert metrics.views == 12
        assert metrics.followers == 3


def test_metrics_preserves_unknown_keys():
    metrics = Metrics.from_api({"views": 5, "unusual_metric": 7})
    assert metrics.model_extra == {"unusual_metric": 7}


def test_organization_and_dataset_metrics_subtypes():
    org = OrganizationMetrics(members=42)
    ds = DatasetMetrics(datasets=9)
    assert org.members == 42
    assert ds.datasets == 9
