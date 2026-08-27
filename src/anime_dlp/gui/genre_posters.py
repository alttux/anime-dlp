"""Статичные обложки жанров, сгенерированные нейросетью (NanoBanana) —
промпты лежат в genre-posters-prompts/ в корне репозитория. В отличие от
обложек аниме, эти постеры не качаются по сети и не кэшируются на диск:
они — часть пакета (src/anime_dlp/gui/assets/genre_posters/) и попадают во
Flatpak через package-data в pyproject.toml, а в сборки PyInstaller
(macOS/Windows) — через --add-data (см. packaging/macos/build.sh и
.github/workflows/windows-build.yml)."""

from functools import lru_cache
from importlib import resources

_ASSETS_DIR = resources.files("anime_dlp.gui") / "assets" / "genre_posters"

# Жанр (anime_service.GENRES) -> имя файла обложки. Имена файлов — латиница,
# чтобы не зависеть от того, как конкретный build-инструмент на конкретной
# платформе обращается с не-ASCII путями при упаковке.
_POSTER_FILES: dict[str, str] = {
    "Военное": "voennoe.jpg",
    "Драма": "drama.jpg",
    "Исторический": "istoricheskiy.jpg",
    "Экшен": "ekshen.jpg",
    "Приключения": "priklyucheniya.jpg",
    "Сёнен": "shonen.jpg",
    "Фэнтези": "fentezi.jpg",
    "Комедия": "komediya.jpg",
    "Боевые искусства": "boevye-iskusstva.jpg",
    "Романтика": "romantika.jpg",
    "Психологическое": "psihologicheskoe.jpg",
    "Триллер": "triller.jpg",
    "Повседневность": "povsednevnost.jpg",
    "Сверхъестественное": "sverhestestvennoe.jpg",
    "Спорт": "sport.jpg",
    "Школа": "shkola.jpg",
    "Музыка": "muzyka.jpg",
    "Фантастика": "fantastika.jpg",
    "Самураи": "samurai.jpg",
}


@lru_cache(maxsize=None)
def get_genre_poster(genre: str) -> bytes:
    """Возвращает байты JPEG-обложки жанра. Кэшируется в памяти процесса —
    файлы маленькие (~30 КБ), а читаются на каждое открытие «Категорий»."""
    filename = _POSTER_FILES[genre]
    return (_ASSETS_DIR / filename).read_bytes()
