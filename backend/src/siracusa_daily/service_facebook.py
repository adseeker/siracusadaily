from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .editorial import EditorialItem
from .facebook import DEFAULT_SIGNUP_URL
from .models import Source, StoryCluster
from .service_updates import is_service_alert


SERVICE_ITEM_LIMIT = 5


class ServiceOutputError(RuntimeError):
    pass


@dataclass(frozen=True)
class ServiceOutputs:
    post: str
    sources: str
    item_count: int


def _clean(value: str) -> str:
    return " ".join(value.replace("—", "-").split())


def render_service_outputs(
    clusters: list[StoryCluster], sources: dict[str, Source],
    editorial_items: list[EditorialItem], *, limit: int = SERVICE_ITEM_LIMIT,
    signup_url: str = DEFAULT_SIGNUP_URL,
) -> ServiceOutputs:
    if not 1 <= limit <= SERVICE_ITEM_LIMIT:
        raise ServiceOutputError(
            f"gli aggiornamenti utili devono contenere da 1 a {SERVICE_ITEM_LIMIT} elementi"
        )
    editorial_by_id = {item.candidate_id: item for item in editorial_items}
    selected = [
        cluster for cluster in clusters
        if is_service_alert(cluster.representative) and cluster.key in editorial_by_id
    ][:limit]
    if not selected:
        raise ServiceOutputError("nessun aggiornamento operativo valido disponibile")

    post_lines = ["SIRACUSA, GLI AGGIORNAMENTI UTILI", ""]
    source_lines = ["FONTI E DETTAGLI", ""]
    for index, cluster in enumerate(selected, 1):
        article = cluster.representative
        editorial = editorial_by_id[cluster.key]
        source = sources.get(article.source_id)
        if source is None:
            raise ServiceOutputError(f"fonte {article.source_id} non disponibile per {cluster.key}")
        post_lines.extend([
            f"{index}. {_clean(editorial.headline)}",
            _clean(editorial.summary),
            f"Fonte: {_clean(source.name)}",
            "",
        ])
        source_lines.extend([
            f"{index}. {_clean(source.name)}",
            article.url,
            "",
        ])

    post_lines.extend([
        "Ricevi ogni mattina la selezione completa di SiracusaDaily direttamente via email.",
        "Il link gratuito è nel primo commento.",
    ])
    source_lines.extend(["ISCRIVITI A SIRACUSADAILY", signup_url])
    return ServiceOutputs(
        post="\n".join(post_lines).strip() + "\n",
        sources="\n".join(source_lines).strip() + "\n",
        item_count=len(selected),
    )


def save_service_outputs(directory: Path, outputs: ServiceOutputs) -> tuple[Path, Path]:
    directory.mkdir(parents=True, exist_ok=True)
    post_path = directory / "facebook_service_updates_post.txt"
    sources_path = directory / "facebook_service_updates_sources.txt"
    post_path.write_text(outputs.post, encoding="utf-8")
    sources_path.write_text(outputs.sources, encoding="utf-8")
    return post_path, sources_path
