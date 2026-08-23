"""Tests for input validators."""

import pytest

from datagouv_mcp_tn.helpers.validators import (
    sanitize_text,
    validate_columns,
    validate_download_args,
    validate_filter_column,
    validate_filter_value,
    validate_id,
    validate_language,
    validate_limit,
    validate_metrics_args,
    validate_object_type,
    validate_offset,
    validate_openapi_args,
    validate_page,
    validate_page_size,
    validate_pagination_args,
    validate_preview_rows,
    validate_query,
    validate_query_resource_args,
    validate_resource_args,
    validate_search_args,
    validate_slug,
    validate_sort_column,
    validate_sort_order,
)


class TestCoreValidators:
    def test_validate_query_happy(self):
        assert validate_query("recensement tunisie") == "recensement tunisie"

    def test_validate_query_strips_whitespace(self):
        assert validate_query("  recensement  ") == "recensement"

    def test_validate_query_empty_raises(self):
        with pytest.raises(ValueError, match="must not be empty"):
            validate_query("")
        with pytest.raises(ValueError, match="must not be empty"):
            validate_query("   ")

    def test_validate_query_too_long_raises(self):
        long = "x" * 501
        with pytest.raises(ValueError, match="too long"):
            validate_query(long)

    def test_validate_query_strips_control_chars(self):
        assert validate_query("recensement\x00\x1f") == "recensement"

    def test_validate_id_happy(self):
        assert validate_id("abc-123", "Dataset ID") == "abc-123"
        assert validate_id("dataset_123", "Resource ID") == "dataset_123"

    def test_validate_id_empty_raises(self):
        with pytest.raises(ValueError, match="must not be empty"):
            validate_id("", "ID")

    def test_validate_id_too_long_raises(self):
        with pytest.raises(ValueError, match="too long"):
            validate_id("x" * 101, "ID")

    def test_validate_id_invalid_chars_raises(self):
        with pytest.raises(ValueError, match="Invalid.*format"):
            validate_id("abc@123", "ID")

    def test_validate_slug_happy(self):
        assert validate_slug("recensement-2024", "slug") == "recensement-2024"

    def test_validate_slug_lowercases(self):
        assert validate_slug("RECENSEMENT-2024", "slug") == "recensement-2024"

    def test_validate_slug_invalid_raises(self):
        with pytest.raises(ValueError, match="Invalid slug"):
            validate_slug("Recensement 2024", "slug")  # space
        with pytest.raises(ValueError, match="Invalid slug"):
            validate_slug("-recensement", "slug")  # leading hyphen

    def test_validate_page(self):
        assert validate_page(1) == 1
        assert validate_page(5) == 5
        with pytest.raises(ValueError, match=">="):
            validate_page(0)
        with pytest.raises(ValueError, match=">="):
            validate_page(-1)

    def test_validate_page_size(self):
        assert validate_page_size(20) == 20
        assert validate_page_size(100) == 100
        with pytest.raises(ValueError, match="between 1 and 100"):
            validate_page_size(0)
        with pytest.raises(ValueError, match="between 1 and 100"):
            validate_page_size(101)

    def test_validate_limit(self):
        assert validate_limit(50) == 50
        assert validate_limit(100, max_limit=100) == 100
        with pytest.raises(ValueError, match="between 1 and 100"):
            validate_limit(0)
        with pytest.raises(ValueError, match="between 1 and 50"):
            validate_limit(51, max_limit=50)

    def test_validate_offset(self):
        assert validate_offset(0) == 0
        assert validate_offset(100) == 100
        with pytest.raises(ValueError, match=">="):
            validate_offset(-1)

    def test_validate_columns_happy(self):
        assert validate_columns("col1,col2", ["col1", "col2", "col3"]) == ["col1", "col2"]
        assert validate_columns(" col1 , col2 ") == ["col1", "col2"]

    def test_validate_columns_empty_raises(self):
        with pytest.raises(ValueError, match="must not be empty"):
            validate_columns("")

    def test_validate_columns_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown column"):
            validate_columns("col1,unknown", ["col1"])

    def test_validate_columns_sql_keyword_raises(self):
        with pytest.raises(ValueError, match="reserved keyword"):
            validate_columns("select", ["select"])

    def test_validate_columns_invalid_name_raises(self):
        with pytest.raises(ValueError, match="Invalid column"):
            validate_columns("123col", ["123col"])

    def test_validate_filter_column(self):
        assert validate_filter_column("name", ["name", "id"]) == "name"
        assert validate_filter_column(None) is None
        with pytest.raises(ValueError, match="Unknown"):
            validate_filter_column("unknown", ["name"])

    def test_validate_filter_value(self):
        assert validate_filter_value("value") == "value"
        assert validate_filter_value(None) is None
        assert validate_filter_value("val\x00ue") == "value"
        with pytest.raises(ValueError, match="too long"):
            validate_filter_value("x" * 201)

    def test_validate_sort_column(self):
        assert validate_sort_column("created_at", ["created_at", "name"]) == "created_at"
        assert validate_sort_column(None) is None
        with pytest.raises(ValueError, match="Unknown"):
            validate_sort_column("unknown", ["name"])

    def test_validate_sort_order(self):
        from datagouv_mcp_tn.models.common import SortOrder

        assert validate_sort_order(SortOrder.ASCENDING) == SortOrder.ASCENDING
        assert validate_sort_order(SortOrder.DESCENDING) == SortOrder.DESCENDING
        assert validate_sort_order(None) == SortOrder.ASCENDING

    def test_validate_language(self):
        from datagouv_mcp_tn.helpers.i18n import Language

        assert validate_language(Language.FRENCH) == Language.FRENCH
        assert validate_language(Language.ARABIC) == Language.ARABIC
        # Default language from settings is French
        assert validate_language(None) == Language.FRENCH

    def test_validate_preview_rows(self):
        assert validate_preview_rows(5) == 5
        assert validate_preview_rows(20) == 20
        with pytest.raises(ValueError, match="between 1 and 20"):
            validate_preview_rows(0)
        with pytest.raises(ValueError, match="between 1 and 20"):
            validate_preview_rows(21)

    def test_validate_object_type(self):
        assert validate_object_type("dataset") == "dataset"
        assert validate_object_type("organization") == "organization"
        with pytest.raises(ValueError, match="must be one of"):
            validate_object_type("invalid")

    def test_sanitize_text(self):
        assert sanitize_text("hello") == "hello"
        assert sanitize_text("hello\x00world") == "helloworld"
        assert sanitize_text("x" * 15000, max_len=100) == "x" * 100


class TestCompositeValidators:
    def test_validate_search_args(self):
        from datagouv_mcp_tn.helpers.i18n import Language

        q, p, ps, lang = validate_search_args("recensement", 2, 50, Language.FRENCH)
        assert q == "recensement"
        assert p == 2
        assert ps == 50
        assert lang == Language.FRENCH

    def test_validate_search_args_invalid_page(self):
        with pytest.raises(ValueError, match=">="):
            validate_search_args("q", 0, 20, None)

    def test_validate_pagination_args(self):
        p, ps = validate_pagination_args(3, 10)
        assert (p, ps) == (3, 10)

    def test_validate_query_resource_args(self):
        from datagouv_mcp_tn.models.common import SortOrder

        args = validate_query_resource_args(
            dataset_id="ds-1",
            resource_id="res-2",
            columns="col1,col2",
            filter_column="name",
            filter_op="eq",
            filter_value="test",
            sort_by="created_at",
            sort_order=SortOrder.ASCENDING,
            limit=25,
            offset=10,
        )
        assert args[0] == "ds-1"
        assert args[1] == "res-2"
        assert args[2] == ["col1", "col2"]
        assert args[3] == "name"
        assert args[4] == "eq"
        assert args[5] == "test"
        assert args[6] == "created_at"
        assert args[7].value == "asc"
        assert args[8] == 25
        assert args[9] == 10

    def test_validate_download_args(self):
        ds, res, pr = validate_download_args("ds-1", "res-2", 10)
        assert (ds, res, pr) == ("ds-1", "res-2", 10)

    def test_validate_metrics_args(self):
        ot, oid = validate_metrics_args("dataset", "obj-123")
        assert (ot, oid) == ("dataset", "obj-123")

    def test_validate_openapi_args(self):
        assert validate_openapi_args("svc-1") == "svc-1"

    def test_validate_resource_args(self):
        assert validate_resource_args("ds-1") == "ds-1"


class TestSanitization:
    def test_sanitize_text_removes_control_chars(self):
        assert sanitize_text("line1\x00line2") == "line1line2"

    def test_sanitize_text_truncates(self):
        assert sanitize_text("x" * 200, max_len=50) == "x" * 50
