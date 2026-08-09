from __future__ import annotations

from dataclasses import dataclass
import json
import os
import socket
from datetime import date
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


API_BASE = "https://api.brevo.com/v3"
DEFAULT_LIST_NAME = "Iscritti SiracusaDaily"


class BrevoError(RuntimeError):
    pass


@dataclass(frozen=True)
class BrevoList:
    list_id: int
    name: str


@dataclass(frozen=True)
class BrevoCampaignDraft:
    campaign_id: int
    list_id: int
    list_name: str


def _api_key(explicit: str | None = None) -> str:
    key = explicit or os.getenv("BREVO_API_KEY", "")
    if not key:
        raise BrevoError("BREVO_API_KEY non configurata")
    return key


def _request(
    method: str, path: str, *, api_key: str | None = None,
    payload: dict[str, Any] | None = None, query: dict[str, Any] | None = None,
    timeout: int = 30,
) -> dict[str, Any]:
    url = f"{API_BASE}{path}"
    if query:
        url = f"{url}?{urlencode(query)}"
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = Request(
        url,
        data=body,
        method=method,
        headers={
            "accept": "application/json",
            "api-key": _api_key(api_key),
            "content-type": "application/json",
        },
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            detail = json.loads(raw).get("message", raw)
        except json.JSONDecodeError:
            detail = raw
        raise BrevoError(f"Brevo API {exc.code}: {detail}") from exc
    except (URLError, socket.timeout, OSError) as exc:
        raise BrevoError(f"Brevo API non raggiungibile: {exc}") from exc
    if not raw:
        return {}
    try:
        result = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise BrevoError("Brevo API ha restituito una risposta non valida") from exc
    if not isinstance(result, dict):
        raise BrevoError("Brevo API ha restituito un formato inatteso")
    return result


def find_list(name: str = DEFAULT_LIST_NAME, *, api_key: str | None = None) -> BrevoList:
    offset = 0
    matches: list[BrevoList] = []
    while True:
        result = _request(
            "GET", "/contacts/lists", api_key=api_key,
            query={"limit": 50, "offset": offset, "sort": "desc"},
        )
        rows = result.get("lists", [])
        if not isinstance(rows, list):
            raise BrevoError("elenco liste Brevo non valido")
        for row in rows:
            if not isinstance(row, dict):
                continue
            row_name = str(row.get("name", "")).strip()
            if row_name.casefold() == name.strip().casefold():
                try:
                    matches.append(BrevoList(int(row["id"]), row_name))
                except (KeyError, TypeError, ValueError) as exc:
                    raise BrevoError("la lista Brevo trovata non contiene un ID valido") from exc
        if len(rows) < 50:
            break
        offset += 50
    if not matches:
        raise BrevoError(f"lista Brevo non trovata: {name}")
    if len(matches) > 1:
        raise BrevoError(f"esistono più liste Brevo chiamate {name}; rinominarle per renderle univoche")
    return matches[0]


def create_campaign_draft(
    html: str, edition_date: date, subject: str, *, run_id: int,
    list_name: str = DEFAULT_LIST_NAME, api_key: str | None = None,
) -> BrevoCampaignDraft:
    if len(html.encode("utf-8")) >= 1_000_000:
        raise BrevoError("HTML della campagna superiore al limite Brevo di 1 MB")
    if len(html.strip()) <= 10:
        raise BrevoError("HTML della campagna vuoto o incompleto")
    target = find_list(list_name, api_key=api_key)
    sender_email = os.getenv("SIRACUSA_BREVO_SENDER", "newsletter@siracusadaily.com")
    sender_name = os.getenv("SIRACUSA_BREVO_SENDER_NAME", "SiracusaDaily")
    reply_to = os.getenv("SIRACUSA_BREVO_REPLY_TO", "ciao@siracusadaily.com")
    name = f"SiracusaDaily | {edition_date:%d/%m/%Y} | run {run_id}"
    result = _request(
        "POST", "/emailCampaigns", api_key=api_key,
        payload={
            "name": name,
            "subject": subject,
            "sender": {"name": sender_name, "email": sender_email},
            "replyTo": reply_to,
            "htmlContent": html,
            "recipients": {"listIds": [target.list_id]},
            "utmCampaign": f"SiracusaDaily {edition_date:%Y%m%d}",
        },
    )
    try:
        campaign_id = int(result["id"])
    except (KeyError, TypeError, ValueError) as exc:
        raise BrevoError("Brevo non ha restituito l'ID della campagna") from exc
    return BrevoCampaignDraft(campaign_id, target.list_id, target.name)
