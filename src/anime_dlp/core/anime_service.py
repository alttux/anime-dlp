import json
import threading

from anime_parsers_ru import KodikList, KodikParser, errors
from anime_parsers_ru.api_kodik import Api

from anime_dlp.core import cache
from anime_dlp.core.token_manager import load_token, save_token


def _clean_surrogates(text: str) -> str:
    return "".join(c if not "\uD800" <= c <= "\uDFFF" else "?" for c in text)


def _dedupe_by_anime(items: list[dict]) -> list[dict]:
    """Kodik часто отдаёт несколько записей (разные переводы/источники) для
    одного и того же аниме — оставляем по одной записи на shikimori_id/
    kinopoisk_id/imdb_id."""
    seen = {}
    for item in items:
        key = (
            item.get("shikimori_id")
            or item.get("kinopoisk_id")
            or item.get("imdb_id")
            or item["link"]
        )
        if key not in seen:
            seen[key] = item
    return list(seen.values())


_parser: KodikParser | None = None
_parser_lock = threading.Lock()


def _get_parser() -> KodikParser:
    """Парсер кэшируется на уровне процесса: с validate_token=True каждое
    создание KodikParser делает 5 доп. запросов к Kodik, а фоновая
    предзагрузка (gui/prefetch.py) вызывает _get_parser() десятки раз подряд
    — пересоздание парсера на каждый вызов умножило бы число запросов."""
    global _parser
    with _parser_lock:
        if _parser is None:
            token = load_token()
            _parser = KodikParser(token=token, validate_token=token is not None)
            if _parser.TOKEN and _parser.TOKEN != token:
                save_token(_parser.TOKEN)
        return _parser


def reset_parser() -> None:
    """Сбрасывает закэшированный парсер — следующий вызов создаст новый и
    заново получит токен. Нужен кнопке «Обновить» в GUI, которая удаляет
    сохранённый токен вместе с кэшем."""
    global _parser
    with _parser_lock:
        _parser = None


def search_anime(title: str) -> list[dict]:
    title = _clean_surrogates(title)
    cache_key = f"search:{title.strip().lower()}"
    cached = cache.get_cached_json(cache_key)
    if cached is not None:
        return cached

    parser = _get_parser()
    results = parser.search(
        title=title,
        include_material_data=True,
        only_anime=True,
        strict=False,
    )
    deduped = _dedupe_by_anime(results)
    cache.store_json(cache_key, deduped)
    return deduped


def get_anime_info(shikimori_id: str) -> dict:
    cache_key = f"info:{shikimori_id}"
    cached = cache.get_cached_json(cache_key)
    if cached is not None:
        return cached

    parser = _get_parser()
    info = parser.get_info(id=shikimori_id, id_type="shikimori")
    cache.store_json(cache_key, info)
    return info


_POPULAR_PAGE_LIMIT = 100  # максимум, который отдаёт Kodik API за один запрос

# Жанры для раздела «Категории». Берём готовый список из библиотеки, чтобы
# ничего не хардкодить: это те же русские строки, что Kodik кладёт в
# material_data["anime_genres"] и что GUI показывает бейджами на странице
# аниме — значит, фильтр и отображение всегда согласованы.
GENRES: list[str] = Api.AnimeGenres.get_list()


def _list_anime(
    cache_prefix: str,
    genre: str | None,
    cursor: str | None,
    limit: int,
) -> tuple[list[dict], str | None]:
    """Возвращает (items, next_cursor). Чтобы получить следующую страницу
    ("Прогрузить ещё"), передайте next_cursor из предыдущего вызова обратно
    как cursor.

    Kodik отдаёт список отсортированным по рейтингу, но одному аниме может
    соответствовать много подряд идущих записей (разные переводы/источники),
    поэтому сырые страницы буферизуются и дедуплицируются, пока не наберётся
    нужное количество уникальных тайтлов — иначе "Прогрузить ещё" почти не
    добавляло бы новых обложек. cursor — непрозрачная JSON-строка с остатком
    буфера и ссылкой на следующую сырую страницу.
    """
    cache_key = f"{cache_prefix}:{cursor or 'first'}:{limit}"
    cached = cache.get_cached_json(cache_key)
    if cached is not None:
        return cached["items"], cached["next_cursor"]

    if cursor:
        state = json.loads(cursor)
        link: str | None = state.get("link")
        buffer: list[dict] = state.get("buffer", [])
        made_initial_request = True
    else:
        link = None
        buffer = []
        made_initial_request = False

    parser = _get_parser()
    unique = _dedupe_by_anime(buffer)
    while len(unique) < limit:
        # allow_warnings=False: при неизвестном жанре билдер печатает
        # предупреждение прямо в stdout, а мы вызываемся из фонового потока
        # GUI и из-под rich-прогрессбара в CLI.
        #
        # _args={} обязателен: у Api.__init__ в anime_parsers_ru этот параметр
        # объявлен изменяемым значением по умолчанию (_args: dict = {}), то
        # есть один и тот же словарь на весь процесс. Без явного пустого
        # словаря фильтр .anime_genres() из запроса по жанру протекал бы во
        # все последующие запросы — «Главное» показывало бы тайтлы последнего
        # открытого жанра.
        query = KodikList(token=parser.TOKEN, allow_warnings=False, _args={})
        if genre:
            query = query.anime_genres(genre)
        try:
            if link is not None:
                raw = query.api_request(link=link)
            elif not made_initial_request:
                raw = (
                    query.anime_status("released")
                    .sort(Api.Sort.shikimori_rating)
                    .order(Api.Order.desc)
                    .limit(_POPULAR_PAGE_LIMIT)
                    .with_material_data(True)
                    .execute(return_json=True)
                )
                made_initial_request = True
            else:
                break  # больше сырых страниц нет
        except errors.NoResults:
            # Kodik отвечает ошибкой, а не пустым списком, когда под фильтр
            # ничего не подошло (узкий жанр или конец пагинации).
            break
        buffer.extend(raw.get("results", []))
        unique = _dedupe_by_anime(buffer)
        link = raw.get("next_page")

    items = unique[:limit]
    leftover = unique[limit:]
    next_cursor = json.dumps({"link": link, "buffer": leftover}) if (leftover or link) else None

    cache.store_json(cache_key, {"items": items, "next_cursor": next_cursor})
    return items, next_cursor


def get_popular_anime(
    cursor: str | None = None, limit: int = 10
) -> tuple[list[dict], str | None]:
    """Популярное для раздела «Главное» — весь каталог по рейтингу."""
    return _list_anime("popular", None, cursor, limit)


def get_genre_anime(
    genre: str, cursor: str | None = None, limit: int = 10
) -> tuple[list[dict], str | None]:
    """То же самое, но с серверной фильтрацией по жанру (раздел «Категории»)."""
    return _list_anime(f"genre:{genre}", genre, cursor, limit)


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
