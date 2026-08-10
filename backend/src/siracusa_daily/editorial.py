from __future__ import annotations

import json
import os
import re
import socket
import time
import urllib.error
import urllib.request
from collections import Counter
from dataclasses import dataclass
from datetime import timezone

from .models import Source, StoryCluster
from .categories import CATEGORY_ORDER
from .text import normalize_text

DEFAULT_MODEL = "gpt-5-mini"
SECTIONS = set(CATEGORY_ORDER)

# This is a publication gate, not a classifier for the newsletter body. A story
# matching these signals may still be published, but can never lead the email.
SENSITIVE_SUBJECT_TERMS = {
    "abuso", "abusi", "accoltellamento", "aggressione", "aggressioni",
    "allarme", "assassinio", "cadavere", "catastrofe", "caos", "decesso",
    "deceduta", "deceduto", "disastro", "dramma", "emergenza", "femminicidio",
    "ferita", "ferite", "feriti", "ferito", "incidente", "incidenti", "lutto",
    "mafia", "maltrattamenti", "mortale", "mortali", "morta", "morte", "morti",
    "morto", "omicidio", "orrore", "sangue", "scomparsa", "scomparso",
    "sparatoria", "strage", "stupro", "suicidio", "tragedia", "tragico",
    "violenza", "violenze", "vittima", "vittime",
}
SENSITIVE_SUBJECT_PHRASES = {
    "ferite gravi", "ferito grave", "in fin di vita", "perde la vita",
    "perso la vita", "perdita della vita", "violenza sessuale",
}


@dataclass(frozen=True)
class EditorialItem:
    candidate_id: str
    headline: str
    summary: str
    section: str
    subject_topic: str = ""
    grounded: bool = True


@dataclass(frozen=True)
class EditorialResult:
    items: list[EditorialItem]
    exclusions: dict[str, str]
    subject: str


class EditorialError(RuntimeError):
    pass


def evidence_packet(clusters: list[StoryCluster], sources: dict[str, Source]) -> list[dict]:
    packet: list[dict] = []
    for cluster in clusters:
        article = cluster.representative
        packet.append({
            "candidate_id": cluster.key,
            "source_title": article.title,
            "source_excerpt": article.excerpt,
            "source_name": sources[article.source_id].name,
            "source_url": article.url,
            "reference_date": article.metadata.get("reference_date", article.published_at.isoformat()),
            "date_label": article.metadata.get("date_label", "Pubblicato"),
            "content_buckets": list(article.content_buckets),
            "locality_evidence": list(article.local_reasons),
            "corroborating_sources": sorted({
                sources[item.source_id].name for item in cluster.articles if item.source_id != article.source_id
            }),
        })
    return packet


def _schema(include_subject: bool = True) -> dict:
    item = {
        "type": "object",
        "properties": {
            "candidate_id": {"type": "string"},
            "publishable": {"type": "boolean"},
            "rejection_reason": {"type": "string"},
            "headline": {"type": "string"},
            "summary": {"type": "string"},
            "section": {"type": "string", "enum": sorted(SECTIONS)},
            "subject_topic": {"type": "string"},
        },
        "required": [
            "candidate_id", "publishable", "rejection_reason", "headline", "summary", "section",
            "subject_topic",
        ],
        "additionalProperties": False,
    }
    properties: dict = {"items": {"type": "array", "items": item}}
    required = ["items"]
    if include_subject:
        properties.update({
            "subject": {"type": "string"},
            "subject_candidate_ids": {
                "type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 3,
            },
        })
        required.extend(["subject", "subject_candidate_ids"])
    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


INSTRUCTIONS = """Sei il writer editoriale di SiracusaDaily. Trasforma ogni candidato in una micro-notizia pronta per la pubblicazione.

OBIETTIVO
Il lettore deve capire il fatto essenziale senza aprire il link. Il link serve soltanto per approfondire.

CONTRATTO EDITORIALE
1. Usa esclusivamente le evidenze del candidato. Non inventare o dedurre dettagli non supportati.
2. Scrivi headline e summary sempre in italiano. Traduci le fonti straniere; conserva solo nomi propri e marchi non traducibili.
3. Riscrivi da zero: non copiare l'incipit, non troncare il testo e non trasformare il titolo nella summary.
4. Headline: informativa, sobria, specifica, massimo 110 caratteri.
5. Summary: micro-notizia autosufficiente, chiara e conclusiva. Scrivi una sola frase di 70-110 caratteri; non superare mai 120 caratteri inclusi gli spazi.
6. La summary deve aggiungere almeno un'informazione utile rispetto alla headline e terminare con punteggiatura conclusiva.
7. Se lo spazio non basta, elimina dettagli secondari e riscrivi l'intera frase. Non usare puntini di sospensione.
8. Niente clickbait, promozione, giudizi non attribuiti, URL o inviti ad approfondire.
9. Per eventi e opportunità conserva, quando disponibili, natura dell'iniziativa, luogo e data o scadenza.
10. Se le evidenze non bastano per una micro-notizia informativa e completa, imposta publishable=false e spiega brevemente il motivo in rejection_reason. Non produrre testo generico per riempire lo spazio.
11. Non usare mai l'em dash (—). Usa virgola, due punti, parentesi o un trattino breve.
12. Per ogni candidato pubblicabile scrivi anche subject_topic: una formulazione autonoma e conclusiva del fatto principale, utilizzabile come oggetto di riserva. Massimo 80 caratteri, niente puntini di sospensione o troncamenti.

OGGETTO DELLA NEWSLETTER
- Scrivi subject come oggetto completo, editoriale e ogni volta diverso. Non usare prefissi, formule o copy ricorrenti.
- Sintetizza la notizia principale e, soltanto se il risultato resta naturale e leggibile, una o due altre notizie presenti nella newsletter.
- Usa esclusivamente fatti contenuti negli elementi che imposti come publishable=true. Non anticipare contenuti esclusi.
- Compila subject_candidate_ids con gli ID, da uno a tre, che supportano integralmente quanto scritto nell'oggetto.
- Scrivi in italiano, tra 20 e 90 caratteri. Niente marchio SiracusaDaily, data dell'edizione, formule generiche come "Siracusa oggi", clickbait, puntini di sospensione o em dash.
- L'oggetto deve avere senso compiuto e non promettere informazioni che la newsletter non contiene.
- Non usare mai come notizia guida, non citare e non includere nei subject_candidate_ids fatti che riguardano decessi, vittime, incidenti gravi, violenza, abusi, cronaca nera, catastrofi o dolore personale. Questi contenuti possono restare nel corpo della newsletter, ma non devono comparire nell'oggetto neppure con eufemismi.
- Evita formulazioni emotivamente forti, allarmistiche o sensazionalistiche. Per l'oggetto preferisci una notizia di interesse civico e tono neutro: servizi, istituzioni, economia, cultura, sport, eventi o opportunità.

CATEGORIA
Assegna semanticamente una sola section tra quelle consentite dallo schema:
- Notizie e cronaca: attualità generale, cronaca, sanità, ambiente, scuola e società;
- Politica ed economia: istituzioni, amministrazione, imprese, lavoro economico, credito, mutui, commercio e industria;
- Cultura: arte, teatro, libri, musica, patrimonio e spettacolo culturale;
- Sport: squadre, gare, risultati e impianti sportivi;
- Eventi: appuntamenti futuri aperti alla partecipazione;
- Servizi e utilità: acqua, viabilità, trasporti, rifiuti, meteo e avvisi operativi;
- Lavoro e opportunità: concorsi, selezioni, bandi, formazione e offerte di lavoro.
Classifica il contenuto reale, non limitarti all'etichetta generica fornita dalla fonte.

OUTPUT
Restituisci esattamente un elemento per ogni candidate_id, nello stesso ordine. Per gli elementi pubblicabili usa publishable=true e rejection_reason vuoto. Prima dell'output verifica lingua, fedeltà, completezza e lunghezza.
"""


def _response_text(payload: dict) -> str:
    direct = payload.get("output_text")
    if isinstance(direct, str) and direct:
        return direct
    for output in payload.get("output", []):
        if output.get("type") != "message":
            continue
        for content in output.get("content", []):
            if content.get("type") == "refusal":
                raise EditorialError(content.get("refusal", "Richiesta rifiutata dal modello"))
            if content.get("type") == "output_text" and content.get("text"):
                return content["text"]
    raise EditorialError("La risposta API non contiene output testuale")


def _numbers(value: str) -> set[str]:
    return set(re.findall(r"(?<!\d)\d+(?:[.,]\d+)?(?!\d)", value))


def _complete_fallback_summary(cluster: StoryCluster) -> str:
    article = cluster.representative
    excerpt = " ".join(article.excerpt.split())
    sentences = re.findall(r"[^.!?]+[.!?]", excerpt)
    complete = ""
    for sentence in sentences:
        candidate = f"{complete} {sentence.strip()}".strip()
        if len(candidate) > 140:
            break
        complete = candidate
    if complete:
        return complete
    title = " ".join(article.title.split())
    if len(title) <= 139:
        return title.rstrip(".!?…") + "."
    return "Notizia locale disponibile nella fonte originale."


def _fallback_item(cluster: StoryCluster) -> EditorialItem:
    article = cluster.representative
    summary = _complete_fallback_summary(cluster)
    section = cluster.category if cluster.category in SECTIONS else "Notizie e cronaca"
    headline = article.title[:110]
    return EditorialItem(cluster.key, headline, summary, section, headline[:44], grounded=True)


def _validation_errors(item: dict | None, cluster: StoryCluster) -> list[str]:
    if item is None:
        return ["elemento mancante"]
    if item.get("candidate_id") != cluster.key:
        return ["candidate_id errato"]
    if item.get("publishable") is False:
        return [] if str(item.get("rejection_reason", "")).strip() else ["rejection_reason mancante"]
    if item.get("publishable") is not True:
        return ["publishable deve essere true o false"]

    headline = " ".join(str(item.get("headline", "")).split())
    summary = " ".join(str(item.get("summary", "")).split())
    section = str(item.get("section", ""))
    subject_topic = " ".join(str(item.get("subject_topic", "")).split())
    errors: list[str] = []
    if not headline:
        errors.append("headline vuota")
    elif len(headline) > 110:
        errors.append(f"headline di {len(headline)} caratteri; massimo 110")
    if not summary:
        errors.append("summary vuota")
    elif len(summary) > 140:
        errors.append(f"summary di {len(summary)} caratteri; massimo 140")
    elif not summary.endswith((".", "!", "?")):
        errors.append("summary senza punteggiatura conclusiva")
    if section not in SECTIONS:
        errors.append("section non valida")
    if not subject_topic:
        errors.append("subject_topic vuoto")
    elif len(subject_topic) > 80:
        errors.append(f"subject_topic di {len(subject_topic)} caratteri; massimo 80")
    if "..." in subject_topic or "…" in subject_topic:
        errors.append("subject_topic troncato")
    if "—" in headline or "—" in summary or "—" in subject_topic:
        errors.append("em dash non consentito")
    evidence = f"{cluster.representative.title} {cluster.representative.excerpt} {cluster.representative.metadata}"
    invented = (_numbers(headline) | _numbers(summary) | _numbers(subject_topic)) - _numbers(evidence)
    if invented:
        errors.append("numeri non presenti nelle evidenze: " + ", ".join(sorted(invented)))
    return errors


def validate_items(raw_items: list[dict], clusters: list[StoryCluster]) -> tuple[list[EditorialItem], dict[str, list[str]], set[str]]:
    id_counts = Counter(
        item.get("candidate_id") for item in raw_items
        if isinstance(item, dict) and isinstance(item.get("candidate_id"), str)
    )
    by_id = {
        item.get("candidate_id"): item for item in raw_items
        if isinstance(item, dict) and isinstance(item.get("candidate_id"), str)
    }
    valid: list[EditorialItem] = []
    invalid: dict[str, list[str]] = {}
    rejected: set[str] = set()
    for cluster in clusters:
        item = by_id.get(cluster.key)
        errors = _validation_errors(item, cluster)
        if id_counts[cluster.key] > 1:
            errors.append("candidate_id duplicato")
        if errors:
            invalid[cluster.key] = errors
            continue
        if item.get("publishable") is False:
            rejected.add(cluster.key)
            continue
        valid.append(EditorialItem(
            candidate_id=cluster.key,
            headline=" ".join(str(item["headline"]).split()),
            summary=" ".join(str(item["summary"]).split()),
            section=str(item["section"]),
            subject_topic=" ".join(str(item["subject_topic"]).split()),
        ))
    return valid, invalid, rejected


def generate_openai(
    clusters: list[StoryCluster], sources: dict[str, Source], model: str = DEFAULT_MODEL,
    api_key: str | None = None, timeout: float | None = None,
) -> EditorialResult:
    api_key = api_key or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise EditorialError("OPENAI_API_KEY non configurata")
    if timeout is None:
        try:
            timeout = float(os.getenv("SIRACUSA_OPENAI_TIMEOUT", "180"))
        except ValueError as exc:
            raise EditorialError("SIRACUSA_OPENAI_TIMEOUT deve essere un numero di secondi") from exc
    if timeout < 10:
        raise EditorialError("SIRACUSA_OPENAI_TIMEOUT deve essere almeno 10 secondi")
    packet = evidence_packet(clusters, sources)
    raw_response = _request_openai(packet, model, api_key, INSTRUCTIONS, timeout, include_subject=True)
    raw_items = raw_response["items"]
    valid, invalid, rejected = validate_items(raw_items, clusters)
    raw_by_id = {item.get("candidate_id"): item for item in raw_items if isinstance(item, dict)}
    exclusions = {
        candidate_id: str(raw_by_id.get(candidate_id, {}).get("rejection_reason", "Evidenze insufficienti"))
        for candidate_id in rejected
    }
    invalid_clusters = [cluster for cluster in clusters if cluster.key in invalid]
    for repair_round in range(1, 4):
        if not invalid_clusters:
            break
        repair_packet = []
        for item in packet:
            candidate_id = item["candidate_id"]
            if candidate_id in invalid:
                repair_packet.append({**item, "validation_errors": invalid[candidate_id]})
        repair_instructions = INSTRUCTIONS + """

CORREZIONE OBBLIGATORIA:
Ogni candidato contiene validation_errors prodotti da controlli oggettivi. Correggi quegli errori e riscrivi integralmente headline e summary rispettando lo stesso contratto editoriale.
Nella correzione scrivi una sola frase di 70-100 caratteri. Conta tutti i caratteri, spazi inclusi, prima di restituire l'output.
"""
        try:
            repaired_response = _request_openai(
                repair_packet, model, api_key, repair_instructions, timeout, include_subject=False,
            )
            repaired_raw = repaired_response["items"]
        except EditorialError as exc:
            exclusions.update({
                cluster.key: f"Correzione editoriale non disponibile: {exc}" for cluster in invalid_clusters
            })
            invalid_clusters = []
            invalid = {}
            break
        else:
            repaired, still_invalid, repaired_rejected = validate_items(repaired_raw, invalid_clusters)
            valid.extend(repaired)
            repaired_by_id = {item.get("candidate_id"): item for item in repaired_raw if isinstance(item, dict)}
            exclusions.update({
                candidate_id: str(repaired_by_id.get(candidate_id, {}).get("rejection_reason", "Evidenze insufficienti"))
                for candidate_id in repaired_rejected
            })
            invalid = still_invalid
            invalid_clusters = [
                cluster for cluster in invalid_clusters if cluster.key in still_invalid
            ]
    exclusions.update({
        candidate_id: "Controlli falliti dopo tre correzioni: " + "; ".join(errors)
        for candidate_id, errors in invalid.items()
    })
    by_id = {item.candidate_id: item for item in valid}
    ordered_items = [by_id[cluster.key] for cluster in clusters if cluster.key in by_id]
    subject = _validated_subject(
        raw_response.get("subject"), raw_response.get("subject_candidate_ids"), ordered_items, clusters,
    )
    if not subject:
        subject = _safe_fallback_subject(ordered_items, clusters)
    return EditorialResult(items=ordered_items, exclusions=exclusions, subject=subject)


def _has_sensitive_subject_language(value: str) -> bool:
    normalized = normalize_text(value)
    words = set(normalized.split())
    return bool(words & SENSITIVE_SUBJECT_TERMS) or any(
        phrase in normalized for phrase in SENSITIVE_SUBJECT_PHRASES
    )


def _sensitive_story(cluster: StoryCluster) -> bool:
    article = cluster.representative
    return _has_sensitive_subject_language(
        f"{article.title} {article.excerpt} {article.metadata}"
    )


def _safe_fallback_subject(items: list[EditorialItem], clusters: list[StoryCluster]) -> str:
    cluster_by_id = {cluster.key: cluster for cluster in clusters}
    for item in items:
        cluster = cluster_by_id.get(item.candidate_id)
        topic = " ".join(item.subject_topic.split()).strip(" .")
        if (
            cluster is None or _sensitive_story(cluster)
            or _has_sensitive_subject_language(topic)
            or not 20 <= len(topic) <= 80
        ):
            continue
        return topic[0].upper() + topic[1:]
    return ""


def _validated_subject(
    raw_subject: object, raw_candidate_ids: object, items: list[EditorialItem],
    clusters: list[StoryCluster],
) -> str:
    subject = " ".join(str(raw_subject or "").split())
    if not 20 <= len(subject) <= 90:
        return ""
    lowered = subject.casefold()
    if (
        "—" in subject or "..." in subject or "…" in subject
        or "siracusadaily" in lowered or lowered.startswith("siracusa oggi")
    ):
        return ""
    if not isinstance(raw_candidate_ids, list):
        return ""
    candidate_ids = [str(value) for value in raw_candidate_ids]
    if not 1 <= len(candidate_ids) <= 3 or len(candidate_ids) != len(set(candidate_ids)):
        return ""
    valid_ids = {item.candidate_id for item in items}
    if any(candidate_id not in valid_ids for candidate_id in candidate_ids):
        return ""
    cluster_by_id = {cluster.key: cluster for cluster in clusters}
    if any(_sensitive_story(cluster_by_id[candidate_id]) for candidate_id in candidate_ids):
        return ""
    if _has_sensitive_subject_language(subject):
        return ""
    evidence = " ".join(
        f"{cluster_by_id[candidate_id].representative.title} "
        f"{cluster_by_id[candidate_id].representative.excerpt} "
        f"{cluster_by_id[candidate_id].representative.metadata}"
        for candidate_id in candidate_ids
    )
    if _numbers(subject) - _numbers(evidence):
        return ""
    return subject


def _request_openai(
    packet: list[dict], model: str, api_key: str, instructions: str, timeout: float,
    *, include_subject: bool,
) -> dict:
    body = json.dumps({
        "model": model,
        "instructions": instructions,
        "input": json.dumps({"candidates": packet}, ensure_ascii=False),
        "text": {"format": {
            "type": "json_schema", "name": "siracusa_daily_editorial", "strict": True,
            "schema": _schema(include_subject),
        }},
        "store": False,
    }, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        "https://api.openai.com/v1/responses", data=body, method="POST",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    )
    try:
        max_attempts = int(os.getenv("SIRACUSA_OPENAI_ATTEMPTS", "3"))
    except ValueError as exc:
        raise EditorialError("SIRACUSA_OPENAI_ATTEMPTS deve essere un numero intero") from exc
    if not 1 <= max_attempts <= 5:
        raise EditorialError("SIRACUSA_OPENAI_ATTEMPTS deve essere compreso tra 1 e 5")

    result: dict = {}
    for attempt in range(1, max_attempts + 1):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                result = json.loads(response.read())
            break
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:1000]
            retryable = exc.code in {408, 409, 429} or 500 <= exc.code <= 599
            if not retryable or attempt == max_attempts:
                raise EditorialError(f"OpenAI API HTTP {exc.code}: {detail}") from exc
        except (urllib.error.URLError, TimeoutError, socket.timeout, json.JSONDecodeError) as exc:
            if attempt == max_attempts:
                raise EditorialError(f"OpenAI API: {exc}") from exc
        time.sleep(min(10, 2 ** attempt))
    try:
        parsed = json.loads(_response_text(result))
    except json.JSONDecodeError as exc:
        raise EditorialError("L'output strutturato non è JSON valido") from exc
    if not isinstance(parsed, dict):
        raise EditorialError("L'output strutturato non è un oggetto JSON")
    items = parsed.get("items", [])
    if not isinstance(items, list):
        raise EditorialError("L'output strutturato non contiene una lista di elementi")
    return parsed


def generate_editorial(
    clusters: list[StoryCluster], sources: dict[str, Source], mode: str = "openai", model: str = DEFAULT_MODEL,
) -> tuple[list[EditorialItem], str, dict[str, str], str]:
    if mode not in {"openai", "fallback"}:
        raise ValueError(f"Modalità writer non valida: {mode}")
    if mode == "fallback":
        return [_fallback_item(cluster) for cluster in clusters], "fallback", {}, ""
    result = generate_openai(clusters, sources, model=model)
    return result.items, "openai", result.exclusions, result.subject
