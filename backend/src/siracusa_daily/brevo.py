from __future__ import annotations

from dataclasses import dataclass
import json
import os
import socket
from datetime import date, datetime, time, timedelta
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo


API_BASE = "https://api.brevo.com/v3"
DEFAULT_LIST_NAME = "Iscritti SiracusaDaily"
ROME = ZoneInfo("Europe/Rome")
DEFAULT_SEND_TIME = time(8, 30)
DEFAULT_MINIMUM_LEAD_MINUTES = 15


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
    scheduled_at: datetime | None = None


@dataclass(frozen=True)
class BrevoCampaign:
    campaign_id: int
    name: str
    status: str


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


def find_campaign_for_edition(
    edition_date: date, *, api_key: str | None = None,
) -> BrevoCampaign | None:
    """Return any Brevo campaign already created for an edition.

    This is the authoritative idempotency check. It deliberately includes drafts,
    scheduled campaigns and sent campaigns so a retry can never create a duplicate.
    """
    prefix = f"SiracusaDaily | {edition_date:%d/%m/%Y} |"
    offset = 0
    while True:
        result = _request(
            "GET", "/emailCampaigns", api_key=api_key,
            query={"type": "classic", "limit": 50, "offset": offset, "sort": "desc"},
        )
        rows = result.get("campaigns", [])
        if not isinstance(rows, list):
            raise BrevoError("elenco campagne Brevo non valido")
        for row in rows:
            if not isinstance(row, dict):
                continue
            name = str(row.get("name", "")).strip()
            if not name.startswith(prefix):
                continue
            try:
                campaign_id = int(row["id"])
            except (KeyError, TypeError, ValueError) as exc:
                raise BrevoError("la campagna Brevo trovata non contiene un ID valido") from exc
            return BrevoCampaign(campaign_id, name, str(row.get("status", "unknown")))
        if len(rows) < 50:
            return None
        offset += 50


def automatic_send_enabled(explicit: str | None = None) -> bool:
    raw = explicit if explicit is not None else os.getenv("SIRACUSA_AUTO_SEND_ENABLED", "")
    normalized = raw.strip().casefold()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"", "0", "false", "no", "off"}:
        return False
    raise BrevoError(
        "SIRACUSA_AUTO_SEND_ENABLED deve essere true oppure false; "
        "programmazione automatica annullata"
    )


def parse_send_time(value: str | None = None) -> time:
    default_value = DEFAULT_SEND_TIME.strftime("%H:%M")
    raw = (value or os.getenv("SIRACUSA_BREVO_SEND_TIME", default_value)).strip()
    try:
        parsed = datetime.strptime(raw, "%H:%M").time()
    except ValueError as exc:
        raise BrevoError("SIRACUSA_BREVO_SEND_TIME deve usare il formato HH:MM") from exc
    return parsed


def campaign_schedule(
    edition_date: date, *, now: datetime | None = None,
    target_time: time | None = None, minimum_lead_minutes: int | None = None,
) -> datetime:
    if minimum_lead_minutes is None:
        raw_lead = os.getenv(
            "SIRACUSA_BREVO_MINIMUM_LEAD_MINUTES",
            str(DEFAULT_MINIMUM_LEAD_MINUTES),
        )
        try:
            minimum_lead_minutes = int(raw_lead)
        except ValueError as exc:
            raise BrevoError(
                "SIRACUSA_BREVO_MINIMUM_LEAD_MINUTES deve essere un numero intero"
            ) from exc
    if not 5 <= minimum_lead_minutes <= 120:
        raise BrevoError(
            "SIRACUSA_BREVO_MINIMUM_LEAD_MINUTES deve essere compreso tra 5 e 120"
        )
    current = now or datetime.now(ROME)
    if current.tzinfo is None or current.utcoffset() is None:
        raise BrevoError("l'orario corrente deve includere il fuso orario")
    current = current.astimezone(ROME)
    planned = datetime.combine(
        edition_date,
        target_time or parse_send_time(),
        tzinfo=ROME,
    )
    lead = timedelta(minutes=minimum_lead_minutes)
    if current <= planned - lead:
        return planned
    delayed = current + lead
    if delayed.second or delayed.microsecond:
        delayed = delayed.replace(second=0, microsecond=0) + timedelta(minutes=1)
    return delayed


def _create_campaign(
    html: str, edition_date: date, subject: str, *, run_id: int,
    list_name: str = DEFAULT_LIST_NAME, api_key: str | None = None,
    scheduled_at: datetime | None = None,
) -> BrevoCampaignDraft:
    if len(html.encode("utf-8")) >= 1_000_000:
        raise BrevoError("HTML della campagna superiore al limite Brevo di 1 MB")
    if len(html.strip()) <= 10:
        raise BrevoError("HTML della campagna vuoto o incompleto")
    if scheduled_at is not None and (
        scheduled_at.tzinfo is None or scheduled_at.utcoffset() is None
    ):
        raise BrevoError("la programmazione Brevo deve includere il fuso orario")
    target = find_list(list_name, api_key=api_key)
    sender_email = os.getenv("SIRACUSA_BREVO_SENDER", "newsletter@siracusadaily.com")
    sender_name = os.getenv("SIRACUSA_BREVO_SENDER_NAME", "SiracusaDaily")
    reply_to = os.getenv("SIRACUSA_BREVO_REPLY_TO", "ciao@siracusadaily.com")
    name = f"SiracusaDaily | {edition_date:%d/%m/%Y} | run {run_id}"
    payload: dict[str, Any] = {
        "name": name,
        "subject": subject,
        "sender": {"name": sender_name, "email": sender_email},
        "replyTo": reply_to,
        "htmlContent": html,
        "recipients": {"listIds": [target.list_id]},
        "utmCampaign": f"SiracusaDaily {edition_date:%Y%m%d}",
    }
    if scheduled_at is not None:
        payload["scheduledAt"] = scheduled_at.isoformat(timespec="milliseconds")
    result = _request(
        "POST", "/emailCampaigns", api_key=api_key,
        payload=payload,
    )
    try:
        campaign_id = int(result["id"])
    except (KeyError, TypeError, ValueError) as exc:
        raise BrevoError("Brevo non ha restituito l'ID della campagna") from exc
    return BrevoCampaignDraft(
        campaign_id, target.list_id, target.name, scheduled_at=scheduled_at,
    )


def create_campaign_draft(
    html: str, edition_date: date, subject: str, *, run_id: int,
    list_name: str = DEFAULT_LIST_NAME, api_key: str | None = None,
) -> BrevoCampaignDraft:
    return _create_campaign(
        html, edition_date, subject, run_id=run_id,
        list_name=list_name, api_key=api_key,
    )


def create_campaign_scheduled(
    html: str, edition_date: date, subject: str, *, run_id: int,
    scheduled_at: datetime, list_name: str = DEFAULT_LIST_NAME,
    api_key: str | None = None,
) -> BrevoCampaignDraft:
    return _create_campaign(
        html, edition_date, subject, run_id=run_id,
        list_name=list_name, api_key=api_key, scheduled_at=scheduled_at,
    )
