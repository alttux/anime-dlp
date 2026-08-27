<div align="center">

# 🎬 anime-dlp

**CLI-утилита для скачивания аниме с плеера Kodik**

[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE.txt)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](pyproject.toml)
[![Rich](https://img.shields.io/badge/UI-rich-cyan.svg)](https://github.com/Textualize/rich)

Простой и удобный терминальный интерфейс для поиска, выбора озвучки и скачивания
аниме-сериалов и фильмов с плеера Kodik.

</div>

---

## 📖 Оглавление

- [Возможности](#-возможности)
- [Установка](#-установка)
  - [Flatpak](#flatpak)
  - [Из исходников](#из-исходников)
  - [Windows и macOS](#windows-и-macos)
  - [Сборка пакета](#сборка-пакета)
- [Использование](#-использование)
  - [Пример работы](#пример-работы)
  - [Аргументы командной строки](#аргументы-командной-строки)
- [Архитектура проекта](#-архитектура-проекта)
- [Стек технологий](#-стек-технологий)
- [Лицензия](#-лицензия)

---

## ✨ Возможности

- 🔎 **Поиск аниме** по названию (поддержка кириллицы) через [anime-parsers-ru](https://github.com/YaNesyTortiK/AnimeParsers)
- 🎙️ **Выбор озвучки** — программа показывает все доступные варианты озвучки/субтитров
- 📺 **Скачивание серии, всего сезона или фильма** одной командой
- ⚡ **Многопоточная загрузка** с докачкой по диапазонам (Range-запросы) для максимальной скорости
- 📊 **Красивый прогресс-бар** с скоростью загрузки и оставшимся временем ([rich](https://github.com/Textualize/rich))
- 🗂️ **Указание директории загрузки** через флаг `-d`
- 📝 **Логирование вывода** всей сессии в файл `anime-dlp.log` через флаг `--logging`
- 🗃️ **Разделы в GUI** — «Главное» с популярным, «Категории» по жанрам, «Избранное» и «Поиск»
- ⭐ **Избранное** — отмечайте аниме звёздочкой на его странице, отметки сохраняются между запусками
- ♻️ **Кнопка «Обновить»** — принудительно перезагружает текущий раздел и чистит весь кэш программы
- ℹ️ **О программе** — версия, ссылки и лицензия: иконка в углу окна или флаг `-a/--about` в консоли

---

## 🚀 Установка

### Flatpak

Самый простой способ — Flatpak: Python, GTK4, libadwaita и **ffmpeg** уже
входят в пакет, ставить их отдельно не нужно.

**Установка готового пакета** (если вам передали файл `anime-dlp.flatpak`):

```bash
flatpak install --user anime-dlp.flatpak
```

Запуск — через меню приложений или командой:

```bash
flatpak run io.github.alttux.AnimeDlp                       # графический интерфейс
flatpak run --command=anime-dlp io.github.alttux.AnimeDlp   # интерфейс командной строки
```

**Сборка Flatpak из исходников.** Понадобятся `flatpak` и `flatpak-builder`,
а также рантайм и SDK GNOME:

```bash
flatpak remote-add --if-not-exists --user flathub https://dl.flathub.org/repo/flathub.flatpakrepo
flatpak install --user flathub org.gnome.Platform//49 org.gnome.Sdk//49
```

Сборка и установка:

```bash
cd flatpak
flatpak-builder --force-clean --user --install --repo=repo build-dir io.github.alttux.AnimeDlp.yml
```

Чтобы получить один файл `.flatpak` и передать его другому человеку:

```bash
flatpak build-bundle repo ../anime-dlp.flatpak io.github.alttux.AnimeDlp
```

Все шаги выше объединены в `flatpak/build.sh` — скрипт сам проверит remote и
рантайм, соберёт пакет и положит готовый `anime-dlp.flatpak` в корень проекта:

```bash
./flatpak/build.sh
```

> Зависимости Python зафиксированы (с хешами) в `flatpak/python3-deps.json`,
> потому что во время сборки Flatpak нет доступа в сеть. Если вы поменяли
> `requirements.txt`, пересоздайте этот файл:
> ```bash
> cd flatpak
> curl -sSLO https://raw.githubusercontent.com/flatpak/flatpak-builder-tools/master/pip/flatpak-pip-generator.py
> pip install "requirements-parser>=0.11.0,<1.0.0" "packaging>=23.0"
> python flatpak-pip-generator.py --runtime='org.gnome.Sdk//49' \
>     --requirements-file=../requirements.txt --output python3-deps
> ```
> Флаг `--runtime` заставляет резолвить пакеты внутри SDK, чтобы версии
> совпадали с Python в рантайме.

В Flatpak файлы по умолчанию скачиваются в `~/Downloads`, а токен Kodik
хранится в `~/.var/app/io.github.alttux.AnimeDlp/data/`.

### Из исходников

Требования: **Python 3.10+**

```bash
git clone https://github.com/alttux/anime-dlp.git
cd anime-dlp

python3 -m venv .venv
source .venv/bin/activate      # для Windows: .venv\Scripts\activate

pip install -r requirements.txt
pip install .
```

После установки в окружении станет доступна команда `anime-dlp`.

Чтобы использовать графический интерфейс (флаг `--gui`), установите
дополнительную зависимость `PyGObject`, а также системные пакеты **GTK4** и
**libadwaita** (в Arch/CachyOS: `gtk4`, `libadwaita`, `python-gobject`):

```bash
pip install -r requirements.txt
pip install ".[gui]"
```

### Windows и macOS

Flatpak — только для Linux, но CLI и GUI работают и на Windows, и на macOS.

**Windows**: готовые портативные **CLI `.exe`** и **GUI `.exe`** (на PyQt6,
ничего дополнительно устанавливать не нужно) собираются автоматически в CI
на каждый релизный тег — скачать можно во вкладке [Releases][releases],
либо для последнего коммита в `main` — во вкладке [Actions][actions-win] →
workflow "Windows build" → артефакты сборки. Файлы автономные (собраны
PyInstaller'ом), Python ставить не нужно:

```powershell
.\anime-dlp-windows-x86_64-<версия>.exe -d "$HOME\Videos\Anime"
.\anime-dlp-gui-windows-x86_64-<версия>.exe
```

> 🪟 На Windows GUI собран на **PyQt6** (а не GTK4/libadwaita, как на
> Linux/macOS — для GTK4 нет готовых pip-колёс под Windows), но повторяет
> тот же интерфейс: экраны, элементы и их расположение совпадают. Собрать
> его самостоятельно из исходников можно через
> `packaging/windows/make_ico.sh` + PyInstaller (см. workflow
> `.github/workflows/windows-build.yml`, job `build-gui`); подробная
> инструкция по CLI/GTK-GUI из исходников — **[WINDOWS.md](WINDOWS.md)**.

**macOS**: готовый **`.dmg`-установщик** с GUI (GTK4 + libadwaita, ffmpeg
внутрь не входит) собирается автоматически в CI на каждый релизный тег —
скачать можно во вкладке [Releases][releases], либо для последнего коммита
в `main` — во вкладке [Actions][actions-macos] → workflow "macOS build" →
артефакты сборки. Откройте `.dmg` и перетащите `AnimeDlp.app` в
`Applications`.

[releases]: https://github.com/alttux/anime-dlp/releases
[actions-win]: https://github.com/alttux/anime-dlp/actions/workflows/windows-build.yml
[actions-macos]: https://github.com/alttux/anime-dlp/actions/workflows/macos-build.yml

> Для серий, которые Kodik отдаёт только через HLS, нужен **ffmpeg** в
> `PATH`: на Windows — `winget install ffmpeg` или скачать с
> [ffmpeg.org](https://ffmpeg.org/download.html), на macOS —
> `brew install ffmpeg`. Без него скачаются только серии с обычной
> Range-раздачей.
>
> Токен Kodik и папка загрузок по умолчанию (если не указан `-d`) для
> Windows-exe — `%APPDATA%\anime-dlp` и `~\Downloads`, для macOS-приложения —
> `~/Library/Application Support/anime-dlp` и `~/Downloads`.

Собрать `.dmg` для macOS самостоятельно из исходников можно скриптами в
`packaging/macos/` (`make_icns.sh` + `build.sh`) — именно они используются в
CI, см. `.github/workflows/macos-build.yml`.

**Графический интерфейс (GUI)** на Linux и macOS собирается из исходников,
так как готовых pip-колёс GTK4/libadwaita для этих платформ (кроме Linux)
нет — их ставят через системный пакетный менеджер платформы. На Windows
GUI написан на **PyQt6** (`pip`-колёса есть, ставить ничего системного не
нужно) и собирается в CI как готовый portable `.exe` — см. раздел выше.

<details>
<summary><b>GUI на Windows — сборка из исходников (PyQt6)</b></summary>

Готовый `.exe` из CI (см. выше) не требует Python вообще. Чтобы запустить
GUI из исходников:

```powershell
git clone https://github.com/alttux/anime-dlp.git
cd anime-dlp
python -m pip install ".[gui]"
anime-dlp --gui
```

`pip install ".[gui]"` на Windows ставит `PyQt6` (на Linux/macOS — вместо
него `PyGObject` для GTK4-версии). Для запуска CLI/GTK-GUI из исходников
через MSYS2 (например, для разработки GTK-версии на Windows) — см.
[WINDOWS.md](WINDOWS.md).
</details>

<details>
<summary><b>GUI на macOS — через Homebrew</b></summary>

1. Поставьте [Homebrew](https://brew.sh/), затем GTK4/libadwaita/PyGObject
   и ffmpeg:
   ```bash
   brew install gtk4 libadwaita pygobject3 adwaita-icon-theme \
                gobject-introspection ffmpeg
   ```
2. Создайте виртуальное окружение с доступом к системным пакетам Homebrew
   (иначе Python не увидит PyGObject, поставленный через brew) и установите
   anime-dlp в него:
   ```bash
   git clone https://github.com/alttux/anime-dlp.git
   cd anime-dlp
   "$(brew --prefix python3)/bin/python3" -m venv --system-site-packages .venv
   source .venv/bin/activate
   pip install .
   ```
3. Запуск (в активированном `.venv`):
   ```bash
   anime-dlp --gui
   ```

Готовый `.dmg` (без сборки из исходников) можно скачать во вкладке
[Releases][releases] — см. выше.
</details>

### Сборка пакета

Проект собирается стандартными средствами Python (`setuptools`):

```bash
python3 -m pip install --upgrade build
python3 -m build
```

Готовые `.whl` и `.tar.gz` появятся в директории `dist/`. Установить собранный пакет можно так:

```bash
pip install dist/anime_dlp-*.whl
```

Либо через `./build.sh` — он делает то же самое, но перед сборкой
автоматически увеличивает patch-версию в `pyproject.toml` на 1 (см.
`scripts/bump_version.py`), чтобы у каждой новой сборки была своя версия.
Тот же скрипт версии дергает и `flatpak/build.sh`, так что версия одна общая
для wheel/sdist и для Flatpak-пакета.

---

## 🕹 Использование

Запустите программу командой:

```bash
anime-dlp
```

По умолчанию файлы скачиваются в директорию самой программы. Чтобы указать
свою директорию для загрузки, используйте флаг `-d`:

```bash
anime-dlp -d ~/Videos/Anime
```

Далее программа проведёт вас через интерактивный диалог: поиск аниме → выбор
варианта из списка → выбор озвучки → выбор серии (или всего сезона).

### Графический интерфейс

Вместо консольного диалога можно запустить GUI — на Linux и macOS это
GTK4 + libadwaita, на Windows (portable `.exe` или из исходников) — PyQt6
с тем же набором экранов и элементов:

```bash
anime-dlp --gui
```

Окно разделено на четыре раздела:

| Раздел          | Что внутри                                                                 |
|-----------------|----------------------------------------------------------------------------|
| **Главное**     | Сетка популярных аниме по рейтингу Shikimori с бесконечной прокруткой       |
| **Категории**   | Сетка жанров (Драма, Фэнтези, Сёнен, Приключения, Экшен и другие) — по клику открывается сетка аниме выбранного жанра |
| **Избранное**   | Аниме, отмеченные звёздочкой на странице аниме                              |
| **Поиск**       | Поиск по названию с подсказками по мере ввода                               |

С любой обложки открывается страница аниме: описание, жанры, рейтинг,
**звёздочка** для добавления в избранное, выбор озвучки и серий. Кнопка
**«Скачать»** в правом нижнем углу открывает системный диалог выбора папки,
после чего скачивание идёт с прогресс-барами по каждому файлу — аналогично
консольной версии.

В шапке окна две кнопки: **ⓘ** слева открывает окно «О программе» (версия,
ссылка на GitHub, лицензия, список используемых библиотек), а **⟳** справа
принудительно перезагружает текущий раздел и очищает весь кэш программы —
обложки, метаданные и сохранённый токен Kodik. Избранное при этом не
затрагивается.

<p align="center">
  <img src="screenshots/img.png" width="49%" alt="Поиск аниме" />
  <img src="screenshots/img_1.png" width="49%" alt="Выбор озвучки и серий" />
</p>
<p align="center">
  <img src="screenshots/img_2.png" width="49%" alt="Выбор папки для скачивания" />
  <img src="screenshots/img_3.png" width="49%" alt="Прогресс скачивания" />
</p>
<p align="center">
  <img src="screenshots/img_4.png" width="49%" alt="Готово — открыть файл или показать в папке" />
</p>

### Аргументы командной строки

| Флаг              | Описание                                                            |
|-------------------|----------------------------------------------------------------------|
| `-a`, `--about`   | Показать информацию о программе (версия, ссылки, лицензия, библиотеки) и выйти |
| `-d`, `--dir`     | Директория для скачивания аниме (по умолчанию — директория программы) |
| `--logging`       | Сохранять весь вывод консоли в файл `anime-dlp.log` внутри директории загрузки |
| `--gui`           | Запустить графический интерфейс (GTK4 + libadwaita на Linux/macOS, PyQt6 на Windows) вместо консольного диалога |
| `-h`, `--help`    | Показать справку по аргументам                                     |

### Пример работы

```bash
$ anime-dlp -d ~/Videos/Anime

Введите название аниме: Рандеву с жизнью
Поиск...

Найдено аниме:
  1. Рандеву с жизнью: приговор Маюми (2015) [shikimori: 24655]
  2. Рандеву с жизнью OVA-1 (2013) [shikimori: 17641]
  3. Рандеву с жизнью [ТВ-1] (2013) [shikimori: 15583]
  4. Рандеву с жизнью [ТВ-2] (2014) [shikimori: 19163]
  5. Рандеву с жизнью [ТВ-3] (2019) [shikimori: 36633]

Выберите номер аниме: 3

Получение информации об озвучках...

Доступные озвучки (всего серий: 12):
  1. [Озвучка] AniDUB (12 эп.)
  2. [Озвучка] AniLibria.TV (12 эп.)
  3. [Озвучка] SHIZA Project (12 эп.)
  4. [Озвучка] Studio Band (12 эп.)
  5. [Озвучка] ODALETYDUB (3 эп.)

Выберите номер озвучки: 2

Доступны серии с 1 по 12
Введите номер серии (или 'all' для скачивания всех): all

# далее программа показывает прогресс скачивания в виде прогресс-бара
```

Если выбранный тайтл — фильм, шаг с выбором серии пропускается автоматически.

Чтобы сохранить весь вывод сессии в лог-файл (например, для запуска на
домашнем сервере без интерактивного терминала под рукой):

```bash
anime-dlp -d ~/Videos/Anime --logging
# лог появится в ~/Videos/Anime/anime-dlp.log
```

---

## 🏗 Архитектура проекта

```
anime-dlp/
├── src/anime_dlp/
│   ├── main.py                # Точка входа, разбор аргументов CLI
│   ├── about.py                # Сведения о программе (для --about и окна «О программе»)
│   ├── config.py               # Конфигурационные параметры (пути, заголовки, число потоков)
│   ├── logger.py               # Логирование вывода консоли в файл (--logging)
│   ├── labels.py                # Общие текстовые метки (типы тайтлов)
│   ├── filenames.py             # Общая логика формирования имён файлов
│   ├── cli/                    # Интерфейс командной строки
│   │   ├── app.py              # Основной сценарий взаимодействия с пользователем
│   │   ├── prompts.py          # Запросы ввода у пользователя
│   │   └── display.py          # Оформление вывода (таблицы, баннеры, сообщения, --about)
│   ├── gui/                     # Графический интерфейс (--gui)
│   │   ├── __init__.py          # Выбор бэкенда: PyQt6 на Windows, GTK4 на Linux/macOS
│   │   ├── formatting.py        # Форматирование размера/скорости (общее для gtk/ и qt/)
│   │   ├── prefetch.py          # Фоновая предзагрузка информации об аниме
│   │   ├── refresh.py           # Очистка всех кэшей по кнопке «Обновить»
│   │   ├── gtk/                 # Бэкенд на GTK4 + libadwaita (Linux/macOS)
│   │   │   ├── app.py           # Точка входа GUI, Adw.Application
│   │   │   ├── window.py        # Главное окно и навигация между экранами
│   │   │   ├── home_page.py     # Четыре вкладки, кнопки «Обновить» и «О программе»
│   │   │   ├── catalog_tab.py   # Сетка обложек с бесконечной прокруткой
│   │   │   ├── categories_tab.py  # Сетка жанров с обложками
│   │   │   ├── genre_page.py    # Сетка аниме выбранного жанра
│   │   │   ├── favorites_tab.py # Аниме, отмеченные звёздочкой
│   │   │   ├── search_tab.py    # Поиск аниме с живыми подсказками
│   │   │   ├── cover_card.py    # Карточка обложки в сетках
│   │   │   ├── about_dialog.py  # Окно «О программе» (Adw.AboutDialog)
│   │   │   ├── details_page.py  # Выбор озвучки и серий, звёздочка, кнопка «Скачать»
│   │   │   └── download_page.py # Экран скачивания с прогресс-барами
│   │   └── qt/                  # Бэкенд на PyQt6 (Windows), тот же набор экранов
│   │       ├── app.py           # Точка входа GUI, QApplication
│   │       ├── window.py        # Главное окно и навигация между экранами
│   │       ├── widgets.py       # Составные виджеты (карточки, строки, flow-layout)
│   │       ├── workers.py       # Фоновые QThread-воркеры (поиск/инфо/каталог/скачивание)
│   │       ├── pixmap_utils.py  # Скругление углов постеров
│   │       ├── home_page.py     # Четыре вкладки, кнопки «Обновить» и «О программе»
│   │       ├── catalog_tab.py   # Сетка обложек с бесконечной прокруткой
│   │       ├── categories_tab.py  # Сетка жанров с обложками
│   │       ├── genre_page.py    # Сетка аниме выбранного жанра
│   │       ├── favorites_tab.py # Аниме, отмеченные звёздочкой
│   │       ├── search_tab.py    # Поиск аниме с живыми подсказками
│   │       ├── cover_card.py    # Карточка обложки в сетках
│   │       ├── about_dialog.py  # Окно «О программе»
│   │       ├── details_page.py  # Выбор озвучки и серий, звёздочка, кнопка «Скачать»
│   │       └── download_page.py # Экран скачивания с прогресс-барами
│   └── core/                   # Основная бизнес-логика
│       ├── anime_service.py    # Поиск, каталог, жанры и получение ссылок на скачивание
│       ├── anime_info.py       # Разбор material_data (описание, жанры, рейтинг)
│       ├── cache.py            # Дисковый кэш обложек и метаданных
│       ├── favorites.py        # Хранилище избранного (JSON)
│       ├── downloader.py       # Многопоточное скачивание с колбэком прогресса
│       └── token_manager.py    # Хранение и получение Kodik-токена
├── pyproject.toml              # Метаданные и зависимости пакета
├── requirements.txt            # Зафиксированные версии зависимостей
└── LICENSE.txt                 # Лицензия MIT
```

Проект скачивает видео с плеера **Kodik**, используя библиотеку
[anime-parsers-ru](https://github.com/YaNesyTortiK/AnimeParsers) для поиска и
получения прямых ссылок, после чего запускает многопоточную загрузку с
докачкой по диапазонам байт (если сервер их поддерживает).

---

## 🛠 Стек технологий

- [anime_parsers_ru](https://pypi.org/project/anime-parsers-ru/) — поиск и получение ссылок на видео с Kodik
- [rich](https://github.com/Textualize/rich) — оформление терминального интерфейса, таблицы и прогресс-бары
- [requests](https://docs.python-requests.org/) — HTTP-запросы и скачивание файлов
- [beautifulsoup4](https://www.crummy.com/software/BeautifulSoup/) — парсинг HTML
- [PyGObject](https://pygobject.gnome.org/) + **GTK4** / **libadwaita** — графический интерфейс на Linux/macOS (опционально, `--gui`)
- [PyQt6](https://pypi.org/project/PyQt6/) — графический интерфейс на Windows (опционально, `--gui`)

---

## 📄 Лицензия

Проект распространяется под лицензией [MIT](LICENSE.txt).
