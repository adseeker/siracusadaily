from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from .models import Article, StoryCluster
from .text import normalize_text


ROME = ZoneInfo("Europe/Rome")
SERVICE_ALERT_KEY = "service_alert"
SERVICE_TYPE_KEY = "service_type"
SERVICE_PRIORITY_KEY = "service_priority"
SERVICE_STATUS_KEY = "service_status"
SERVICE_START_KEY = "service_start"
SERVICE_END_KEY = "service_end"

SERVICE_TYPES = (
    "meteo e protezione civile",
    "acqua",
    "energia",
    "viabilità",
    "trasporti",
    "rifiuti",
    "chiusure pubbliche",
)

TYPE_TERMS = {
    "meteo e protezione civile": (
        "allerta meteo", "allerta gialla", "allerta arancione", "allerta rossa",
        "rischio idrogeologico", "rischio idraulico", "protezione civile",
        "ondata di calore", "forti venti", "mareggiata",
    ),
    "acqua": (
        "interruzione idrica", "sospensione idrica", "servizio idrico",
        "rete idrica", "erogazione idrica", "erogazione dell acqua",
        "cali di pressione", "riduzione dell erogazione", "mancanza d acqua",
        "condotta idrica", "acquedotto",
    ),
    "energia": (
        "interruzione di corrente", "interruzione elettrica", "energia elettrica",
        "guasto elettrico", "blackout", "e distribuzione", "enel",
    ),
    "viabilità": (
        "modifica viabilita", "modifiche alla viabilita", "strada chiusa",
        "chiusura al traffico", "divieto di transito", "divieto di sosta",
        "interdizione al traffico", "senso unico alternato", "deviazione",
        "rifacimento del manto", "lavori stradali", "odcs", "o d c s",
        "ztl", "circolazione veicolare",
    ),
    "trasporti": (
        "trasporto pubblico", "bus urbano", "autobus", "linea urbana",
        "treno", "ferrovia", "corsa sospesa", "corse sospese",
        "modifica degli orari", "modifiche agli orari",
    ),
    "rifiuti": (
        "raccolta rifiuti", "raccolta differenziata", "conferimento rifiuti",
        "ritiro rifiuti", "calendario di raccolta", "centro comunale di raccolta",
    ),
    "chiusure pubbliche": (
        "scuole chiuse", "chiusura delle scuole", "chiusura scuole",
        "chiusura degli uffici", "uffici chiusi", "chiusura del cimitero",
        "chiusura dei cimiteri", "chiusura dei mercati", "impianti chiusi",
        "chiusura degli impianti",
    ),
}

IMPACT_TERMS = (
    "interruzione", "sospensione", "chiusura", "chiuso", "chiuse", "divieto",
    "interdizione", "deviazione", "senso unico", "modifica viabilita",
    "modifiche alla viabilita", "allerta", "guasto", "blackout", "disservizio",
    "cali di pressione", "riduzione dell erogazione", "lavori stradali",
    "rifacimento del manto", "corsa sospesa", "corse sospese", "ritardo",
    "posticipata", "anticipata", "variazione del servizio", "odcs", "o d c s",
)

EXCLUSION_TERMS = (
    "avviso ai creditori", "avviso ad opponendum", "manifestazione di interesse",
    "richiesta di preventivo", "concorso", "selezione pubblica", "candidatura",
    "assegnazione", "bilancio", "consiglio comunale", "cordoglio", "condoglianze",
    "scomparsa di", "inaugurazione", "mostra", "spettacolo", "campionato",
    "graduatoria", "tumulazione", "inumazione", "esumazione", "estumulazione",
    "istituzione stallo h", "concessione suolo", "parere", "mozione",
)

RESOLVED_TERMS = (
    "servizio ripristinato", "erogazione ripristinata", "rete in pressione",
    "intervento concluso", "lavori conclusi", "guasto risolto", "riapertura",
    "regolare esercizio ripristinato",
)

CRITICAL_TERMS = (
    "allerta arancione", "allerta rossa", "scuole chiuse", "chiusura delle scuole",
    "interruzione idrica", "sospensione idrica", "interruzione di corrente",
    "blackout", "evacuazione", "centro operativo comunale",
)


def _metadata_datetime(article: Article, key: str) -> datetime | None:
    value = article.metadata.get(key, "")
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ROME)
    return parsed.astimezone(timezone.utc)


def _service_type(text: str) -> str | None:
    for service_type, terms in TYPE_TERMS.items():
        if any(term in text for term in terms):
            return service_type
    return None


def _date_candidates(value: str, fallback_year: int) -> list[datetime]:
    # Conserva i separatori numerici: normalize_text trasformerebbe 14/08 in
    # "14 08" rendendo impossibile distinguere una data da due numeri.
    text = value.lower()
    months = {
        "gennaio": 1, "febbraio": 2, "marzo": 3, "aprile": 4, "maggio": 5,
        "giugno": 6, "luglio": 7, "agosto": 8, "settembre": 9, "ottobre": 10,
        "novembre": 11, "dicembre": 12,
    }
    matches: list[tuple[int, datetime]] = []
    for match in re.finditer(r"\b(\d{1,2})[/.](\d{1,2})(?:[/.](\d{2,4}))?\b", text):
        year = int(match.group(3)) if match.group(3) else fallback_year
        if year < 100:
            year += 2000
        try:
            matches.append((match.start(), datetime(year, int(match.group(2)), int(match.group(1)), tzinfo=ROME)))
        except ValueError:
            continue
    for match in re.finditer(
        r"\b(\d{1,2})\s+(gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|"
        r"settembre|ottobre|novembre|dicembre)(?:\s+(\d{4}))?\b",
        text,
    ):
        year = int(match.group(3) or fallback_year)
        try:
            matches.append((match.start(), datetime(year, months[match.group(2)], int(match.group(1)), tzinfo=ROME)))
        except ValueError:
            continue
    return [item[1].astimezone(timezone.utc) for item in sorted(matches, key=lambda item: item[0])]


def apply_service_metadata(article: Article) -> Article:
    """Mark only concrete, citizen-facing operational communications."""
    text = normalize_text(f"{article.title} {article.excerpt}")
    # I PDF regionali elencano tutte le zone e i comuni anche in assenza di
    # conseguenze locali. Il solo riferimento tabellare non è sufficiente:
    # l'avviso DRPC entra nel flusso operativo soltanto se Siracusa è oggetto
    # esplicito del titolo; altrimenti resta disponibile come corroborazione.
    if article.endpoint_id == "END-0051" and "siracusa" not in normalize_text(article.title):
        return article
    if any(term in text for term in EXCLUSION_TERMS):
        return article
    service_type = _service_type(text)
    if service_type is None or not any(term in text for term in IMPACT_TERMS):
        return article

    article.metadata[SERVICE_ALERT_KEY] = "true"
    article.metadata[SERVICE_TYPE_KEY] = service_type
    article.metadata.setdefault("service_verified_at", article.retrieved_at.isoformat())
    article.metadata.setdefault(
        SERVICE_PRIORITY_KEY,
        "critical" if any(term in text for term in CRITICAL_TERMS) else "normal",
    )
    article.metadata.setdefault(
        SERVICE_STATUS_KEY,
        "resolved" if any(term in normalize_text(article.title) for term in RESOLVED_TERMS) else "active",
    )

    if SERVICE_START_KEY not in article.metadata:
        dates = _date_candidates(f"{article.title} {article.excerpt}", article.published_at.astimezone(ROME).year)
        if dates:
            article.metadata[SERVICE_START_KEY] = dates[0].isoformat()
            if len(dates) > 1 and dates[-1] >= dates[0]:
                end_local = dates[-1].astimezone(ROME).replace(hour=23, minute=59, second=59)
                article.metadata[SERVICE_END_KEY] = end_local.astimezone(timezone.utc).isoformat()
    return article


def is_service_alert(article: Article) -> bool:
    return article.metadata.get(SERVICE_ALERT_KEY) == "true"


def service_alert_is_active(article: Article, edition_date: date, horizon_days: int = 3) -> bool:
    if not is_service_alert(article):
        return False
    start = _metadata_datetime(article, SERVICE_START_KEY)
    end = _metadata_datetime(article, SERVICE_END_KEY)
    day_start = datetime.combine(edition_date, time.min, tzinfo=ROME).astimezone(timezone.utc)
    horizon_end = day_start + timedelta(days=horizon_days + 1)
    if start is not None and start >= horizon_end:
        return False
    if end is not None and end < day_start:
        return False

    published_date = article.published_at.astimezone(ROME).date()
    if article.metadata.get(SERVICE_STATUS_KEY) == "resolved":
        return published_date == edition_date
    if end is not None:
        return True
    if start is not None and day_start <= start < horizon_end:
        return True
    max_age = 2 if article.metadata.get(SERVICE_PRIORITY_KEY) == "critical" else 3
    return published_date >= edition_date - timedelta(days=max_age)


def service_alert_is_due(
    article: Article, edition_date: date, previously_published_ids: set[int] | None = None,
) -> bool:
    if not service_alert_is_active(article, edition_date):
        return False
    if article.article_id not in (previously_published_ids or set()):
        return True
    if article.metadata.get(SERVICE_STATUS_KEY) == "resolved":
        return article.published_at.astimezone(ROME).date() == edition_date
    return article.metadata.get(SERVICE_PRIORITY_KEY) == "critical"


def service_sort_key(cluster: StoryCluster, edition_date: date) -> tuple:
    article = cluster.representative
    priority = 0 if article.metadata.get(SERVICE_PRIORITY_KEY) == "critical" else 1
    start = _metadata_datetime(article, SERVICE_START_KEY)
    start_date = start.astimezone(ROME).date() if start else date.max
    starts_today = start_date == edition_date
    return (
        priority,
        0 if starts_today else 1,
        start_date,
        -article.published_at.timestamp(),
    )


def diversify_service_clusters(
    clusters: list[StoryCluster], edition_date: date, limit: int = 5,
) -> list[StoryCluster]:
    ordered = sorted(clusters, key=lambda item: service_sort_key(item, edition_date))
    selected: list[StoryCluster] = []
    used_types: set[str] = set()
    for cluster in ordered:
        service_type = cluster.representative.metadata.get(SERVICE_TYPE_KEY, "")
        if service_type and service_type not in used_types:
            selected.append(cluster)
            used_types.add(service_type)
        if len(selected) >= limit:
            return selected
    for cluster in ordered:
        if cluster not in selected:
            selected.append(cluster)
        if len(selected) >= limit:
            break
    return selected
