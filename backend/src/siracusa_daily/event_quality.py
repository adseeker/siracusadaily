from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import re
import unicodedata

from .events import event_interval, is_dated_event
from .models import Article
from .text import normalize_text


# These sources are useful for discovery, but an item appearing there is not
# enough on its own to establish that it is meant for Siracusa's local public.
DISCOVERY_ONLY_EVENT_SOURCES = frozenset({"SRC-0011", "SRC-0013"})

QUALITY_STATUS_KEY = "event_quality_status"
QUALITY_REASONS_KEY = "event_quality_reasons"
ELIGIBLE = "eligible"
QUARANTINED = "quarantined"

GENERIC_ORGANIZERS = {
    "", "allevents", "all events", "virgilio", "virgilio eventi",
}

# Function words are deliberately included: unlike topic words, they are a
# strong signal that the supplied prose is actually written for Italian readers.
ITALIAN_MARKERS = {
    "a", "al", "alla", "alle", "anche", "con", "da", "dal", "dalla", "dalle",
    "dei", "del", "della", "delle", "di", "e", "gli", "i", "il", "in", "la",
    "le", "lo", "nel", "nella", "nelle", "per", "piu", "questa", "questo", "su",
    "tra", "un", "una", "uno", "che", "come", "dove", "durante", "ogni",
    "concerto", "evento", "eventi", "festival", "incontro", "laboratorio", "mostra",
    "musica", "presentazione", "rassegna", "serata", "spettacolo", "teatro",
}

ITALIAN_STRONG_MARKERS = ITALIAN_MARKERS - {
    "a", "al", "con", "da", "di", "e", "i", "in", "per", "su", "tra", "un", "una", "uno",
    "festival",
}


@dataclass(frozen=True)
class EventQualityDecision:
    status: str
    reasons: tuple[str, ...]

    @property
    def eligible(self) -> bool:
        return self.status == ELIGIBLE


def _editorial_text(article: Article) -> str:
    """Use event copy only, excluding the location appended by retrievers."""
    excerpt = article.excerpt or ""
    location = article.metadata.get("location", "").strip()
    if location:
        excerpt = excerpt.replace(location, " ")
    return re.sub(r"\s+", " ", f"{article.title} {excerpt}").strip()


def _letter_profile(value: str) -> tuple[int, int]:
    latin = 0
    non_latin = 0
    for character in value:
        if not unicodedata.category(character).startswith("L"):
            continue
        name = unicodedata.name(character, "")
        if "LATIN" in name:
            latin += 1
        else:
            non_latin += 1
    return latin, non_latin


def _contains_substantial_non_latin_script(value: str) -> bool:
    latin, non_latin = _letter_profile(value)
    total = latin + non_latin
    return non_latin >= 4 and (total == 0 or non_latin / total >= 0.08)


def _italian_evidence(value: str) -> tuple[int, int, int]:
    words = normalize_text(value).split()
    markers = [word for word in words if word in ITALIAN_MARKERS]
    strong_markers = [word for word in words if word in ITALIAN_STRONG_MARKERS]
    return len(markers), len(strong_markers), len(words)


def evaluate_event_quality(article: Article) -> EventQualityDecision:
    """Conservative eligibility gate used before event editorial selection."""
    if not is_dated_event(article):
        return EventQualityDecision(ELIGIBLE, ("non_evento_datato",))
    if article.source_id not in DISCOVERY_ONLY_EVENT_SOURCES:
        return EventQualityDecision(ELIGIBLE, ("fonte_non_aggregatore_generalista",))

    text = _editorial_text(article)
    reasons: list[str] = []
    if _contains_substantial_non_latin_script(text):
        return EventQualityDecision(QUARANTINED, ("scrittura_non_latina_prevalente",))

    marker_count, strong_marker_count, word_count = _italian_evidence(text)
    if marker_count < 3 or strong_marker_count < 2:
        reasons.append("pubblico_italiano_non_dimostrato")

    # A bare card from a general aggregator cannot be verified editorially.
    description = article.excerpt or ""
    location = article.metadata.get("location", "").strip()
    if location:
        description = description.replace(location, " ")
    description_words = normalize_text(description).split()
    if len(description_words) < 5:
        reasons.append("descrizione_insufficiente")

    organizer = normalize_text(article.metadata.get("organizer", article.author))
    if (
        article.source_id == "SRC-0011"
        and organizer in GENERIC_ORGANIZERS
        and len(description_words) < 12
    ):
        reasons.append("organizzatore_non_verificabile")

    # A very short card with few Italian markers is too ambiguous even when it
    # contains a place name or a translated category label.
    if word_count < 8 and marker_count < 4:
        reasons.append("scheda_troppo_scarsa")

    if reasons:
        return EventQualityDecision(QUARANTINED, tuple(dict.fromkeys(reasons)))
    return EventQualityDecision(ELIGIBLE, ("testo_italiano_e_scheda_coerente",))


def apply_event_quality(article: Article) -> EventQualityDecision:
    decision = evaluate_event_quality(article)
    if is_dated_event(article):
        article.metadata[QUALITY_STATUS_KEY] = decision.status
        article.metadata[QUALITY_REASONS_KEY] = ";".join(decision.reasons)
    return decision


def event_is_publishable(article: Article) -> bool:
    # Preserve a batch-level duplicate quarantine. Records collected before the
    # quality gate have no stored status and are evaluated with the current rules.
    if article.metadata.get(QUALITY_STATUS_KEY) == QUARANTINED:
        return False
    return evaluate_event_quality(article).eligible


def mark_multilingual_duplicates(articles: list[Article]) -> None:
    """Quarantine suspicious same-day cards replicated in multiple scripts."""
    groups: dict[tuple[str, str, str], list[Article]] = defaultdict(list)
    for article in articles:
        if article.source_id not in DISCOVERY_ONLY_EVENT_SOURCES:
            continue
        interval = event_interval(article)
        if interval is None:
            continue
        start, _ = interval
        location = normalize_text(article.metadata.get("location", ""))
        organizer = normalize_text(article.metadata.get("organizer", article.author))
        if location and organizer and organizer not in GENERIC_ORGANIZERS:
            groups[(start.date().isoformat(), location, organizer)].append(article)

    for group in groups.values():
        if len(group) < 2 or not any(
            _contains_substantial_non_latin_script(_editorial_text(article)) for article in group
        ):
            continue
        for article in group:
            article.metadata[QUALITY_STATUS_KEY] = QUARANTINED
            existing = article.metadata.get(QUALITY_REASONS_KEY, "")
            reasons = [reason for reason in existing.split(";") if reason]
            if "duplicato_multilingua_sospetto" not in reasons:
                reasons.append("duplicato_multilingua_sospetto")
            article.metadata[QUALITY_REASONS_KEY] = ";".join(reasons)
