import sys
from importlib import resources
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gdk, Gtk

from anime_dlp import about
from anime_dlp.core import episodes
from anime_dlp.gui.gtk.window import AnimeDlpWindow

# По умолчанию Gtk.FlowBoxChild сам подсвечивается при наведении/фокусе
# (отдельно от содержимого), из-за чего в Gtk.FlowBox-сетках (обложки на
# «Главном», карточки на странице аниме) подсвечивалась вся ячейка целиком,
# а не сама интерактивная обложка/карточка внутри неё. Убираем встроенную
# подсветку flowboxchild — подсветка при наведении остаётся только у самих
# кликабельных виджетов (например, у CoverCard).
_APP_CSS = """
flowboxchild {
    padding: 0;
}
flowboxchild:hover,
flowboxchild:focus,
flowboxchild:selected {
    background: none;
    box-shadow: none;
    outline: none;
}

.rounded-poster {
    border-radius: 12px;
}

.watched-episode {
    background-color: alpha(@success_color, 0.16);
}

.watched-badge {
    background-color: @success_bg_color;
    color: @success_fg_color;
    border-radius: 999px;
    padding: 4px;
    margin: 6px;
}

.player-video {
    background-color: black;
}

.player-controls {
    border-radius: 12px;
    margin: 12px;
    padding: 8px 12px;
}

.player-panel {
    border-radius: 12px;
    padding: 24px;
}

.player-osd-text {
    color: white;
    font-weight: bold;
    text-shadow: 0 1px 3px black;
}

.pill-badge {
    background-color: alpha(currentColor, 0.1);
    border-radius: 999px;
    padding: 4px 12px;
    font-size: 0.9em;
}
"""


def _setup_icon_theme() -> None:
    display = Gdk.Display.get_default()
    if display is None:
        return
    theme = Gtk.IconTheme.get_for_display(display)

    candidates: list[Path] = []

    # 1. Ресурсы пакета (src/anime_dlp/gui/assets/icons)
    try:
        assets_icons = resources.files("anime_dlp.gui") / "assets" / "icons"
        candidates.append(Path(str(assets_icons)))
    except Exception:
        pass

    # 2. PyInstaller-бандл (sys._MEIPASS)
    if getattr(sys, "frozen", False):
        bundle_root = Path(sys._MEIPASS)
        candidates.extend(
            [
                bundle_root / "anime_dlp" / "gui" / "assets" / "icons",
                bundle_root / "share" / "icons" / "hicolor" / "512x512" / "apps",
                bundle_root / "share" / "icons" / "hicolor" / "scalable" / "apps",
                bundle_root / "share" / "icons",
                bundle_root / "data" / "icons",
            ]
        )

    # 3. Исходный код / репозиторий
    candidates.extend(
        [
            Path(__file__).resolve().parent.parent / "assets" / "icons",
            Path(__file__).resolve().parents[4] / "data" / "icons",
        ]
    )

    current_paths = set(theme.get_search_path())
    for path in candidates:
        if path.is_dir() and str(path) not in current_paths:
            theme.add_search_path(str(path))
            current_paths.add(str(path))

    Gtk.Window.set_default_icon_name(about.APP_ID)


def _on_shutdown(_app):
    episodes.cancel_all()
    # Плеер импортируется лениво (нужен GStreamer) — останавливаем, только
    # если его вообще открывали: заодно он сохранит позицию просмотра.
    player_page = sys.modules.get("anime_dlp.gui.gtk.player_page")
    if player_page is not None:
        player_page.stop_all()


def run_gui(download_dir: Path) -> int:
    app = Adw.Application(application_id=about.APP_ID)

    def on_activate(app):
        _setup_icon_theme()
        provider = Gtk.CssProvider()
        provider.load_from_string(_APP_CSS)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

        from anime_dlp.config import DOWNLOAD_DIR
        from anime_dlp.core import settings as app_settings
        from anime_dlp.gui.gtk import theme_manager

        theme_manager.init_theme()

        saved_dir = app_settings.get_setting("download_dir")
        effective_download_dir = download_dir
        if saved_dir and download_dir == DOWNLOAD_DIR:
            effective_download_dir = Path(saved_dir)

        win = AnimeDlpWindow(application=app, download_dir=effective_download_dir)
        win.present()

    app.connect("activate", on_activate)
    # Потоки скачивания — daemon и умрут вместе с процессом, а вот запущенный
    # ими ffmpeg (HLS) — нет: просим всё остановиться заранее.
    app.connect("shutdown", _on_shutdown)
    return app.run(None)
