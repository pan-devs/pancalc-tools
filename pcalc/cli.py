"""
pcalc/cli.py — Entry point for PanCalc Tools CLI.
"""

import os
import click
from rich.console import Console
from rich.table import Table
from rich.text import Text
from rich.progress import Progress, BarColumn, DownloadColumn, TransferSpeedColumn, TimeRemainingColumn
from pcalc import theme

console = Console()

VERSION = "0.1.0"


# ---------------------------------------------------------------------------
# Global context
# ---------------------------------------------------------------------------

class AppContext:
    def __init__(self):
        self.yes   = False
        self.quiet = False
        self.plain = False

pass_ctx = click.make_pass_decorator(AppContext, ensure=True)


# ---------------------------------------------------------------------------
# Main group
# ---------------------------------------------------------------------------

@click.group(invoke_without_command=True, context_settings={"help_option_names": ["-h", "--help"]})
@click.option("-y", "--yes",   is_flag=True, help="Skip all confirmation prompts")
@click.option("-q", "--quiet", is_flag=True, help="Minimal output")
@click.option("--plain",       is_flag=True, help="No colors (useful in CI/scripts)")
@click.version_option(VERSION, "-v", "--version", prog_name="pcalc")
@click.pass_context
def cli(ctx, yes, quiet, plain):
    """PanCalc Tools — Package manager and developer toolkit for Casio Prizm."""
    ctx.ensure_object(AppContext)
    ctx.obj.yes   = yes
    ctx.obj.quiet = quiet
    ctx.obj.plain = plain

    if ctx.invoked_subcommand is None:
        from pcalc.banner import print_banner
        from pcalc.calculator import find_calculator
        from pcalc.installer import get_installed
        _calc = find_calculator()
        _installed = get_installed()
        print_banner(
            version=VERSION,
            calc=_calc.model if _calc else None,
            installed=len(_installed),
        )
        click.echo(ctx.get_help())
    else:
        if not quiet and not plain:
            from pcalc.banner import print_header
            from pcalc.calculator import find_calculator
            _calc = find_calculator()
            print_header(version=VERSION, calc=_calc.model if _calc else None)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _addin_table(addins: list[dict], title: str = "") -> Table:
    table = Table(
        title=title,
        show_header=True,
        header_style=theme.S_PRIMARY,
        border_style=theme.PRIMARY,
        show_lines=False,
        pad_edge=True,
    )
    table.add_column("ID",         style="bold white",   no_wrap=True)
    table.add_column("Name",       style="white")
    table.add_column("Author",     style=theme.S_DIM)
    table.add_column("Version",    style=theme.S_ACCENT, no_wrap=True)
    table.add_column("Category",   style="white")
    table.add_column("Compatible", style=theme.S_DIM)

    for a in addins:
        compat = ", ".join(a.get("compatible", []))
        table.add_row(
            a.get("id", ""),
            a.get("name", ""),
            a.get("author", ""),
            a.get("version", ""),
            a.get("category", ""),
            compat,
        )
    return table


def _registry_error(e: Exception) -> None:
    console.print(f"\n  [bold red]Error:[/] {e}")
    console.print(f"  [dim]Check your internet connection and try again.[/]\n")


def _confirm(app: AppContext, message: str) -> bool:
    """Ask for confirmation unless -y was passed."""
    if app.yes:
        return True
    return click.confirm(f"  {message}", default=False)


# ---------------------------------------------------------------------------
# Add-in management
# ---------------------------------------------------------------------------

@cli.command("list")
@click.option("--category", "-c", default=None, help="Filter by category")
@pass_ctx
def cmd_list(app, category):
    """List all available add-ins from the registry."""
    from pcalc import registry

    try:
        if category:
            addins = registry.filter_by_category(category)
            title = f"Add-ins — category: {category}"
        else:
            addins = registry.get_registry()
            title = "All add-ins"
    except RuntimeError as e:
        _registry_error(e)
        return

    if not addins:
        console.print(f"  [dim]No add-ins found.[/]")
        return

    console.print(_addin_table(addins, title=title))
    console.print(f"\n  [dim]{len(addins)} add-in{'s' if len(addins) != 1 else ''} found.[/]\n")


@cli.command("search")
@click.argument("query")
@pass_ctx
def cmd_search(app, query):
    """Search add-ins by name, tag, author or description."""
    from pcalc import registry

    try:
        addins = registry.search_registry(query)
    except RuntimeError as e:
        _registry_error(e)
        return

    if not addins:
        console.print(f"\n  [dim]No results for '[/][white]{query}[/][dim]'.[/]\n")
        return

    console.print(_addin_table(addins, title=f"Results for '{query}'"))
    console.print(f"\n  [dim]{len(addins)} result{'s' if len(addins) != 1 else ''} found.[/]\n")


@cli.command("info")
@click.argument("name")
@pass_ctx
def cmd_info(app, name):
    """Show full details of an add-in."""
    from pcalc import registry
    from pcalc.installer import is_installed

    try:
        addin = registry.get_addin(name)
    except RuntimeError as e:
        _registry_error(e)
        return

    if addin is None:
        console.print(f"\n  [bold red]Not found:[/] '{name}'\n")
        return

    console.print()
    title = Text()
    title.append(f"  {addin.get('name', '')} ", style="bold white")
    version_str = addin.get('version', '')
    if version_str and version_str != "latest":
        title.append(f"v{version_str}  ", style=theme.S_ACCENT)
    title.append(f"by {addin.get('author', '')}", style=theme.S_DIM)
    console.print(title)
    console.print(f"  [dim]{'─' * 44}[/]")

    desc = addin.get("description", "")
    if desc:
        console.print(f"\n  {desc}\n")

    installed_mark = f"[{theme.SUCCESS}]installed[/]" if is_installed(addin.get("id","")) else "[dim]not installed[/]"

    fields = [
        ("ID",          addin.get("id", "")),
        ("Status",      installed_mark),
        ("Category",    addin.get("category", "")),
        ("Compatible",  ", ".join(addin.get("compatible", []))),
        ("License",     addin.get("license", "unknown")),
        ("Size",        f"{addin.get('size_kb')} KiB" if addin.get("size_kb") else "unknown"),
        ("Tags",        ", ".join(addin.get("tags", []))),
        ("URL",         addin.get("url", "")),
        ("Download",    addin.get("download_url", "")),
    ]

    for label, value in fields:
        label_t = Text(f"  {label:<12}", style=theme.S_DIM)
        console.print(label_t, end="")
        console.print(value)

    console.print()


@cli.command("install")
@click.argument("names", nargs=-1, required=True)
@pass_ctx
def cmd_install(app, names):
    """Install one or more add-ins to the calculator."""
    from pcalc import registry
    from pcalc.calculator import require_calculator
    from pcalc.installer import install, is_installed

    # Resolve all add-ins, skipping already installed
    resolved = []
    for name in names:
        try:
            addin = registry.get_addin(name)
        except RuntimeError as e:
            _registry_error(e)
            return

        if addin is None:
            console.print(f"\n  [bold red]Not found:[/] '{name}'\n")
            return

        if is_installed(addin["id"]):
            console.print(f"  [dim]'{addin['name']}' is already installed, skipping.[/]")
            continue

        resolved.append(addin)

    if not resolved:
        console.print()
        return

    # Show summary and confirm once
    console.print()
    for addin in resolved:
        console.print(f"  [bold white]{addin['name']}[/] [dim]v{addin.get('version','')} by {addin.get('author','')}[/]")
    if not _confirm(app, f"Install {'this add-in' if len(resolved) == 1 else f'these {len(resolved)} add-ins'}?"):
        console.print(f"  [dim]Cancelled.[/]\n")
        return

    # Detect calculator once
    try:
        calc = require_calculator()
    except RuntimeError as e:
        console.print(f"\n  [bold red]Error:[/] {e}\n")
        return

    # Install each add-in sequentially
    for addin in resolved:
        with Progress(
            "[progress.description]{task.description}",
            BarColumn(bar_width=30, style=theme.PRIMARY, complete_style=theme.SUCCESS),
            DownloadColumn(),
            TransferSpeedColumn(),
            TimeRemainingColumn(),
            console=console,
            transient=True,
        ) as progress:
            dl_task = progress.add_task(f"  [{addin['name']}] Downloading...", total=None)

            def on_progress(downloaded, total):
                progress.update(dl_task, completed=downloaded, total=total or downloaded)

            write_task = None
            def on_write(filename, written, total):
                nonlocal write_task
                if write_task is None:
                    write_task = progress.add_task(f"  [{addin['name']}] Writing {filename}...", total=total)
                progress.update(write_task, completed=written, total=total, description=f"  [{addin['name']}] Writing {filename}...")

            try:
                dests = install(addin, calc, progress_callback=on_progress, write_callback=on_write)
            except RuntimeError as e:
                console.print(f"\n  [bold red]Error installing {addin['name']}:[/] {e}\n")
                continue

        file_list = ", ".join(str(d) for d in dests)
        console.print(f"  [bold {theme.SUCCESS}]✓[/] {addin['name']} installed to [dim]{file_list}[/]\n")


@cli.command("remove")
@click.argument("names", nargs=-1, required=True)
@pass_ctx
def cmd_remove(app, names):
    """Remove one or more add-ins from the calculator."""
    from pcalc.calculator import require_calculator
    from pcalc.installer import remove, get_installed

    installed = get_installed()

    # Resolve all by ID or name
    resolved = []
    for name in names:
        addin_id = None
        for aid, entry in installed.items():
            if aid.lower() == name.lower() or entry.get("name", "").lower() == name.lower():
                addin_id = aid
                entry_data = entry
                break

        if addin_id is None:
            console.print(f"\n  [bold red]Not installed:[/] '{name}'\n")
            return

        resolved.append((addin_id, entry_data))

    # Show summary and confirm once
    console.print()
    for _, entry in resolved:
        console.print(f"  [bold white]{entry['name']}[/] [dim]v{entry.get('version','')}[/]")
    if not _confirm(app, f"Remove {'this add-in' if len(resolved) == 1 else f'these {len(resolved)} add-ins'} from the calculator?"):
        console.print(f"  [dim]Cancelled.[/]\n")
        return

    # Detect calculator once
    try:
        calc = require_calculator()
    except RuntimeError as e:
        console.print(f"\n  [bold red]Error:[/] {e}\n")
        return

    # Remove each
    for addin_id, entry in resolved:
        try:
            remove(addin_id, calc)
        except RuntimeError as e:
            console.print(f"  [bold red]Error removing {entry['name']}:[/] {e}\n")
            continue

        console.print(f"  [bold {theme.SUCCESS}]✓[/] {entry['name']} removed.\n")


@cli.command("installed")
@pass_ctx
def cmd_installed(app):
    """List add-ins currently installed on the calculator."""
    from pcalc.installer import get_installed

    installed = get_installed()

    if not installed:
        console.print(f"\n  [dim]No add-ins installed.[/]\n")
        return

    table = Table(
        show_header=True,
        header_style=theme.S_PRIMARY,
        border_style=theme.PRIMARY,
        pad_edge=True,
    )
    table.add_column("ID",       style="bold white", no_wrap=True)
    table.add_column("Name",     style="white")
    table.add_column("Version",  style=theme.S_ACCENT)
    table.add_column("Files",    style=theme.S_DIM)

    for aid, entry in installed.items():
        files = entry.get("files", [{"filename": entry.get("filename", f"{aid}.g3a")}])
        file_str = files[0]["filename"]
        if len(files) > 1:
            file_str += f" +{len(files)-1} more"
        table.add_row(
            aid,
            entry.get("name", ""),
            entry.get("version", ""),
            file_str,
        )

    console.print(table)
    console.print(f"\n  [dim]{len(installed)} add-in{'s' if len(installed) != 1 else ''} installed.[/]\n")


# ---------------------------------------------------------------------------
# Calculator
# ---------------------------------------------------------------------------

@cli.command("calc")
@click.option("--storage", is_flag=True, help="Show free/used storage")
@pass_ctx
def cmd_calc(app, storage):
    """Detect connected calculator and show device info."""
    from pcalc.calculator import find_calculator

    calc = find_calculator()
    if calc is None:
        console.print(f"\n  [dim]No calculator detected.[/]")
        console.print(f"  [dim]Connect via USB and enable mass storage mode (F1).[/]\n")
        return

    console.print()
    console.print(f"  [bold white]{calc.model}[/]  [bold {theme.SUCCESS}]connected[/]")
    console.print(f"  [dim]Mount:[/] {calc.mount_path}")

    if storage:
        used_pct = (calc.storage_used / calc.storage_total * 100) if calc.storage_total else 0
        console.print(f"  [dim]Storage:[/] {calc.storage_used_mb:.1f} MB used / {calc.storage_total_mb:.1f} MB total ({used_pct:.0f}%)")

    console.print()


# ---------------------------------------------------------------------------
# Developer tools
# ---------------------------------------------------------------------------

@cli.command("convert")
@click.argument("file", type=click.Path(exists=True))
@click.option("-o", "--output", default=None, help="Output file path")
@click.option("--bits", "-b", type=click.Choice(["3", "16"]), default="16",
              show_default=True, help="Color depth (images only)")
@click.option("--decode", is_flag=True, help="Decode .g3p → PNG")
@click.option("--split", type=click.Choice(["auto", "on", "off"]), default="auto",
              show_default=True, help="Split tall images into strips")
@click.option("--overlap", type=int, default=16, show_default=True,
              help="Overlap in pixels between strips")
@pass_ctx
def cmd_convert(app, file, output, bits, decode, split, overlap):
    """Convert files: image→G3P, PDF→TXT, DOCX→TXT."""
    from pcalc.converter import convert_image, decode_image

    if decode:
        if not output:
            base = os.path.splitext(file)[0]
            output = f"{base}_decoded.png"
        decode_image(file, output)
    else:
        if not output:
            base = os.path.splitext(file)[0]
            output = f"{base}.g3p"
        convert_image(file, output, int(bits), split, overlap)


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


@cli.command("eject")
@pass_ctx
def cmd_eject(app):
    """Safely unmount the calculator before disconnecting."""
    import platform
    import subprocess
    from pcalc.calculator import find_calculator

    calc = find_calculator()
    if calc is None:
        console.print(f"\n  [dim]No calculator detected.[/]\n")
        return

    mount = str(calc.mount_path)
    system = platform.system()

    console.print(f"\n  Ejecting [bold white]{calc.model}[/] at [dim]{mount}[/]...", end="")

    try:
        if system == "Linux":
            # Use udisksctl for proper eject (unmount + power-off, no sudo needed)
            import re
            # Get the block device from mount path
            result = subprocess.run(
                ["findmnt", "-n", "-o", "SOURCE", mount],
                capture_output=True, text=True
            )
            device = result.stdout.strip()  # e.g. /dev/sdb1
            parent = re.sub(r'p?\d+$', '', device)  # e.g. /dev/sdb

            subprocess.run(["udisksctl", "unmount", "-b", device], check=True, capture_output=True)
            subprocess.run(["udisksctl", "power-off", "-b", parent], check=True, capture_output=True)
        elif system == "Darwin":
            subprocess.run(["diskutil", "unmount", mount], check=True, capture_output=True)
            subprocess.run(["diskutil", "eject", mount], capture_output=True)
        elif system == "Windows":
            try:
                import win32api
                import win32file
                drive = str(calc.mount_path)[:2]  # e.g. "E:"
                handle = win32file.CreateFile(
                    f"\\.\\{drive}",
                    win32file.GENERIC_READ,
                    win32file.FILE_SHARE_READ | win32file.FILE_SHARE_WRITE,
                    None, win32file.OPEN_EXISTING, 0, None
                )
                win32api.DeviceIoControl(handle, 0x2D4808, None, 0)  # IOCTL_STORAGE_EJECT_MEDIA
                handle.close()
            except ImportError:
                console.print(f" [bold {theme.WARNING}]manual eject required[/]")
                console.print(f"  [dim]pywin32 not installed. Eject manually from Windows Explorer[/]")
                console.print(f"  [dim]or install with: pip install pancalc-tools[windows][/]\n")
                return
        else:
            console.print(f" [bold {theme.WARNING}]not supported[/]")
            console.print(f"  [dim]Automatic eject is not supported on this OS.")
            console.print(f"  Please eject the calculator manually before disconnecting.[/]\n")
            return
        console.print(f" [bold {theme.SUCCESS}]done[/]")
        console.print(f"  [dim]Safe to disconnect.[/]\n")
    except subprocess.CalledProcessError:
        console.print(f" [bold red]failed[/]")
        console.print(f"  [bold red]Error:[/] Could not eject automatically.")
        console.print(f"  [dim]Please eject the calculator manually before disconnecting.[/]\n")

@cli.command("update-registry")
@pass_ctx
def cmd_update_registry(app):
    """Force a refresh of the add-in registry."""
    from pcalc import registry

    console.print(f"\n  Updating registry...", end="")
    try:
        addins = registry.get_registry(force=True)
        console.print(f" [bold {theme.SUCCESS}]done[/]")
        console.print(f"  [dim]{len(addins)} add-ins loaded.[/]\n")
    except RuntimeError as e:
        console.print(f" [bold red]failed[/]")
        _registry_error(e)