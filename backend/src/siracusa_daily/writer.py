from __future__ import annotations

from datetime import date, datetime
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

CATEGORY_LABELS = {
    "Eventi": "I prossimi eventi",
}

# Link tracciato usato dai CTA di referral interni alla newsletter (viral loop).
DEFAULT_SIGNUP_URL = (
    "https://siracusadaily.com/"
    "?utm_source=newsletter&utm_medium=forward&utm_campaign=viral_loop"
)

WEEKDAYS = ("lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica")
MONTHS = (
    "gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
    "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre",
)


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
        lines.extend([f"## {CATEGORY_LABELS.get(category, category)}", ""])
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


def _metadata_date(article) -> datetime:
    reference_date = article.metadata.get("reference_date")
    display_date = article.published_at
    if reference_date:
        try:
            display_date = datetime.fromisoformat(reference_date)
        except ValueError:
            pass
    if display_date.tzinfo:
        display_date = display_date.astimezone(ZoneInfo("Europe/Rome"))
    return display_date


def _long_date(value: datetime, include_time: bool = True) -> str:
    label = f"{WEEKDAYS[value.weekday()]} {value.day} {MONTHS[value.month - 1]}"
    if include_time and (value.hour or value.minute):
        label += f" · {value:%H:%M}"
    return label


def _event_badge(article, edition_date: date, color: str) -> str:
    if article.metadata.get("date_label", "Pubblicato") not in {"Inizio", "Data"}:
        return ""
    display_date = _metadata_date(article)
    label = _long_date(display_date)
    event_end = article.metadata.get("event_end")
    if display_date.date() < edition_date and event_end:
        try:
            end = datetime.fromisoformat(event_end)
            if end.tzinfo:
                end = end.astimezone(ZoneInfo("Europe/Rome"))
            label = f"Fino a {_long_date(end)}"
        except ValueError:
            pass
    return f'''<table role="presentation" cellspacing="0" cellpadding="0" border="0" style="margin:0 0 13px;">
      <tr><td style="padding:7px 10px;background:#fff3ed;border-left:4px solid {color};font:700 13px/1.25 Arial,sans-serif;letter-spacing:.45px;text-transform:uppercase;color:#9a3412;">{escape(label)}</td></tr>
    </table>'''


def _opportunity_badge(article, edition_date: date, color: str) -> str:
    if article.metadata.get("date_label") != "Scadenza":
        return ""
    deadline = _metadata_date(article)
    remaining_days = (deadline.date() - edition_date).days
    if remaining_days == 0:
        deadline_label = "Scade oggi"
    elif remaining_days == 1:
        deadline_label = "Scade domani"
    else:
        deadline_label = f"Scadenza {deadline.day} {MONTHS[deadline.month - 1]}"
    urgent = 0 <= remaining_days <= 3
    urgent_cell = (
        f'<td style="padding:7px 10px;background:{color};font:700 12px/1.25 Arial,sans-serif;'
        'letter-spacing:.55px;text-transform:uppercase;color:#ffffff;">In scadenza</td>'
        if urgent else ""
    )
    border = "border:1px solid #e5c77a;border-left:0;" if urgent else f"border-left:4px solid {color};"
    return f'''<table role="presentation" cellspacing="0" cellpadding="0" border="0" style="margin:0 0 13px;">
      <tr>{urgent_cell}<td style="padding:7px 10px;background:#fff8e6;{border}font:700 13px/1.25 Arial,sans-serif;letter-spacing:.35px;text-transform:uppercase;color:#854d0e;">{escape(deadline_label)}</td></tr>
    </table>'''


def _summary_html(article, summary: str) -> str:
    image_url = article.metadata.get("newsletter_image_url", "")
    if not image_url:
        return f'<p class="sd-summary" style="margin:0 0 15px;font:16px/1.65 Arial,sans-serif;color:#46505f;">{escape(summary)}</p>'
    alt = article.metadata.get("newsletter_image_alt") or article.title
    return f'''<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin:0 0 15px;">
      <tr>
        <td class="sd-thumb-cell" width="150" valign="top" style="width:150px;">
          <img class="sd-thumb" src="{escape(image_url, quote=True)}" width="150" height="96" alt="{escape(alt, quote=True)}" style="display:block;width:150px;height:96px;border:0;border-radius:10px;object-fit:cover;">
        </td>
        <td valign="top" style="padding:0 0 0 16px;">
          <p class="sd-summary" style="margin:0;font:16px/1.65 Arial,sans-serif;color:#46505f;">{escape(summary)}</p>
        </td>
      </tr>
    </table>'''


def render_html(
    edition_date: date, clusters: list[StoryCluster], sources: dict[str, Source],
    editorial_items: list[EditorialItem] | None = None, publisher_name: str = "SiracusaDaily",
    publisher_address: str = "", unsubscribe_url: str = "", signup_url: str = "",
) -> str:
    editorial_by_id = {item.candidate_id: item for item in editorial_items or []}
    grouped = {category: [] for category in CATEGORY_ORDER}
    for cluster in clusters:
        grouped.setdefault(cluster.category, []).append(cluster)

    sections: list[str] = []
    for category in CATEGORY_ORDER:
        cards: list[str] = []
        category_clusters = grouped.get(category, [])
        color = CATEGORY_COLORS[category]
        for card_index, cluster in enumerate(category_clusters):
            article = cluster.representative
            source = sources[article.source_id]
            editorial = editorial_by_id.get(cluster.key)
            headline = _display_text(editorial.headline if editorial else article.title)
            summary = _display_text(editorial.summary if editorial else "Notizia locale disponibile nella fonte originale.")
            badge = ""
            if category == "Eventi":
                badge = _event_badge(article, edition_date, color)
            elif category == "Lavoro e opportunità":
                badge = _opportunity_badge(article, edition_date, color)
            title_size = 22 if card_index == 0 else 20
            featured_class = " sd-title-featured" if card_index == 0 else ""
            divider = "border-bottom:1px solid #dbe1e8;" if card_index < len(category_clusters) - 1 else ""
            cards.append(f'''<tr><td class="sd-card" style="padding:26px 0;{divider}">
              {badge}
              <h3 class="sd-title{featured_class}" style="margin:0 0 11px;font:700 {title_size}px/1.3 Arial,sans-serif;color:#172033;">{escape(headline)}</h3>
              {_summary_html(article, summary)}
              <a class="sd-link" href="{escape(article.url, quote=True)}" style="font:700 14px/1.5 Arial,sans-serif;color:#075985;text-decoration:underline;text-decoration-thickness:1px;text-underline-offset:3px;">Approfondisci su {escape(_display_text(source.name))} →</a>
            </td></tr>''')
        if cards:
            sections.append(f'''<tr><td style="height:28px;background:#ffffff;font-size:0;line-height:0;">&nbsp;</td></tr>
            <tr><td class="sd-section-title" style="padding:14px 28px;background:{color};border-radius:14px 14px 0 0;">
              <h2 style="margin:0;font:700 16px/1.3 Arial,sans-serif;letter-spacing:.8px;text-transform:uppercase;color:#ffffff;">{escape(CATEGORY_LABELS.get(category, category))}</h2>
            </td></tr>
            <tr><td class="sd-section-body" style="padding:0 28px 6px;background:#f8fafc;border-right:1px solid #e2e5e9;border-bottom:1px solid #e2e5e9;border-left:1px solid #e2e5e9;border-radius:0 0 14px 14px;">
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">{''.join(cards)}</table>
            </td></tr>''')

    footer_parts = [escape(publisher_name)]
    if publisher_address:
        footer_parts.append(escape(publisher_address))
    footer = " · ".join(footer_parts)
    unsubscribe = ""
    if unsubscribe_url:
        unsubscribe = f'<br><a href="{escape(unsubscribe_url, quote=True)}" style="color:#475569;">Annulla iscrizione</a>'

    # Viral loop interno: un unico blocco in fondo invita l'iscritto a inoltrare
    # l'edizione e chi l'ha ricevuta inoltrata a iscriversi. Il link è tracciato.
    signup_link = escape(signup_url or DEFAULT_SIGNUP_URL, quote=True)
    referral_cta = f'''<tr><td class="sd-forward-bottom" style="padding:22px 28px 0;background:#ffffff;">
      <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0"><tr>
        <td style="padding:18px;background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;text-align:center;font:15px/1.6 Arial,sans-serif;color:#334155;">📩 <strong style="color:#172033;">Ti è stata utile oggi?</strong> Inoltra SiracusaDaily a un siracusano che dovrebbe leggerla.
          <div style="height:1px;line-height:1px;font-size:0;background:#e2e8f0;margin:14px 0;">&nbsp;</div>
          <span style="font:14px/1.55 Arial,sans-serif;color:#475569;">Ti hanno inoltrato questa email? <a href="{signup_link}" style="color:#1d4ed8;font-weight:700;text-decoration:underline;text-underline-offset:2px;">Iscriviti gratis a SiracusaDaily →</a></span></td>
      </tr></table>
    </td></tr>'''

    return f'''<!doctype html>
<html lang="it"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>SiracusaDaily</title>
<style>
@media only screen and (max-width:480px) {{
  .sd-outer {{ padding-left:8px !important; padding-right:8px !important; }}
  .sd-container {{ width:100% !important; max-width:100% !important; table-layout:fixed !important; }}
  .sd-header {{ padding:30px 20px 18px !important; }}
  .sd-section-title {{ padding:13px 20px !important; }}
  .sd-section-body {{ padding-left:20px !important; padding-right:20px !important; }}
  .sd-forward-bottom {{ padding-left:20px !important; padding-right:20px !important; }}
  .sd-card {{ padding:24px 0 !important; }}
  .sd-title {{ font-size:20px !important; line-height:1.3 !important; overflow-wrap:anywhere !important; }}
  .sd-title-featured {{ font-size:22px !important; }}
  .sd-summary {{ font-size:16px !important; line-height:1.62 !important; overflow-wrap:anywhere !important; }}
  .sd-link {{ overflow-wrap:anywhere !important; }}
  .sd-thumb-cell {{ width:118px !important; }}
  .sd-thumb {{ width:118px !important; height:78px !important; }}
  .sd-footer {{ padding-left:20px !important; padding-right:20px !important; }}
}}
</style></head>
<body style="margin:0;padding:0;background:#ffffff;">
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background:#ffffff;"><tr><td class="sd-outer" align="center" style="padding:0 12px 28px;">
  <table class="sd-container" role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="width:100%;max-width:640px;table-layout:fixed;background:#ffffff;">
    <tr><td class="sd-header" align="center" style="padding:36px 28px 22px;background:#ffffff;color:#000000;">
      <h1 style="margin:0;font:italic 700 38px/1.1 Georgia,'Times New Roman',serif;color:#000000;letter-spacing:-.5px;"><span style="display:inline-block;margin-right:9px;font:normal 30px/1 Arial,sans-serif;vertical-align:3px;">🗞️</span>SiracusaDaily</h1>
      <p style="margin:9px 0 0;font:13px/1.45 Arial,sans-serif;color:#64748b;">Edizione del {edition_date:%d/%m/%Y}</p>
    </td></tr>
    {''.join(sections)}
    {referral_cta}
    <tr><td class="sd-footer" style="padding:24px 28px 28px;border-top:1px solid #e5e7eb;text-align:center;background:#ffffff;font:12px/1.65 Arial,sans-serif;color:#64748b;">{footer}{unsubscribe}</td></tr>
  </table>
</td></tr></table></body></html>'''


def save_html(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
