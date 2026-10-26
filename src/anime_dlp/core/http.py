"""Общие HTTP-сессии для скачивания видео и обложек.

requests.Session держит пул keep-alive соединений: без неё каждый запрос
(каждый диапазон байт, каждая обложка в сетке) заново проходит TCP + TLS
рукопожатие с CDN. Сессия официально не потокобезопасна, поэтому у каждого
потока своя (threading.local) — потоков у нас ограниченное число (пул
скачивания, предзагрузка, воркеры GUI), так что сессий тоже немного.
"""

import threading

import requests
from requests.adapters import HTTPAdapter

from anime_dlp.config import HEADERS, NUM_THREADS

# (connect, read): без таймаута зависшее соединение с CDN блокирует поток
# скачивания навсегда — с ним запрос падает и уходит на повтор.
TIMEOUT = (10, 30)

_local = threading.local()


def get_session() -> requests.Session:
    session = getattr(_local, "session", None)
    if session is None:
        session = requests.Session()
        session.headers.update(HEADERS)
        adapter = HTTPAdapter(pool_connections=4, pool_maxsize=NUM_THREADS)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        _local.session = session
    return session
