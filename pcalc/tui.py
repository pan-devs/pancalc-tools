"""
pcalc/tui.py — Textual TUI for PanCalc Tools.
"""

import os
import re
import unicodedata
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, Horizontal, ScrollableContainer
from textual.message import Message
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, Footer, Header, Label, ListItem, ListView, RichLog, Static
from textual.worker import Worker, WorkerState

from pcalc import theme
from pcalc import _data_root, _project_root


KEY_HINT = "  [dim]↑↓ navigate · Space toggle · Enter act · Esc home[/]"


# ── Messages ───────────────────────────────────────────────────────


class LogMessage(Message):
    """Posted by workers to add a line to the status log."""
    def __init__(self, text: str) -> None:
        super().__init__()
        self.text = text


class OperationDone(Message):
    """Posted when an async operation finishes."""
    def __init__(self, text: str = "") -> None:
        super().__init__()
        self.text = text


class PushDone(Message):
    """Posted after push completes, with list of pushed files."""
    def __init__(self, files: list[Path]) -> None:
        super().__init__()
        self.files = files


class ConvertDone(Message):
    """Posted after conversion completes, with list of converted originals."""
    def __init__(self, files: list[Path]) -> None:
        super().__init__()
        self.files = files


# ── ToggleRow — clickable item with checkbox ───────────────────────


class ToggleRow(Horizontal):
    """A single selectable row with checkbox indicator."""

    def __init__(self, index: int, text: str, checked: bool = False,
                 disabled: bool = False) -> None:
        super().__init__()
        self._idx = index
        self._checked = checked
        self._disabled = disabled

    def compose(self) -> ComposeResult:
        ck = "✅" if self._disabled else ("☑" if self._checked else "☐")
        yield Label(ck, classes="toggle-cb")
        yield Label(self._label, classes="toggle-text")

    def on_click(self) -> None:
        if not self._disabled:
            self._checked = not self._checked
            self.query_one(".toggle-cb").update("☑" if self._checked else "☐")

    @property
    def _label(self) -> str:
        return ""


class InstallRow(ToggleRow):
    def __init__(self, index: int, addin: dict, checked: bool = False,
                 disabled: bool = False) -> None:
        self._addin = addin
        super().__init__(index, "", checked, disabled)

    @property
    def _label(self) -> str:
        name = self._addin.get("name", self._addin.get("id", "?"))
        aid = self._addin.get("id", "?")
        is_local = self._addin.get("source") == "local"
        marker = " [yellow]L[/]" if is_local else ""
        if self._disabled:
            return f"[dim]{name}  {aid}{marker}  (installed)[/]"
        return f"[bold]{name}[/]  [dim]{aid}{marker}[/]"


class GameRow(ToggleRow):
    def __init__(self, index: int, game: dict, checked: bool = False,
                 disabled: bool = False) -> None:
        self._game = game
        super().__init__(index, "", checked, disabled)

    @property
    def _label(self) -> str:
        name = self._game.get("name", self._game.get("id", "?"))
        aid = self._game.get("id", "?")
        platform = self._game.get("platform", "unknown")
        emulator = self._game.get("emulator", "unknown")
        info = f"[{platform}] via {emulator}"
        is_local = self._game.get("source") == "local"
        marker = " [yellow]L[/]" if is_local else ""
        if self._disabled:
            return f"[dim]{name}  {aid}{marker}  ({info})  (installed)[/]"
        return f"[bold]{name}[/]  [dim]{aid}{marker}  [italic]{info}[/]"


class RemoveRow(ToggleRow):
    def __init__(self, index: int, display_name: str, filename: str,
                 checked: bool = False, disabled: bool = False,
                 kind: str = "addin", path: Path | None = None) -> None:
        self._display_name = display_name
        self._filename = filename
        self._kind = kind  # "addin", "file", or "orphan"
        self._path = path  # full calc path (for "file" and "orphan" kind)
        super().__init__(index, "", checked, disabled)

    @property
    def _label(self) -> str:
        tag = {"addin": "bold cyan", "file": "bold magenta", "orphan": "bold yellow"}
        icon = {"addin": "📦", "file": "📄", "orphan": "🎮"}
        style = tag.get(self._kind, "dim")
        badge = " [O]" if self._kind == "orphan" else ""
        return f"[{style}]{icon.get(self._kind, '📦')}[/] [bold]{self._display_name}[/]{badge}  [dim]{self._filename}[/]"


class VerifyRow(ToggleRow):
    def __init__(self, index: int, display_name: str, filename: str,
                 checked: bool = True, disabled: bool = False) -> None:
        self._display_name = display_name
        self._filename = filename
        super().__init__(index, "", checked, disabled)

    @property
    def _label(self) -> str:
        return f"[bold]{self._display_name}[/]  [dim]{self._filename}[/]"


class ConvertRow(ToggleRow):
    def __init__(self, index: int, fpath: Path, checked: bool = True) -> None:
        self._fpath = fpath
        ext = fpath.suffix.lower()
        if ext in (".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tiff", ".tif", ".webp"):
            self._ftype = "IMG"
        elif ext in (".g3p",):
            self._ftype = "G3P"
        elif ext in (".txt",):
            self._ftype = "TXT"
        else:
            self._ftype = "DOC"
        super().__init__(index, "", checked)

    @property
    def _label(self) -> str:
        tag_map = {"IMG": "bold green", "G3P": "bold cyan", "TXT": "bold magenta", "DOC": "bold yellow"}
        style = tag_map.get(self._ftype, "dim")
        return f"[{style}]{self._ftype}[/]  {self._fpath.name}"


# ── Main Screen (sidebar + content panel) ──────────────────────────


class MainScreen(Screen):
    def compose(self) -> ComposeResult:
        yield Header()
        yield Horizontal(
            Vertical(
                Label("PanCalc Tools", classes="sidebar-title"),
                Label("", id="calc-status", classes="sidebar-status"),
                Button("🏠  Home",             id="home",      variant="primary"),
                Button("📂  Catch",            id="catch"),
                Button("📥  Install",          id="install"),
                Button("🎮  Games",            id="games"),
                Button("🗑️  Remove",           id="remove"),
                Button("🔄  Convert",          id="convert"),
                Button("📤  Push",             id="convpush"),
                Button("✅  Verify",           id="verify"),
                Button("📋  Registry",         id="list-reg"),
                Button("🔑  PGP Keys",         id="list-keys"),
                Button("🔄  Update Registry",  id="update-reg"),
                Button("⏏️   Eject",            id="eject"),
                Button("🚪  Quit",             id="quit"),
                Label(KEY_HINT, classes="sidebar-hint"),
                classes="sidebar",
            ),
            Vertical(id="content-panel"),
        )
        yield Footer()

    def on_mount(self) -> None:
        self._output = None
        self._view = None
        self._worker_running = False
        self._update_calc_status()
        self._show_home()

    @staticmethod
    def _sanitize(name: str) -> str:
        """Strip accents, remove special chars, spaces → _."""
        # Strip accents (é→e, ñ→n, etc.)
        plain = unicodedata.normalize('NFD', name).encode('ascii', 'ignore').decode('ascii')
        # Spaces → _
        plain = plain.replace(' ', '_')
        # Remove anything that isn't alphanumeric, _, -, or .
        plain = re.sub(r'[^\w.\-]', '', plain)
        return plain

    def _confirm(self, message: str, callback, yes_label: str = "Yes") -> None:
        """Show a confirmation dialog. callback(bool) is called with result."""
        self.app.push_screen(ConfirmDialog(message, yes_label=yes_label), callback)

    def _update_calc_status(self) -> None:
        from pcalc.calculator import find_calculator
        try:
            status = self.query_one("#calc-status", Label)
            calc = find_calculator()
            if calc:
                status.update(f"[bold green]✅ {calc.model}[/]")
            else:
                status.update("[red]❌ No calculator[/]")
        except Exception:
            pass

    # ── Content helpers ────────────────────────────────────────────

    def _set_content(self, *widgets) -> None:
        panel = self.query_one("#content-panel")
        # Remember sidebar scroll to restore after swap
        sidebar = self.query_one(".sidebar")
        try:
            scroll_y = sidebar.scroll_y
        except Exception:
            scroll_y = 0
        panel.remove_children()
        for w in widgets:
            panel.mount(w)
        # Restore sidebar scroll position
        try:
            sidebar.scroll_to(y=scroll_y, animate=False)
        except Exception:
            pass

    def _log(self, text: str) -> None:
        """Write a line to the status output, creating one if needed."""
        if self._output is None:
            self._output = RichLog(highlight=True, markup=True)
            self._output.styles.height = "1fr"
            panel = self.query_one("#content-panel")
            panel.mount(self._output)
        self._output.write(text)

    # ── LogMessage handler ─────────────────────────────────────────

    def on_log_message(self, event: LogMessage) -> None:
        self._log(event.text)

    def on_operation_done(self, event: OperationDone) -> None:
        self._worker_running = False
        if event.text:
            self._log(event.text)

    def on_convert_done(self, event: ConvertDone) -> None:
        files = event.files
        if not files:
            return
        self._confirm(
            f"Delete {len(files)} original file(s) from convert/?",
            lambda ok: self._delete_convert_originals(files) if ok else None,
        )

    def _delete_convert_originals(self, files: list[Path]) -> None:
        for f in files:
            try:
                f.unlink()
                self.post_message(LogMessage(f"  🗑️  [bold]{f.name}[/] deleted from convert/"))
            except Exception as e:
                self.post_message(LogMessage(f"  ❌ [bold]{f.name}[/]: [red]{e}[/]"))
        self._refresh_convert_view()

    def on_push_done(self, event: PushDone) -> None:
        files = event.files
        if not files:
            return
        self._confirm(
            f"Delete {len(files)} original(s) from converted/?",
            lambda ok: self._delete_pushed_originals(files) if ok else None,
        )

    def _delete_pushed_originals(self, files: list[Path]) -> None:
        for f in files:
            try:
                f.unlink()
                self.post_message(LogMessage(f"  🗑️  [bold]{f.name}[/] deleted from converted/"))
            except Exception as e:
                self.post_message(LogMessage(f"  ❌ [bold]{f.name}[/]: [red]{e}[/]"))

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        if event.state == WorkerState.ERROR:
            self._worker_running = False
            self._log(f"  [bold red]Worker failed[/]")

    # ── Update Registry ────────────────────────────────────────────

    def _update_registry_impl(self) -> None:
        from pcalc import registry
        try:
            addins = registry.get_registry(force=True)
            self.post_message(LogMessage(f"  [bold green]Registry updated[/] — {len(addins)} add-ins loaded"))
        except RuntimeError as e:
            self.post_message(LogMessage(f"  [red]Failed to update registry: {e}[/]"))
        self.post_message(OperationDone())

    # ── Home ───────────────────────────────────────────────────────

    def _show_home(self) -> None:
        self._update_calc_status()
        from pcalc.calculator import find_calculator
        from pcalc.banner import PANDEVS_ASCII

        self._output = None
        self._view = "home"
        out = RichLog(highlight=True, markup=True)
        out.write(f"[bold {theme.S_PRIMARY}]{PANDEVS_ASCII.strip()}[/]")

        calc = find_calculator()
        if calc:
            try:
                from pcalc import registry as reg
                from pcalc.installer import walk_calc, count_calc_files, iter_calc_files
                addins = reg.get_registry()
                entries = walk_calc(calc, addins)
                dcount = count_calc_files(entries)
                known = sum(1 for f in iter_calc_files(entries) if f.addin is not None)
                unk = dcount - known
            except RuntimeError:
                dcount = known = unk = 0
            out.write(f"\n[bold]{calc.model}[/]  [dim]{calc.mount_path}[/]")
            out.write(f"  {known} add-ins found  ·  {dcount} files ({unk} unknown)")
        else:
            out.write(f"\n[dim]no calculator detected — connect via USB (F1)[/]")

        out.write("")
        out.write("[bold underline]About[/]")
        out.write("  PanCalc Tools — package manager & converter for Casio Prizm calculators.")
        out.write("  Part of the [bold]Pan Devs[/bold] project: open-source software for graphing")
        out.write("  calculators.  [dim]https://github.com/pan-devs[/]")
        out.write("")
        out.write("[bold underline]Commands[/]")
        out.write("  [bold]Catch[/]      — browse calculator filesystem")
        out.write("  [bold]Install[/]   — install add-ins from the registry")
        out.write("  [bold]Remove[/]    — uninstall add-ins or delete pthings files")
        out.write("  [bold]Convert[/]   — convert images/docs to G3P/TXT")
        out.write("  [bold]Push[/]      — copy converted files to calculator (pthings/)")
        out.write("  [bold]Verify[/]    — check SHA256 of installed add-ins")
        out.write("  [bold]Registry[/]  — browse available add-ins")
        out.write("  [bold]PGP Keys[/]  — manage cryptographic keys")
        out.write("  [bold]Eject[/]     — safely unmount calculator")
        out.write("")
        out.write("[dim]Ctrl+S  — command palette · Esc — home · ↑↓ — navigate · Space — toggle[/]")

        self._output = out
        self._set_content(out)

    # ── Catch ──────────────────────────────────────────────────────

    def _show_catch(self) -> None:
        self._update_calc_status()
        from pcalc.calculator import find_calculator
        from pcalc.installer import walk_calc, count_calc_files, iter_calc_files

        self._output = None
        self._view = "catch"
        out = RichLog(highlight=True, markup=True)
        calc = find_calculator()

        if not calc:
            out.write("  [dim]No calculator detected.[/]")
            out.write("  Connect via USB with mass storage mode (F1).")
        else:
            out.write(f"  [bold]{calc.model}[/]  ({calc.mount_path})")
            out.write(f"  Storage: {_fmt_size(calc.storage_free)} free / {_fmt_size(calc.storage_total)} total\n")
            try:
                from pcalc import registry as reg
                addins = reg.get_registry()
                entries = walk_calc(calc, addins)
                dcount = count_calc_files(entries)
                known = sum(1 for f in iter_calc_files(entries) if f.addin is not None)
                unk = dcount - known
            except RuntimeError:
                entries = []
                dcount = known = unk = 0
            out.write(f"  Add-ins on device: {known}  ·  Files: {dcount} ({unk} unknown)\n")
            if entries:
                out.write("  [bold]Files:[/]")
                self._render_tree(entries, out)

        self._catch_refresh_btn = Button("🔄  Refresh")
        self._catch_refresh_btn.styles.margin = (1, 2)
        self._set_content(out, self._catch_refresh_btn)
        self._output = out

    def _render_tree(self, entries, out, indent=0):
        for i, e in enumerate(entries):
            is_last = i == len(entries) - 1
            prefix = "└── " if is_last else "├── "
            if indent == 0:
                prefix = ""

            if e.is_dir:
                style = theme.S_DIM if e.name.lower() in ("@mainmem", "@backup", "@save_f") else "bold white"
                out.write(f"{'  ' * indent}{prefix}[{style}]{e.name}/[/]")
                if e.children:
                    self._render_tree(e.children, out, indent + 1)
            else:
                size_str = f"{e.size/1024:.1f} KiB" if e.size < 1024*1024 else f"{e.size/(1024*1024):.1f} MiB"
                info = f"  [dim]{e.addin['name']}[/]" if e.addin else ""
                out.write(f"{'  ' * indent}{prefix}{e.name}  [dim]{size_str}[/]{info}")

    # ── Install ────────────────────────────────────────────────────

    def _show_install(self) -> None:
        self._update_calc_status()
        from pcalc import registry
        from pcalc.calculator import find_calculator
        from pcalc.installer import scan_device

        self._view = "install"

        try:
            addins = registry.get_registry()
        except RuntimeError:
            addins = []

        # Determine which add-ins are already on device
        on_device_ids: set[str] = set()
        calc = find_calculator()
        if calc:
            try:
                for df in scan_device(calc, addins):
                    if df.addin:
                        on_device_ids.add(df.addin.get("id", ""))
            except RuntimeError:
                pass

        rows: list[InstallRow] = []
        for i, a in enumerate(addins):
            already = a.get("id", "") in on_device_ids
            rows.append(InstallRow(i, a, disabled=already))

        self._install_rows = rows
        list_container = ScrollableContainer(*rows, classes="select-list")
        self._install_list = list_container

        self._output = None
        add_btn = Button("📁  Add Add-in File")
        self._addin_add_btn = add_btn
        remove_local_btn = Button("🗑️  Remove Local", variant="error")
        self._addin_remove_local_btn = remove_local_btn
        install_btn = Button("📥  Install Checked", variant="primary")
        self._install_do_btn = install_btn
        top_row = Horizontal(add_btn, remove_local_btn, install_btn, classes="button-row-inline")
        out = RichLog(highlight=True, markup=True)
        self._output = out
        if not calc:
            out.write("  [red]No calculator detected — install will fail until connected[/]")
        self._set_content(list_container, top_row, out)

    def _install_impl(self) -> None:
        selected = [r for r in self._install_rows if r._checked and not r._disabled]
        if not selected:
            self.post_message(LogMessage("  [dim]No add-ins selected for install.[/]"))
            return

        from pcalc.calculator import require_calculator
        from pcalc.installer import install, _get_addin_files, _resolve_file_name

        try:
            calc = require_calculator()
        except RuntimeError as e:
            self.post_message(LogMessage(f"  [red]{e}[/]"))
            return

        for row in selected:
            addin = row._addin
            name = addin.get("name", addin.get("id", "?"))

            # Check for missing required fields
            if not addin.get("id"):
                self.post_message(LogMessage(f"  ❌ [bold]{name}[/]: [red]missing 'id' in registry data[/]"))
                continue

            # Determine which files already exist and skip them
            skip_files: set[str] = set()
            try:
                for f_info in _get_addin_files(addin):
                    filename = f_info.get("filename", addin.get("filename", _resolve_file_name(f_info, addin["id"])))
                    dest = calc.mount_path / filename
                    if dest.exists():
                        self.post_message(LogMessage(f"  ⏭️  [dim]{filename} already on device, skipping[/]"))
                        skip_files.add(filename)
            except (KeyError, RuntimeError):
                pass

            self.post_message(LogMessage(f"  Installing [bold]{name}[/]..."))
            try:
                install(addin, calc, skip_files=skip_files)
                self.post_message(LogMessage(f"  ✅ [bold]{name}[/] installed"))
            except RuntimeError as e:
                self.post_message(LogMessage(f"  ❌ [bold]{name}[/]: [red]{e}[/]"))

        self.post_message(OperationDone())

    # ── Games ──────────────────────────────────────────────────────

    def _show_games(self) -> None:
        self._update_calc_status()
        from pcalc import registry
        from pcalc.calculator import find_calculator
        from pcalc.installer import scan_device

        self._view = "games"

        try:
            games = registry.get_games()
        except RuntimeError:
            games = []

        # Determine which games are already on device
        on_device_ids: set[str] = set()
        calc = find_calculator()
        if calc:
            try:
                for df in scan_device(calc, games):
                    if df.addin:
                        on_device_ids.add(df.addin.get("id", ""))
            except RuntimeError:
                pass

        rows: list[GameRow] = []
        for i, g in enumerate(games):
            already = g.get("id", "") in on_device_ids
            rows.append(GameRow(i, g, disabled=already))

        self._game_rows = rows
        list_container = ScrollableContainer(*rows, classes="select-list")
        self._install_list = list_container

        self._output = None
        add_btn = Button("📁  Add Game File")
        self._game_add_btn = add_btn
        remove_local_btn = Button("🗑️  Remove Local", variant="error")
        self._game_remove_local_btn = remove_local_btn
        install_btn = Button("📥  Install Checked Games", variant="primary")
        self._games_do_btn = install_btn
        top_row = Horizontal(add_btn, remove_local_btn, install_btn, classes="button-row-inline")
        out = RichLog(highlight=True, markup=True)
        self._output = out
        if not calc:
            out.write("  [red]No calculator detected — install will fail until connected[/]")
        self._set_content(list_container, top_row, out)

    def _games_impl(self) -> None:
        selected = [r for r in self._game_rows if r._checked and not r._disabled]
        if not selected:
            self.post_message(LogMessage("  [dim]No games selected for install.[/]"))
            return

        from pcalc.calculator import require_calculator
        from pcalc.installer import install, _get_addin_files, _resolve_file_name

        try:
            calc = require_calculator()
        except RuntimeError as e:
            self.post_message(LogMessage(f"  [red]{e}[/]"))
            return

        for row in selected:
            game = row._game
            name = game.get("name", game.get("id", "?"))

            # Check for missing required fields
            if not game.get("id"):
                self.post_message(LogMessage(f"  ❌ [bold]{name}[/]: [red]missing 'id' in registry data[/]"))
                continue
            if not game.get("download_url") and not game.get("local_path"):
                self.post_message(LogMessage(f"  ❌ [bold]{name}[/]: [red]missing 'download_url' or 'local_path' in registry data[/]"))
                continue

            # Determine which files already exist and skip them
            skip_files: set[str] = set()
            try:
                for f_info in _get_addin_files(game):
                    filename = f_info.get("filename", game.get("filename", _resolve_file_name(f_info, game["id"])))
                    dest = calc.mount_path / filename
                    if dest.exists():
                        self.post_message(LogMessage(f"  ⏭️  [dim]{filename} already on device, skipping[/]"))
                        skip_files.add(filename)
            except (KeyError, RuntimeError):
                pass

            self.post_message(LogMessage(f"  Installing [bold]{name}[/]..."))
            try:
                install(game, calc, skip_files=skip_files)
                self.post_message(LogMessage(f"  ✅ [bold]{name}[/] installed"))
            except RuntimeError as e:
                self.post_message(LogMessage(f"  ❌ [bold]{name}[/]: [red]{e}[/]"))

        self.post_message(OperationDone())

    def _remove_local_impl(self, rows: list) -> None:
        """Remove selected local items from the library."""
        from pcalc import library as _lib
        removed = 0
        for row in rows:
            item = getattr(row, '_addin', None) or getattr(row, '_game', None)
            if not item or item.get("source") != "local":
                continue
            if _lib.remove(item.get("id", "")):
                self.post_message(LogMessage(f"  🗑️  [bold]{item.get('name', '?')}[/] removed from local library"))
                removed += 1
        if removed:
            self._refresh_install_view()
        else:
            self.post_message(LogMessage("  [dim]No local items selected for removal.[/]"))

    # ── Remove ─────────────────────────────────────────────────────

    def _show_remove(self) -> None:
        self._update_calc_status()
        from pcalc.calculator import find_calculator
        from pcalc.installer import walk_calc, _match_addin_by_filename
        from pcalc import registry

        self._view = "remove"

        ADDIN_EXTS = {".g3a", ".g3e"}
        GAME_EXTS = {".rom", ".bin", ".gba", ".nes", ".sms", ".gg"}
        ALL_EXTS = ADDIN_EXTS | GAME_EXTS

        rows: list[RemoveRow] = []
        calc = find_calculator()
        if calc:
            # Get all registry entries (addins + games)
            all_registry = []
            try:
                all_registry.extend(registry.get_registry())
            except RuntimeError:
                pass
            try:
                all_registry.extend(registry.get_games())
            except RuntimeError:
                pass

            # Matched entries from walk_calc
            matched_paths: set[str] = set()
            try:
                addin_entries = [e for e in walk_calc(calc, all_registry) if e.addin]
                for i, e in enumerate(addin_entries):
                    name = e.addin.get("name", e.addin.get("id", "?"))
                    rows.append(RemoveRow(i, name, e.name, kind="addin"))
                    matched_paths.add(e.name)
            except RuntimeError:
                pass

            # Recursive scan for orphan files (not in registry)
            for f in calc.mount_path.rglob("*"):
                if not f.is_file():
                    continue
                if f.suffix.lower() not in ALL_EXTS:
                    continue
                rel = str(f.relative_to(calc.mount_path))
                if rel in matched_paths:
                    continue
                match = _match_addin_by_filename(f.name, all_registry)
                if match:
                    # Should have been caught by walk_calc, but just in case
                    continue
                # Orphan: not in registry
                rows.append(RemoveRow(len(rows), f.stem, rel, kind="orphan", path=f))

            # Also scan pthings subdirectories for user files
            for sub in ("fotos", "textos"):
                d = calc.mount_path / "pthings" / sub
                if d.exists():
                    for f in sorted(d.iterdir()):
                        if f.is_file():
                            rows.append(RemoveRow(len(rows), f.name, str(f.relative_to(calc.mount_path)), kind="file", path=f))
            # Also scan pthings/ root for any loose files
            pthings_root = calc.mount_path / "pthings"
            if pthings_root.exists():
                for f in sorted(pthings_root.iterdir()):
                    if f.is_file():
                        rows.append(RemoveRow(len(rows), f.name, str(f.relative_to(calc.mount_path)), kind="file", path=f))

        self._install_rows = rows
        children = rows if rows else [Label("  [dim]No items found on calculator[/]")]
        list_container = ScrollableContainer(*children, classes="select-list")
        self._install_list = list_container

        self._output = None
        btn = Button("🗑️  Remove Checked", variant="error")
        btn.styles.margin = (1, 1, 0, 1)
        self._remove_do_btn = btn
        out = RichLog(highlight=True, markup=True)
        self._output = out
        if not calc:
            out.write("  [red]No calculator detected — connect via USB (F1)[/]")
        self._set_content(list_container, btn, out)

    def _remove_impl(self) -> None:
        selected = [r for r in self._install_rows if r._checked and not r._disabled]
        if not selected:
            self.post_message(LogMessage("  [dim]No items selected for removal.[/]"))
            return

        from pcalc.calculator import require_calculator
        from pcalc import registry
        from pcalc.installer import remove, walk_calc, _clean_save_files

        try:
            calc = require_calculator()
        except RuntimeError as e:
            self.post_message(LogMessage(f"  [red]{e}[/]"))
            return

        for row in selected:
            if row._kind == "addin":
                name = row._display_name
                try:
                    all_registry = registry.get_registry() + registry.get_games()
                    entries = [e for e in walk_calc(calc, all_registry) if e.addin]
                except RuntimeError:
                    entries = []
                match = next((e for e in entries if e.addin.get("name", e.addin.get("id", "")) == name), None)
                if not match:
                    self.post_message(LogMessage(f"  ❌ [bold]{name}[/]: [red]not found on device[/]"))
                    continue
                self.post_message(LogMessage(f"  Removing [bold]{name}[/]..."))
                try:
                    remove(match.addin["id"], calc)
                    self.post_message(LogMessage(f"  ✅ [bold]{name}[/] removed"))
                except RuntimeError as e:
                    self.post_message(LogMessage(f"  ❌ [bold]{name}[/]: [red]{e}[/]"))
            elif row._kind == "orphan":
                path = row._path
                if path and path.exists():
                    try:
                        path.unlink()
                        _clean_save_files(path)
                        self.post_message(LogMessage(f"  🗑️  [bold]{row._display_name}[/] (orphan) removed from {row._filename}"))
                    except OSError as e:
                        self.post_message(LogMessage(f"  ❌ [bold]{row._display_name}[/]: [red]{e}[/]"))
                else:
                    self.post_message(LogMessage(f"  ⏭️  [dim]{row._display_name} — already gone[/]"))
            else:
                path = row._path
                if path and path.exists():
                    try:
                        path.unlink()
                        self.post_message(LogMessage(f"  🗑️  [bold]{row._display_name}[/] removed from {row._filename}"))
                    except OSError as e:
                        self.post_message(LogMessage(f"  ❌ [bold]{row._display_name}[/]: [red]{e}[/]"))
                else:
                    self.post_message(LogMessage(f"  ⏭️  [dim]{row._display_name} — already gone[/]"))

        self.post_message(OperationDone())

    # ── Convert helpers (shared by Convert & ConvPush) ────────────

    def _convert_base(self) -> Path:
        return _data_root()

    def _scan_convert_files(self) -> list[Path]:
        base = self._convert_base()
        files: list[Path] = []
        for sub in ("images", "documents"):
            d = base / "convert" / sub
            if d.exists():
                for f in sorted(d.iterdir()):
                    if f.is_file():
                        files.append(f)
        return files

    def _build_convert_list(self) -> list["ConvertRow"]:
        rows: list[ConvertRow] = []
        for f in self._scan_convert_files():
            rows.append(ConvertRow(len(rows), f))
        return rows

    def _copy_files_to_convert(self, paths: list[str]) -> None:
        base = self._convert_base()
        img_dir = base / "convert/images"
        doc_dir = base / "convert/documents"
        img_dir.mkdir(parents=True, exist_ok=True)
        doc_dir.mkdir(parents=True, exist_ok=True)
        img_exts = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tiff", ".tif", ".webp"}
        doc_exts = {".pdf", ".docx", ".doc", ".txt"}
        all_valid = img_exts | doc_exts
        import shutil
        copied = 0
        for p in paths:
            src = Path(p)
            if not src.is_file():
                continue
            ext = src.suffix.lower()
            if ext in img_exts:
                shutil.copy2(str(src), str(img_dir / src.name))
                copied += 1
            elif ext in doc_exts:
                shutil.copy2(str(src), str(doc_dir / src.name))
                copied += 1
        if copied:
            self.post_message(LogMessage(f"  [dim]{copied} file(s) added to convert/[/]"))

    def _pick_files(self) -> None:
        paths = self._open_file_dialog("Select files to convert")
        if not paths:
            return

        img_exts = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tiff", ".tif", ".webp"}
        doc_exts = {".pdf", ".docx", ".doc", ".txt"}
        all_valid = img_exts | doc_exts

        valid, invalid = [], []
        for p in paths:
            (valid if Path(p).suffix.lower() in all_valid else invalid).append(p)

        if invalid:
            names = ", ".join(Path(p).name for p in invalid[:3])
            if len(invalid) > 3:
                names += f" ... (+{len(invalid)-3} more)"
            self.post_message(LogMessage(
                f"  [yellow]⚠[/] {len(invalid)} file(s) with unsupported format: {names}"
            ))
            def _on_confirm(ok: bool):
                self._copy_files_to_convert(valid + (invalid if ok else []))
                self._refresh_convert_view()
            self._confirm("Add files with unsupported formats anyway?", _on_confirm)
        else:
            self._copy_files_to_convert(valid)
            self._refresh_convert_view()

    def _open_file_dialog(self, title: str) -> list[str]:
        paths: list[str] = []
        try:
            import subprocess
            r = subprocess.run(
                ["zenity", "--file-selection", "--multiple", f"--title={title}"],
                capture_output=True, timeout=30
            )
            if r.returncode == 0:
                paths = r.stdout.decode().strip().split("|")
        except Exception:
            pass
        if not paths:
            try:
                import tkinter as tk
                from tkinter import filedialog
                root = tk.Tk()
                root.withdraw()
                root.lift()
                paths = list(filedialog.askopenfilenames(title=title))
                root.destroy()
            except Exception:
                self.post_message(LogMessage("  [red]No file dialog available (install zenity or tkinter)[/]"))
        return [p.strip() for p in paths if p.strip()]

    def _import_files(self, paths: list[str], item_type: str) -> None:
        from pcalc import library as _lib
        label = "Add-in" if item_type == "addin" else "Game"
        imported = 0
        for p in paths:
            src = Path(p)
            if not src.is_file():
                continue
            try:
                entry = _lib.import_file(str(src), item_type=item_type)
                self.post_message(LogMessage(f"  ✅ [bold]{entry['name']}[/] ({label}) imported"))
                imported += 1
            except (ValueError, FileNotFoundError) as e:
                self.post_message(LogMessage(f"  [red]{e}[/]"))
        if imported:
            self.post_message(LogMessage(f"  [dim]{imported} file(s) imported[/]"))

    def _pick_file_for_import(self, item_type: str) -> None:
        title = "Select add-in file" if item_type == "addin" else "Select game/ROM file"
        paths = self._open_file_dialog(title)
        if not paths:
            return

        from pcalc import library as _lib
        expected = _lib.expected_extensions(item_type)
        valid, invalid = [], []
        for p in paths:
            (valid if _lib.has_valid_extension(p, item_type) else invalid).append(p)

        if invalid:
            names = ", ".join(Path(p).name for p in invalid[:3])
            if len(invalid) > 3:
                names += f" ... (+{len(invalid)-3} more)"
            self.post_message(LogMessage(
                f"  [yellow]⚠[/] {len(invalid)} file(s) with unexpected format: {names}"
            ))
            def _confirm_cb(ok: bool):
                self._import_files(valid + (invalid if ok else []), item_type)
                self._refresh_install_view()
            self._confirm("Import files with unexpected formats anyway?", _confirm_cb)
        else:
            self._import_files(valid, item_type)
            self._refresh_install_view()

    def _ensure_convert_dirs(self) -> None:
        base = self._convert_base()
        # One-time migration from project-relative paths
        old_root = _project_root()
        if old_root and old_root.resolve() != base.resolve():
            for rel in ("convert/images", "convert/documents", "convert/g3p",
                        "converted/g3p", "converted/txt", "converted/images"):
                old_dir = old_root / rel
                new_dir = base / rel
                if old_dir.exists() and not new_dir.exists():
                    new_dir.parent.mkdir(parents=True, exist_ok=True)
                    import shutil; shutil.move(str(old_dir), str(new_dir))
        (base / "convert/images").mkdir(parents=True, exist_ok=True)
        (base / "convert/documents").mkdir(parents=True, exist_ok=True)
        (base / "converted/g3p").mkdir(parents=True, exist_ok=True)
        (base / "converted/txt").mkdir(parents=True, exist_ok=True)
        (base / "converted/images").mkdir(parents=True, exist_ok=True)

    def _refresh_convert_view(self) -> None:
        if self._view == "convert":
            self._show_convert()
        elif self._view == "convpush":
            self._show_convpush()

    def _refresh_install_view(self) -> None:
        if self._view == "install":
            self._show_install()
        elif self._view == "games":
            self._show_games()

    def on_file_dropped(self, event) -> None:
        pass

    # ── Convert ────────────────────────────────────────────────────

    def _show_convert(self) -> None:
        self._update_calc_status()
        self._view = "convert"
        rows = self._build_convert_list()
        self._convert_rows = rows
        if rows:
            list_container = ScrollableContainer(*rows, classes="select-list")
        else:
            hint = ""
            g3p = self._convert_base() / "converted/g3p"
            txt = self._convert_base() / "converted/txt"
            g3p_count = len(list(g3p.iterdir())) if g3p.exists() else 0
            txt_count = len(list(txt.iterdir())) if txt.exists() else 0
            if g3p_count or txt_count:
                hint = f"  [dim](but {g3p_count + txt_count} files in converted/ — try Push)[/]"
            list_container = Label(f"  [dim]No files in convert/[/]{hint}")

        select_btn = Button("📁  Select Files")
        self._conv_select_btn = select_btn
        refresh_btn = Button("🔄  Refresh")
        self._conv_refresh_btn = refresh_btn
        top_row = Horizontal(select_btn, refresh_btn, classes="button-row-inline")

        g3p_btn   = Button("→ G3P")
        txt_btn   = Button("Docs → TXT")
        both_btn  = Button("Docs → Both")
        del_btn   = Button("🗑️  Delete Selected", variant="error")
        self._conv_g3p_btn = g3p_btn
        self._conv_txt_btn = txt_btn
        self._conv_both_btn = both_btn
        self._conv_del_btn = del_btn
        action_row = Horizontal(g3p_btn, txt_btn, both_btn, del_btn, classes="button-row-inline")

        out = RichLog(highlight=True, markup=True)
        self._output = out
        self._set_content(top_row, list_container, action_row, out)

    def _run_convert(self, mode: str) -> None:
        if not self._worker_running:
            self._worker_running = True
            self.run_worker(lambda: self._convert_impl(mode), thread=True, exclusive=True)

    def _convert_impl(self, mode: str) -> None:
        selected = [r for r in self._convert_rows if r._checked]
        if not selected:
            self.post_message(LogMessage("  [dim]No files selected[/]"))
            return

        from pcalc.converter import convert_image, convert_text, convert_document_g3p
        base = self._convert_base()
        import tempfile
        ok = 0
        converted_files: list[Path] = []

        for row in selected:
            f = row._fpath
            # Sanitize: strip accents, special chars, spaces→_
            safe_stem = self._sanitize(f.stem)
            if safe_stem != f.stem:
                new_name = f.with_stem(safe_stem)
                try:
                    f.rename(new_name)
                    f = new_name
                    row._fpath = f
                    self.post_message(LogMessage(f"  [yellow]Sanitized[/] → [bold]{f.name}[/]"))
                except OSError as e:
                    self.post_message(LogMessage(f"  [red]Failed to rename {f.name}: {e}[/]"))
                    continue
            self.post_message(LogMessage(f"  Processing [bold]{f.name}[/]..."))

            try:
                if mode == "g3p":
                    dest_dir = base / "converted/g3p"
                    dest_dir.mkdir(parents=True, exist_ok=True)
                    if row._ftype == "IMG":
                        convert_image(str(f), str(dest_dir / (f.stem + ".g3p")), bit_depth=16)
                    else:
                        convert_document_g3p(str(f), str(dest_dir / f.stem))
                    self.post_message(LogMessage(f"  ✅ [bold]{f.name}[/] converted to G3P"))

                elif mode == "txt":
                    if row._ftype != "DOC":
                        self.post_message(LogMessage(f"  ⏭️  [dim]{f.name} — not a document[/]"))
                        continue
                    dest_dir = base / "converted/txt"
                    dest_dir.mkdir(parents=True, exist_ok=True)
                    convert_text(str(f), str(dest_dir / (f.stem + ".txt")))
                    self.post_message(LogMessage(f"  ✅ [bold]{f.name}[/] converted to TXT"))

                elif mode == "both":
                    if row._ftype != "DOC":
                        self.post_message(LogMessage(f"  ⏭️  [dim]{f.name} — not a document[/]"))
                        continue
                    g3p_dir = base / "converted/g3p"
                    txt_dir = base / "converted/txt"
                    g3p_dir.mkdir(parents=True, exist_ok=True)
                    txt_dir.mkdir(parents=True, exist_ok=True)
                    convert_document_g3p(str(f), str(g3p_dir / f.stem))
                    convert_text(str(f), str(txt_dir / (f.stem + ".txt")))
                    self.post_message(LogMessage(f"  ✅ [bold]{f.name}[/] → G3P + TXT"))

                ok += 1
                converted_files.append(f)
            except Exception as e:
                self.post_message(LogMessage(f"  ❌ [bold]{f.name}[/]: [red]{e}[/]"))

        self._ensure_convert_dirs()
        if ok:
            self.post_message(LogMessage(f"\n  [bold green]{ok} file(s) converted[/]"))
            self.post_message(ConvertDone(converted_files))
        self.post_message(OperationDone())

    def _delete_selected_convert(self) -> None:
        selected = [r for r in self._convert_rows if r._checked]
        if not selected:
            self.post_message(LogMessage("  [dim]No files selected[/]"))
            return
        for row in selected:
            f = row._fpath
            try:
                f.unlink()
                self.post_message(LogMessage(f"  🗑️  [bold]{f.name}[/] deleted"))
            except Exception as e:
                self.post_message(LogMessage(f"  ❌ [bold]{f.name}[/]: [red]{e}[/]"))
        self._ensure_convert_dirs()
        self._refresh_convert_view()

    # ── Push ───────────────────────────────────────────────────────

    def _scan_push_files(self) -> list[Path]:
        base = self._convert_base()
        files: list[Path] = []
        for sub in ("g3p", "txt", "images"):
            d = base / "converted" / sub
            if d.exists():
                for f in sorted(d.iterdir()):
                    if f.is_file():
                        files.append(f)
        return files

    def _build_push_list(self) -> list["ConvertRow"]:
        rows: list[ConvertRow] = []
        for f in self._scan_push_files():
            # Tag based on extension for display
            rows.append(ConvertRow(len(rows), f))
        return rows

    def _show_convpush(self) -> None:
        self._update_calc_status()
        self._view = "convpush"
        rows = self._build_push_list()
        self._convert_rows = rows

        if not rows:
            hint = ""
            img_dir = self._convert_base() / "convert/images"
            doc_dir = self._convert_base() / "convert/documents"
            img_count = len(list(img_dir.iterdir())) if img_dir.exists() else 0
            doc_count = len(list(doc_dir.iterdir())) if doc_dir.exists() else 0
            if img_count or doc_count:
                hint = f"  [dim](but {img_count + doc_count} files in convert/ — try Convert)[/]"
            list_container = Label(f"  [dim]No converted files in converted/[/]{hint}")
        else:
            list_container = ScrollableContainer(*rows, classes="select-list")

        refresh_btn = Button("🔄  Refresh")
        self._conv_refresh_btn = refresh_btn
        del_btn = Button("🗑️  Delete Selected", variant="error")
        self._conv_del_btn = del_btn
        push_btn = Button("Push Selected to Calculator", variant="primary")
        self._convpush_do_btn = push_btn
        btn_row = Horizontal(refresh_btn, del_btn, push_btn, classes="button-row-inline")
        out = RichLog(highlight=True, markup=True)
        self._output = out
        self._set_content(btn_row, list_container, out)

    def _convpush_impl(self) -> None:
        self._convert_rows = getattr(self, '_convert_rows', [])
        selected = [r for r in self._convert_rows if r._checked]
        if not selected:
            self.post_message(LogMessage("  [dim]No files selected[/]"))
            return

        from pcalc.calculator import find_calculator
        calc = find_calculator()
        if not calc:
            self.post_message(LogMessage("  [red]No calculator detected[/]"))
            return

        try:
            fotos = calc.mount_path / "pthings/fotos"
            textos = calc.mount_path / "pthings/textos"
            fotos.mkdir(parents=True, exist_ok=True)
            textos.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            self.post_message(LogMessage(f"  [red]Failed to create pthings/ directories: {e}[/]"))
            return

        ok = 0
        pushed_files: list[Path] = []
        for row in selected:
            f = row._fpath
            dest_name = self._sanitize(f.name)
            self.post_message(LogMessage(f"  Pushing [bold]{dest_name}[/]..."))
            try:
                dest = (fotos if f.suffix.lower() == ".g3p" else textos) / dest_name
                dest.write_bytes(f.read_bytes())
                self.post_message(LogMessage(f"  ✅ [bold]{dest_name}[/] pushed to {'fotos/' if f.suffix.lower() == '.g3p' else 'textos/'}"))
                ok += 1
                pushed_files.append(f)
            except Exception as e:
                self.post_message(LogMessage(f"  ❌ [bold]{dest_name}[/]: [red]{e}[/]"))

        if ok:
            self.post_message(LogMessage(f"\n  [bold green]{ok} file(s) pushed[/]"))
            self.post_message(PushDone(pushed_files))
        self.post_message(OperationDone())

    # ── Verify ─────────────────────────────────────────────────────

    def _show_verify(self) -> None:
        self._update_calc_status()
        from pcalc.calculator import find_calculator
        from pcalc.installer import walk_calc, iter_calc_files
        from pcalc import registry

        self._view = "verify"
        rows: list[VerifyRow] = []
        calc = find_calculator()
        if calc:
            try:
                addins = registry.get_registry()
                entries = walk_calc(calc, addins)
                for f in iter_calc_files(entries):
                    if f.addin:
                        name = f.addin.get("name", f.addin.get("id", "?"))
                        rows.append(VerifyRow(len(rows), name, f.name))
            except RuntimeError:
                pass

        if not rows:
            self._set_content(RichLog(highlight=True, markup=True))
            self._output = self.query_one(RichLog)
            self._output.write("  [dim]No add-ins found on calculator[/]")
            return

        self._verify_rows = rows
        list_container = ScrollableContainer(*rows, classes="select-list")
        btn = Button("✅  Verify Checked", variant="primary")
        btn.styles.margin = (1, 1, 0, 1)
        self._verify_do_btn = btn
        self._output = None
        self._set_content(list_container, btn)

    def _verify_impl(self) -> None:
        from pcalc.calculator import find_calculator
        from pcalc.installer import verify_addin

        selected = [r for r in self._verify_rows if r._checked]
        if not selected:
            self.post_message(LogMessage("  [dim]No add-ins selected for verification.[/]"))
            return

        calc = find_calculator()
        if not calc:
            self.post_message(LogMessage("  [red]No calculator detected[/]"))
            return

        all_ok = True
        for row in selected:
            name = row._display_name
            # Match by name amongst all add-in entries on device
            from pcalc import registry
            from pcalc.installer import walk_calc, iter_calc_files
            try:
                addins = registry.get_registry()
                entries = walk_calc(calc, addins)
                match = None
                for f in iter_calc_files(entries):
                    if f.addin and f.addin.get("name", f.addin.get("id", "")) == name:
                        match = f
                        break
                if not match or not match.addin:
                    self.post_message(LogMessage(f"  ❌ [bold]{name}[/]: [red]not found[/]"))
                    all_ok = False
                    continue
                ok = verify_addin(match.addin, calc)
                self.post_message(LogMessage(f"  {'✅' if ok else '❌'} [bold]{name}[/] {'— OK' if ok else '— FAILED'}"))
                if not ok:
                    all_ok = False
            except RuntimeError as e:
                self.post_message(LogMessage(f"  ❌ [bold]{name}[/]: [red]{e}[/]"))
                all_ok = False

        self.post_message(LogMessage(f"\n  [{'bold green' if all_ok else 'bold red'}]All {'OK' if all_ok else 'some failed'}[/]"))
        self.post_message(OperationDone())

    # ── Registry List ──────────────────────────────────────────────

    def _show_registry(self) -> None:
        self._update_calc_status()
        from pcalc import registry

        self._view = "registry"
        try:
            addins = registry.get_registry()
        except RuntimeError:
            addins = []
        try:
            games = registry.get_games()
        except RuntimeError:
            games = []

        combined = []
        for a in addins:
            a["_type"] = "addin"
            combined.append(a)
        for g in games:
            g["_type"] = "emulator"
            combined.append(g)

        self._registry_addins = combined

        items = []
        for a in combined:
            aid = a.get("id", "?")
            name = a.get("name", aid)
            author = a.get("author", "")
            ver = a.get("version", "")
            typ = a.get("_type", "?")
            type_label = f"[{typ}]"
            if typ == "emulator":
                emu = a.get("emulator", "?")
                plat = a.get("platform", "?")
                type_label = f"[emulator:{emu}/{plat}]"
            items.append(ListItem(Label(
                f"{type_label} [bold]{name}[/]  [dim]{aid}[/]  [italic]{author}[/]  [{theme.S_ACCENT}]{ver}[/]"
            )))
        if not items:
            items.append(ListItem(Label("[dim]Failed to load registry[/]")))

        self._output = None
        lv = ListView(*items)
        lv.styles.height = "1fr"
        out = RichLog(highlight=True, markup=True)
        self._output = out
        out.write("  [dim]Click an entry for details[/]")
        self._set_content(lv, out)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        from pcalc import registry as reg
        addins = getattr(self, '_registry_addins', [])
        idx = event.list_view.index
        if idx is None or idx >= len(addins):
            return
        a = addins[idx]
        typ = a.get("_type", "?")
        lines = [
            f"  [bold]{a.get('name', '?')}[/]  [dim]{a.get('id', '?')}[/]",
            f"  Type: {typ}   Author: {a.get('author', '?')}   Version: {a.get('version', '?')}",
            f"  Category: {a.get('category', '?')}",
            f"  Compatible: {', '.join(a.get('compatible', []))}",
            f"  Description: {a.get('description', '?')}",
            f"  URL: {a.get('url', '?')}",
        ]
        if typ == "emulator":
            emu = a.get("emulator", "?")
            plat = a.get("platform", "?")
            lines.append(f"  Emulator: {emu}   Platform: {plat}")
        if "size_kb" in a:
            lines.append(f"  Size: {a['size_kb']:.1f} KiB")
        if "license" in a:
            lines.append(f"  License: {a['license']}")
        self._output = self.query_one(RichLog) if not self._output or not self._output.is_mounted else self._output
        self._output.clear()
        for l in lines:
            self._log(l)

    # ── PGP Keys ───────────────────────────────────────────────────

    def _show_keys(self) -> None:
        self._update_calc_status()
        from pcalc.crypto import official_key_info, list_keys

        self._output = None
        self._view = "keys"
        out = RichLog(highlight=True, markup=True)

        # Official key
        official = official_key_info()
        if official:
            uid = official.get("uids", ["(no UID)"])[0]
            out.write(f"  [bold green]✅ Official Pan Devs key[/]")
            out.write(f"    {uid}")
            out.write(f"    Fingerprint: {official['fingerprint']}")
            out.write(f"    Key ID: {official['keyid']}")
        else:
            out.write("  [dim]Official Pan Devs key not loaded.[/]")
            out.write("  It will be downloaded automatically when needed.")

        # Other keys (advanced users)
        others = [k for k in list_keys() if not k.get("official")]
        if others:
            out.write("")
            out.write("  [dim]Other imported keys:[/]")
            for k in others:
                trust = "✅ trusted" if k["trusted"] else "❌ untrusted"
                uid = k.get("uids", ["(no UID)"])[0]
                out.write(f"  [bold]{k['keyid']}[/]  {uid}")
                out.write(f"    Status: {trust}")

        self._keys_refresh_btn = Button("🔄  Refresh")
        self._keys_refresh_btn.styles.margin = (1, 2)
        self._set_content(out, self._keys_refresh_btn)
        self._output = out

    # ── Button routing ─────────────────────────────────────────────

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        # Sidebar buttons
        if bid == "home":        self._show_home();       return
        if bid == "catch":       self._show_catch();      return
        if bid == "install":     self._show_install();    return
        if bid == "games":       self._show_games();      return
        if bid == "remove":      self._show_remove();     return
        if bid == "convert":     self._show_convert();    return
        if bid == "convpush":    self._show_convpush();   return
        if bid == "verify":      self._show_verify();     return
        if bid == "list-reg":    self._show_registry();   return
        if bid == "list-keys":   self._show_keys();       return
        if bid == "eject":       self._eject();           return
        if bid == "update-reg":
            if not self._worker_running:
                self._worker_running = True
                self.run_worker(self._update_registry_impl, thread=True, exclusive=True)
            return
        if bid == "quit":        self.app.exit();         return

        # Dynamic content buttons — route by object identity
        btn = event.button
        if btn is getattr(self, '_catch_refresh_btn', None):
            self._show_catch(); return
        if btn is getattr(self, '_keys_refresh_btn', None):
            self._show_keys(); return
        if btn is getattr(self, '_verify_do_btn', None):
            if not self._worker_running:
                self._worker_running = True
                self.run_worker(self._verify_impl, thread=True, exclusive=True)
            return
        # Convert/ConvPush: select files
        if btn is getattr(self, '_conv_select_btn', None):
            self._pick_files()
            return
        if btn is getattr(self, '_conv_refresh_btn', None):
            self._refresh_convert_view()
            return
        # Convert: action buttons — start conversion, then ask about deleting originals
        for mode, attr in [("g3p", "_conv_g3p_btn"), ("txt", "_conv_txt_btn"), ("both", "_conv_both_btn")]:
            if btn is getattr(self, attr, None):
                if not self._worker_running and hasattr(self, '_convert_rows'):
                    n = sum(1 for r in self._convert_rows if r._checked)
                    if n == 0:
                        self.post_message(LogMessage("  [dim]No files selected[/]"))
                        return
                    self._run_convert(mode)
                return
        # Delete selected (Convert & Push)
        if btn is getattr(self, '_conv_del_btn', None):
            if hasattr(self, '_convert_rows'):
                n = sum(1 for r in self._convert_rows if r._checked)
                if n == 0:
                    self.post_message(LogMessage("  [dim]No files selected[/]"))
                    return
                self._confirm(f"Delete {n} file(s)?", lambda ok: self._delete_selected_convert() if ok else None)
            return
        # ConvPush: do it
        if btn is getattr(self, '_convpush_do_btn', None):
            if not self._worker_running and hasattr(self, '_convert_rows'):
                self._worker_running = True
                self.run_worker(self._convpush_impl, thread=True, exclusive=True)
            return

        # Install/Games: add file import buttons
        if btn is getattr(self, '_addin_add_btn', None):
            self._pick_file_for_import("addin")
            return
        if btn is getattr(self, '_game_add_btn', None):
            self._pick_file_for_import("game")
            return
        # Remove local items
        if btn is getattr(self, '_addin_remove_local_btn', None):
            rows = getattr(self, '_install_rows', [])
            selected = [r for r in rows if r._checked and getattr(r, '_addin', {}).get("source") == "local"]
            self._remove_local_impl(selected)
            return
        if btn is getattr(self, '_game_remove_local_btn', None):
            rows = getattr(self, '_game_rows', [])
            selected = [r for r in rows if r._checked and getattr(r, '_game', {}).get("source") == "local"]
            self._remove_local_impl(selected)
            return

        # Install/Remove/Games action buttons — route by identity
        if btn is getattr(self, '_install_do_btn', None):
            if not self._worker_running and hasattr(self, '_install_rows'):
                self._worker_running = True
                self.run_worker(self._install_impl, thread=True, exclusive=True)
            return
        if btn is getattr(self, '_games_do_btn', None):
            if not self._worker_running and hasattr(self, '_game_rows'):
                self._worker_running = True
                self.run_worker(self._games_impl, thread=True, exclusive=True)
            return
        if btn is getattr(self, '_remove_do_btn', None):
            if not self._worker_running and hasattr(self, '_install_rows'):
                self._worker_running = True
                self.run_worker(self._remove_impl, thread=True, exclusive=True)
            return

    # ── Escape → Home ──────────────────────────────────────────────

    def key_escape(self) -> None:
        self._show_home()

    # ── Eject ──────────────────────────────────────────────────────

    def _eject(self) -> None:
        def handle(result: bool):
            if result:
                from pcalc.cli import _eject as _eject_cli
                from pcalc.calculator import find_calculator
                calc = find_calculator()
                if calc:
                    _eject_cli(calc)
                self._show_home()

        self.app.push_screen(_EjectDialog(), handle)


# ── Eject Confirmation Dialog ──────────────────────────────────────


class _EjectDialog(ModalScreen):
    def compose(self) -> ComposeResult:
        yield Vertical(
            Label("Eject Calculator?", classes="title"),
            Label("Make sure all transfers are complete.", id="eject-msg"),
            Horizontal(
                Button("Yes, Eject", id="eject-yes", variant="error"),
                Button("Cancel",     id="eject-no",  variant="primary"),
                classes="button-row",
            ),
            classes="dialog-box",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "eject-yes")


# ── Generic Confirm Dialog ─────────────────────────────────────────


class ConfirmDialog(ModalScreen):
    """Generic yes/no confirmation dialog."""
    def __init__(self, message: str, yes_label: str = "Yes", no_label: str = "No") -> None:
        super().__init__()
        self._msg = message
        self._yes = yes_label
        self._no = no_label

    def compose(self) -> ComposeResult:
        yield Vertical(
            Label(self._msg, classes="title"),
            Horizontal(
                Button(self._yes, id="confirm-yes", variant="error"),
                Button(self._no,  id="confirm-no", variant="primary"),
                classes="button-row",
            ),
            classes="dialog-box",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "confirm-yes")


# ── App ────────────────────────────────────────────────────────────


class PanCalcApp(App):
    CSS = """
    .sidebar {
        width: 28;
        height: 1fr;
        border-right: solid $surface;
        overflow-y: auto;
        padding: 0 1;
    }

    .sidebar-title {
        text-style: bold;
        padding: 1 0 0 0;
        height: 3;
    }

    .sidebar-status {
        height: 3;
        padding: 0 0 1 0;
    }

    .sidebar-hint {
        height: 3;
        margin: 0;
        padding: 0 0 1 0;
    }

    .sidebar Button {
        width: 100%;
        margin: 0 0 1 0;
    }

    #content-panel {
        width: 1fr;
        height: 1fr;
        min-height: 100%;
        padding: 1 2;
    }

    .banner-box {
        border: none;
        height: auto;
        max-height: 23;
        margin: 0;
        padding: 0 1;
    }

    RichLog {
        border: solid $surface;
        height: 1fr;
        margin: 1 0;
    }

    .button-row-inline {
        height: 5;
        align: center middle;
    }

    .button-row-inline Button {
        margin: 0 1;
    }

    ListView {
        border: solid $surface;
        height: 1fr;
        margin: 1 0;
    }

    .select-list {
        height: 1fr;
        border: solid $surface;
        margin: 0;
        padding: 0 1;
        overflow-y: auto;
    }

    .select-list > Horizontal {
        height: 3;
        padding: 0 1;
    }

    .select-list > Horizontal:hover {
        background: $surface;
    }

    .toggle-cb {
        width: 4;
        padding: 0 0 0 1;
    }

    .toggle-text {
        width: 1fr;
        padding: 0 0 0 1;
    }

    #eject-msg {
        text-align: center;
        padding: 1 2;
    }

    .dialog-box {
        border: solid $primary;
        width: 50;
        height: 11;
        align: center middle;
    }
    """

    BINDINGS = [
        Binding("ctrl+s", "command_palette", "Search"),
    ]

    def on_mount(self) -> None:
        self.push_screen(MainScreen())


# ── Utility ────────────────────────────────────────────────────────


def _fmt_size(size: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"
