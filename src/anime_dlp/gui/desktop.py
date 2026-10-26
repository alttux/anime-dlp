"""«Показать в папке» средствами ОС — общее для GTK и Qt.

На Windows и macOS у файлового менеджера есть штатная команда «открыть
папку и выделить файл»; на Linux такой команды нет, там каждый бэкенд
использует свой способ (GTK — D-Bus org.freedesktop.FileManager1), а при
неудаче просто открывает папку.
"""

import subprocess
import sys
from pathlib import Path


def reveal_in_file_manager(path: Path) -> bool:
    """True — команда ОС запущена; False — платформа без такой команды или
    запуск не удался (вызывающий откроет саму папку)."""
    if sys.platform == "win32":
        # «/select,» отдельным аргументом: иначе list2cmdline возьмёт в кавычки
        # всё «/select,C:\...», и explorer не распознает ключ. Код возврата
        # explorer бессмыслен (1 даже при успехе) — не проверяем.
        cmd = ["explorer", "/select,", str(path)]
    elif sys.platform == "darwin":
        cmd = ["open", "-R", str(path)]
    else:
        return False
    try:
        subprocess.Popen(cmd)
    except OSError:
        return False
    return True
