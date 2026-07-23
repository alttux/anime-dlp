from anime_parsers_ru import KodikParser

from core.token_manager import load_token, save_token


def _clean_surrogates(text: str) -> str:
    return "".join(c if not "\uD800" <= c <= "\uDFFF" else "?" for c in text)


def _get_parser() -> KodikParser:
    token = load_token()
    parser = KodikParser(token=token, validate_token=token is not None)
    if parser.TOKEN and parser.TOKEN != token:
        save_token(parser.TOKEN)
    return parser


def search_anime(title: str) -> list[dict]:
    title = _clean_surrogates(title)
    parser = _get_parser()
    results = parser.search(
        title=title,
        include_material_data=True,
        only_anime=True,
        strict=False,
    )
    seen = {}
    for item in results:
        key = (
            item.get("shikimori_id")
            or item.get("kinopoisk_id")
            or item.get("imdb_id")
            or item["link"]
        )
        if key not in seen:
            seen[key] = item
    return list(seen.values())


def get_anime_info(shikimori_id: str) -> dict:
    parser = _get_parser()
    return parser.get_info(id=shikimori_id, id_type="shikimori")


def get_download_link(
    shikimori_id: str, episode: int, translation_id: str
) -> tuple[str, int, list]:
    parser = _get_parser()
    return parser.get_link(
        id=shikimori_id,
        id_type="shikimori",
        seria_num=episode,
        translation_id=translation_id,
    )
