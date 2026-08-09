from __future__ import annotations

from .models import Article, Source
from .text import normalize_text

MUNICIPALITIES = {
    "siracusa", "augusta", "avola", "buccheri", "buscemi", "canicattini bagni", "carlentini",
    "cassaro", "ferla", "floridia", "francofonte", "lentini", "melilli", "noto", "pachino",
    "palazzolo acreide", "portopalo di capo passero", "priolo gargallo", "rosolini", "solarino",
    "sortino", "ortigia", "plemmirio", "cassibile", "belvedere", "fontane bianche", "siracusano",
}


def evaluate_locality(article: Article, source: Source) -> tuple[float, tuple[str, ...]]:
    text = normalize_text(f"{article.title} {article.excerpt}")
    for boilerplate in ("proviene da siracusa news", "siracusa news", "siracusanews", "siracusaoggi"):
        text = text.replace(boilerplate, " ")
    matches = sorted(place for place in MUNICIPALITIES if place in text)
    reasons: list[str] = []
    score = 0.0
    if matches:
        score = min(1.0, 0.72 + 0.08 * len(matches))
        reasons.append("località: " + ", ".join(matches[:4]))
    if "provincia di siracusa" in text or "libero consorzio di siracusa" in text:
        score = max(score, 0.9)
        reasons.append("riferimento provinciale")
    if source.source_id in {"SRC-0008", "SRC-0010"} and score == 0:
        score = 0.62
        reasons.append("fonte istituzionale territoriale")
    return score, tuple(reasons)
