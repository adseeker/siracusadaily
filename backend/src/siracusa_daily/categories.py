from __future__ import annotations

from .models import Article
from .text import normalize_text

CATEGORY_ORDER = (
    "Notizie e cronaca",
    "Politica ed economia",
    "Cultura",
    "Sport",
    "Eventi",
    "Servizi e utilità",
    "Lavoro e opportunità",
)

CATEGORY_PRECEDENCE = (
    "Eventi", "Lavoro e opportunità", "Servizi e utilità", "Sport", "Cultura", "Politica ed economia",
)

BUCKET_CATEGORY = {
    "politica": "Politica ed economia", "amministrazione": "Politica ed economia",
    "economia": "Politica ed economia", "industria": "Politica ed economia",
    "business": "Politica ed economia", "commercio": "Politica ed economia",
    "sindacato": "Politica ed economia", "turismo": "Politica ed economia",
    "cultura": "Cultura", "musica": "Cultura", "spettacoli": "Cultura", "religione": "Cultura",
    "sport": "Sport",
    "eventi": "Eventi", "nightlife": "Eventi",
    "servizi": "Servizi e utilità", "pubblica utilità": "Servizi e utilità",
    "meteo": "Servizi e utilità", "acqua": "Servizi e utilità", "avvisi": "Servizi e utilità",
    "mobilità": "Servizi e utilità",
    "lavoro": "Lavoro e opportunità", "concorsi": "Lavoro e opportunità",
    "selezioni": "Lavoro e opportunità", "bandi": "Lavoro e opportunità",
    "opportunità": "Lavoro e opportunità", "scadenze": "Lavoro e opportunità",
    "formazione": "Lavoro e opportunità",
}

KEYWORDS = (
    ("Lavoro e opportunità", ("concorso", "selezione", "assunzion", "posto di lavoro", "candidatur", "bando")),
    ("Eventi", ("evento", "concerto", "in programma", "appuntamento", "spettacolo")),
    ("Sport", ("campionato", "partita", "calcio", "pallanuoto", "basket")),
    ("Politica ed economia", ("consiglio comunale", "sindaco", "assessore", "giunta", "imprese", "commercio", "economia")),
    ("Servizi e utilità", ("interruzione idrica", "servizio idrico", "viabilita", "strada chiusa", "allerta meteo", "raccolta rifiuti")),
)


def classify_article(article: Article) -> str:
    buckets = {normalize_text(item) for item in article.content_buckets}
    for category in CATEGORY_PRECEDENCE:
        if any(BUCKET_CATEGORY.get(bucket) == category for bucket in buckets):
            return category
    text = normalize_text(f"{article.title} {article.excerpt}")
    for category, words in KEYWORDS:
        if any(word in text for word in words):
            return category
    return "Notizie e cronaca"
