from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("anime-dlp")
except PackageNotFoundError:
    # Пакет запущен из исходников без установки (pip install/-e .) —
    # например, напрямую через `python src/anime_dlp/main.py`.
    __version__ = "0.0.0+unknown"

__all__ = ["__version__"]
