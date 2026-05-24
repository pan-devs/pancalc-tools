"""
pcalc/cli.py — Entry point for PanCalc Tools CLI.
"""

import os
from pathlib import Path
import click
from rich.console import Console
from rich.table import Table
from rich.text import Text
from rich.progress import Progress, ProgressColumn, DownloadColumn, TransferSpeedColumn, TimeRemainingColumn
from pcalc import theme

console = Console()


class AsciiBarColumn(ProgressColumn):
    """Progress bar using the same chars as the banner (▓/░) with theme colours."""

    def __init__(self, bar_width: int = 30):
        self.bar_width = bar_width
        super().__init__()

    def render(self, task) -> Text:
        if task.total is None:
            filled = 0
        else:
            completed = task.completed / max(task.total, 1)
            filled = min(int(self.bar_width * completed), self.bar_width)
        result = Text()
        if filled:
            result.append("▓" * filled, style=theme.SUCCESS)
        if self.bar_width - filled:
            result.append("░" * (self.bar_width - filled), style=theme.PRIMARY)
        return result

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
        from pcalc.installer import get_installed, walk_calc, count_calc_files, iter_calc_files
        _calc = find_calculator()
        _installed = get_installed()
        if _calc:
            try:
                from pcalc import registry
                _addins = registry.get_registry()
                _entries = walk_calc(_calc, _addins)
                _dcount = count_calc_files(_entries)
                _unk = sum(1 for f in iter_calc_files(_entries) if f.addin is None)
            except RuntimeError:
                _dcount = _unk = 0
        else:
            _dcount = _unk = 0
        print_banner(
            version=VERSION,
            calc=_calc.model if _calc else None,
            installed=len(_installed),
            device_files=_dcount,
            device_unknown=_unk,
        )
        from pcalc.tui import PanCalcApp
        PanCalcApp().run()
    else:
        if not quiet and not plain:
            from pcalc.banner import print_header
            from pcalc.calculator import find_calculator
            _calc = find_calculator()
            _dcount = _unk = 0
            if _calc:
                try:
                    from pcalc import registry
                    from pcalc.installer import walk_calc, count_calc_files, iter_calc_files
                    _addins = registry.get_registry()
                    _entries = walk_calc(_calc, _addins)
                    _dcount = count_calc_files(_entries)
                    _unk = sum(1 for f in iter_calc_files(_entries) if f.addin is None)
                except RuntimeError:
                    pass
            print_header(version=VERSION, calc=_calc.model if _calc else None,
                         device_files=_dcount, device_unknown=_unk)


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


def _fail(msg: str, code: int = 1):
    """Print message and exit non-zero (for && chaining)."""
    console.print(f"\n  [bold red]Error:[/] {msg}\n")
    raise SystemExit(code)


def _no_calc():
    """Exit when no calculator is detected."""
    console.print(f"\n  [dim]No calculator detected.[/]")
    console.print(f"  [dim]Connect via USB and enable mass storage mode (F1).[/]\n")
    raise SystemExit(1)


def _confirm(app: AppContext, message: str) -> bool:
    """Ask for confirmation unless -y was passed."""
    if app.yes:
        return True
    return click.confirm(f"  {message}", default=False)


# ---------------------------------------------------------------------------
# TUI helpers
# ---------------------------------------------------------------------------


def _eject(calc) -> None:
    """Safely unmount the calculator before disconnecting."""
    import platform
    import subprocess

    mount = str(calc.mount_path)
    system = platform.system()

    console.print(f"\n  Ejecting [bold white]{calc.model}[/] at [dim]{mount}[/]...", end="")

    try:
        if system == "Linux":
            import re
            result = subprocess.run(
                ["findmnt", "-n", "-o", "SOURCE", mount],
                capture_output=True, text=True
            )
            device = result.stdout.strip()
            parent = re.sub(r'p?\d+$', '', device)
            subprocess.run(["udisksctl", "unmount", "-b", device], check=True, capture_output=True)
            subprocess.run(["udisksctl", "power-off", "-b", parent], check=True, capture_output=True)
        elif system == "Darwin":
            subprocess.run(["diskutil", "unmount", mount], check=True, capture_output=True)
            subprocess.run(["diskutil", "eject", mount], capture_output=True)
        elif system == "Windows":
            try:
                import win32api
                import win32file
                drive = str(calc.mount_path)[:2]
                handle = win32file.CreateFile(
                    f"\\.\\{drive}",
                    win32file.GENERIC_READ,
                    win32file.FILE_SHARE_READ | win32file.FILE_SHARE_WRITE,
                    None, win32file.OPEN_EXISTING, 0, None
                )
                win32api.DeviceIoControl(handle, 0x2D4808, None, 0)
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


def _cmd_install_tui(names: list[str], force: bool = False) -> None:
    """Install add-ins from the TUI (simplified, no progress bars).

    Args:
        names: Add-in names/IDs to install.
        force: If True, skip the 'is_installed' check.
    """
    from pcalc import registry
    from pcalc.calculator import require_calculator
    from pcalc.installer import install, is_installed

    for name in names:
        try:
            addin = registry.get_addin(name)
        except RuntimeError as e:
            console.print(f"\n  [bold red]Error:[/] {e}\n")
            continue
        if addin is None:
            console.print(f"\n  [bold red]Error:[/] Add-in '{name}' not found.\n")
            continue
        if not force and is_installed(addin["id"]):
            console.print(f"  [dim]'{addin['name']}' is already installed, skipping.[/]")
            continue
        try:
            calc = require_calculator()
        except RuntimeError as e:
            console.print(f"\n  [bold red]Error:[/] {e}\n")
            return
        try:
            install(addin, calc)
            console.print(f"  [bold {theme.SUCCESS}]✓[/] {addin['name']} installed.\n")
        except RuntimeError as e:
            console.print(f"\n  [bold red]Error installing {addin['name']}:[/] {e}\n")


def _cmd_remove_tui(names: list[str]) -> None:
    """Remove add-ins from the TUI (simplified).

    Handles both installed.json-tracked add-ins and device-scanned add-ins.
    """
    from pcalc.calculator import require_calculator
    from pcalc.installer import remove, get_installed, walk_calc

    # Try installed.json first, then fall back to device scan
    installed = get_installed()
    addin_ids = []
    for name in names:
        found = False
        for aid, entry in installed.items():
            if aid.lower() == name.lower() or entry.get("name", "").lower() == name.lower():
                addin_ids.append((aid, entry.get("name", aid)))
                found = True
                break
        if not found:
            from pcalc import registry
            try:
                calc = require_calculator()
                addins = registry.get_registry()
                entries = [e for e in walk_calc(calc, addins) if e.addin and e.addin.get("id") == name]
                if entries:
                    addin_ids.append((name, entries[0].addin.get("name", name)))
                    found = True
            except RuntimeError:
                pass
            if not found:
                addin_ids.append((name, name))
    try:
        calc = require_calculator()
    except RuntimeError as e:
        console.print(f"\n  [bold red]Error:[/] {e}\n")
        return
    for aid, display_name in addin_ids:
        try:
            remove(aid, calc)
            console.print(f"  [bold {theme.SUCCESS}]✓[/] {display_name} removed.\n")
        except RuntimeError as e:
            console.print(f"\n  [bold red]Error removing {display_name}:[/] {e}\n")


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
    from pcalc.installer import is_installed, scan_device

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

    cached = is_installed(addin.get("id", ""))
    # Check device for actual files
    on_device = False
    from pcalc.calculator import find_calculator
    calc = find_calculator()
    if calc:
        device_files = scan_device(calc)
        addin_files = addin.get("files", [])
        if not addin_files:
            legacy = addin.get("zip_file") or addin.get("download_url", "").rsplit("/", 1)[-1]
            addin_files = [{"filename": legacy}]
        on_device = any(
            df.filename.lower() == f.get("filename", "").lower()
            for df in device_files for f in addin_files
        )

    if cached:
        status_text = f"[{theme.SUCCESS}]tracked as installed[/]"
        if on_device:
            status_text += f"  [{theme.SUCCESS}]✓ on device[/]"
        else:
            status_text += f"  [{theme.WARNING}]not on device[/]"
    elif on_device:
        status_text = f"[{theme.SUCCESS}]on device[/]  [dim](not tracked)[/]"
    else:
        status_text = "[dim]not installed[/]"

    fields = [
        ("ID",          addin.get("id", "")),
        ("Status",      status_text),
        ("Category",    addin.get("category", "")),
        ("Compatible",  ", ".join(addin.get("compatible", []))),
        ("License",     addin.get("license", "unknown")),
        ("Size",        f"{addin.get('size_kb')} KiB" if addin.get("size_kb") else "unknown"),
        ("Tags",        ", ".join(addin.get("tags", []))),
        ("URL",         addin.get("url", "")),
    ]

    for label, value in fields:
        label_t = Text(f"  {label:<12}", style=theme.S_DIM)
        console.print(label_t, end="")
        console.print(value)

    console.print()


@cli.command("install")
@click.argument("names", nargs=-1, required=True)
@click.option("--overwrite", is_flag=True, help="Overwrite existing files without asking")
@pass_ctx
def cmd_install(app, names, overwrite):
    """Install one or more add-ins to the calculator."""
    from pcalc import registry
    from pcalc.calculator import require_calculator
    from pcalc.installer import install, is_installed, _get_addin_files, _resolve_file_name

    # Resolve all add-ins, skipping already installed
    resolved = []
    for name in names:
        try:
            addin = registry.get_addin(name)
        except RuntimeError as e:
            _registry_error(e)
            raise SystemExit(1)

        if addin is None:
            _fail(f"Add-in '{name}' not found.")

        if is_installed(addin["id"]):
            console.print(f"  [dim]'{addin['name']}' is already tracked as installed, skipping.[/]")
            continue

        resolved.append(addin)

    if not resolved:
        console.print()
        raise SystemExit(1)

    # Show summary and confirm once
    console.print()
    for addin in resolved:
        console.print(f"  [bold white]{addin['name']}[/] [dim]v{addin.get('version','')} by {addin.get('author','')}[/]")
    if not _confirm(app, f"Install {'this add-in' if len(resolved) == 1 else f'these {len(resolved)} add-ins'}?"):
        console.print(f"  [dim]Cancelled.[/]\n")
        raise SystemExit(1)

    # Detect calculator once
    try:
        calc = require_calculator()
    except RuntimeError as e:
        _fail(str(e))

    # Install each add-in sequentially
    for addin in resolved:
        # Check for existing files on device
        skip_files: set[str] = set()
        for f_info in _get_addin_files(addin):
            filename = _resolve_file_name(f_info, addin["id"])
            dest = calc.mount_path / filename
            try:
                file_exists = dest.exists()
            except OSError:
                file_exists = False
            if file_exists:
                if app.yes or overwrite:
                    continue
                if not _confirm(app, f"File '{filename}' already exists on device. Overwrite?"):
                    console.print(f"  [dim]Skipping {filename}.[/]")
                    skip_files.add(filename)

        if skip_files and len(skip_files) == len(_get_addin_files(addin)):
            console.print(f"  [dim]All files skipped for '{addin['name']}'.[/]\n")
            continue

        with Progress(
            "[progress.description]{task.description}",
            AsciiBarColumn(bar_width=30),
            DownloadColumn(),
            TransferSpeedColumn(),
            TimeRemainingColumn(),
            console=console,
            transient=True,
        ) as progress:
            dl_task = progress.add_task(
                f"  [{addin['name']}] Downloading...", total=None)

            def on_progress(downloaded, total, label=""):
                if label:
                    progress.update(dl_task, completed=downloaded, total=total or downloaded,
                                    description=f"  [{addin['name']}] Downloading {label}")
                else:
                    progress.update(dl_task, completed=downloaded, total=total or downloaded)

            write_task = None
            def on_write(filename, written, total):
                nonlocal write_task
                if write_task is None:
                    write_task = progress.add_task(
                        f"  [{addin['name']}] Writing {filename}...", total=total)
                progress.update(write_task, completed=written, total=total,
                                description=f"  [{addin['name']}] Writing {filename}...")

            try:
                dests = install(addin, calc, progress_callback=on_progress,
                                write_callback=on_write, skip_files=skip_files)
            except RuntimeError as e:
                console.print(f"\n  [bold red]Error installing {addin['name']}:[/] {e}\n")
                continue

        file_list = ", ".join(str(d) for d in dests)
        if file_list:
            console.print(f"  [bold {theme.SUCCESS}]✓[/] {addin['name']} installed to [dim]{file_list}[/]\n")


def _cmd_remove_impl(app, names):
    """Shared implementation for 'remove' and 'rm' commands."""
    from pcalc.calculator import require_calculator
    from pcalc.installer import remove, get_installed, walk_calc

    installed = get_installed()

    # Separate addin names from path names
    addin_names = []
    path_names = []
    for name in names:
        # Check if it matches an installed addin
        found = False
        for aid, entry in installed.items():
            if aid.lower() == name.lower() or entry.get("name", "").lower() == name.lower():
                addin_names.append((aid, entry))
                found = True
                break
        if not found:
            path_names.append(name)

    failed_any = False

    # --- Remove addins (current behavior) ---
    if addin_names:
        console.print()
        for _, entry in addin_names:
            console.print(f"  [bold white]{entry['name']}[/] [dim]v{entry.get('version','')}[/]")
        if not _confirm(app, f"Remove {'this add-in' if len(addin_names) == 1 else f'these {len(addin_names)} add-ins'} from the calculator?"):
            console.print(f"  [dim]Cancelled (add-ins).[/]\n")
        else:
            try:
                calc = require_calculator()
            except RuntimeError as e:
                console.print(f"\n  [bold red]Error:[/] {e}\n")
                failed_any = True
            else:
                for addin_id, entry in addin_names:
                    try:
                        remove(addin_id, calc)
                        console.print(f"  [bold {theme.SUCCESS}]✓[/] {entry['name']} removed.\n")
                    except RuntimeError as e:
                        console.print(f"  [bold red]Error removing {entry['name']}:[/] {e}\n")
                        failed_any = True

    # --- Remove paths (non-addin files/dirs) ---
    if path_names:
        try:
            calc = require_calculator()
        except RuntimeError as e:
            console.print(f"\n  [bold red]Error:[/] {e}\n")
            raise SystemExit(1)

        mount = calc.mount_path
        resolved_paths = []
        for p in path_names:
            full = (mount / p).resolve()
            if not full.exists():
                console.print(f"  [bold red]Not found:[/] '{p}'")
                failed_any = True
                continue
            resolved_paths.append((p, full))

        if not resolved_paths:
            raise SystemExit(1 if failed_any else 0)

        # Confirm deletion
        console.print()
        for p, full in resolved_paths:
            if full.is_dir():
                console.print(f"  [bold white]{p}/[/] [dim](directory, recursive)[/]")
            else:
                size_str = f"{full.stat().st_size/1024:.1f} KiB" if full.stat().st_size < 1024*1024 else f"{full.stat().st_size/(1024*1024):.1f} MiB"
                console.print(f"  [bold white]{p}[/]  [dim]{size_str}[/]")
        if not _confirm(app, f"Delete {'this file' if len(resolved_paths) == 1 else 'these items'} from calculator?"):
            console.print(f"  [dim]Cancelled.[/]\n")
            raise SystemExit(1 if failed_any else 0)

        import shutil
        for p, full in resolved_paths:
            try:
                if full.is_dir():
                    shutil.rmtree(full)
                    console.print(f"  [bold {theme.SUCCESS}]✓[/] {p}/ removed.\n")
                else:
                    full.unlink()
                    console.print(f"  [bold {theme.SUCCESS}]✓[/] {p} removed.\n")
            except OSError as e:
                console.print(f"  [bold red]Error removing {p}:[/] {e}\n")
                failed_any = True

    if failed_any:
        raise SystemExit(1)


@cli.command("remove")
@click.argument("names", nargs=-1, required=True)
@pass_ctx
def cmd_remove(app, names):
    """Remove one or more add-ins, files or directories from the calculator.

    Accepts add-in names (from the install registry) or paths
    relative to the calculator mount (e.g. pthings/g3p/foto.g3p).
    """
    _cmd_remove_impl(app, names)


@cli.command("rm", hidden=True)
@click.argument("names", nargs=-1, required=True)
@pass_ctx
def cmd_rm(app, names):
    """Alias for 'remove'."""
    _cmd_remove_impl(app, names)


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

_SYSTEM_DIRS = {"@mainmem", "@backup", "@save_f"}


def _render_tree(entries, indent=0):
    """Render a list of CalcEntry as an indented tree. Yields (rel_path, line) tuples."""
    for i, e in enumerate(entries):
        is_last = i == len(entries) - 1
        prefix = "└── " if is_last else "├── "
        pad = "    " if is_last else "│   "
        if indent == 0:
            prefix = ""
            pad = ""

        if e.is_dir:
            style = theme.S_DIM if e.name.lower() in _SYSTEM_DIRS else "bold white"
            yield (e.rel_path, f"{'  ' * indent}{prefix}[{style}]{e.name}/[/]")
            if e.children:
                yield from _render_tree(e.children, indent + 1)
        else:
            size_str = f"{e.size/1024:.1f} KiB" if e.size < 1024*1024 else f"{e.size/(1024*1024):.1f} MiB"
            if e.addin:
                info = f"  [dim]{e.addin['name']}[/]"
            else:
                info = ""
            yield (e.rel_path, f"{'  ' * indent}{prefix}{e.name}  [dim]{size_str}[/]{info}")


def _show_calc_info(app, storage):
    """Shared implementation for 'catch' and 'calc' commands."""
    from pcalc.calculator import find_calculator
    from pcalc.installer import walk_calc, count_calc_files
    from pcalc import registry

    calc = find_calculator()
    if calc is None:
        _no_calc()

    console.print()
    console.print(f"  [bold white]{calc.model}[/]  [bold {theme.SUCCESS}]connected[/]")
    console.print(f"  [dim]Mount:[/] {calc.mount_path}")

    used_pct = (calc.storage_used / calc.storage_total * 100) if calc.storage_total else 0
    console.print(f"  [dim]Storage:[/] {calc.storage_used_mb:.1f} MB used / {calc.storage_total_mb:.1f} MB total ({used_pct:.0f}%)")

    try:
        addins = registry.get_registry()
        entries = walk_calc(calc, addins)
    except RuntimeError:
        entries = []

    if entries:
        from pcalc.installer import iter_calc_files
        total_files = count_calc_files(entries)
        known = sum(1 for _ in iter_calc_files(entries) if _.addin)
        unknown = total_files - known
        console.print()
        console.print(f"  [dim]Contents ({total_files} files, {known} known, {unknown} unknown):[/]")
        for rel_path, line in _render_tree(entries):
            console.print(f"  {line}")
    else:
        console.print(f"\n  [dim]No files found on device.[/]")

    console.print()


@cli.command("catch")
@click.option("--storage", is_flag=True, help="Show free/used storage")
@pass_ctx
def cmd_catch(app, storage):
    """Detect connected calculator and show device info."""
    _show_calc_info(app, storage)


@cli.command("calc", hidden=True)
@click.option("--storage", is_flag=True, help="Show free/used storage")
@pass_ctx
def cmd_calc(app, storage):
    """Alias for 'catch'."""
    _show_calc_info(app, storage)


# ---------------------------------------------------------------------------
# Developer tools
# ---------------------------------------------------------------------------

CONVERT_DIR   = Path(__file__).parent.parent / "convert"
CONVERTED_DIR = Path(__file__).parent.parent / "converted"

_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tiff"}
_DOC_EXT   = {".pdf", ".docx"}
_G3P_EXT   = {".g3p"}

_INPUT_DIRS = {}
for e in _IMAGE_EXT:  _INPUT_DIRS[e] = "images"
for e in _DOC_EXT:    _INPUT_DIRS[e] = "documents"
for e in _G3P_EXT:    _INPUT_DIRS[e] = "g3p"

_OUTPUT_DIRS = {
    "images":    "g3p",
    "documents": "txt",
    "g3p":       "images",
}


def _resolve_convert_path(file: str, decode: bool) -> tuple[Path, str]:
    """Resolve input file path and its category dir name.

    Returns (resolved_path, category) where category is 'images', 'documents' or 'g3p'.
    """
    path = Path(file)
    ext  = path.suffix.lower()

    # Absolute or existing → use as-is, infer category from ext
    if path.is_absolute():
        if not path.exists():
            raise click.BadArgumentUsage(f"File not found: {file}")
        cat = _INPUT_DIRS.get(ext, "images")
        return path, cat

    # Search in the corresponding input dir first, then current dir
    for search_dir in [_INPUT_DIRS.get(ext, "images"), None]:
        if search_dir:
            candidate = CONVERT_DIR / search_dir / path
            if candidate.exists():
                return candidate, search_dir
        # Fallback to cwd
        if path.exists():
            cat = _INPUT_DIRS.get(ext, "images")
            return path.resolve(), cat

    raise click.BadArgumentUsage(
        f"File not found: {file}\n"
        f"  Looked in: {CONVERT_DIR / _INPUT_DIRS.get(ext, 'images') / path}\n"
        f"         or: {path.resolve()}"
    )


def _auto_output_path(input_path: Path, category: str, decode: bool, filename: str) -> Path:
    """Generate output path when -o is not given."""
    base = input_path.stem
    out_dir = CONVERTED_DIR / _OUTPUT_DIRS[category]
    out_dir.mkdir(parents=True, exist_ok=True)

    if decode:
        return out_dir / f"{base}_decoded.png"
    if category == "documents":
        return out_dir / f"{base}.txt"
    return out_dir / f"{base}.g3p"


@cli.command("convert")
@click.argument("file")
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
    """Convert files: image→G3P, PDF/DOCX→G3P or TXT, G3P→PNG.

    Puts output under converted/ next to convert/.

    Examples:
      pcalc convert photo.jpg        → converted/g3p/photo.g3p
      pcalc convert doc.pdf          → (prompts g3p or txt)
      pcalc convert photo.g3p -d     → converted/images/photo_decoded.png
    """
    from pcalc.converter import convert_image, decode_image, convert_text, convert_document_g3p

    input_path, category = _resolve_convert_path(file, decode)

    if decode:
        if not output:
            output = str(_auto_output_path(input_path, category, decode, file))
        decode_image(str(input_path), output)
        console.print(f"  [bold {theme.SUCCESS}]✓[/] {file} → [dim]{output}[/]")
    elif category == "documents":
        if app.yes:
            mode = "both"
        else:
            console.print(f"\n  Convert [bold white]{file}[/] as:")
            console.print(f"    [bold {theme.SUCCESS}]1[/] — G3P pages (images for calculator)")
            console.print(f"    [dim]2[/] — TXT (extract text only)")
            console.print(f"    [dim]3[/] — Both")
            choice = click.prompt("  Choose", type=click.Choice(["1", "2", "3"], case_sensitive=False),
                                  default="1", show_choices=False, show_default=False)
            mode = {"1": "g3p", "2": "txt", "3": "both"}[choice]
            console.print()

        if mode in ("g3p", "both"):
            g3p_out = output or str(CONVERTED_DIR / "g3p" / f"{input_path.stem}.g3p")
            Path(g3p_out).parent.mkdir(parents=True, exist_ok=True)
            convert_document_g3p(str(input_path), g3p_out, int(bits), overlap)
            console.print(f"  [bold {theme.SUCCESS}]✓[/] {file} → [dim]{g3p_out}_*.g3p[/]")
        if mode in ("txt", "both"):
            txt_out = output or str(_auto_output_path(input_path, category, decode, file))
            convert_text(str(input_path), txt_out)
            console.print(f"  [bold {theme.SUCCESS}]✓[/] {file} → [dim]{txt_out}[/]")
    else:
        if not output:
            output = str(_auto_output_path(input_path, category, decode, file))
        convert_image(str(input_path), output, int(bits), split, overlap)
        console.print(f"  [bold {theme.SUCCESS}]✓[/] {file} → [dim]{output}[/]")


# ---------------------------------------------------------------------------
# convpush — copy converted files to calculator
# ---------------------------------------------------------------------------


@cli.command("convpush")
@pass_ctx
def cmd_convpush(app):
    """Copy converted files (G3P, TXT) from converted/ to the calculator.

    Files are placed under a pthings/ folder on the calculator's storage.
    """
    from pcalc.calculator import find_calculator
    import shutil

    calc = find_calculator()
    if calc is None:
        _no_calc()

    mount = calc.mount_path

    if not os.access(mount, os.W_OK):
        _fail(f"Write access denied to {mount}")

    g3p_files = sorted((CONVERTED_DIR / "g3p").glob("*.g3p")) if (CONVERTED_DIR / "g3p").exists() else []
    txt_files = sorted((CONVERTED_DIR / "txt").glob("*.txt")) if (CONVERTED_DIR / "txt").exists() else []

    if not g3p_files and not txt_files:
        console.print(f"\n  [dim]No converted files found in {CONVERTED_DIR}[/]\n")
        console.print(f"  [dim]Run [bold]pcalc convert[/] first.[/]\n")
        raise SystemExit(1)

    # Calculate total size needed
    total_bytes = sum(f.stat().st_size for f in g3p_files) + sum(f.stat().st_size for f in txt_files)

    if calc.storage_free < total_bytes:
        need = total_bytes / (1024 * 1024)
        free = calc.storage_free_mb
        console.print(f"\n  [bold {theme.WARNING}]⚠ Not enough free space:[/] need {need:.1f} MB, only {free:.1f} MB available.")
        if not app.yes:
            continue_copy = click.confirm("  Continue anyway?", default=False)
            if not continue_copy:
                console.print(f"  [dim]Aborted.[/]\n")
                raise SystemExit(1)

    g3p_dest_dir = mount / "pthings" / "g3p"
    txt_dest_dir = mount / "pthings" / "txt"
    try:
        g3p_dest_dir.mkdir(parents=True, exist_ok=True)
        txt_dest_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        _fail(f"Failed to create pthings directories: {e}")

    from rich.progress import Progress, DownloadColumn, TransferSpeedColumn, TimeRemainingColumn

    all_files = [(f, g3p_dest_dir, "pthings/g3p/") for f in g3p_files] + \
                [(f, txt_dest_dir, "pthings/txt/") for f in txt_files]

    copied = 0
    skipped = 0
    failed = 0

    with Progress(
        "[progress.description]{task.description}",
        AsciiBarColumn(bar_width=30),
        DownloadColumn(),
        TransferSpeedColumn(),
        TimeRemainingColumn(),
        console=console,
        transient=True,
    ) as progress:
        for f, dest_dir, label_prefix in all_files:
            dest = dest_dir / f.name
            if dest.exists():
                skipped += 1
                continue

            total = f.stat().st_size
            task = progress.add_task(
                f"  Copying {f.name}...", total=total)

            try:
                with open(f, 'rb') as src_f, open(dest, 'wb') as dst_f:
                    written = 0
                    while written < total:
                        chunk = src_f.read(min(65536, total - written))
                        if not chunk:
                            break
                        dst_f.write(chunk)
                        written += len(chunk)
                        progress.update(task, completed=written)
                progress.update(task, description=f"  [bold {theme.SUCCESS}]✓[/] {f.name} → {label_prefix}")
                copied += 1
            except OSError as e:
                progress.update(task, description=f"  [bold red]✗[/] {f.name} → {e}")
                failed += 1

    if copied or failed or skipped:
        parts = []
        if copied:  parts.append(f"[bold]{copied}[/] copied")
        if failed:  parts.append(f"[bold red]{failed}[/] failed")
        if skipped: parts.append(f"[dim]{skipped}[/] skipped")
        console.print(f"  {' · '.join(parts)} on {calc.model}.\n")
    else:
        console.print(f"  [dim]Nothing to copy.[/]\n")


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


@cli.command("eject")
@pass_ctx
def cmd_eject(app):
    """Safely unmount the calculator before disconnecting."""
    from pcalc.calculator import find_calculator

    calc = find_calculator()
    if calc is None:
        console.print(f"\n  [dim]No calculator detected.[/]\n")
        return

    _eject(calc)

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


# ---------------------------------------------------------------------------
# Cryptographic / verification
# ---------------------------------------------------------------------------


@cli.command("verify")
@click.argument("names", nargs=-1)
@pass_ctx
def cmd_verify(app, names):
    """Verify installed add-ins against their recorded SHA256 checksums.

    If no add-in names are given, verifies ALL installed add-ins.
    """
    from pcalc.installer import get_installed, verify as verify_installed
    from pcalc.calculator import find_calculator

    calc = find_calculator()
    if not calc:
        _no_calc()

    installed = get_installed()
    if not installed:
        console.print(f"  [dim]No add-ins are installed. Nothing to verify.[/]\n")
        return

    if not names:
        names = list(installed.keys())
    else:
        missing = [n for n in names if n not in installed]
        if missing:
            _fail(f"Add-in(s) not installed: {', '.join(missing)}")

    all_ok = True
    for name in names:
        entry = installed[name]
        label = entry.get("name", name)
        console.print(f"\n  Verifying [bold]{label}[/] ...", end="")
        try:
            result = verify_installed(name, calc)
            if result:
                console.print(f" [bold {theme.SUCCESS}]OK[/]")
            else:
                console.print(f" [bold red]FAILED[/]")
                all_ok = False
        except RuntimeError as e:
            console.print(f" [bold red]FAILED[/]")
            console.print(f"    [red]{e}[/]")
            all_ok = False

    if not all_ok:
        raise SystemExit(1)
    console.print()


@cli.command("import-key")
@click.argument("key_file", type=click.Path(exists=True))
@pass_ctx
def cmd_import_key(app, key_file):
    """Import a PGP public key for signature verification."""
    from pcalc.crypto import import_key

    console.print(f"\n  Importing key from [dim]{key_file}[/] ...", end="")
    try:
        result = import_key(key_file)
        fp = result["fingerprint"]
        console.print(f" [bold {theme.SUCCESS}]done[/]")
        console.print(f"  Fingerprint: [bold]{fp}[/]")
        console.print(f"  Key ID:      [bold]{result['keyid']}[/]")
        console.print(f"\n  [dim]Use 'pcalc trust-key {fp}' to trust this key for signature verification.[/]\n")
    except RuntimeError as e:
        console.print(f" [bold red]failed[/]")
        _fail(str(e))


@cli.command("list-keys")
@pass_ctx
def cmd_list_keys(app):
    """List imported PGP keys and their trust status."""
    from pcalc.crypto import list_keys

    keys = list_keys()
    if not keys:
        console.print(f"\n  [dim]No PGP keys imported. Use 'pcalc import-key <file>' to add one.[/]\n")
        return

    from rich.table import Table
    table = Table(
        show_header=True, header_style=theme.S_PRIMARY, border_style=theme.PRIMARY,
        show_lines=False, pad_edge=True,
    )
    table.add_column("Key ID", style="bold white", no_wrap=True)
    table.add_column("Fingerprint", style=theme.S_DIM)
    table.add_column("UID", style="white")
    table.add_column("Trusted", style=theme.S_ACCENT)

    for k in keys:
        trusted = "[bold green]yes[/]" if k["trusted"] else "[dim]no[/]"
        uids = k.get("uids", ["(none)"])
        table.add_row(k["keyid"], k["fingerprint"][:32] + "...", uids[0], trusted)
    console.print("\n", table, "\n")


@cli.command("trust-key")
@click.argument("fingerprint")
@pass_ctx
def cmd_trust_key(app, fingerprint):
    """Mark a PGP key as trusted for signature verification."""
    from pcalc.crypto import trust_key

    console.print(f"\n  Trusting key [dim]{fingerprint}[/] ...", end="")
    try:
        trust_key(fingerprint)
        console.print(f" [bold {theme.SUCCESS}]done[/]\n")
    except RuntimeError as e:
        console.print(f" [bold red]failed[/]")
        _fail(str(e))


@cli.command("untrust-key")
@click.argument("fingerprint")
@pass_ctx
def cmd_untrust_key(app, fingerprint):
    """Remove trust from a previously trusted PGP key."""
    from pcalc.crypto import untrust_key

    untrust_key(fingerprint)
    console.print(f"\n  Key [dim]{fingerprint}[/] is no longer trusted.\n")