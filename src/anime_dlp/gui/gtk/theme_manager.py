"""Управление темами оформления (светлая/тёмная/системная) и цветовыми палитрами GTK4.

Поддерживает палитры:
- Системная (стандартная Adwaita)
- Gruvbox (тёмный и светлый режимы)
- Catppuccin (Mocha для тёмного, Latte для светлого)
- Monokai (тёмный и светлый)
- Tokyo Night (тёмный и светлый)
- LGBTQ (радужные акценты, тёмный и светлый)

Каждая палитра автоматически адаптируется при переключении между тёмным и светлым режимами.
"""

from gi.repository import Adw, Gdk, Gtk

from anime_dlp.core import settings as app_settings

PALETTES = {
    "system": "Системная",
    "gruvbox": "Gruvbox",
    "catppuccin": "Catppuccin",
    "monokai": "Monokai",
    "tokyo_night": "Tokyo Night",
    "lgbtq": "LGBTQ",
}

THEMES = {
    "system": "Системная",
    "light": "Светлая",
    "dark": "Тёмная",
}

_PALETTE_CSS = {
    "gruvbox": {
        "dark": """
            @define-color accent_color #fe8019;
            @define-color accent_bg_color #fe8019;
            @define-color accent_fg_color #282828;
            @define-color window_bg_color #282828;
            @define-color window_fg_color #ebdbb2;
            @define-color view_bg_color #1d2021;
            @define-color view_fg_color #ebdbb2;
            @define-color headerbar_bg_color #32302f;
            @define-color headerbar_fg_color #ebdbb2;
            @define-color card_bg_color #3c3836;
            @define-color card_fg_color #ebdbb2;
            @define-color dialog_bg_color #282828;
            @define-color dialog_fg_color #ebdbb2;
            @define-color popover_bg_color #3c3836;
            @define-color popover_fg_color #ebdbb2;
        """,
        "light": """
            @define-color accent_color #af3a03;
            @define-color accent_bg_color #af3a03;
            @define-color accent_fg_color #fbf1c7;
            @define-color window_bg_color #fbf1c7;
            @define-color window_fg_color #3c3836;
            @define-color view_bg_color #f9f5d7;
            @define-color view_fg_color #3c3836;
            @define-color headerbar_bg_color #f2e5bc;
            @define-color headerbar_fg_color #3c3836;
            @define-color card_bg_color #ebdbb2;
            @define-color card_fg_color #3c3836;
            @define-color dialog_bg_color #fbf1c7;
            @define-color dialog_fg_color #3c3836;
            @define-color popover_bg_color #ebdbb2;
            @define-color popover_fg_color #3c3836;
        """,
    },
    "catppuccin": {
        "dark": """
            @define-color accent_color #cba6f7;
            @define-color accent_bg_color #cba6f7;
            @define-color accent_fg_color #11111b;
            @define-color window_bg_color #1e1e2e;
            @define-color window_fg_color #cdd6f4;
            @define-color view_bg_color #181825;
            @define-color view_fg_color #cdd6f4;
            @define-color headerbar_bg_color #181825;
            @define-color headerbar_fg_color #cdd6f4;
            @define-color card_bg_color #313244;
            @define-color card_fg_color #cdd6f4;
            @define-color dialog_bg_color #1e1e2e;
            @define-color dialog_fg_color #cdd6f4;
            @define-color popover_bg_color #313244;
            @define-color popover_fg_color #cdd6f4;
        """,
        "light": """
            @define-color accent_color #8839ef;
            @define-color accent_bg_color #8839ef;
            @define-color accent_fg_color #ffffff;
            @define-color window_bg_color #eff1f5;
            @define-color window_fg_color #4c4f69;
            @define-color view_bg_color #e6e9ef;
            @define-color view_fg_color #4c4f69;
            @define-color headerbar_bg_color #e6e9ef;
            @define-color headerbar_fg_color #4c4f69;
            @define-color card_bg_color #ccd0da;
            @define-color card_fg_color #4c4f69;
            @define-color dialog_bg_color #eff1f5;
            @define-color dialog_fg_color #4c4f69;
            @define-color popover_bg_color #ccd0da;
            @define-color popover_fg_color #4c4f69;
        """,
    },
    "monokai": {
        "dark": """
            @define-color accent_color #a6e22e;
            @define-color accent_bg_color #a6e22e;
            @define-color accent_fg_color #272822;
            @define-color window_bg_color #272822;
            @define-color window_fg_color #f8f8f2;
            @define-color view_bg_color #1e1f1c;
            @define-color view_fg_color #f8f8f2;
            @define-color headerbar_bg_color #1e1f1c;
            @define-color headerbar_fg_color #f8f8f2;
            @define-color card_bg_color #3e3d32;
            @define-color card_fg_color #f8f8f2;
            @define-color dialog_bg_color #272822;
            @define-color dialog_fg_color #f8f8f2;
            @define-color popover_bg_color #3e3d32;
            @define-color popover_fg_color #f8f8f2;
        """,
        "light": """
            @define-color accent_color #f92672;
            @define-color accent_bg_color #f92672;
            @define-color accent_fg_color #ffffff;
            @define-color window_bg_color #fafafa;
            @define-color window_fg_color #2d2a2e;
            @define-color view_bg_color #f0f0f0;
            @define-color view_fg_color #2d2a2e;
            @define-color headerbar_bg_color #f0f0f0;
            @define-color headerbar_fg_color #2d2a2e;
            @define-color card_bg_color #e6e6e6;
            @define-color card_fg_color #2d2a2e;
            @define-color dialog_bg_color #fafafa;
            @define-color dialog_fg_color #2d2a2e;
            @define-color popover_bg_color #e6e6e6;
            @define-color popover_fg_color #2d2a2e;
        """,
    },
    "tokyo_night": {
        "dark": """
            @define-color accent_color #7aa2f7;
            @define-color accent_bg_color #7aa2f7;
            @define-color accent_fg_color #15161e;
            @define-color window_bg_color #1a1b26;
            @define-color window_fg_color #c0caf5;
            @define-color view_bg_color #16161e;
            @define-color view_fg_color #c0caf5;
            @define-color headerbar_bg_color #16161e;
            @define-color headerbar_fg_color #c0caf5;
            @define-color card_bg_color #24283b;
            @define-color card_fg_color #c0caf5;
            @define-color dialog_bg_color #1a1b26;
            @define-color dialog_fg_color #c0caf5;
            @define-color popover_bg_color #24283b;
            @define-color popover_fg_color #c0caf5;
        """,
        "light": """
            @define-color accent_color #2e7de9;
            @define-color accent_bg_color #2e7de9;
            @define-color accent_fg_color #ffffff;
            @define-color window_bg_color #e1e2e7;
            @define-color window_fg_color #343b58;
            @define-color view_bg_color #d5d6db;
            @define-color view_fg_color #343b58;
            @define-color headerbar_bg_color #d5d6db;
            @define-color headerbar_fg_color #343b58;
            @define-color card_bg_color #c8ccd6;
            @define-color card_fg_color #343b58;
            @define-color dialog_bg_color #e1e2e7;
            @define-color dialog_fg_color #343b58;
            @define-color popover_bg_color #c8ccd6;
            @define-color popover_fg_color #343b58;
        """,
    },
    "lgbtq": {
        "dark": """
            @define-color accent_color #e55ea0;
            @define-color accent_bg_color #e55ea0;
            @define-color accent_fg_color #ffffff;
            @define-color window_bg_color #1c1926;
            @define-color window_fg_color #f7f4fc;
            @define-color view_bg_color #15121f;
            @define-color view_fg_color #f7f4fc;
            @define-color headerbar_bg_color #241f32;
            @define-color headerbar_fg_color #f7f4fc;
            @define-color card_bg_color #2e283f;
            @define-color card_fg_color #f7f4fc;
            @define-color dialog_bg_color #1c1926;
            @define-color dialog_fg_color #f7f4fc;
            @define-color popover_bg_color #2e283f;
            @define-color popover_fg_color #f7f4fc;

            button.suggested-action {
                background-image: linear-gradient(90deg, #e40303, #ff8c00, #ffed00, #008026, #24408e, #732982);
                color: #ffffff;
            }
        """,
        "light": """
            @define-color accent_color #d02476;
            @define-color accent_bg_color #d02476;
            @define-color accent_fg_color #ffffff;
            @define-color window_bg_color #fbf9fd;
            @define-color window_fg_color #271e33;
            @define-color view_bg_color #f3eef8;
            @define-color view_fg_color #271e33;
            @define-color headerbar_bg_color #f3eef8;
            @define-color headerbar_fg_color #271e33;
            @define-color card_bg_color #e9e0f3;
            @define-color card_fg_color #271e33;
            @define-color dialog_bg_color #fbf9fd;
            @define-color dialog_fg_color #271e33;
            @define-color popover_bg_color #e9e0f3;
            @define-color popover_fg_color #271e33;

            button.suggested-action {
                background-image: linear-gradient(90deg, #e40303, #ff8c00, #ffed00, #008026, #24408e, #732982);
                color: #ffffff;
            }
        """,
    },
}

_current_provider: Gtk.CssProvider | None = None
_current_palette: str = "system"
_connected_dark_listener: bool = False


def _get_active_mode() -> str:
    return "dark" if Adw.StyleManager.get_default().get_dark() else "light"


def apply_theme(theme: str) -> None:
    """Применяет тему: 'system', 'light', 'dark'."""
    style_manager = Adw.StyleManager.get_default()
    if theme == "light":
        style_manager.set_color_scheme(Adw.ColorScheme.FORCE_LIGHT)
    elif theme == "dark":
        style_manager.set_color_scheme(Adw.ColorScheme.FORCE_DARK)
    else:
        style_manager.set_color_scheme(Adw.ColorScheme.DEFAULT)


def apply_palette(palette: str) -> None:
    """Применяет цветовую схему к дисплею GTK."""
    global _current_provider, _current_palette
    _current_palette = palette

    display = Gdk.Display.get_default()
    if not display:
        return

    # Снимаем старый провайдер стиля, если был
    if _current_provider is not None:
        Gtk.StyleContext.remove_provider_for_display(display, _current_provider)
        _current_provider = None

    if palette == "system" or palette not in _PALETTE_CSS:
        return

    mode = _get_active_mode()
    css = _PALETTE_CSS[palette].get(mode, "")
    if not css.strip():
        return

    provider = Gtk.CssProvider()
    provider.load_from_string(css)
    Gtk.StyleContext.add_provider_for_display(
        display, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    )
    _current_provider = provider


def _on_dark_changed(*_args) -> None:
    apply_palette(_current_palette)


def init_theme() -> None:
    """Инициализирует тему и палитру при запуске приложения."""
    global _connected_dark_listener
    settings = app_settings.load_settings()
    theme = settings.get("theme", "system")
    palette = settings.get("palette", "system")

    apply_theme(theme)
    apply_palette(palette)

    if not _connected_dark_listener:
        Adw.StyleManager.get_default().connect("notify::dark", _on_dark_changed)
        _connected_dark_listener = True
