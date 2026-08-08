from dataclasses import dataclass

from anime_dlp.labels import STATUS_MAP


@dataclass
class AnimeInfo:
    description: str | None
    genres: list[str]
    studios: list[str]
    status: str | None
    score: float | None
    votes: int | None
    episodes_total: int | None
    episodes_aired: int | None
    poster_url: str | None


def _first_text(material: dict, *keys: str) -> str | None:
    for key in keys:
        value = material.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _first_list(material: dict, *keys: str) -> list[str]:
    for key in keys:
        value = material.get(key)
        if isinstance(value, list) and value:
            return [str(v) for v in value if v]
    return []


def _to_float(value) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result or None


def _to_int(value) -> int | None:
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result or None


def extract_anime_info(item: dict) -> AnimeInfo:
    material = item.get("material_data") or {}

    description = _first_text(material, "anime_description", "description")
    genres = _first_list(material, "anime_genres", "genres", "all_genres")
    studios = _first_list(material, "anime_studios")

    raw_status = material.get("anime_status")
    status = STATUS_MAP.get(raw_status, raw_status) if raw_status else None

    score = _to_float(material.get("shikimori_rating"))
    votes = _to_int(material.get("shikimori_votes")) if score is not None else None

    episodes_total = _to_int(material.get("episodes_total"))
    episodes_aired = _to_int(material.get("episodes_aired"))

    poster_url = _first_text(material, "anime_poster_url", "poster_url")

    return AnimeInfo(
        description=description,
        genres=genres,
        studios=studios,
        status=status,
        score=score,
        votes=votes,
        episodes_total=episodes_total,
        episodes_aired=episodes_aired,
        poster_url=poster_url,
    )


def has_any_info(info: AnimeInfo) -> bool:
    return bool(
        info.description
        or info.genres
        or info.studios
        or info.status
        or info.score
        or info.episodes_total
        or info.episodes_aired
    )
