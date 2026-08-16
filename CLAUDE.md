# Суть проекта
Проект предназначен для скачивания аниме (например, на домашнем сервере) через
CLI **или** GUI (GTK4/libadwaita на Linux/macOS, PyQt6 на Windows) при помощи
библиотеки
[anime-parsers-ru](https://github.com/YaNesyTortiK/AnimeParsers), используя
плеер Kodik. Пакет называется `anime-dlp`, устанавливается как консольная
команда `anime-dlp`, распространяется как обычный Python-пакет и как Flatpak
(`io.github.alttux.AnimeDlp`).

# Принцип работы (CLI)
1. Пользователь запускает программу через терминал, указывая при необходимости
   директорию загрузки, флаг логирования и сетевой интерфейс:
```
anime-dlp -d <ДИРЕКТОРИЯ КУДА СКАЧАЕТСЯ АНИМЕ> [--logging] [-i <ИНТЕРФЕЙС>]
```
Если директория не указана — файлы скачаются в `downloads/` рядом с
программой (вне Flatpak и вне PyInstaller-сборки) либо в `~/Downloads`
(внутри Flatpak или в собранном PyInstaller-исполняемом файле для
Windows/macOS — см. `config.py`, `IS_FROZEN`).
Флаг `--logging` дублирует весь вывод консоли в файл `anime-dlp.log` внутри
директории загрузки. Флаг `-i/--interface` привязывает исходящий трафик к
конкретному сетевому интерфейсу (в обход VPN/TUN) через `SO_BINDTODEVICE` —
эта сокет-опция есть только в Linux, поэтому на Windows/macOS флаг завершает
программу с понятной ошибкой, а сам пункт меню в GUI на этих платформах не
показывается (`core/network.py`, `network.SUPPORTED`).
2. После запуска программа попросит название аниме (поддерживается кириллица).
3. Программа найдёт варианты и выведет пронумерованный список (с годом, типом
   и `shikimori_id`), чтобы пользователь выбрал нужный.
4. Сразу после выбора программа показывает карточку с информацией об аниме —
   статус, эпизоды, рейтинг Shikimori, жанры, студия, описание и ссылка на
   постер (данные берутся из `material_data`, который Kodik уже отдаёт вместе
   с результатами поиска — без дополнительных запросов).
5. Программа ищет варианты озвучки выбранного аниме и выводит пронумерованный
   список со всеми доступными озвучками, чтобы пользователь выбрал нужную.
6. Программа спрашивает, какую серию нужно скачать, или скачать весь сезон
   (принимает на вход либо номер серии, либо `all`; если это фильм — шаг
   пропускается).
7. Скачивание идёт многопоточно с докачкой по HTTP Range-запросам и
   прогресс-баром (rich). Если сервер Kodik отдаёт только HLS-прокси-ссылку
   (без поддержки Range), скачивание автоматически переключается на HLS через
   `ffmpeg`.

## Пример работы
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

# программа показывает панель с описанием, жанрами, статусом, рейтингом и тд.

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

# Графический интерфейс (GUI)
Вместо консольного диалога программу можно запустить с флагом `--gui` —
откроется окно, повторяющее тот же сценарий: поиск с живыми подсказками →
карточка с информацией об аниме, выбором озвучки и серий → системный диалог
выбора папки загрузки → прогресс-бары по каждому файлу → экран «Готово» с
кнопками «Открыть» и «Показать в папке».

У GUI два бэкенда с идентичным набором экранов и порядком элементов:
**GTK4 + libadwaita** (`gui/gtk/`, Linux/macOS) и **PyQt6** (`gui/qt/`,
Windows — у GTK4/libadwaita нет pip-колёс под Windows, у PyQt6 есть).
`gui/__init__.py` сам выбирает бэкенд по `sys.platform`
(`ANIME_DLP_GUI_BACKEND=gtk|qt` переопределяет выбор — например, чтобы
запустить GTK-версию на Windows через MSYS2, см. `WINDOWS.md`). GUI —
опциональная зависимость (`pyproject.toml` → `[project.optional-dependencies].gui`
ставит `PyGObject` на Linux/macOS и `PyQt6` на Windows через PEP 508
environment markers, через `pip install ".[gui]"`), поэтому оба бэкенда
импортируются лениво (только при `--gui`), чтобы CLI не требовал ни GTK, ни
Qt.

Бизнес-логика (поиск, получение ссылок, скачивание с колбэком прогресса)
переиспользуется между CLI и GUI через `core/` — сама GUI ничего не знает
про сеть/парсинг напрямую.

# Архитектура проекта
```
anime-dlp/
├── src/anime_dlp/
│   ├── __init__.py                # anime_dlp.__version__ (importlib.metadata)
│   ├── main.py                  # Точка входа, разбор аргументов CLI (-d, --logging, --gui, -i, --version)
│   ├── config.py                 # Пути (в т.ч. Flatpak-режим), заголовки запросов, число потоков
│   ├── logger.py                 # Логирование вывода консоли в файл (--logging)
│   ├── labels.py                  # Текстовые метки (типы тайтлов, статусы)
│   ├── filenames.py               # Формирование безопасных имён файлов
│   ├── cli/                      # Интерфейс командной строки
│   │   ├── app.py                # Основной сценарий взаимодействия с пользователем
│   │   ├── prompts.py            # Запросы ввода у пользователя
│   │   └── display.py            # Оформление вывода (таблицы, панели, баннеры, сообщения)
│   ├── gui/                       # Графический интерфейс (--gui)
│   │   ├── __init__.py            # Выбор бэкенда: PyQt6 на Windows, GTK4 на Linux/macOS (ANIME_DLP_GUI_BACKEND)
│   │   ├── formatting.py          # Форматирование размера/скорости (общее для gtk/ и qt/)
│   │   ├── gtk/                   # Бэкенд GTK4 + libadwaita (Linux/macOS)
│   │   │   ├── app.py             # Точка входа GUI, Adw.Application
│   │   │   ├── window.py          # Главное окно и навигация между экранами
│   │   │   ├── search_page.py     # Поиск аниме с живыми подсказками, выбор сетевого интерфейса
│   │   │   ├── details_page.py    # Информация об аниме, выбор озвучки и серий, кнопка «Скачать»
│   │   │   └── download_page.py   # Экран скачивания с прогресс-барами, кнопки «Открыть»/«Показать в папке»
│   │   └── qt/                    # Бэкенд PyQt6 (Windows), тот же набор экранов и порядок элементов
│   │       ├── app.py             # Точка входа GUI, QApplication
│   │       ├── window.py          # Главное окно, навигация (QStackedWidget) и toast-оверлей
│   │       ├── widgets.py         # Составные виджеты (карточки/строки/flow-layout под Adwaita-стиль)
│   │       ├── workers.py         # Фоновые QThread-воркеры (поиск/инфо/постер/скачивание)
│   │       ├── search_page.py     # Поиск аниме с живыми подсказками (сетевой интерфейс не показывается — Linux-only)
│   │       ├── details_page.py    # Информация об аниме, выбор озвучки и серий, кнопка «Скачать»
│   │       └── download_page.py   # Экран скачивания с прогресс-барами, кнопки «Открыть»/«Показать в папке»
│   └── core/                     # Основная бизнес-логика (используется и CLI, и GUI)
│       ├── anime_service.py      # Поиск аниме и получение ссылок на скачивание
│       ├── anime_info.py         # Извлечение описания/жанров/рейтинга/статуса из material_data
│       ├── downloader.py         # Многопоточное скачивание с колбэком прогресса + HLS-фолбэк через ffmpeg
│       ├── network.py            # Привязка исходящего трафика к сетевому интерфейсу (-i/--interface)
│       └── token_manager.py      # Хранение и получение Kodik-токена
├── data/                          # Desktop-файл, AppStream-метаданные и иконка для Flatpak
├── flatpak/                       # Манифест и скрипт сборки Flatpak-пакета
│   ├── io.github.alttux.AnimeDlp.yml
│   └── build.sh                   # Сборка + бамп версии, кладёт anime-dlp.flatpak в корень
├── packaging/
│   ├── pyinstaller_entry.py       # Точка входа для ручной PyInstaller-сборки CLI (любая платформа)
│   ├── macos_gui_entry.py         # Точка входа GUI для macOS .app-бандла (PyInstaller, --windowed)
│   ├── windows_gui_entry.py       # Точка входа GUI (PyQt6) для Windows .exe-бандла (PyInstaller, --windowed)
│   ├── macos/
│   │   ├── make_icns.sh           # SVG-иконка проекта → AnimeDlp.icns (rsvg-convert + iconutil)
│   │   └── build.sh               # Сборка dist/AnimeDlp.app через PyInstaller (GTK4/libadwaita из Homebrew)
│   └── windows/
│       ├── make_ico.sh            # SVG-иконка проекта → AnimeDlp.ico (rsvg-convert + Pillow)
│       └── AnimeDlp.ico           # Сгенерированная иконка для Windows GUI .exe
├── scripts/
│   └── bump_version.py            # Увеличивает patch-версию в pyproject.toml и metainfo.xml на 1
├── screenshots/                   # Скриншоты GUI для README
├── .github/workflows/
│   ├── flatpak.yml                # CI: сборка Flatpak (Linux)
│   ├── windows-build.yml          # CI: сборка Windows CLI .exe и GUI .exe (PyQt6, PyInstaller)
│   └── macos-build.yml            # CI: сборка macOS .app + .dmg-установщика (GUI, Homebrew + PyInstaller)
├── build.sh                       # Сборка Python-пакета (wheel/sdist) + бамп версии
├── pyproject.toml                 # Метаданные и зависимости пакета
├── requirements.txt                # Зафиксированные версии зависимостей
├── WINDOWS.md                      # Подробная пошаговая инструкция: CLI+GUI на Windows из исходников
└── LICENSE.txt                     # Лицензия MIT
```

Проект скачивает видео с плеера **Kodik**, используя библиотеку
[anime-parsers-ru](https://github.com/YaNesyTortiK/AnimeParsers) для поиска и
получения прямых ссылок (включая `material_data` с Shikimori/Kinopoisk/IMDB
для карточки с информацией об аниме), после чего запускает многопоточную
загрузку с докачкой по диапазонам байт, либо, если сервер не отдаёт видео
через Range-запросы, скачивание через HLS-поток при помощи `ffmpeg`.

# Сборка и версионирование
- Единый источник версии — поле `version` в `pyproject.toml`. Она читается
  во время выполнения через `anime_dlp.__version__`
  (`src/anime_dlp/__init__.py`, `importlib.metadata.version("anime-dlp")`,
  с фолбэком `"0.0.0+unknown"` для запуска из неустановленных исходников) и
  показывается пользователю: флагом `anime-dlp --version`/`-V`, а также в
  заголовке окна GUI (`Anime Downloader vX.Y.Z`, оба бэкенда — см.
  `gui/formatting.py:APP_TITLE`).
- Версия увеличивается **автоматически и только в CI**, без ручных
  действий разработчика: `.github/workflows/release.yml` при каждом пуше в
  `main`, который затрагивает не только документацию (`paths-ignore`),
  сам вызывает `scripts/bump_version.py` (увеличивает patch-версию в
  `pyproject.toml` и синхронизирует её с последним `<release>` в
  `data/io.github.alttux.AnimeDlp.metainfo.xml`), коммитит это изменение
  от имени `github-actions[bot]` (с меткой `[auto-version]` в сообщении —
  по ней же следующий запуск отличает свой бамп-коммит от обычного пуша и
  не бампает версию повторно) и пушит обратно в `main`, затем создаёт и
  пушит git-тег `v<версия>`, создаёт под него GitHub Release
  (`gh release create`) и вызывает `windows-build.yml`, `macos-build.yml` и
  `flatpak.yml` как reusable workflows (`workflow_call`, вход `tag_name`) —
  они собирают файлы (со встроенной версией — см. ниже) и прикрепляют их к
  этому релизу. Три build-workflow'а больше НЕ запускаются напрямую по
  пушу тега (раньше запускались и так — это приводило к двойной сборке на
  каждый релиз), только через `workflow_call` из `release.yml` — но
  по-прежнему запускаются как обычный CI (без прикрепления к релизу) на
  каждый пуш/PR в `main`, чтобы проверять, что всё собирается.
- Локальные скрипты сборки (`./build.sh`, `./flatpak/build.sh`) версию
  **не трогают** — собирают с той версией, что уже закоммичена в
  `pyproject.toml`, чтобы не расходиться с CI и не плодить конфликты в
  этой строке между машинами разработчиков.
- Python-пакет: `./build.sh` (или вручную `python3 -m build`) — собирает
  wheel/sdist в `dist/`.
- Flatpak: `./flatpak/build.sh` — добавляет remote flathub, ставит
  рантайм/SDK при отсутствии, собирает и упаковывает
  `anime-dlp-<версия>.flatpak` в корень проекта.
- macOS (GitHub Actions, `.github/workflows/macos-build.yml`, `runs-on:
  macos-14`, только `aarch64`): ставит GTK4/libadwaita/PyGObject через
  Homebrew, генерирует иконку (`packaging/macos/make_icns.sh`), собирает
  `dist/AnimeDlp.app` через PyInstaller (`packaging/macos/build.sh` +
  `packaging/macos_gui_entry.py`, GUI запускается напрямую, без
  CLI-диалога, флаг `--copy-metadata anime-dlp` нужен, чтобы
  `importlib.metadata` работал и внутри собранного бандла), затем шаг
  «Set app bundle version» прописывает `CFBundleShortVersionString`/
  `CFBundleVersion` в `Info.plist` через `PlistBuddy`, упаковывает в `.dmg`
  через `create-dmg` и прикрепляет его к GitHub Release при вызове из
  `release.yml`.
- Windows (GitHub Actions, `.github/workflows/windows-build.yml`, два
  job'а): `build` собирает автономный CLI-исполняемый файл (`.exe`, без
  GUI) через PyInstaller (`packaging/pyinstaller_entry.py`); `build-gui`
  собирает автономный GUI-исполняемый файл на **PyQt6** (`.exe`,
  `--windowed`) через PyInstaller (`packaging/windows_gui_entry.py`,
  иконка `packaging/windows/AnimeDlp.ico`) — в отличие от GTK4/libadwaita,
  у PyQt6 есть готовые pip-колёса под Windows, поэтому сборка полностью
  автоматическая, без MSYS2. Оба вызова PyInstaller получают
  `--copy-metadata anime-dlp` (тот же смысл, что и на macOS) и
  `--version-file` со сгенерированным на лету VSVersionInfo-ресурсом (шаг
  «Generate Windows version resource» — вручную собирает `.txt` в формате
  `PyInstaller.utils.win32.versioninfo`, без сторонних пакетов), поэтому у
  готовых `.exe` версия видна и в свойствах файла в Проводнике. Оба `.exe`
  прикрепляются к GitHub Release при вызове из `release.yml`. GTK-версию
  GUI на Windows всё ещё можно запустить из исходников вручную через MSYS2
  (`ANIME_DLP_GUI_BACKEND=gtk`, см. `WINDOWS.md`) — например, для
  разработки самого GTK-бэкенда.
- Flatpak — только для Linux (сборка через `flatpak.yml`). Готовых
  GTK4-пакетов для macOS в pip нет — их устанавливают через Homebrew (см.
  README → «Windows и macOS»).

Подробная инструкция по установке и использованию — в `README.md`.
