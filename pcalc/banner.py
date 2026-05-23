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


def print_banner(version: str, calc: str | None = None, installed: int = 0, updates: int = 0,
                 device_files: int = 0, device_unknown: int = 0):
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

    if calc:
        known = device_files - device_unknown
        status.append("  ·  ", style=theme.S_DIM)
        if device_files == 0:
            status.append("device empty", style=theme.S_DIM)
        elif device_unknown == 0:
            status.append(f"{device_files} files on device", style=theme.S_DIM)
        else:
            status.append(f"{device_files} files ({known} known, {device_unknown} unknown)", style="white")

    if updates > 0:
        status.append("  ·  ", style=theme.S_DIM)
        status.append(f"{updates} update{'s' if updates != 1 else ''} available", style=theme.S_WARNING)

    console.print(status)
    console.print()


def print_header(version: str, calc: str | None = None, device_files: int = 0, device_unknown: int = 0):
    """Print compact one-line header for subcommands."""
    line = Text("  ")
    line.append("PanCalc Tools ", style="bold white")
    line.append(f"v{version}", style=theme.S_ACCENT)
    line.append("  ·  ", style=theme.S_DIM)
    if calc:
        line.append(f"󰻟 {calc}", style=theme.S_SUCCESS)
        if device_files:
            known = device_files - device_unknown
            if device_unknown == 0:
                line.append(f"  ({device_files} files)", style=theme.S_DIM)
            else:
                line.append(f"  ({known}+{device_unknown} files)", style=theme.S_DIM)
    else:
        line.append("no calculator detected", style=theme.S_DIM)
    console.print(line)
    console.print(f"  [dim]{'─' * 44}[/]")
    console.print()