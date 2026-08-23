"""Lightweight AR/FR/EN internationalization for tool-facing messages.

Messages live in a flat catalog keyed by message id; each entry maps a
:class:`Language` to a ``str.format`` template. Tools accept an optional
``language`` argument (surfaced as an enum in the MCP tool schema) resolved
through :func:`resolve_language`, falling back to the portal's default
(French) when omitted.
"""

from __future__ import annotations

import logging
from enum import StrEnum

from datagouv_mcp_tn.helpers.config import get_settings

logger = logging.getLogger(__name__)


class Language(StrEnum):
    FRENCH = "fr"
    ARABIC = "ar"
    ENGLISH = "en"


DEFAULT_LANGUAGE = Language.FRENCH


class MessageKey(StrEnum):
    RESULTS_FOUND = "results_found"
    NO_RESULTS = "no_results"
    GENERIC_QUERY_ERROR = "generic_query_error"
    SUGGESTIONS_TITLE = "suggestions_title"
    NO_SUGGESTIONS = "no_suggestions"
    WHAT_DATASETS = "what_datasets"
    WHAT_ORGANIZATIONS = "what_organizations"
    WHAT_DATASERVICES = "what_dataservices"
    PAGINATION_LINE = "pagination_line"


_MESSAGES: dict[str, dict[Language, str]] = {
    MessageKey.RESULTS_FOUND: {
        Language.FRENCH: "Trouvé {count} {what} pour « {query} »",
        Language.ARABIC: "تم العثور على {count} {what} لـ «{query}»",
        Language.ENGLISH: "Found {count} {what} for '{query}'",
    },
    MessageKey.NO_RESULTS: {
        Language.FRENCH: ("Aucun résultat. Essayez des mots-clés plus courts ou plus précis."),
        Language.ARABIC: "لا توجد نتائج. جرّب كلمات مفتاحية أقصر أو أدق.",
        Language.ENGLISH: "No results found. Try shorter or more specific keywords.",
    },
    MessageKey.GENERIC_QUERY_ERROR: {
        Language.FRENCH: (
            "La requête ne contient pas de mots significatifs "
            "(les mots génériques comme « données », « fichier », « csv » sont ignorés)."
        ),
        Language.ARABIC: (
            "الطلب لا يحتوي على كلمات ذات معنى (الكلمات العامة مثل «بيانات» و«ملف» يتم تجاهلها)."
        ),
        Language.ENGLISH: (
            "Query has no meaningful keywords "
            "(generic words like 'data', 'file', 'csv' are ignored)."
        ),
    },
    MessageKey.SUGGESTIONS_TITLE: {
        Language.FRENCH: "Suggestions pour « {query} »",
        Language.ARABIC: "اقتراحات لـ «{query}»",
        Language.ENGLISH: "Suggestions for '{query}'",
    },
    MessageKey.NO_SUGGESTIONS: {
        Language.FRENCH: "Aucune suggestion pour cette requête.",
        Language.ARABIC: "لا توجد اقتراحات لهذا الطلب.",
        Language.ENGLISH: "No suggestions for this query.",
    },
    MessageKey.WHAT_DATASETS: {
        Language.FRENCH: "jeu(x) de données",
        Language.ARABIC: "مجموعة(ات) بيانات",
        Language.ENGLISH: "dataset(s)",
    },
    MessageKey.WHAT_ORGANIZATIONS: {
        Language.FRENCH: "organisation(s)",
        Language.ARABIC: "منظمة(ات)",
        Language.ENGLISH: "organization(s)",
    },
    MessageKey.WHAT_DATASERVICES: {
        Language.FRENCH: "service(s) de données",
        Language.ARABIC: "خدمة(ات) بيانات",
        Language.ENGLISH: "dataservice(s)",
    },
    MessageKey.PAGINATION_LINE: {
        # {pages} may be empty when total is unknown; templates tolerate it.
        Language.FRENCH: "Page {page}{pages} · {count} résultat{plural}",
        Language.ARABIC: "صفحة {page}{pages} · {count} {unit}",
        Language.ENGLISH: "Page {page}{pages} · {count} result{plural}",
    },
}


def resolve_language(language: str | Language | None) -> Language:
    """Resolve a raw language argument, falling back to settings then French."""
    if isinstance(language, Language):
        return language
    if language:
        try:
            return Language(language.strip().lower())
        except ValueError:
            logger.warning("Unsupported language %r, falling back to default", language)
    configured = getattr(get_settings(), "default_language", None)
    if configured:
        try:
            return Language(str(configured).strip().lower())
        except ValueError:
            pass
    return DEFAULT_LANGUAGE


def translate(key: str | MessageKey, language: Language, **kwargs: object) -> str:
    """Return the localized template formatted with ``kwargs``."""
    lang = language if isinstance(language, Language) else resolve_language(str(language))
    key_value = key.value if isinstance(key, MessageKey) else key
    catalog = _MESSAGES.get(key_value, {})
    template = catalog.get(lang) or catalog.get(DEFAULT_LANGUAGE)
    if template is None:
        return f"missing translation: {key_value}"
    return template.format(**kwargs)
