from __future__ import annotations

import argparse
import os
from datetime import date
from pathlib import Path

from .brevo import (
    BrevoError,
    DEFAULT_LIST_NAME,
    create_campaign_draft,
    find_campaign_for_edition,
    find_list,
)
from .database import connect, get_brevo_campaign_for_edition, get_newsletter_run, record_brevo_draft
from .pipeline import build_newsletter, ingest
from .editorial import DEFAULT_MODEL, EditorialError
from .mailer import MailerError, send_html

PROJECT = Path(__file__).resolve().parents[2]


def _remote_campaign_or_exit(edition_date: date):
    try:
        return find_campaign_for_edition(edition_date)
    except BrevoError as exc:
        raise SystemExit(
            f"Controllo anti-duplicato Brevo non disponibile: {exc}. "
            "Esecuzione interrotta senza creare campagne."
        ) from exc


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="siracusa-daily")
    root.add_argument("--source-map", type=Path, default=PROJECT / "data/source_map.csv")
    root.add_argument("--endpoint-map", type=Path, default=PROJECT / "data/endpoint_map.csv")
    root.add_argument("--database", type=Path, default=PROJECT / "data/siracusa_daily.db")
    commands = root.add_subparsers(dest="command", required=True)
    commands.add_parser("init")
    preflight = commands.add_parser("preflight")
    preflight.add_argument("--date", type=date.fromisoformat)
    preflight.add_argument("--brevo-list", default=DEFAULT_LIST_NAME)
    retry_draft = commands.add_parser("brevo-draft")
    retry_draft.add_argument("--run-id", type=int, required=True)
    retry_draft.add_argument("--input", type=Path)
    retry_draft.add_argument("--brevo-list", default=DEFAULT_LIST_NAME)
    retry_draft.add_argument("--subject")
    ingest_parser = commands.add_parser("ingest")
    ingest_parser.add_argument("--endpoint-limit", type=int)
    ingest_parser.add_argument("--item-limit", type=int, default=30)
    ingest_parser.add_argument("--method", action="append", choices=["rss", "web_html"])
    build = commands.add_parser("build")
    build.add_argument("--output", type=Path, default=PROJECT / "output/newsletter-draft.md")
    build.add_argument("--date", type=date.fromisoformat)
    build.add_argument("--lookback-hours", type=int, default=72)
    build.add_argument("--limit", type=int, default=8)
    build.add_argument("--event-limit", type=int, default=8)
    build.add_argument("--opportunity-limit", type=int, default=6)
    build.add_argument("--writer", choices=["openai", "fallback"], default="openai")
    build.add_argument("--model", default=DEFAULT_MODEL)
    build_delivery = build.add_mutually_exclusive_group()
    build_delivery.add_argument("--send-to", action="append")
    build_delivery.add_argument("--test-send-to", action="append")
    build_delivery.add_argument("--brevo-draft", action="store_true")
    build.add_argument("--brevo-list", default=DEFAULT_LIST_NAME)
    build.add_argument("--subject")
    build.add_argument("--minimum-items", type=int, default=0)
    run = commands.add_parser("run")
    run.add_argument("--output", type=Path, default=PROJECT / "output/newsletter-draft.md")
    run.add_argument("--date", type=date.fromisoformat)
    run.add_argument("--endpoint-limit", type=int)
    run.add_argument("--item-limit", type=int, default=30)
    run.add_argument("--method", action="append", choices=["rss", "web_html"])
    run.add_argument("--lookback-hours", type=int, default=72)
    run.add_argument("--limit", type=int, default=8)
    run.add_argument("--event-limit", type=int, default=8)
    run.add_argument("--opportunity-limit", type=int, default=6)
    run.add_argument("--writer", choices=["openai", "fallback"], default="openai")
    run.add_argument("--model", default=DEFAULT_MODEL)
    run_delivery = run.add_mutually_exclusive_group()
    run_delivery.add_argument("--send-to", action="append")
    run_delivery.add_argument("--test-send-to", action="append")
    run_delivery.add_argument("--brevo-draft", action="store_true")
    run.add_argument("--brevo-list", default=DEFAULT_LIST_NAME)
    run.add_argument("--subject")
    run.add_argument("--minimum-items", type=int, default=0)
    run.add_argument("--skip-existing-brevo-date", action="store_true")
    return root


def main() -> None:
    args = parser().parse_args()
    if args.command == "init":
        connect(args.database).close()
        print(f"Database inizializzato: {args.database}")
        return
    if args.command == "preflight":
        if not os.getenv("OPENAI_API_KEY"):
            raise SystemExit("Preflight fallito: OPENAI_API_KEY non configurata")
        connection = connect(args.database)
        connection.close()
        try:
            target = find_list(args.brevo_list)
        except BrevoError as exc:
            raise SystemExit(f"Preflight fallito: {exc}") from exc
        edition_date = args.date or date.today()
        existing = _remote_campaign_or_exit(edition_date)
        campaign = (
            f"campagna #{existing.campaign_id} ({existing.status}) già presente"
            if existing is not None else "nessuna campagna ancora presente"
        )
        print(
            f"Preflight riuscito: database disponibile; lista Brevo '{target.name}' "
            f"(ID {target.list_id}); {campaign} per {edition_date.isoformat()}; "
            "OPENAI_API_KEY configurata."
        )
        return
    if args.command == "brevo-draft":
        connection = connect(args.database)
        try:
            run = get_newsletter_run(connection, args.run_id)
            if run is None:
                raise SystemExit(f"Newsletter #{args.run_id} non trovata")
            if run["writer_name"] != "openai":
                raise SystemExit("Bozza Brevo annullata: una newsletter fallback non può essere pubblicata")
            if run["brevo_campaign_id"] is not None:
                print(f"Newsletter #{args.run_id} già collegata alla campagna Brevo #{run['brevo_campaign_id']}")
                return
            output = args.input or Path(run["output_path"])
            if not output.is_absolute():
                output = PROJECT / output
            if output.suffix.lower() != ".html" or not output.is_file():
                raise SystemExit(f"HTML della newsletter non trovato: {output}")
            edition_date = date.fromisoformat(run["edition_date"])
            existing_remote = _remote_campaign_or_exit(edition_date)
            if existing_remote is not None:
                print(
                    f"Bozza non creata: l’edizione del {edition_date.isoformat()} esiste già "
                    f"su Brevo come campagna #{existing_remote.campaign_id} ({existing_remote.status})"
                )
                return
            subject = args.subject or run["email_subject"]
            if not subject:
                raise SystemExit("Oggetto non disponibile per questa newsletter; usa --subject")
            try:
                draft = create_campaign_draft(
                    output.read_text(encoding="utf-8"), edition_date, subject,
                    run_id=args.run_id, list_name=args.brevo_list,
                )
                record_brevo_draft(connection, args.run_id, draft.campaign_id, draft.list_id)
            except (BrevoError, OSError) as exc:
                raise SystemExit(f"Bozza Brevo non creata: {exc}") from exc
        finally:
            connection.close()
        print(
            f"Bozza Brevo creata: campagna #{draft.campaign_id}; "
            f"lista '{draft.list_name}' (ID {draft.list_id})"
        )
        print("Apri Brevo > Marketing > Campagne per controllarla. Nessun invio è stato eseguito.")
        return
    if args.command == "run" and args.skip_existing_brevo_date:
        edition_date = args.date or date.today()
        if args.brevo_draft:
            existing_remote = _remote_campaign_or_exit(edition_date)
            if existing_remote is not None:
                print(
                    f"Esecuzione ignorata: l’edizione del {edition_date.isoformat()} esiste già "
                    f"su Brevo come campagna #{existing_remote.campaign_id} ({existing_remote.status})"
                )
                return
        else:
            connection = connect(args.database)
            try:
                existing = get_brevo_campaign_for_edition(connection, edition_date.isoformat())
            finally:
                connection.close()
            if existing is not None:
                print(
                    f"Esecuzione ignorata: l’edizione del {edition_date.isoformat()} "
                    f"ha già la campagna Brevo #{existing['brevo_campaign_id']}"
                )
                return
    if args.command in {"ingest", "run"}:
        report = ingest(
            args.source_map, args.endpoint_map, args.database, args.endpoint_limit, args.item_limit,
            set(args.method) if args.method else None,
        )
        print(
            f"Retrieval: {report.endpoints_succeeded}/{report.endpoints_attempted} endpoint; "
            f"{report.articles_seen} articoli; {report.articles_local} locali; "
            f"{report.events_quarantined} eventi in quarantena"
        )
        for error in report.errors:
            print(f"WARN {error}")
        if args.command == "ingest":
            return
    try:
        run_id, count, writer_used, generated_subject = build_newsletter(
            args.source_map, args.database, args.output, getattr(args, "date", None), args.lookback_hours,
            args.limit, args.writer, args.model,
            unsubscribe_url="{{ unsubscribe }}" if args.brevo_draft else None,
            event_limit=args.event_limit,
            opportunity_limit=args.opportunity_limit,
        )
    except EditorialError as exc:
        raise SystemExit(f"Writer OpenAI non disponibile: {exc}") from exc
    print(f"Newsletter #{run_id}: {count} notizie; writer={writer_used} -> {args.output}")
    if args.brevo_draft:
        if writer_used != "openai":
            raise SystemExit("Bozza Brevo annullata: una newsletter fallback non può essere pubblicata")
        if args.output.suffix.lower() != ".html":
            raise SystemExit("Per creare una bozza Brevo, usa un file --output con estensione .html")
        if count < args.minimum_items:
            raise SystemExit(
                f"Bozza Brevo annullata: solo {count} notizie, minimo richiesto {args.minimum_items}"
            )
        edition_date = getattr(args, "date", None) or date.today()
        subject = args.subject or generated_subject
        if not subject:
            raise SystemExit("Bozza Brevo annullata: il writer non ha prodotto un oggetto valido")
        # A second authoritative check closes the window between the initial
        # preflight and campaign creation (manual retriggers, retries, stale state).
        existing_remote = _remote_campaign_or_exit(edition_date)
        if existing_remote is not None:
            print(
                f"Bozza non creata: l’edizione del {edition_date.isoformat()} esiste già "
                f"su Brevo come campagna #{existing_remote.campaign_id} ({existing_remote.status})"
            )
            return
        try:
            draft = create_campaign_draft(
                args.output.read_text(encoding="utf-8"), edition_date, subject,
                run_id=run_id, list_name=args.brevo_list,
            )
            connection = connect(args.database)
            try:
                record_brevo_draft(connection, run_id, draft.campaign_id, draft.list_id)
            finally:
                connection.close()
        except (BrevoError, OSError) as exc:
            raise SystemExit(f"Bozza Brevo non creata: {exc}") from exc
        print(
            f"Bozza Brevo creata: campagna #{draft.campaign_id}; "
            f"lista '{draft.list_name}' (ID {draft.list_id})"
        )
        print("Apri Brevo > Marketing > Campagne per controllarla. Nessun invio è stato eseguito.")
        return
    recipients = args.send_to or args.test_send_to
    if recipients:
        if writer_used != "openai":
            raise SystemExit("Invio annullato: una newsletter fallback non può essere spedita")
        if args.output.suffix.lower() != ".html":
            raise SystemExit("Per inviare la newsletter, usa un file --output con estensione .html")
        subject = args.subject or generated_subject
        if not subject:
            raise SystemExit("Invio annullato: il writer non ha prodotto un oggetto valido")
        try:
            send_html(
                recipients,
                subject,
                args.output.read_text(encoding="utf-8"),
                require_compliance=not bool(args.test_send_to),
            )
        except MailerError as exc:
            raise SystemExit(f"Email non inviata: {exc}") from exc
        label = "Email di test inviata" if args.test_send_to else "Email inviata"
        print(f"{label} a: {', '.join(recipients)}")


if __name__ == "__main__":
    main()
