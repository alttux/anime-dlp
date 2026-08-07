import re
import sys
from pathlib import Path

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")


class _Tee:
    """Прокси над потоком вывода, дублирующий запись в лог-файл."""

    def __init__(self, stream, log_file):
        self._stream = stream
        self._log_file = log_file

    def write(self, data: str) -> int:
        written = self._stream.write(data)
        self._log_file.write(_ANSI_RE.sub("", data))
        self._log_file.flush()
        return written

    def flush(self):
        self._stream.flush()
        self._log_file.flush()

    def isatty(self):
        return self._stream.isatty()

    def __getattr__(self, name):
        return getattr(self._stream, name)


class ConsoleLogger:
    """Дублирует весь вывод в stdout/stderr в лог-файл на время работы программы."""

    def __init__(self, log_path: Path):
        self._log_path = log_path
        self._log_file = None
        self._orig_stdout = None
        self._orig_stderr = None

    def __enter__(self):
        self._log_file = open(self._log_path, "a", encoding="utf-8")
        self._orig_stdout = sys.stdout
        self._orig_stderr = sys.stderr
        sys.stdout = _Tee(self._orig_stdout, self._log_file)
        sys.stderr = _Tee(self._orig_stderr, self._log_file)
        return self

    def __exit__(self, exc_type, exc, tb):
        sys.stdout = self._orig_stdout
        sys.stderr = self._orig_stderr
        self._log_file.close()
