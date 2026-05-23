import os
from rich.console import Console
from rich.text import Text
from pcalc import theme

console = Console()

ASCII_MIN_WIDTH = 95

PANDEVS_ASCII = r"""
 ███████████    █████████   ██████   █████ ██████████   ██████████ █████   █████  █████████ 
▒▒███▒▒▒▒▒███  ███▒▒▒▒▒███ ▒▒██████ ▒▒███ ▒▒███▒▒▒▒███ ▒▒███▒▒▒▒▒█▒▒███   ▒▒███  ███▒▒▒▒▒███
 ▒███    ▒███ ▒███    ▒███  ▒███▒███ ▒███  ▒███   ▒▒███ ▒███  █ ▒  ▒███    ▒███ ▒███    ▒▒▒ 
 ▒██████████  ▒███████████  ▒███▒▒███▒███  ▒███    ▒███ ▒██████    ▒███    ▒███ ▒▒█████████ 
 ▒███▒▒▒▒▒▒   ▒███▒▒▒▒▒███  ▒███ ▒▒██████  ▒███    ▒███ ▒███▒▒█    ▒▒███   ███   ▒▒▒▒▒▒▒▒███
 ▒███         ▒███    ▒███  ▒███  ▒▒█████  ▒███    ███  ▒███ ▒   █  ▒▒▒█████▒    ███    ▒███
 █████        █████   █████ █████  ▒▒█████ ██████████   ██████████    ▒▒███     ▒▒█████████ 
▒▒▒▒▒        ▒▒▒▒▒   ▒▒▒▒▒ ▒▒▒▒▒    ▒▒▒▒▒ ▒▒▒▒▒▒▒▒▒▒   ▒▒▒▒▒▒▒▒▒▒      ▒▒▒       ▒▒▒▒▒▒▒▒▒  
"""

PDEVS_ASCII = r"""
███████████  ██████████   ██████████ █████   █████  █████████ 
▒▒███▒▒▒▒▒███▒▒███▒▒▒▒███ ▒▒███▒▒▒▒▒█▒▒███   ▒▒███  ███▒▒▒▒▒███
 ▒███    ▒███ ▒███   ▒▒███ ▒███  █ ▒  ▒███    ▒███ ▒███    ▒▒▒ 
 ▒██████████  ▒███    ▒███ ▒██████    ▒███    ▒███ ▒▒█████████ 
 ▒███▒▒▒▒▒▒   ▒███    ▒███ ▒███▒▒█    ▒▒███   ███   ▒▒▒▒▒▒▒▒███
 ▒███         ▒███    ███  ▒███ ▒   █  ▒▒▒█████▒    ███    ▒███
 █████        ██████████   ██████████    ▒▒███     ▒▒█████████ 
▒▒▒▒▒        ▒▒▒▒▒▒▒▒▒▒   ▒▒▒▒▒▒▒▒▒▒      ▒▒▒       ▒▒▒▒▒▒▒▒▒  
"""


def _terminal_width() -> int:
    try:
        return os.get_terminal_size().columns
    except OSError:
        return 80


def print_banner(version: str, calc: str | None = None, installed: int = 0, updates: int = 0):
    """Print the PanCalc Tools banner with status info."""

    if _terminal_width() >= ASCII_MIN_WIDTH:
        console.print(PANDEVS_ASCII, style=theme.S_PRIMARY, highlight=False)
    else:
        console.print(PDEVS_ASCII, style=theme.S_PRIMARY, highlight=False)

    # Product name + version line
    title = Text()
    title.append("  PanCalc Tools ", style="bold white")
    title.append(f"v{version}", style=theme.S_ACCENT)
    title.append("  ·  ", style=theme.S_DIM)
    title.append("package manager for Casio Prizm", style=theme.S_DIM)
    console.print(title)

    # Status line
    status = Text("  ")
    if calc:
        status.append(f"󰻟 {calc}", style=theme.S_SUCCESS)
    else:
        status.append("no calculator detected", style=theme.S_DIM)

    status.append("  ·  ", style=theme.S_DIM)
    status.append(f"{installed} add-ins installed", style="white")

    if updates > 0:
        status.append("  ·  ", style=theme.S_DIM)
        status.append(f"{updates} update{'s' if updates != 1 else ''} available", style=theme.S_WARNING)

    console.print(status)
    console.print()


def print_header(version: str, calc: str | None = None):
    """Print compact one-line header for subcommands."""
    line = Text("  ")
    line.append("PanCalc Tools ", style="bold white")
    line.append(f"v{version}", style=theme.S_ACCENT)
    line.append("  ·  ", style=theme.S_DIM)
    if calc:
        line.append(f"󰻟 {calc}", style=theme.S_SUCCESS)
    else:
        line.append("no calculator detected", style=theme.S_DIM)
    console.print(line)
    console.print(f"  [dim]{'─' * 44}[/]")
    console.print()