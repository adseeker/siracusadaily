from __future__ import annotations

from datetime import date
from html import escape
from pathlib import Path
from zoneinfo import ZoneInfo

from .models import Source, StoryCluster
from .editorial import EditorialItem
from .categories import CATEGORY_ORDER

CATEGORY_COLORS = {
    "Notizie e cronaca": "#1d4ed8",
    "Politica ed economia": "#7e22ce",
    "Cultura": "#be185d",
    "Sport": "#15803d",
    "Eventi": "#c2410c",
    "Servizi e utilità": "#0e7490",
    "Lavoro e opportunità": "#a16207",
}


def _display_text(value: str) -> str:
    return value.replace("—", "-")


def render_markdown(
    edition_date: date, clusters: list[StoryCluster], sources: dict[str, Source],
    editorial_items: list[EditorialItem] | None = None, writer_name: str = "template",
) -> str:
    editorial_by_id = {item.candidate_id: item for item in editorial_items or []}
    lines = [f"# SiracusaDaily - {edition_date.isoformat()}", "", "Le informazioni locali da conoscere oggi.", ""]
    grouped = {category: [] for category in CATEGORY_ORDER}
    for cluster in clusters:
        grouped.setdefault(cluster.category, []).append(cluster)
    index = 0
    for category in CATEGORY_ORDER:
        category_clusters = grouped.get(category, [])
        if not category_clusters:
            continue
        lines.extend([f"## {category}", ""])
        for cluster in category_clusters:
            index += 1
            article = cluster.representative
            source = sources[article.source_id]
            editorial = editorial_by_id.get(cluster.key)
            date_label = article.metadata.get("date_label", "Pubblicato")
            reference_date = article.metadata.get("reference_date")
            display_date = article.published_at
            if reference_date:
                try:
                    from datetime import datetime
                    display_date = datetime.fromisoformat(reference_date)
                except ValueError:
                    pass
            if display_date.tzinfo:
                display_date = display_date.astimezone(ZoneInfo("Europe/Rome"))
            headline = _display_text(editorial.headline if editorial else article.title)
            summary = _display_text(editorial.summary if editorial else "Notizia locale disponibile nella fonte originale.")
            link = f"[Approfondisci su {_display_text(source.name)}]({article.url})"
            if cluster.category == "Eventi" and date_label in {"Inizio", "Data"}:
                date_format = "%d/%m/%Y %H:%M" if (display_date.hour or display_date.minute) else "%d/%m/%Y"
                link += f" · {date_label} {display_date:{date_format}}"
            elif cluster.category == "Lavoro e opportunità" and date_label == "Scadenza":
                link += f" · Scadenza {display_date:%d/%m/%Y}"
            lines.extend([
                f"### {index}. {headline}", "",
                summary, "",
                link, "",
            ])
    return "\n".join(lines)


def save_markdown(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def render_html(
    edition_date: date, clusters: list[StoryCluster], sources: dict[str, Source],
    editorial_items: list[EditorialItem] | None = None, publisher_name: str = "SiracusaDaily",
    publisher_address: str = "", unsubscribe_url: str = "",
) -> str:
    editorial_by_id = {item.candidate_id: item for item in editorial_items or []}
    grouped = {category: [] for category in CATEGORY_ORDER}
    for cluster in clusters:
        grouped.setdefault(cluster.category, []).append(cluster)

    sections: list[str] = []
    for category in CATEGORY_ORDER:
        cards: list[str] = []
        for cluster in grouped.get(category, []):
            article = cluster.representative
            source = sources[article.source_id]
            editorial = editorial_by_id.get(cluster.key)
            headline = _display_text(editorial.headline if editorial else article.title)
            summary = _display_text(editorial.summary if editorial else "Notizia locale disponibile nella fonte originale.")
            date_label = article.metadata.get("date_label", "Pubblicato")
            reference_date = article.metadata.get("reference_date")
            display_date = article.published_at
            if reference_date:
                try:
                    from datetime import datetime
                    display_date = datetime.fromisoformat(reference_date)
                except ValueError:
                    pass
            if display_date.tzinfo:
                display_date = display_date.astimezone(ZoneInfo("Europe/Rome"))
            timing = ""
            if category == "Eventi" and date_label in {"Inizio", "Data"}:
                fmt = "%d/%m/%Y %H:%M" if (display_date.hour or display_date.minute) else "%d/%m/%Y"
                timing = f" · {escape(date_label)} {display_date:{fmt}}"
            elif category == "Lavoro e opportunità" and date_label == "Scadenza":
                timing = f" · Scadenza {display_date:%d/%m/%Y}"
            timing_html = f'<span style="font:14px/1.4 Arial,sans-serif;color:#64748b;">{timing}</span>' if timing else ""
            cards.append(f'''<tr><td style="padding:24px 0;border-bottom:1px solid #dbe3ea;">
              <h3 style="margin:0 0 10px;font:700 21px/1.3 Arial,sans-serif;color:#172033;">{escape(headline)}</h3>
              <p style="margin:0 0 14px;font:16px/1.55 Arial,sans-serif;color:#374151;">{escape(summary)}</p>
              <a href="{escape(article.url, quote=True)}" style="font:700 14px/1.4 Arial,sans-serif;color:#075985;text-decoration:none;">Approfondisci su {escape(_display_text(source.name))}</a>{timing_html}
            </td></tr>''')
        if cards:
            color = CATEGORY_COLORS[category]
            sections.append(f'''<tr><td style="height:24px;background:#ffffff;font-size:0;line-height:0;">&nbsp;</td></tr>
            <tr><td style="padding:18px 32px;background:{color};">
              <h2 style="margin:0;font:700 18px/1.25 Arial,sans-serif;letter-spacing:.5px;text-transform:uppercase;color:#ffffff;">{escape(category)}</h2>
            </td></tr>
            <tr><td style="padding:0 32px 8px;background:#ffffff;">
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">{''.join(cards)}</table>
            </td></tr>''')

    footer_parts = [escape(publisher_name)]
    if publisher_address:
        footer_parts.append(escape(publisher_address))
    footer = " · ".join(footer_parts)
    unsubscribe = ""
    if unsubscribe_url:
        unsubscribe = f'<br><a href="{escape(unsubscribe_url, quote=True)}" style="color:#475569;">Annulla iscrizione</a>'

    return f'''<!doctype html>
<html lang="it"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>SiracusaDaily</title></head>
<body style="margin:0;padding:0;background:#ffffff;">
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background:#ffffff;"><tr><td align="center" style="padding:0 12px 28px;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="max-width:640px;background:#ffffff;">
    <tr><td align="center" style="padding:36px 32px 20px;background:#ffffff;color:#000000;">
      <h1 style="margin:0;font:italic 700 38px/1.1 Georgia,'Times New Roman',serif;color:#000000;letter-spacing:-.5px;">SiracusaDaily</h1>
      <p style="margin:10px 0 0;font:15px/1.4 Arial,sans-serif;color:#000000;">Edizione del {edition_date:%d/%m/%Y}</p>
    </td></tr>
    {''.join(sections)}
    <tr><td style="padding:28px 32px;text-align:center;background:#ffffff;font:12px/1.6 Arial,sans-serif;color:#64748b;">{footer}{unsubscribe}</td></tr>
  </table>
</td></tr></table></body></html>'''


def save_html(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
