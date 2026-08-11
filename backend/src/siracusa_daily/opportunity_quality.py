from __future__ import annotations

from .models import Article

QUALITY_STATUS_KEY = "opportunity_quality_status"
QUALITY_REASONS_KEY = "opportunity_quality_reasons"
ELIGIBLE = "eligible"
QUARANTINED = "quarantined"


def apply_opportunity_quality(article: Article) -> str:
    """Quarantine structured listings whose actual workplace is not verified locally."""
    if article.metadata.get("opportunity") != "true":
        return "not_applicable"
    verified = article.metadata.get("opportunity_location_verified", "").strip().lower()
    if verified == "false":
        article.metadata[QUALITY_STATUS_KEY] = QUARANTINED
        article.metadata[QUALITY_REASONS_KEY] = article.metadata.get(
            "opportunity_location_reason", "Sede effettiva non verificata in provincia di Siracusa",
        )
        return QUARANTINED
    article.metadata[QUALITY_STATUS_KEY] = ELIGIBLE
    article.metadata[QUALITY_REASONS_KEY] = article.metadata.get(
        "opportunity_location_reason", "Nessuna anomalia territoriale rilevata",
    )
    return ELIGIBLE


def opportunity_is_publishable(article: Article) -> bool:
    return article.metadata.get(QUALITY_STATUS_KEY, ELIGIBLE) != QUARANTINED
