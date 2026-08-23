import json
import xml.etree.ElementTree as ET

import pytest
from _factories import (
    CSV_BYTES,
    HTML_PAGE,
    KML_DOC,
    SVG_DOC,
    make_docx,
    make_kmz,
    make_pdf,
    make_png,
    make_pptx,
    make_zip,
)
from PIL import UnidentifiedImageError

from datagouv_mcp_tn.helpers.document_inspector import inspect_non_tabular, sniff_kind
from datagouv_mcp_tn.helpers.file_parser import (
    decode_text_best_effort,
    is_tabular_filename,
    normalize_format,
)


def test_normalize_format_variants():
    assert normalize_format(" CSV ") == "csv"
    assert normalize_format(".JPG") == "jpg"
    assert normalize_format(None) == ""
    assert normalize_format("Word") == "word"


def test_is_tabular_filename():
    assert is_tabular_filename("data/population.CSV")
    assert is_tabular_filename("stats.xlsx")
    assert not is_tabular_filename("rapport.pdf")
    assert not is_tabular_filename("no_extension")


def test_decode_text_best_effort_handles_cp1252():
    legacy = "Prix en dinars: élevé".encode("cp1252")
    assert "élevé" in decode_text_best_effort(legacy)
    assert decode_text_best_effort(b"utf8 ok") == "utf8 ok"


def test_ole2_branch():
    kind, lines = inspect_non_tabular(b"\xd0\xcf\x11\xe0a1\xb1\x1a\xe1rest", "doc")
    assert kind == "document"
    assert any("OLE2" in line for line in lines)


def test_zip_without_tabular_members():
    archive = make_zip({"images/a.png": b"\x89PNG", "readme.txt": b"notes"})
    kind, lines = inspect_non_tabular(archive, "zip")
    assert kind == "archive"
    joined = "\n".join(lines)
    assert "readme.txt" in joined
    assert "tabular member(s)" not in joined


def test_kmz_without_kml_member_is_plain_zip():
    archive = make_zip({"data.csv": CSV_BYTES})
    kind, lines = inspect_non_tabular(archive, "kmz")
    assert kind == "archive"
    joined = "\n".join(lines)
    assert "KMZ" not in joined
    assert "tabular member(s): 1" in joined or "Contains 1 tabular member(s)" in joined


# --- sniffing ---


@pytest.mark.parametrize(
    "content,expected",
    [
        (b"%PDF-1.7 ...", "pdf"),
        (make_zip({"f.txt": b"x"}), "zip"),
        (b"\xd0\xcf\x11\xe0a1\xb1\x1a\xe1", "ole2"),
        (make_png(), "png"),
        (b"GIF89a", "gif"),
        (b"\xff\xd8\xff\xe0", "jpeg"),
        (HTML_PAGE, "markup"),
        (b'{"a": 1}', "markup"),
        (b"hello world plain text", "text"),
    ],
)
def test_sniff_kind(content, expected):
    assert sniff_kind(content) == expected


# --- inspectors ---


def test_pdf_summary():
    kind, lines = inspect_non_tabular(make_pdf(pages=3), "pdf")
    assert kind == "document"
    assert any("Pages: 3" in line for line in lines)
    assert any("No extractable text" in line for line in lines)


def test_docx_summary():
    kind, lines = inspect_non_tabular(make_docx(), "word")
    assert kind == "document"
    assert any("Paragraphs: 2" in line for line in lines)
    assert any("Population de la Tunisie" in line for line in lines)


def test_pptx_summary():
    kind, lines = inspect_non_tabular(make_pptx(), "pptx")
    assert kind == "document"
    assert any("Slides: 1" in line for line in lines)
    assert any("Recensement 2024" in line for line in lines)


def test_png_dimensions():
    kind, lines = inspect_non_tabular(make_png(), ".jpg")
    assert kind == "image"
    assert any("Dimensions: 64×32" in line for line in lines)


def test_svg_structure():
    kind, lines = inspect_non_tabular(SVG_DOC, "svg")
    assert kind == "image"
    assert any("ViewBox: 0 0 100 50" in line for line in lines)
    assert any("Shape elements: 3" in line for line in lines)


def test_html_summary():
    html = (
        b"<!DOCTYPE html><html><head><title>Statistiques</title>"
        b'<meta name="description" content="Donnees ouvertes tunisiennes."></head>'
        b"<body><h1>Budget</h1><script>var x=1;</script>"
        b"<p>Budget de l'Etat 2024 en dinars.</p>"
        b'<a href="#">lien</a><img src="x.png"><table><tr><td>1</td></tr></table></body></html>'
    )
    kind, lines = inspect_non_tabular(html, "html")
    assert kind == "markup"
    joined = "\n".join(lines)
    assert "Title: Statistiques" in joined
    assert "Description: Donnees ouvertes tunisiennes." in joined
    assert "Links: 1" in joined and "Tables: 1" in joined
    assert "Images: 1" in joined and "Forms: 0" in joined
    assert "Headings: Budget" in joined
    assert "Budget de l'Etat 2024" in joined
    assert "var x=1" not in joined


def test_kml_counts_placemarks():
    kind, lines = inspect_non_tabular(KML_DOC, "kml")
    assert kind == "markup"
    assert any("Placemarks: 1" in line for line in lines)
    assert any("Tunis" in line for line in lines)


def test_text_detects_delimiters():
    content = b"nom;prenom;score\nahmed;ben;12\n"
    kind, lines = inspect_non_tabular(content, "txt")
    assert kind == "text"
    joined = "\n".join(lines)
    assert ";" in joined and "CSV-like" in joined


def test_text_single_delimiter_no_hint():
    """One occurrence is prose (a comma in a sentence), not delimited data."""
    content = b"Bonjour, ceci est une phrase simple."
    _, lines = inspect_non_tabular(content, "txt")
    assert not any("CSV-like" in line for line in lines)


def test_zip_lists_entries_and_flags_tabular_members():
    archive = make_zip({"data/pop.csv": CSV_BYTES, "readme.txt": b"notes"})
    kind, lines = inspect_non_tabular(archive, "zip")
    assert kind == "archive"
    joined = "\n".join(lines)
    assert "data/pop.csv" in joined and "Contains 1 tabular member(s)" in joined


def test_kmz_reports_placemark_count():
    kind, lines = inspect_non_tabular(make_kmz(5), "kmz")
    assert kind == "archive"
    joined = "\n".join(lines)
    assert "KMZ" in joined and "Placemarks: 5" in joined


def test_unknown_binary_gets_guidance():
    kind, lines = inspect_non_tabular(b"\x00\x01\x02\x03weird", "test")
    assert kind == "binary"
    assert any("Unrecognized binary format" in line for line in lines)


def test_empty_payload():
    kind, lines = inspect_non_tabular(b"", "test")
    assert kind == "binary"
    assert any("empty (0 bytes)" in line for line in lines)


# --- adversarial fixtures: malformed content must never raise ---


def test_corrupt_pdf_raises_and_tool_guards():
    """Contract: the inspector may raise on malformed input; tools guard it."""
    from pypdf.errors import PdfStreamError

    corrupt = b"%PDF-1.7 this is not really a pdf \x00\xff garbage"
    with pytest.raises(PdfStreamError):
        inspect_non_tabular(corrupt, "pdf")


def test_truncated_png_raises():
    truncated = make_png()[:20]
    with pytest.raises((UnidentifiedImageError, OSError)):
        inspect_non_tabular(truncated, "png")


def test_invalid_svg_xml():
    bad_svg = b'<?xml version="1.0"?><svg><unclosed>'
    with pytest.raises(ET.ParseError):
        inspect_non_tabular(bad_svg, "svg")


def test_invalid_json_hint():
    with pytest.raises(json.JSONDecodeError):
        inspect_non_tabular(b"{not json", "json")


def test_json_hint_returns_preview():
    payload = json.dumps({"meta": "single object", "rows": None})
    kind, lines = inspect_non_tabular(payload.encode(), "json")
    assert kind == "data"
    assert any("JSON document" in line for line in lines)
