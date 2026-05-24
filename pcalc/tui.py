"""
pcalc/tui.py — Textual TUI for PanCalc Tools.
"""

import os
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, Horizontal, ScrollableContainer
from textual.message import Message
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, Footer, Header, Label, ListItem, ListView, RichLog, Static
from textual.worker import Worker, WorkerState

from pcalc import theme


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
        if self._disabled:
            return f"[dim]{name}  {aid}  (installed)[/]"
        return f"[bold]{name}[/]  [dim]{aid}[/]"


class RemoveRow(ToggleRow):
    def __init__(self, index: int, display_name: str, filename: str,
                 checked: bool = False, disabled: bool = False) -> None:
        self._display_name = display_name
        self._filename = filename
        super().__init__(index, "", checked, disabled)

    @property
    def _label(self) -> str:
        return f"[bold]{self._display_name}[/]  [dim]{self._filename}[/]"


# ── Main Screen (sidebar + content panel) ──────────────────────────


class MainScreen(Screen):
    def compose(self) -> ComposeResult:
        yield Header()
        yield Horizontal(
            Vertical(
                Label("PanCalc Tools", classes="sidebar-title"),
                Button("🏠  Home",             id="home",      variant="primary"),
                Button("📂  Catch",            id="catch"),
                Button("📥  Install",          id="install"),
                Button("🗑️  Remove",           id="remove"),
                Button("🔄  Convert",          id="convert"),
                Button("📤  Conv & Push",      id="convpush"),
                Button("✅  Verify",           id="verify"),
                Button("📋  Registry",         id="list-reg"),
                Button("🔑  PGP Keys",         id="list-keys"),
                Button("⏏️   Eject",            id="eject"),
                Button("🚪  Quit",             id="quit"),
                Label(KEY_HINT, classes="sidebar-hint"),
                classes="sidebar",
            ),
            Vertical(id="content-panel"),
        )
        yield Footer()

    def on_mount(self) -> None:
        self._output = None   # current RichLog for status/output
        self._view = None     # current view name
        self._worker_running = False
        self._show_home()

    # ── Content helpers ────────────────────────────────────────────

    def _set_content(self, *widgets) -> None:
        panel = self.query_one("#content-panel")
        panel.remove_children()
        for w in widgets:
            panel.mount(w)
        if widgets:
            widgets[0].focus()

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

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        if event.state == WorkerState.ERROR:
            self._worker_running = False
            self._log(f"  [bold red]Worker failed[/]")

    # ── Home ───────────────────────────────────────────────────────

    def _show_home(self) -> None:
        from pcalc.calculator import find_calculator
        from pcalc.banner import PANDEVS_ASCII

        self._output = None
        self._view = "home"
        self._output = RichLog(highlight=True, markup=True, classes="banner-box")
        self._output.write(f"[bold {theme.S_PRIMARY}]{PANDEVS_ASCII.strip()}[/]")

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
            self._output.write(f"\n[bold]{calc.model}[/]  [dim]{calc.mount_path}[/]")
            self._output.write(f"  {known} add-ins found  ·  {dcount} files ({unk} unknown)")
        else:
            self._output.write(f"\n[dim]no calculator detected — connect via USB (F1)[/]")

        self._set_content(self._output)

    # ── Catch ──────────────────────────────────────────────────────

    def _show_catch(self) -> None:
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
        btn = Button("📥  Install Checked", id="install-do", variant="primary")
        btn.styles.margin = (1, 1, 0, 1)
        self._set_content(list_container, btn)

    def _install_impl(self) -> None:
        selected = [r for r in self._install_rows if r._checked and not r._disabled]
        if not selected:
            self.post_message(LogMessage("  [dim]No add-ins selected for install.[/]"))
            return

        from pcalc.calculator import require_calculator
        from pcalc.installer import install

        try:
            calc = require_calculator()
        except RuntimeError as e:
            self.post_message(LogMessage(f"  [red]{e}[/]"))
            return

        for row in selected:
            addin = row._addin
            name = addin.get("name", addin.get("id", "?"))
            self.post_message(LogMessage(f"  Installing [bold]{name}[/]..."))
            try:
                install(addin, calc)
                self.post_message(LogMessage(f"  ✅ [bold]{name}[/] installed"))
            except RuntimeError as e:
                self.post_message(LogMessage(f"  ❌ [bold]{name}[/]: [red]{e}[/]"))

        self.post_message(OperationDone())

    # ── Remove ─────────────────────────────────────────────────────

    def _show_remove(self) -> None:
        from pcalc.calculator import find_calculator
        from pcalc.installer import walk_calc
        from pcalc import registry

        self._view = "remove"

        entries: list = []
        calc = find_calculator()
        if calc:
            try:
                entries = [e for e in walk_calc(calc, registry.get_registry()) if e.addin]
            except RuntimeError:
                pass

        rows: list[RemoveRow] = []
        for i, e in enumerate(entries):
            name = e.addin.get("name", e.addin.get("id", "?"))
            rows.append(RemoveRow(i, name, e.name))

        self._install_rows = rows
        children = rows if rows else [Label("  [dim]No add-ins found on calculator[/]")]
        list_container = ScrollableContainer(*children, classes="select-list")
        self._install_list = list_container

        self._output = None
        btn = Button("🗑️  Remove Checked", id="remove-do", variant="error")
        btn.styles.margin = (1, 1, 0, 1)
        self._set_content(list_container, btn)

    def _remove_impl(self) -> None:
        selected = [r for r in self._install_rows if r._checked and not r._disabled]
        if not selected:
            self.post_message(LogMessage("  [dim]No add-ins selected for removal.[/]"))
            return

        from pcalc.calculator import require_calculator
        from pcalc.installer import remove

        try:
            calc = require_calculator()
        except RuntimeError as e:
            self.post_message(LogMessage(f"  [red]{e}[/]"))
            return

        for row in selected:
            name = row._display_name
            from pcalc import registry
            from pcalc.installer import walk_calc
            try:
                entries = [e for e in walk_calc(calc, registry.get_registry()) if e.addin]
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

        self.post_message(OperationDone())

    # ── Convert ────────────────────────────────────────────────────

    def _show_convert(self) -> None:
        self._output = None
        self._view = "convert"
        self._conv_img_g3p = Button("🖼️  Image → G3P")
        self._conv_img_txt = Button("📄  Image → TXT")
        self._conv_doc     = Button("📑  PDF/DOCX")
        row = Horizontal(
            self._conv_img_g3p,
            self._conv_img_txt,
            self._conv_doc,
            classes="button-row-inline",
        )
        out = RichLog(highlight=True, markup=True)
        self._output = out
        self._set_content(out, row)

    def _convert_impl(self, mode: str) -> None:
        from pcalc.converter import convert_image, convert_text, convert_document_g3p

        base = Path.home() / "Git/pan-devs/pancalc-tools"
        converted_dir = base / "converted"

        if mode in ("img-g3p", "img-txt"):
            src = base / "convert/images"
            if not src.exists():
                self.post_message(LogMessage("  [red]convert/images/ not found[/]"))
                return
            files = sorted(src.iterdir())
            pat = "g3p" if mode == "img-g3p" else "txt"
            dest_dir = converted_dir / pat
            dest_dir.mkdir(parents=True, exist_ok=True)
            for f in files:
                if not f.is_file():
                    continue
                try:
                    dest = dest_dir / f"{f.stem}.{pat}"
                    if mode == "img-g3p":
                        convert_image(str(f), str(dest), bit_depth=8)
                    else:
                        convert_text(str(f), str(dest))
                    self.post_message(LogMessage(f"  ✅ [bold]{f.name}[/]"))
                except Exception as e:
                    self.post_message(LogMessage(f"  ❌ [bold]{f.name}[/]: [red]{e}[/]"))
        else:
            src = base / "convert/documents"
            if not src.exists():
                self.post_message(LogMessage("  [red]convert/documents/ not found[/]"))
                return
            for f in sorted(src.iterdir()):
                if not f.is_file():
                    continue
                try:
                    out_base = str((converted_dir / "g3p" / f.stem).with_suffix(""))
                    convert_document_g3p(str(f), out_base)
                    self.post_message(LogMessage(f"  ✅ [bold]{f.name}[/]"))
                except Exception as e:
                    self.post_message(LogMessage(f"  ❌ [bold]{f.name}[/]: [red]{e}[/]"))

        self.post_message(OperationDone())

    # ── ConvPush ───────────────────────────────────────────────────

    def _show_convpush(self) -> None:
        self._output = None
        self._view = "convpush"
        self._convpush_img = Button("🖼️  Images → G3P & Push", variant="primary")
        self._convpush_doc = Button("📄  Docs → G3P & Push")
        row = Horizontal(
            self._convpush_img,
            self._convpush_doc,
            classes="button-row-inline",
        )
        out = RichLog(highlight=True, markup=True)
        self._output = out
        self._set_content(out, row)

    def _convpush_impl(self, mode: str) -> None:
        from pcalc.calculator import find_calculator
        from pcalc.converter import convert_image, convert_document_g3p

        calc = find_calculator()
        if not calc:
            self.post_message(LogMessage("  [red]No calculator detected[/]"))
            return

        base = Path.home() / "Git/pan-devs/pancalc-tools"
        pthings = calc.mount_path / "pthings"
        try:
            pthings.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            self.post_message(LogMessage(f"  [red]Failed to create pthings/: {e}[/]"))
            return

        if mode == "convpush-images":
            src = base / "convert/images"
            if not src.exists():
                self.post_message(LogMessage("  [red]convert/images/ not found[/]"))
                return
            import tempfile
            for f in sorted(src.iterdir()):
                if not f.is_file():
                    continue
                self.post_message(LogMessage(f"  Converting [bold]{f.name}[/]..."))
                try:
                    fd, tmp = tempfile.mkstemp(suffix=".g3p")
                    os.close(fd)
                    convert_image(str(f), tmp, bit_depth=8)
                    (pthings / (f.stem + ".g3p")).write_bytes(Path(tmp).read_bytes())
                    os.unlink(tmp)
                    self.post_message(LogMessage(f"  ✅ [bold]{f.name}[/]"))
                except Exception as e:
                    self.post_message(LogMessage(f"  ❌ [bold]{f.name}[/]: [red]{e}[/]"))
        else:
            src = base / "convert/documents"
            if not src.exists():
                self.post_message(LogMessage("  [red]convert/documents/ not found[/]"))
                return
            import tempfile
            for f in sorted(src.iterdir()):
                if not f.is_file():
                    continue
                self.post_message(LogMessage(f"  Converting [bold]{f.name}[/]..."))
                try:
                    td = tempfile.mkdtemp()
                    out_base = os.path.join(td, f.stem)
                    convert_document_g3p(str(f), out_base)
                    for pf in sorted(Path(td).iterdir()):
                        pf.rename(pthings / pf.name)
                    os.rmdir(td)
                    self.post_message(LogMessage(f"  ✅ [bold]{f.name}[/]"))
                except Exception as e:
                    self.post_message(LogMessage(f"  ❌ [bold]{f.name}[/]: [red]{e}[/]"))

        self.post_message(OperationDone())

    # ── Verify ─────────────────────────────────────────────────────

    def _show_verify(self) -> None:
        self._output = None
        self._view = "verify"
        self._verify_btn = Button("🔄  Run Verification", variant="primary")
        self._verify_btn.styles.margin = (1, 2)
        out = RichLog(highlight=True, markup=True)
        self._output = out
        self._set_content(out, self._verify_btn)

    def _verify_impl(self) -> None:
        from pcalc.installer import verify
        from pcalc.calculator import find_calculator
        from pcalc import registry as reg
        from pcalc.installer import walk_calc, iter_calc_files

        calc = find_calculator()
        if not calc:
            self.post_message(LogMessage("  [red]No calculator detected[/]"))
            return

        try:
            addins = reg.get_registry()
            entries = walk_calc(calc, addins)
            on_device = [f for f in iter_calc_files(entries) if f.addin]
        except RuntimeError:
            on_device = []

        if not on_device:
            self.post_message(LogMessage("  [dim]No add-ins found on calculator[/]"))
            return

        all_ok = True
        for f in on_device:
            name = f.addin.get("name", f.addin.get("id", "?"))
            try:
                ok = verify(f.addin["id"], calc) if f.addin else False
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
        from pcalc import registry

        self._view = "registry"
        try:
            addins = registry.get_registry()
        except RuntimeError:
            addins = []

        items = []
        for a in addins:
            aid = a.get("id", "?")
            name = a.get("name", aid)
            author = a.get("author", "")
            ver = a.get("version", "")
            items.append(ListItem(Label(
                f"[bold]{name}[/]  [dim]{aid}[/]  [italic]{author}[/]  [{theme.S_ACCENT}]{ver}[/]"
            )))
        if not items:
            items.append(ListItem(Label("[dim]Failed to load registry[/]")))

        self._output = None
        lv = ListView(*items)
        lv.styles.height = "1fr"
        self._set_content(lv)

    # ── PGP Keys ───────────────────────────────────────────────────

    def _show_keys(self) -> None:
        from pcalc.crypto import list_keys

        self._output = None
        self._view = "keys"
        out = RichLog(highlight=True, markup=True)

        keys = list_keys()
        if not keys:
            out.write("  [dim]No PGP keys imported.[/]")
            out.write("  Use 'pcalc import-key <file>' in the terminal.")
        else:
            for k in keys:
                trust = "✅ trusted" if k["trusted"] else "❌ untrusted"
                uid = k.get("uids", ["(no UID)"])[0]
                out.write(f"  [bold]{k['keyid']}[/]  {uid}")
                out.write(f"    Fingerprint: {k['fingerprint']}")
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
        if bid == "remove":      self._show_remove();     return
        if bid == "convert":     self._show_convert();    return
        if bid == "convpush":    self._show_convpush();   return
        if bid == "verify":      self._show_verify();     return
        if bid == "list-reg":    self._show_registry();   return
        if bid == "list-keys":   self._show_keys();       return
        if bid == "eject":       self._eject();           return
        if bid == "quit":        self.app.exit();         return

        # Dynamic content buttons — route by object identity
        btn = event.button
        if btn is getattr(self, '_catch_refresh_btn', None):
            self._show_catch(); return
        if btn is getattr(self, '_keys_refresh_btn', None):
            self._show_keys(); return
        if btn is getattr(self, '_verify_btn', None):
            if not self._worker_running:
                self._worker_running = True
                self.run_worker(self._verify_impl, thread=True, exclusive=True)
            return
        if btn is getattr(self, '_conv_img_g3p', None):
            if not self._worker_running:
                self._worker_running = True
                self.run_worker(lambda: self._convert_impl("img-g3p"), thread=True, exclusive=True)
            return
        if btn is getattr(self, '_conv_img_txt', None):
            if not self._worker_running:
                self._worker_running = True
                self.run_worker(lambda: self._convert_impl("img-txt"), thread=True, exclusive=True)
            return
        if btn is getattr(self, '_conv_doc', None):
            if not self._worker_running:
                self._worker_running = True
                self.run_worker(lambda: self._convert_impl("doc-conv"), thread=True, exclusive=True)
            return
        if btn is getattr(self, '_convpush_img', None):
            if not self._worker_running:
                self._worker_running = True
                self.run_worker(lambda: self._convpush_impl("convpush-images"), thread=True, exclusive=True)
            return
        if btn is getattr(self, '_convpush_doc', None):
            if not self._worker_running:
                self._worker_running = True
                self.run_worker(lambda: self._convpush_impl("convpush-docs"), thread=True, exclusive=True)
            return

        # Install/Remove action buttons
        if bid == "install-do":
            if not self._worker_running and hasattr(self, '_install_rows'):
                self._worker_running = True
                self.run_worker(self._install_impl, thread=True, exclusive=True)
            return
        if bid == "remove-do":
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
        padding: 1 0;
        height: 3;
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
        Binding("ctrl+p", "command_palette", "Search"),
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
