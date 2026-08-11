from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .categories import CATEGORY_ORDER
from .editorial import EditorialItem
from .models import Source, StoryCluster


FACEBOOK_CATEGORIES = tuple(CATEGORY_ORDER)
DEFAULT_SIGNUP_URL = (
    "https://siracusadaily.com/"
    "?utm_source=facebook&utm_medium=organic&utm_campaign=recap_giornaliero"
    "#iscriviti"
)


class FacebookOutputError(RuntimeError):
    pass


@dataclass(frozen=True)
class FacebookOutputs:
    post: str
    sources: str
    item_count: int


def _clean(value: str) -> str:
    return " ".join(value.replace("—", "-").split())


def _select_clusters(
    clusters: list[StoryCluster], editorial_by_id: dict[str, EditorialItem], limit: int,
) -> list[StoryCluster]:
    if not 1 <= limit <= 7:
        raise FacebookOutputError("il recap Facebook deve contenere da 1 a 7 elementi")
    eligible = [
        cluster for cluster in clusters
        if cluster.category in FACEBOOK_CATEGORIES and cluster.key in editorial_by_id
    ]
    if not eligible:
        raise FacebookOutputError("nessun contenuto editoriale disponibile per il recap Facebook")

    original_position = {cluster.key: index for index, cluster in enumerate(eligible)}
    selected: list[StoryCluster] = []
    selected_ids: set[str] = set()
    for category in FACEBOOK_CATEGORIES:
        first = next((cluster for cluster in eligible if cluster.category == category), None)
        if first is not None:
            selected.append(first)
            selected_ids.add(first.key)

    remaining = sorted(
        (cluster for cluster in eligible if cluster.key not in selected_ids),
        key=lambda cluster: (-cluster.score, original_position[cluster.key]),
    )
    selected.extend(remaining)
    selected = selected[:limit]
    category_position = {category: index for index, category in enumerate(FACEBOOK_CATEGORIES)}
    return sorted(
        selected,
        key=lambda cluster: (
            category_position[cluster.category],
            original_position[cluster.key],
        ),
    )


def render_facebook_outputs(
    clusters: list[StoryCluster], sources: dict[str, Source],
    editorial_items: list[EditorialItem], *, limit: int = 7,
    signup_url: str = DEFAULT_SIGNUP_URL,
) -> FacebookOutputs:
    editorial_by_id = {item.candidate_id: item for item in editorial_items}
    selected = _select_clusters(clusters, editorial_by_id, limit)

    post_lines = ["SIRACUSA, LE NOTIZIE DI OGGI", ""]
    source_lines = ["FONTI", ""]
    for index, cluster in enumerate(selected, 1):
        article = cluster.representative
        editorial = editorial_by_id[cluster.key]
        source = sources.get(article.source_id)
        if source is None:
            raise FacebookOutputError(
                f"fonte {article.source_id} non disponibile per {cluster.key}"
            )
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
    source_lines.extend([
        "ISCRIVITI A SIRACUSADAILY",
        signup_url,
    ])
    return FacebookOutputs(
        post="\n".join(post_lines).strip() + "\n",
        sources="\n".join(source_lines).strip() + "\n",
        item_count=len(selected),
    )


def save_facebook_outputs(directory: Path, outputs: FacebookOutputs) -> tuple[Path, Path]:
    directory.mkdir(parents=True, exist_ok=True)
    post_path = directory / "facebook_post.txt"
    sources_path = directory / "facebook_sources.txt"
    post_path.write_text(outputs.post, encoding="utf-8")
    sources_path.write_text(outputs.sources, encoding="utf-8")
    return post_path, sources_path
