from gi.repository import Adw, Gtk

from anime_dlp import about


def _credits() -> list[str]:
    # Adw показывает элементы вида "Название URL" ссылками.
    return [f"{name} {url}" for name, url, _ in about.LIBRARIES]


def show_about_dialog(window):
    """Открывает стандартное окно «О программе».

    Adw.AboutDialog появился в libadwaita 1.5; в более старых рантаймах
    (Flatpak/Homebrew) остаётся Adw.AboutWindow с тем же набором свойств,
    но другим способом показа.
    """
    use_dialog = hasattr(Adw, "AboutDialog")
    cls = Adw.AboutDialog if use_dialog else Adw.AboutWindow

    dialog = cls(
        application_name=about.APP_NAME,
        application_icon=about.APP_ID,
        developer_name=about.DEVELOPER,
        version=about.VERSION,
        comments=about.SUMMARY,
        website=about.WEBSITE,
        issue_url=about.ISSUE_URL,
        license_type=Gtk.License.MIT_X11,
    )
    dialog.add_credit_section("Библиотеки", _credits())

    if use_dialog:
        dialog.present(window)
    else:
        dialog.set_transient_for(window)
        dialog.present()
