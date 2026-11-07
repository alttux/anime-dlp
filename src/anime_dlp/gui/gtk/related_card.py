"""Карточка связанного аниме под описанием тайтла."""

import threading

from gi.repository import Gdk, GLib, Gtk, Pango

from anime_dlp.core.cache import fetch_image_cached

_WIDTH = 110
_HEIGHT = 155


class RelatedAnimeCard(Gtk.Button):
    def __init__(self, related: dict, on_click):
        super().__init__(css_classes=["flat"], valign=Gtk.Align.START)
        self.related = related
        self._on_click = on_click
        self.connect("clicked", lambda *_: self._on_click(self.related))

        card_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=4, width_request=_WIDTH
        )

        self.picture = Gtk.Picture(content_fit=Gtk.ContentFit.COVER, can_shrink=True)
        self.picture.set_size_request(_WIDTH, _HEIGHT)
        self.picture.add_css_class("card")
        self.picture.add_css_class("rounded-poster")
        self.picture.set_overflow(Gtk.Overflow.HIDDEN)
        card_box.append(self.picture)

        # Тип связи и тип тайтла: например, "Продолжение • TV Сериал"
        relation = (related.get("relation") or "").strip()
        kind = (related.get("type") or "").strip()
        badge_parts = [p for p in (relation, kind) if p]
        if badge_parts:
            badge_label = Gtk.Label(
                label=" • ".join(badge_parts),
                css_classes=["caption", "dim-label"],
                ellipsize=Pango.EllipsizeMode.END,
                justify=Gtk.Justification.CENTER,
                max_width_chars=16,
            )
            card_box.append(badge_label)

        title = related.get("name") or "Anime"
        title_label = Gtk.Label(
            label=title,
            wrap=True,
            lines=2,
            ellipsize=Pango.EllipsizeMode.END,
            justify=Gtk.Justification.CENTER,
            max_width_chars=16,
            tooltip_text=title,
        )
        card_box.append(title_label)

        self.set_child(card_box)

        pic_url = related.get("picture")
        if pic_url:
            threading.Thread(target=self._load_poster, args=(pic_url,), daemon=True).start()

    def _load_poster(self, url: str):
        try:
            data = fetch_image_cached(url)
        except Exception:
            return
        GLib.idle_add(self._on_poster_loaded, data)

    def _on_poster_loaded(self, data: bytes):
        try:
            texture = Gdk.Texture.new_from_bytes(GLib.Bytes.new(data))
            self.picture.set_paintable(texture)
        except GLib.Error:
            pass
        return GLib.SOURCE_REMOVE
