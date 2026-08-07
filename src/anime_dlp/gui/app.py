from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw

from anime_dlp.gui.window import AnimeDlpWindow


def run_gui(download_dir: Path) -> int:
    app = Adw.Application(application_id="io.github.alttux.AnimeDlp")

    def on_activate(app):
        win = AnimeDlpWindow(application=app, download_dir=download_dir)
        win.present()

    app.connect("activate", on_activate)
    return app.run(None)
