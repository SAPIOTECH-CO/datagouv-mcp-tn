"""Clean free-text search queries before sending them to the CKAN API.

The CKAN search uses AND logic: generic words that never appear in
dataset metadata ("données", "fichier", "بيانات"...) cause zero results.
This module strips them while preserving the user's meaningful keywords.

It also provides typo tolerance via fuzzy matching (R12).
"""

from __future__ import annotations

import re

from rapidfuzz import fuzz, process

# Generic words users add but that are not typically present in dataset
# metadata. French first, then Arabic equivalents commonly used on agridata.tn.
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

# Common French/Arabic synonyms for open data terms (R12 query expansion)
_SYNONYMS = {
    "population": ["habitants", "recensement", "démographie"],
    "budget": ["finances", "dépenses", "recettes"],
    "agriculture": ["agridata", "cultures", "récoltes"],
    "transport": ["mobilité", "trafic", "routes"],
    "education": ["école", "écoles", "scolaire"],
    "santé": ["health", "médical", "hôpitaux"],
    "environnement": ["climate", "climat", "pollution"],
}

_WORD_SPLIT = re.compile(r"\s+")


def clean_search_query(query: str) -> str:
    """Remove generic stop words from a search query.

    Case-insensitive matching; original casing of kept words is preserved.
    Returns a possibly empty string when every word was generic.
    """
    words = [word for word in _WORD_SPLIT.split(query.strip()) if word]
    kept = [word for word in words if word.lower() not in STOP_WORDS]
    return " ".join(kept)


def expand_query(query: str) -> str:
    """Expand a query with common synonyms (R12).

    Adds related terms to improve recall on CKAN portals where dataset
    metadata may use different terminology.
    """
    words = [word.lower() for word in _WORD_SPLIT.split(query.strip()) if word]
    expansions: set[str] = set()
    for word in words:
        for key, synonyms in _SYNONYMS.items():
            if word == key or word in synonyms:
                expansions.add(key)
                expansions.update(synonyms)
    # Merge original query with expansions
    original = set(words)
    all_terms = original | expansions
    return " ".join(sorted(all_terms))


def fuzzy_match(partial: str, choices: list[str], *, cutoff: int = 80) -> list[str]:
    """Return fuzzy matches from choices above the similarity cutoff.

    Uses rapidfuzz for typo-tolerant matching (R12).
    """
    if not partial or not choices:
        return []
    results = process.extract(
        partial,
        choices,
        scorer=fuzz.WRatio,
        score_cutoff=cutoff,
        limit=5,
    )
    return [match[0] for match in results]


def suggest_correction(query: str) -> str | None:
    """Suggest a correction for a potentially misspelled query word.

    Returns a corrected query string or None if no correction is needed.
    """
    words = [word for word in _WORD_SPLIT.split(query.strip()) if word]
    if not words:
        return None

    # Build a small dictionary of common CKAN metadata terms
    dictionary = list(STOP_WORDS) + [
        "population",
        "budget",
        "agriculture",
        "transport",
        "éducation",
        "santé",
        "environnement",
        "données",
        "données ouvertes",
        "open data",
        "dataset",
        "statistiques",
    ]

    corrected_words = []
    for word in words:
        matches = process.extract(
            word,
            dictionary,
            scorer=fuzz.WRatio,
            score_cutoff=75,
            limit=1,
        )
        if matches and matches[0][1] >= 75 and matches[0][0] != word:
            corrected_words.append(matches[0][0])
        else:
            corrected_words.append(word)

    corrected = " ".join(corrected_words)
    return corrected if corrected != query else None
