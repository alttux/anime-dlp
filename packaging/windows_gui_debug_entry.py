r"""Отладочная точка входа GUI для диагностики крашей на Windows.

Проблема: релизная GUI-сборка (`--windowed`) и запуск из исходников
одинаково не показывают НИЧЕГО при падении, потому что:

* в GUI-пути (`anime_dlp.gui.qt.app.run_gui`) не настроен ни один канал
  вывода — нет `logging`, нет `sys.excepthook`, нет `faulthandler`, нет
  обработчика сообщений Qt; библиотека `anime_parsers_ru` пишет через
  `print()`/warnings, и они намеренно подавлены (`allow_warnings=False`);
* реальное падение обычно происходит НИЖЕ Python — это нативный `abort()`
  (`QThread: Destroyed while thread is still running` → `qFatal()`) или
  access violation в C-расширении (общий `KodikParser`/`requests`/OpenSSL,
  используемый параллельно из нескольких QThread). Питоновского трейсбека
  в таком случае не существует в принципе;
* даже то, что Qt пытается напечатать, на Windows уходит в
  `OutputDebugString`, а не в консоль `cmd.exe`.

Эта точка входа поднимает все каналы диагностики сразу и дублирует их в
файл, чтобы поймать и питоновские исключения (в главном потоке и в любых
`threading.Thread`), и нативные крахи (стек всех потоков через
`faulthandler`), и сообщения Qt (включая предупреждения про QThread).

Запускать из настоящего терминала (не `pythonw`, не двойным кликом):

    set PYTHONFAULTHANDLER=1
    set PYTHONUNBUFFERED=1
    set QT_LOGGING_RULES=*=true
    set QT_FATAL_WARNINGS=1      # первый "Destroyed while running" сразу
                                # станет fatal с указанием места
    python -X dev -X faulthandler packaging\windows_gui_debug_entry.py

Путь к логу можно переопределить переменной ANIME_DLP_DEBUG_LOG
(по умолчанию anime-dlp-debug.log в текущей директории).
"""

import faulthandler
import logging
import os
import sys
import threading
from pathlib import Path

LOG_PATH = Path(os.environ.get("ANIME_DLP_DEBUG_LOG", "anime-dlp-debug.log")).resolve()

# Единственный дескриптор файла лога: и faulthandler, и logging пишут в него,
# чтобы не открывать один файл дважды и не затирать записи друг друга.
_log_file = open(LOG_PATH, "w", buffering=1, encoding="utf-8", errors="replace")

# 1. Нативные крахи (segfault, abort, qFatal) — печатает C-стек ВСЕХ потоков.
faulthandler.enable(file=_log_file, all_threads=True)

# 2. Логи и питоновские исключения — в файл и в stderr (если он есть).
_handlers: list[logging.Handler] = [logging.StreamHandler(_log_file)]
if sys.__stderr__ is not None:
    _handlers.append(logging.StreamHandler(sys.__stderr__))
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(threadName)s %(levelname)s %(name)s: %(message)s",
    handlers=_handlers,
)


def _excepthook(exc_type, exc_value, exc_tb):
    logging.critical("UNCAUGHT EXCEPTION", exc_info=(exc_type, exc_value, exc_tb))


sys.excepthook = _excepthook


def _thread_excepthook(args: threading.ExceptHookArgs):
    thread_name = args.thread.name if args.thread is not None else "<unknown>"
    logging.critical(
        "UNCAUGHT EXCEPTION in thread %s",
        thread_name,
        exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
    )


threading.excepthook = _thread_excepthook


def _install_qt_message_handler() -> None:
    """Перехватывает ВСЕ сообщения Qt (в т.ч. `QThread: Destroyed while
    thread is still running`), которые иначе на Windows ушли бы только в
    `OutputDebugString`."""
    from PyQt6.QtCore import QtMsgType, qInstallMessageHandler

    _level_by_type = {
        QtMsgType.QtDebugMsg: logging.DEBUG,
        QtMsgType.QtInfoMsg: logging.INFO,
        QtMsgType.QtWarningMsg: logging.WARNING,
        QtMsgType.QtCriticalMsg: logging.ERROR,
        QtMsgType.QtFatalMsg: logging.CRITICAL,
    }

    def _handler(msg_type, context, message):
        level = _level_by_type.get(msg_type, logging.INFO)
        logging.log(
            level,
            "Qt: %s (%s:%s, %s)",
            message,
            context.file,
            context.line,
            context.function,
        )
        if msg_type == QtMsgType.QtFatalMsg:
            # qFatal() всё равно вызовет abort() — но сначала сохраняем
            # нативный стек всех потоков в тот же лог.
            faulthandler.dump_traceback(file=_log_file, all_threads=True)
            _log_file.flush()

    qInstallMessageHandler(_handler)


def main() -> int:
    _install_qt_message_handler()

    from anime_dlp.config import DOWNLOAD_DIR
    from anime_dlp.gui.qt.app import run_gui

    logging.info("anime-dlp debug entry started; log file: %s", LOG_PATH)
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    try:
        return_code = run_gui(DOWNLOAD_DIR)
    except BaseException:
        logging.critical("run_gui() crashed", exc_info=True)
        raise
    logging.info("run_gui() returned %s", return_code)
    return return_code


if __name__ == "__main__":
    sys.exit(main())
