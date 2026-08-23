"""Clean free-text search queries before sending them to the uData API.

The uData search uses strict AND logic: generic words that never appear in
dataset metadata ("données", "fichier", "بيانات"...) cause zero results.
This module strips them while preserving the user's meaningful keywords.
"""

import re

# Generic words users add but that are not typically present in dataset
# metadata. French first (mirrors datagouv/datagouv-mcp), then the Arabic
# equivalents commonly used on data.gouv.tn.
STOP_WORDS = frozenset(
    {
        # French
        "données",
        "donnee",
        "donnees",
        "fichier",
        "fichiers",
        "tableau",
        "tableaux",
        "jeu",
        "jeux",
        "liste",
        "listes",
        # File formats
        "csv",
        "excel",
        "xlsx",
        "json",
        "xml",
        # Arabic
        "بيانات",
        "ملف",
        "ملفات",
        "جدول",
        "جداول",
    }
)

_WORD_SPLIT = re.compile(r"\s+")


def clean_search_query(query: str) -> str:
    """Remove generic stop words from a search query.

    Case-insensitive matching; original casing of kept words is preserved.
    Returns a possibly empty string when every word was generic.
    """
    words = [word for word in _WORD_SPLIT.split(query.strip()) if word]
    kept = [word for word in words if word.lower() not in STOP_WORDS]
    return " ".join(kept)
