import threading

from gi.repository import Gdk, GdkPixbuf, Gio, GLib, Gtk, Pango

from anime_dlp.core.anime_info import extract_anime_info
from anime_dlp.core.cache import fetch_image_cached

_WIDTH = 140
_HEIGHT = 200


class CoverCard(Gtk.Button):
    """Обложка + подпись. item=None и title=... — карточка без записи аниме
    (так сделаны карточки жанров в «Категориях»): подпись показывается сразу,
    а обложка привязывается позже через set_item(), когда её найдут в фоне."""

    def __init__(self, item: dict | None, on_click, title: str | None = None):
        super().__init__(css_classes=["flat"], halign=Gtk.Align.START)
        self._item = item
        self._on_click = on_click
        self.connect("clicked", lambda *_: self._on_click(self._item))

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, width_request=_WIDTH)

        self.picture = Gtk.Picture(content_fit=Gtk.ContentFit.COVER, can_shrink=True)
        self.picture.set_size_request(_WIDTH, _HEIGHT)
        self.picture.add_css_class("card")
        self.picture.add_css_class("rounded-poster")
        self.picture.set_overflow(Gtk.Overflow.HIDDEN)
        box.append(self.picture)

        title_label = Gtk.Label(
            label=title or (item or {}).get("title", "Unknown"),
            wrap=True,
            lines=2,
            ellipsize=Pango.EllipsizeMode.END,
            justify=Gtk.Justification.CENTER,
            max_width_chars=16,
        )
        box.append(title_label)
        self.set_child(box)

        if item is not None:
            self._start_poster_load()

    def set_item(self, item: dict):
        """Привязывает запись аниме к уже показанной карточке и подгружает
        её обложку."""
        self._item = item
        self._start_poster_load()

    def _start_poster_load(self):
        poster_url = extract_anime_info(self._item).poster_url
        if poster_url:
            threading.Thread(target=self._load_poster, args=(poster_url,), daemon=True).start()

    def _load_poster(self, url: str):
        try:
            data = fetch_image_cached(url)
        except Exception:
            return
        GLib.idle_add(self._on_poster_loaded, data)

    def _on_poster_loaded(self, data: bytes):
        # Обрезаем/масштабируем постер до фиксированного размера карточки
        # заранее: GtkPicture иначе сообщает исходное разрешение постера как
        # свой natural size (даже с can_shrink=True), из-за чего
        # Gtk.FlowBox с homogeneous=True неверно считает ширину колонки.
        try:
            pixbuf = GdkPixbuf.Pixbuf.new_from_stream(
                Gio.MemoryInputStream.new_from_bytes(GLib.Bytes.new(data))
            )
        except GLib.Error:
            return GLib.SOURCE_REMOVE

        src_w, src_h = pixbuf.get_width(), pixbuf.get_height()
        scale = max(_WIDTH / src_w, _HEIGHT / src_h)
        scaled_w, scaled_h = round(src_w * scale), round(src_h * scale)
        scaled = pixbuf.scale_simple(scaled_w, scaled_h, GdkPixbuf.InterpType.BILINEAR)
        x_off = (scaled_w - _WIDTH) // 2
        y_off = (scaled_h - _HEIGHT) // 2
        cropped = scaled.new_subpixbuf(x_off, y_off, _WIDTH, _HEIGHT)

        self.picture.set_paintable(Gdk.Texture.new_for_pixbuf(cropped))
        return GLib.SOURCE_REMOVE
