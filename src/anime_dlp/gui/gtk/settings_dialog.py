"""Окно / диалог настроек приложения в стиле GNOME / Libadwaita.

Предоставляет:
- выбор темы (системная, светлая, тёмная);
- выбор цветовой палитры (системная, gruvbox, catppuccin, monokai, tokyo night, lgbtq);
- выбор директории для скачивания и переключатель «спрашивать каждый раз»;
- экспорт и импорт всех настроек, конфигураций и избранного со статусами.
"""

from datetime import datetime
from pathlib import Path

from gi.repository import Adw, Gio, GLib, Gtk

from anime_dlp.config import DOWNLOAD_DIR
from anime_dlp.core import settings as app_settings
from anime_dlp.gui.gtk import theme_manager

DialogBase = getattr(Adw, "PreferencesDialog", getattr(Adw, "PreferencesWindow", Adw.Window))

THEME_KEYS = ["system", "light", "dark"]
THEME_NAMES = ["Системная", "Светлая", "Тёмная"]

PALETTE_KEYS = ["system", "gruvbox", "catppuccin", "monokai", "tokyo_night", "lgbtq"]
PALETTE_NAMES = ["Системная", "Gruvbox", "Catppuccin", "Monokai", "Tokyo Night", "LGBTQ"]


class SettingsDialog(DialogBase):
    def __init__(self, window):
        super().__init__()
        self.window = window
        self.set_title("Настройки")
        if hasattr(self, "set_transient_for"):
            self.set_transient_for(window)

        self._syncing = False

        page = Adw.PreferencesPage()

        # --- 1. Внешний вид ---
        appearance_group = Adw.PreferencesGroup(
            title="Внешний вид",
            description="Оформление интерфейса и цветовые схемы",
        )

        # Тема
        self.theme_combo = Adw.ComboRow(title="Тема оформления")
        theme_model = Gtk.StringList()
        for name in THEME_NAMES:
            theme_model.append(name)
        self.theme_combo.set_model(theme_model)
        self.theme_combo.connect("notify::selected", self._on_theme_changed)
        appearance_group.add(self.theme_combo)

        # Цветовая палитра
        self.palette_combo = Adw.ComboRow(
            title="Цветовая палитра",
            subtitle="Каждая палитра адаптируется под светлый и тёмный режимы",
        )
        palette_model = Gtk.StringList()
        for name in PALETTE_NAMES:
            palette_model.append(name)
        self.palette_combo.set_model(palette_model)
        self.palette_combo.connect("notify::selected", self._on_palette_changed)
        appearance_group.add(self.palette_combo)

        page.add(appearance_group)

        # --- 2. Загрузки ---
        downloads_group = Adw.PreferencesGroup(
            title="Загрузки",
            description="Параметры сохранения видеофайлов",
        )

        self.folder_row = Adw.ActionRow(
            title="Папка для скачивания",
            subtitle=str(DOWNLOAD_DIR),
        )

        choose_folder_btn = Gtk.Button(
            icon_name="folder-open-symbolic",
            tooltip_text="Выбрать папку",
            valign=Gtk.Align.CENTER,
            css_classes=["flat"],
        )
        choose_folder_btn.connect("clicked", self._on_choose_folder_clicked)
        self.folder_row.add_suffix(choose_folder_btn)

        reset_folder_btn = Gtk.Button(
            icon_name="edit-clear-symbolic",
            tooltip_text="Сбросить по умолчанию",
            valign=Gtk.Align.CENTER,
            css_classes=["flat"],
        )
        reset_folder_btn.connect("clicked", self._on_reset_folder_clicked)
        self.folder_row.add_suffix(reset_folder_btn)

        downloads_group.add(self.folder_row)

        self.ask_folder_switch = Adw.SwitchRow(
            title="Спрашивать папку каждый раз",
            subtitle="Запрашивать папку перед каждым скачиванием серии или сезона",
        )
        self.ask_folder_switch.connect("notify::active", self._on_ask_folder_changed)
        downloads_group.add(self.ask_folder_switch)

        page.add(downloads_group)

        # --- 3. Резервное копирование ---
        backup_group = Adw.PreferencesGroup(
            title="Резервное копирование",
            description="Экспорт и импорт настроек, избранного и истории",
        )

        export_row = Adw.ActionRow(
            title="Экспорт настроек и данных",
            subtitle="Сохранить настройки, избранное по статусам и историю в файл",
        )
        export_btn = Gtk.Button(
            label="Экспорт…",
            icon_name="document-save-symbolic",
            valign=Gtk.Align.CENTER,
            css_classes=["pill"],
        )
        export_btn.connect("clicked", self._on_export_clicked)
        export_row.add_suffix(export_btn)
        backup_group.add(export_row)

        import_row = Adw.ActionRow(
            title="Импорт настроек и данных",
            subtitle="Восстановить настройки, избранное и историю из файла",
        )
        import_btn = Gtk.Button(
            label="Импорт…",
            icon_name="document-open-symbolic",
            valign=Gtk.Align.CENTER,
            css_classes=["pill"],
        )
        import_btn.connect("clicked", self._on_import_clicked)
        import_row.add_suffix(import_btn)
        backup_group.add(import_row)

        page.add(backup_group)

        self.add(page)
        self._sync_controls()

    def _sync_controls(self):
        self._syncing = True
        settings = app_settings.load_settings()

        # Тема
        theme = settings.get("theme", "system")
        if theme in THEME_KEYS:
            self.theme_combo.set_selected(THEME_KEYS.index(theme))

        # Палитра
        palette = settings.get("palette", "system")
        if palette in PALETTE_KEYS:
            self.palette_combo.set_selected(PALETTE_KEYS.index(palette))

        # Папка
        download_dir = settings.get("download_dir", str(DOWNLOAD_DIR))
        self.folder_row.set_subtitle(str(download_dir))

        # Галочка
        ask = settings.get("ask_download_folder", True)
        self.ask_folder_switch.set_active(bool(ask))

        self._syncing = False

    def _on_theme_changed(self, combo, _pspec):
        if self._syncing:
            return
        idx = combo.get_selected()
        if idx != Gtk.INVALID_LIST_POSITION and idx < len(THEME_KEYS):
            key = THEME_KEYS[idx]
            app_settings.set_setting("theme", key)
            theme_manager.apply_theme(key)

    def _on_palette_changed(self, combo, _pspec):
        if self._syncing:
            return
        idx = combo.get_selected()
        if idx != Gtk.INVALID_LIST_POSITION and idx < len(PALETTE_KEYS):
            key = PALETTE_KEYS[idx]
            app_settings.set_setting("palette", key)
            theme_manager.apply_palette(key)

    def _on_ask_folder_changed(self, switch, _pspec):
        if self._syncing:
            return
        app_settings.set_setting("ask_download_folder", switch.get_active())

    def _on_choose_folder_clicked(self, _button):
        dialog = Gtk.FileDialog(title="Выберите папку для скачивания")
        current_dir = app_settings.get_setting("download_dir", str(DOWNLOAD_DIR))
        dialog.set_initial_folder(Gio.File.new_for_path(str(current_dir)))
        dialog.select_folder(self.window, None, self._on_folder_selected)

    def _on_folder_selected(self, dialog, result):
        try:
            gfile = dialog.select_folder_finish(result)
        except GLib.Error:
            return
        if gfile is not None:
            path_str = gfile.get_path()
            if path_str:
                app_settings.set_setting("download_dir", path_str)
                self.window.download_dir = Path(path_str)
                self.folder_row.set_subtitle(path_str)
                self.window.show_toast(f"Папка загрузки: {path_str}")

    def _on_reset_folder_clicked(self, _button):
        default_str = str(DOWNLOAD_DIR)
        app_settings.set_setting("download_dir", default_str)
        self.window.download_dir = Path(default_str)
        self.folder_row.set_subtitle(default_str)
        self.window.show_toast("Папка загрузок сброшена по умолчанию")

    def _on_export_clicked(self, _button):
        dialog = Gtk.FileDialog(title="Экспорт настроек и данных")
        date_str = datetime.now().strftime("%Y%m%d")
        dialog.set_initial_name(f"anime-dlp-backup-{date_str}.json")
        dialog.save(self.window, None, self._on_export_finished)

    def _on_export_finished(self, dialog, result):
        try:
            gfile = dialog.save_finish(result)
        except GLib.Error:
            return
        if gfile is not None:
            path = Path(gfile.get_path())
            try:
                app_settings.export_all_data_to_file(path)
                self.window.show_toast(f"Данные успешно экспортированы в {path.name}")
            except Exception as exc:
                self.window.show_toast(f"Ошибка экспорта: {exc}")

    def _on_import_clicked(self, _button):
        dialog = Gtk.FileDialog(title="Импорт настроек и данных")
        dialog.open(self.window, None, self._on_import_finished)

    def _on_import_finished(self, dialog, result):
        try:
            gfile = dialog.open_finish(result)
        except GLib.Error:
            return
        if gfile is not None:
            path = Path(gfile.get_path())
            try:
                ok = app_settings.import_all_data_from_file(path)
                if ok:
                    self._sync_controls()
                    theme_manager.init_theme()
                    self.window.download_dir = Path(
                        app_settings.get_setting("download_dir", str(DOWNLOAD_DIR))
                    )
                    if hasattr(self.window, "home_page") and hasattr(
                        self.window.home_page, "favorites_tab"
                    ):
                        self.window.home_page.favorites_tab.reload()
                    self.window.show_toast("Настройки и данные успешно импортированы")
                else:
                    self.window.show_toast("Ошибка: не удалось прочитать файл резервной копии")
            except Exception as exc:
                self.window.show_toast(f"Ошибка импорта: {exc}")


def show_settings_dialog(window):
    dialog = SettingsDialog(window)
    dialog.present(window)
