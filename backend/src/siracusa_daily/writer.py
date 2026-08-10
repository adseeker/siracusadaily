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
        category_clusters = grouped.get(category, [])
        for card_index, cluster in enumerate(category_clusters):
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
            timing_html = f'<span style="font:14px/1.45 Arial,sans-serif;color:#64748b;">{timing}</span>' if timing else ""
            divider = "border-bottom:1px solid #e5e7eb;" if card_index < len(category_clusters) - 1 else ""
            cards.append(f'''<tr><td class="sd-card" style="padding:22px 0;{divider}">
              <h3 class="sd-title" style="margin:0 0 10px;font:700 20px/1.3 Georgia,'Times New Roman',serif;color:#172033;">{escape(headline)}</h3>
              <p class="sd-summary" style="margin:0 0 13px;font:16px/1.6 Arial,sans-serif;color:#374151;">{escape(summary)}</p>
              <a class="sd-link" href="{escape(article.url, quote=True)}" style="font:700 15px/1.45 Arial,sans-serif;color:#075985;text-decoration:underline;text-decoration-thickness:1px;text-underline-offset:3px;">Approfondisci su {escape(_display_text(source.name))}</a>{timing_html}
            </td></tr>''')
        if cards:
            color = CATEGORY_COLORS[category]
            sections.append(f'''<tr><td style="height:28px;background:#ffffff;font-size:0;line-height:0;">&nbsp;</td></tr>
            <tr><td class="sd-section-title" style="padding:14px 28px;background:{color};">
              <h2 style="margin:0;font:700 16px/1.3 Arial,sans-serif;letter-spacing:.8px;text-transform:uppercase;color:#ffffff;">{escape(category)}</h2>
            </td></tr>
            <tr><td class="sd-section-body" style="padding:0 28px 6px;background:#ffffff;">
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
<html lang="it"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>SiracusaDaily</title>
<style>
@media only screen and (max-width:480px) {{
  .sd-outer {{ padding-left:8px !important; padding-right:8px !important; }}
  .sd-container {{ width:100% !important; max-width:100% !important; table-layout:fixed !important; }}
  .sd-header {{ padding:30px 20px 18px !important; }}
  .sd-section-title {{ padding:13px 20px !important; }}
  .sd-section-body {{ padding-left:20px !important; padding-right:20px !important; }}
  .sd-card {{ padding:20px 0 !important; }}
  .sd-title {{ font-size:20px !important; line-height:1.3 !important; overflow-wrap:anywhere !important; }}
  .sd-summary {{ font-size:16px !important; line-height:1.6 !important; overflow-wrap:anywhere !important; }}
  .sd-link {{ overflow-wrap:anywhere !important; }}
  .sd-footer {{ padding-left:20px !important; padding-right:20px !important; }}
}}
</style></head>
<body style="margin:0;padding:0;background:#ffffff;">
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background:#ffffff;"><tr><td class="sd-outer" align="center" style="padding:0 12px 28px;">
  <table class="sd-container" role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="width:100%;max-width:640px;table-layout:fixed;background:#ffffff;">
    <tr><td class="sd-header" align="center" style="padding:36px 28px 22px;background:#ffffff;color:#000000;">
      <h1 style="margin:0;font:italic 700 38px/1.1 Georgia,'Times New Roman',serif;color:#000000;letter-spacing:-.5px;">SiracusaDaily</h1>
      <p style="margin:9px 0 0;font:13px/1.45 Arial,sans-serif;color:#64748b;">Edizione del {edition_date:%d/%m/%Y}</p>
    </td></tr>
    {''.join(sections)}
    <tr><td class="sd-footer" style="padding:24px 28px 28px;border-top:1px solid #e5e7eb;text-align:center;background:#ffffff;font:12px/1.65 Arial,sans-serif;color:#64748b;">{footer}{unsubscribe}</td></tr>
  </table>
</td></tr></table></body></html>'''


def save_html(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
