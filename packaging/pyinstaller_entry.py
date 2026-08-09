"""Точка входа для PyInstaller.

PyInstaller анализирует зависимости, начиная с одного скрипта, поэтому
вместо того чтобы указывать ему на src/-layout пакета напрямую, здесь
просто вызывается уже установленная (через `pip install .`) точка входа
`anime_dlp.main:main` — так же, как это делает консольный скрипт
`anime-dlp`, создаваемый setuptools.
"""

from anime_dlp.main import main

if __name__ == "__main__":
    main()
