#!/usr/bin/env python3
"""Увеличивает patch-версию проекта на 1.

Меняет version в pyproject.toml и синхронизирует с ней версию/дату самого
свежего <release> в data/io.github.alttux.AnimeDlp.metainfo.xml — это
единственные два места, где версия хранится статически. Вызывается
автоматически из .github/workflows/release.yml при каждом пуше в main
(см. CLAUDE.md → «Сборка и версионирование»); build.sh/flatpak/build.sh
версию больше не бампают, чтобы не расходиться с CI.
"""

import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = ROOT / "pyproject.toml"
METAINFO = ROOT / "data" / "io.github.alttux.AnimeDlp.metainfo.xml"

VERSION_RE = re.compile(r'^version = "(\d+)\.(\d+)\.(\d+)"$', re.MULTILINE)
RELEASE_RE = re.compile(r'(<release version=")[^"]+(" date=")[^"]+(">)')


def bump_pyproject() -> tuple[str, str]:
    text = PYPROJECT.read_text(encoding="utf-8")
    match = VERSION_RE.search(text)
    if not match:
        sys.exit(f"Не найдена строка version = \"X.Y.Z\" в {PYPROJECT}")

    major, minor, patch = (int(part) for part in match.groups())
    old_version = f"{major}.{minor}.{patch}"
    new_version = f"{major}.{minor}.{patch + 1}"

    text = text[: match.start()] + f'version = "{new_version}"' + text[match.end() :]
    PYPROJECT.write_text(text, encoding="utf-8")
    return old_version, new_version


def sync_metainfo(new_version: str) -> None:
    if not METAINFO.exists():
        return

    text = METAINFO.read_text(encoding="utf-8")
    today = date.today().isoformat()
    new_text, count = RELEASE_RE.subn(rf'\g<1>{new_version}\g<2>{today}\g<3>', text, count=1)
    if count:
        METAINFO.write_text(new_text, encoding="utf-8")


def main() -> None:
    old_version, new_version = bump_pyproject()
    sync_metainfo(new_version)
    print(f"Версия: {old_version} -> {new_version}")


if __name__ == "__main__":
    main()
