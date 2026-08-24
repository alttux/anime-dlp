"""Полная очистка кэша по кнопке «Обновить» — общая для GTK и Qt.

Кэшей у программы три (дисковый, in-memory предзагрузка и singleton
KodikParser) плюс сохранённый токен Kodik; кнопка «Обновить» должна сбросить
всё сразу, иначе часть данных продолжит отдаваться из памяти. Избранное
(DATA_DIR/favorites.json) кэшем не является и не трогается.
"""

from anime_dlp.core import anime_service, cache, token_manager
from anime_dlp.gui import prefetch


def clear_all_caches() -> None:
    cache.clear_all()
    token_manager.delete_token()
    anime_service.reset_parser()
    prefetch.clear()
