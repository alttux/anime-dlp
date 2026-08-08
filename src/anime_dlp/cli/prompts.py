import re

from rich.prompt import IntPrompt, Prompt

from anime_dlp.cli.display import console

_RANGE_RE = re.compile(r"^(\d+)-(\d+)$")


def ask_title() -> str:
    return Prompt.ask("\n[bold yellow]Введите название аниме[/]")


def ask_anime_choice(count: int) -> int:
    return IntPrompt.ask(
        f"\n[green]Выберите номер аниме[/]",
        default=1,
    ) - 1


def ask_translation_choice(count: int) -> int:
    return IntPrompt.ask(
        f"\n[green]Выберите номер озвучки[/]",
        default=1,
    ) - 1


def ask_episode(series_count: int) -> int | str | tuple[int, int]:
    console.print(
        f"\n[bold]Доступны серии с [green]1[/] по [green]{series_count}[/][/]"
    )
    while True:
        answer = Prompt.ask(
            "[yellow]Введите номер серии, диапазон (например [bold]5-10[/]) "
            "или [bold]all[/] для скачивания всех[/]"
        )
        if answer.lower() == "all":
            return "all"

        match = _RANGE_RE.match(answer.strip())
        if match:
            start, end = int(match.group(1)), int(match.group(2))
            if start > end:
                console.print("[red]Начало диапазона больше конца[/]")
            elif start < 1 or end > series_count:
                console.print(f"[red]Диапазон должен быть в пределах 1-{series_count}[/]")
            else:
                return start, end
            continue

        try:
            ep = int(answer)
            if 1 <= ep <= series_count:
                return ep
            console.print(f"[red]Введите число от 1 до {series_count}[/]")
        except ValueError:
            console.print("[red]Введите число, диапазон вида 5-10 или 'all'[/]")
