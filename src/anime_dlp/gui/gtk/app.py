import sys
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gdk, Gtk

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


def _on_shutdown(_app):
    episodes.cancel_all()
    # Плеер импортируется лениво (нужен GStreamer) — останавливаем, только
    # если его вообще открывали: заодно он сохранит позицию просмотра.
    player_page = sys.modules.get("anime_dlp.gui.gtk.player_page")
    if player_page is not None:
        player_page.stop_all()


def run_gui(download_dir: Path) -> int:
    app = Adw.Application(application_id="io.github.alttux.AnimeDlp")

    def on_activate(app):
        provider = Gtk.CssProvider()
        provider.load_from_string(_APP_CSS)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )
        win = AnimeDlpWindow(application=app, download_dir=download_dir)
        win.present()

    app.connect("activate", on_activate)
    # Потоки скачивания — daemon и умрут вместе с процессом, а вот запущенный
    # ими ffmpeg (HLS) — нет: просим всё остановиться заранее.
    app.connect("shutdown", _on_shutdown)
    return app.run(None)
