"""Сведения о программе — единый источник для CLI (`--about`) и диалогов
«О программе» в обоих GUI-бэкендах.

Версия берётся только из anime_dlp.__version__ (метаданные установленного
пакета): её единственный статический источник — pyproject.toml, который в CI
правит scripts/bump_version.py, поэтому здесь её дублировать нельзя.
"""

from anime_dlp import __version__

APP_NAME = "Anime Downloader"
APP_ID = "io.github.alttux.AnimeDlp"
VERSION = __version__
SUMMARY = "Скачивание аниме с плеера Kodik"
DEVELOPER = "alttux"

WEBSITE = "https://github.com/alttux/anime-dlp"
ISSUE_URL = f"{WEBSITE}/issues"

LICENSE_NAME = "MIT"
LICENSE_URL = f"{WEBSITE}/blob/main/LICENSE.txt"

# (название, ссылка, назначение)
LIBRARIES: list[tuple[str, str, str]] = [
    (
        "anime-parsers-ru",
        "https://github.com/YaNesyTortiK/AnimeParsers",
        "поиск аниме и получение ссылок на видео с Kodik",
    ),
    (
        "rich",
        "https://github.com/Textualize/rich",
        "оформление консольного интерфейса, таблицы и прогресс-бары",
    ),
    (
        "requests",
        "https://docs.python-requests.org/",
        "HTTP-запросы и многопоточное скачивание",
    ),
    (
        "beautifulsoup4",
        "https://www.crummy.com/software/BeautifulSoup/",
        "разбор HTML-страниц плеера",
    ),
    (
        "PyGObject + GTK4/libadwaita",
        "https://pygobject.gnome.org/",
        "графический интерфейс на Linux и macOS",
    ),
    (
        "PyQt6",
        "https://pypi.org/project/PyQt6/",
        "графический интерфейс на Windows",
    ),
]
