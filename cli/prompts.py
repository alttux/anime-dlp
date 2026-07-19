from rich.prompt import IntPrompt, Prompt

from cli.display import console


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


def ask_episode(series_count: int) -> int | str:
    console.print(
        f"\n[bold]Доступны серии с [green]1[/] по [green]{series_count}[/][/]"
    )
    while True:
        answer = Prompt.ask(
            "[yellow]Введите номер серии (или [bold]all[/] для скачивания всех)[/]"
        )
        if answer.lower() == "all":
            return "all"
        try:
            ep = int(answer)
            if 1 <= ep <= series_count:
                return ep
            console.print(f"[red]Введите число от 1 до {series_count}[/]")
        except ValueError:
            console.print("[red]Введите число или 'all'[/]")
