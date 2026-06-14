"""
pcalc/gui.py — Flet GUI for PanCalc Tools (core).
View builders live in gui_views.py.
"""

from __future__ import annotations

import asyncio
import shutil
from pathlib import Path

import flet as ft

from pcalc import __version__, config as pconfig, theme as ptheme
from pcalc import library as plibrary
from pcalc import registry as pregistry
from pcalc.calculator import find_calculator
from pcalc.cli import _eject as eject_calc
from pcalc.crypto import import_key as _import_key
from pcalc.crypto import (
    list_keys,
    official_key_info,
    trust_key as _trust_key,
    untrust_key as _untrust_key,
)
from pcalc.gui_views import ViewBuilder
from pcalc.installer import (
    install,
    remove,
    verify_addin,
)


# ── Helpers ─────────────────────────────────────────────────────────

def _fmt_size(size: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


async def run_sync(fn, *args, **kwargs):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: fn(*args, **kwargs))


def _create_theme() -> ft.Theme:
    primary_hex = ptheme.PRIMARY.lstrip("#")
    return ft.Theme(color_scheme_seed=primary_hex, use_material3=True)


ADDIN_EXTS = {".g3a", ".g3e"}
GAME_EXTS = {".rom", ".bin", ".gba", ".nes", ".sms", ".gg"}
ALL_EXTS = ADDIN_EXTS | GAME_EXTS
SAVE_EXTS = {".sav", ".srm", ".state", ".sgm", ".frz"}


# ── Main Application ────────────────────────────────────────────────

class PanCalcGUI:
    def __init__(self):
        self.page: ft.Page | None = None
        self.nav_rail: ft.NavigationRail | None = None
        self.content_area: ft.Column | None = None
        self.status_chip: ft.Chip | None = None
        self.registry_count: ft.Text | None = None
        self.games_count: ft.Text | None = None

        self.current_view_index = 0
        self.registry_data: list[dict] = []
        self.games_data: list[dict] = []
        self.installed_addin_ids: set[str] = set()
        self._dlg_result: bool | None = None

        self.views = ViewBuilder(self)

    def build(self, page: ft.Page) -> None:
        self.page = page
        page.title = f"PanCalc Tools v{__version__}"
        page.window.width = 1200
        page.window.height = 800
        page.window.min_width = 900
        page.window.min_height = 600
        page.theme = _create_theme()
        page.theme_mode = ft.ThemeMode.LIGHT
        page.scroll = None
        page.on_window_event = self._on_window_event

        saved = pconfig.get_all()
        if saved.get("window_width"):
            page.window.width = saved["window_width"]
        if saved.get("window_height"):
            page.window.height = saved["window_height"]
        if saved.get("theme_mode") == "dark":
            page.theme_mode = ft.ThemeMode.DARK
            page.theme = _create_theme()

        self.status_leading = ft.Container(
            content=ft.ProgressRing(width=14, height=14, stroke_width=2)
        )
        self.status_label = ft.Text("Scanning...", size=12)
        self.status_chip = ft.Chip(
            label=self.status_label,
            leading=self.status_leading,
            on_click=lambda _: asyncio.create_task(self._scan_calculator()),
        )

        self.registry_count = ft.Text("0 add-ins", size=11, color=ft.Colors.OUTLINE)
        self.games_count = ft.Text("0 games", size=11, color=ft.Colors.OUTLINE)

        page.appbar = ft.AppBar(
            title=ft.Row([
                ft.Text("PanCalc Tools", weight=ft.FontWeight.BOLD, size=18),
                ft.Text(f"v{__version__}", size=11, color=ft.Colors.OUTLINE),
                ft.Container(expand=True),
                self.status_chip,
                ft.IconButton(
                    icon=ft.Icons.REFRESH, tooltip="Refresh calculator",
                    icon_size=20,
                    on_click=lambda _: asyncio.create_task(self._scan_calculator()),
                ),
                ft.IconButton(
                    icon=ft.Icons.SYSTEM_UPDATE, tooltip="Update registry",
                    icon_size=20,
                    on_click=lambda _: asyncio.create_task(self._update_registry()),
                ),
                ft.IconButton(
                    icon=ft.Icons.EJECT, tooltip="Eject calculator",
                    icon_size=20,
                    on_click=lambda _: asyncio.create_task(self._eject()),
                ),
            ]),
            center_title=False,
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
        )

        self.nav_rail = ft.NavigationRail(
            selected_index=0,
            label_type=ft.NavigationRailLabelType.ALL,
            destinations=[
                ft.NavigationRailDestination(icon=ft.Icons.PUBLIC, label="Registry"),
                ft.NavigationRailDestination(icon=ft.Icons.SPORTS_ESPORTS, label="Games"),
                ft.NavigationRailDestination(icon=ft.Icons.INVENTORY, label="Installed"),
                ft.NavigationRailDestination(icon=ft.Icons.TRANSFORM, label="Convert"),
                ft.NavigationRailDestination(icon=ft.Icons.FOLDER_OPEN, label="Catch"),
                ft.NavigationRailDestination(icon=ft.Icons.KEY, label="PGP Keys"),
                ft.NavigationRailDestination(icon=ft.Icons.SETTINGS, label="Settings"),
            ],
            on_change=lambda e: self.switch_view(e.control.selected_index),
        )

        self.content_area = ft.Column(expand=True, scroll=ft.ScrollMode.AUTO)
        page.add(ft.Row([
            self.nav_rail,
            ft.VerticalDivider(),
            self.content_area,
        ], expand=True, vertical_alignment=ft.CrossAxisAlignment.STRETCH))
        page.update()

        self._set_content(
            ft.Column([
                ft.ProgressRing(width=32, height=32),
                ft.Container(height=10),
                ft.Text("Loading...", color=ft.Colors.OUTLINE),
            ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER, expand=True)
        )

        task = asyncio.create_task(self._init())
        def _init_done(t):
            try:
                exc = t.exception()
            except asyncio.CancelledError:
                return
            if exc and not isinstance(exc, asyncio.CancelledError):
                try:
                    self._show_snackbar(f"Init error: {exc}")
                except Exception:
                    pass
        task.add_done_callback(_init_done)

    async def _init(self):
        try:
            await asyncio.sleep(0.3)
            first_run = pconfig.get("first_run")
            if first_run is None or first_run is True:
                await self._show_first_run_wizard()
                pconfig.set("first_run", False)
            else:
                await self._scan_calculator()

            await self._load_registry_data()
            self._build_current_view()
        except Exception as e:
            if not isinstance(e, asyncio.CancelledError):
                try:
                    self._show_snackbar(f"Init error: {e}")
                except Exception:
                    pass
            raise

    async def _on_window_event(self, e: ft.WindowEvent):
        if e.type in (ft.WindowEventType.RESIZED, ft.WindowEventType.MOVED):
            pconfig.set("window_width", self.page.window.width)
            pconfig.set("window_height", self.page.window.height)

    def _build_current_view(self):
        builders = [
            self.views._build_registry_view,
            self.views._build_games_view,
            self.views._build_installed_view,
            self.views._build_convert_view,
            self.views._build_catch_view,
            self.views._build_pgp_keys_view,
            self.views._build_settings_view,
        ]
        builders[self.current_view_index]()

    def switch_view(self, index: int):
        self.current_view_index = index
        self._build_current_view()
        self.nav_rail.selected_index = index
        if self.page:
            self.page.update()

    def _set_content(self, *controls):
        self.content_area.controls.clear()
        for c in controls:
            self.content_area.controls.append(c)
        if self.page:
            self.page.update()

    # ── Helpers ─────────────────────────────────────────────────────

    def _show_snackbar(self, text: str, color: str | None = None):
        if not self.page:
            return
        self.page.show_dialog(
            ft.SnackBar(
                ft.Text(text, color=color or ft.Colors.ON_SURFACE),
                duration=3000,
                behavior=ft.SnackBarBehavior.FLOATING,
            )
        )

    async def _confirm(self, title: str, message: str) -> bool:
        self._dlg_result = None
        dlg = ft.AlertDialog(
            title=ft.Text(title),
            content=ft.Text(message),
            modal=True,
            actions=[
                ft.TextButton("Cancel", on_click=lambda _: self._dlg_close(dlg, False)),
                ft.TextButton("Confirm", on_click=lambda _: self._dlg_close(dlg, True)),
            ],
        )
        self.page.dialog = dlg
        dlg.open = True
        self.page.update()
        while self._dlg_result is None:
            await asyncio.sleep(0.05)
        return self._dlg_result

    def _dlg_close(self, dlg, result):
        self._dlg_result = result
        dlg.open = False
        self.page.update()

    # ── Async ops ───────────────────────────────────────────────────

    async def _scan_calculator(self):
        try:
            self.status_leading.content = ft.ProgressRing(width=14, height=14, stroke_width=2)
            self.status_label.value = "Scanning..."
            self.page.update()
        except Exception:
            pass

        calc = await run_sync(find_calculator)
        try:
            if calc:
                self.status_leading.content = ft.Icon(ft.Icons.CHECK_CIRCLE, color=ft.Colors.GREEN, size=16)
                self.status_label.value = f"{calc.model}  {_fmt_size(calc.storage_free)} free"
            else:
                self.status_leading.content = ft.Icon(ft.Icons.ERROR_OUTLINE, color=ft.Colors.RED, size=16)
                self.status_label.value = "No calculator"
            self.page.update()
        except Exception:
            pass

        if self.current_view_index == 2:
            self._build_current_view()
        return calc

    async def _update_registry(self):
        self._show_snackbar("Updating registry...")
        try:
            await run_sync(lambda: pregistry.get_registry(force=True))
            await run_sync(lambda: pregistry.get_games(force=True))
            self._show_snackbar("Registry updated")
        except RuntimeError as e:
            self._show_snackbar(f"Failed: {e}")
        await self._load_registry_data()
        if self.current_view_index in (0, 1):
            self._build_current_view()

    async def _load_registry_data(self):
        try:
            self.registry_data = await run_sync(pregistry.get_registry)
        except RuntimeError:
            self.registry_data = []
        try:
            self.games_data = await run_sync(pregistry.get_games)
        except RuntimeError:
            self.games_data = []
        self.registry_count.value = f"{len(self.registry_data)} add-ins"
        self.games_count.value = f"{len(self.games_data)} games"
        if self.current_view_index in (0, 1):
            self._build_current_view()

    async def _eject(self):
        calc = await run_sync(find_calculator)
        if not calc:
            self._show_snackbar("No calculator to eject")
            return
        await run_sync(eject_calc, calc)
        self._show_snackbar("Calculator ejected")
        await self._scan_calculator()

    # ── First-run wizard ────────────────────────────────────────────

    async def _show_first_run_wizard(self):
        PAGE_COUNT = 3
        current = [0]

        wizard_container = ft.Column(width=400, horizontal_alignment=ft.CrossAxisAlignment.CENTER)
        dlg = ft.AlertDialog(content=wizard_container, modal=True)
        self.page.dialog = dlg

        def render():
            step = current[0]
            content = []
            if step == 0:
                content = [
                    ft.Text("Welcome to PanCalc Tools!", size=22, weight=ft.FontWeight.BOLD),
                    ft.Container(height=10),
                    ft.Icon(ft.Icons.USB, size=64, color=ptheme.PRIMARY),
                    ft.Container(height=10),
                    ft.Text("Manage add-ins, games, and media on your Casio Prizm calculator.",
                            text_align=ft.TextAlign.CENTER),
                    ft.Container(height=10),
                    ft.Text("To get started:"),
                    ft.Text("1. Connect your calculator via USB"),
                    ft.Text("2. Press F1 for mass storage mode"),
                    ft.Container(height=10),
                    ft.Row(
                        [ft.TextButton("Skip", on_click=lambda _: _finish()),
                         ft.FilledButton("Next →", on_click=lambda _: _next())],
                        alignment=ft.MainAxisAlignment.END,
                    ),
                ]
            elif step == 1:
                def _do_scan():
                    async def work():
                        calc = await run_sync(find_calculator)
                        content.clear()
                        content.append(ft.Text("Detecting Calculator", size=22, weight=ft.FontWeight.BOLD))
                        content.append(ft.Container(height=10))
                        if calc:
                            content.append(ft.Icon(ft.Icons.CHECK_CIRCLE, size=64, color=ft.Colors.GREEN))
                            content.append(ft.Text(f"✅ {calc.model} detected!", weight=ft.FontWeight.BOLD))
                        else:
                            content.append(ft.Icon(ft.Icons.ERROR_OUTLINE, size=64, color=ft.Colors.RED))
                            content.append(ft.Text("❌ No calculator detected"))
                            content.append(ft.Text("Make sure it's connected and in F1 mode."))
                        content.append(ft.Container(height=10))
                        content.append(ft.Row(
                            [ft.TextButton("Back", on_click=lambda _: setattr(current, 0, 0) or render()),
                             ft.FilledButton("Next →" if calc else "Skip", on_click=lambda _: _next())],
                            alignment=ft.MainAxisAlignment.END,
                        ))
                        wizard_container.controls = content
                        dlg.update()
                    asyncio.create_task(work())

                content = [
                    ft.Text("Detecting Calculator", size=22, weight=ft.FontWeight.BOLD),
                    ft.Container(height=10),
                    ft.ProgressRing(width=40, height=40),
                    ft.Container(height=10),
                    ft.Text("Scanning connected devices..."),
                ]
                wizard_container.controls = content
                dlg.open = True
                self.page.update()
                _do_scan()
                return
            else:
                content = [
                    ft.Text("Update Registry", size=22, weight=ft.FontWeight.BOLD),
                    ft.Container(height=10),
                    ft.Text("Download the latest add-in and game catalogs?"),
                    ft.Container(height=10),
                    ft.Row(
                        [ft.TextButton("Later", on_click=lambda _: _finish()),
                         ft.FilledButton("Update", on_click=lambda _: _do_update())],
                        alignment=ft.MainAxisAlignment.END,
                    ),
                ]

                async def _do_update():
                    try:
                        await run_sync(lambda: pregistry.get_registry(force=True))
                        await run_sync(lambda: pregistry.get_games(force=True))
                    except RuntimeError:
                        pass
                    _finish()

            wizard_container.controls = content
            dlg.open = True
            if self.page:
                self.page.update()

        def _next():
            current[0] = min(current[0] + 1, PAGE_COUNT - 1)
            render()

        def _finish():
            dlg.open = False
            if self.page:
                self.page.update()
            asyncio.create_task(self._scan_calculator())

        render()
        while dlg.open:
            await asyncio.sleep(0.1)

    # ── Shared actions (called by views) ────────────────────────────

    async def _show_addin_detail(self, d: dict):
        name = d.get("name", d.get("id", "?"))
        aid = d.get("id", "?")
        desc = d.get("description", "No description")
        author = d.get("author", "?")
        ver = d.get("version", "?")
        category = d.get("category", "?")
        url = d.get("url", "")
        compatible = ", ".join(d.get("compatible", []))
        size = d.get("size_kb", 0)

        lines = [
            ft.Text(name, size=18, weight=ft.FontWeight.BOLD),
            ft.Container(height=4),
            ft.Text(desc, italic=True, color=ft.Colors.ON_SURFACE_VARIANT),
            ft.Container(height=8),
            ft.Row([ft.Text("ID:", weight=ft.FontWeight.BOLD), ft.Text(aid)]),
            ft.Row([ft.Text("Author:", weight=ft.FontWeight.BOLD), ft.Text(author)]),
            ft.Row([ft.Text("Version:", weight=ft.FontWeight.BOLD), ft.Text(ver)]),
            ft.Row([ft.Text("Category:", weight=ft.FontWeight.BOLD), ft.Text(category)]),
        ]
        if compatible:
            lines.append(ft.Row([ft.Text("Compatible:", weight=ft.FontWeight.BOLD), ft.Text(compatible)]))
        if size:
            lines.append(ft.Row([ft.Text("Size:", weight=ft.FontWeight.BOLD), ft.Text(f"{size:.1f} KiB")]))
        if url:
            lines.append(ft.Row([ft.Text("URL:", weight=ft.FontWeight.BOLD),
                                 ft.Text(url, size=11, color=ft.Colors.PRIMARY, selectable=True)]))

        dlg = ft.AlertDialog(
            title=ft.Text(name),
            content=ft.Column(lines, width=450, tight=True, scroll=ft.ScrollMode.AUTO),
            actions=[
                ft.TextButton("Close", on_click=lambda _: self._dlg_close(dlg, None)),
                ft.FilledButton("Install", on_click=lambda _: asyncio.create_task(self._install_item(d, dlg))),
            ],
        )
        self._dlg_result = None
        self.page.dialog = dlg
        dlg.open = True
        self.page.update()
        while self._dlg_result is None:
            await asyncio.sleep(0.05)

    async def _install_item(self, d: dict, dlg: ft.AlertDialog | None = None):
        if dlg:
            dlg.open = False
            self.page.update()

        calc = await run_sync(find_calculator)
        if not calc:
            self._show_snackbar("No calculator connected")
            return

        self._show_snackbar(f"Installing {d.get('name', '?')}...")
        try:
            await run_sync(install, d, calc)
            self._show_snackbar(f"✅ {d.get('name', '?')} installed")
            if self.current_view_index in (0, 1):
                self._build_current_view()
        except RuntimeError as e:
            self._show_snackbar(f"Failed: {e}")

    async def _pick_file_for_import(self, item_type: str):
        def pick():
            try:
                import tkinter as tk
                from tkinter import filedialog
                root = tk.Tk()
                root.withdraw()
                root.lift()
                paths = list(filedialog.askopenfilenames(title=f"Select {item_type} file(s)"))
                root.destroy()
                return paths
            except Exception:
                return []

        paths = await run_sync(pick)
        if not paths:
            return

        imported = 0
        for p in paths:
            src = Path(p)
            if not src.is_file():
                continue
            if not plibrary.has_valid_extension(p, item_type):
                ok = await self._confirm("Warning", f"'{src.name}' has an unexpected extension. Import anyway?")
                if not ok:
                    continue
            try:
                await run_sync(plibrary.import_file, str(src), item_type=item_type)
                imported += 1
            except (ValueError, FileNotFoundError):
                pass

        self._show_snackbar(f"{imported} file(s) imported to library")
        await self._load_registry_data()
        if self.current_view_index in (0, 1):
            self._build_current_view()

    async def _verify_item(self, addin: dict, name: str):
        calc = await run_sync(find_calculator)
        if not calc:
            self._show_snackbar("No calculator")
            return
        try:
            ok = await run_sync(verify_addin, addin, calc)
            self._show_snackbar(f"{'✅' if ok else '❌'} {name} {'OK' if ok else 'FAILED'}")
        except RuntimeError as e:
            self._show_snackbar(f"Verify failed: {e}")

    async def _remove_item(self, addin: dict, name: str):
        ok = await self._confirm("Remove", f"Remove '{name}' from calculator?")
        if not ok:
            return
        calc = await run_sync(find_calculator)
        if not calc:
            self._show_snackbar("No calculator")
            return
        try:
            await run_sync(remove, addin["id"], calc)
            self._show_snackbar(f"🗑️ {name} removed")
            self._build_current_view()
        except RuntimeError as e:
            self._show_snackbar(f"Failed: {e}")

    async def _remove_orphan(self, path: Path):
        ok = await self._confirm("Remove Orphan", f"Delete '{path.name}' and associated save files?")
        if not ok:
            return
        try:
            path.unlink()
            from pcalc.installer import _clean_save_files
            await run_sync(_clean_save_files, path)
            self._show_snackbar(f"🗑️ {path.name} removed")
            self._build_current_view()
        except OSError as e:
            self._show_snackbar(f"Failed: {e}")

    async def _remove_file(self, path: Path):
        ok = await self._confirm("Delete", f"Delete '{path.name}' from calculator?")
        if not ok:
            return
        try:
            path.unlink()
            self._show_snackbar(f"🗑️ {path.name} deleted")
            self._build_current_view()
        except OSError as e:
            self._show_snackbar(f"Failed: {e}")

    async def _toggle_trust(self, keyid: str, trust: bool):
        try:
            if trust:
                await run_sync(_trust_key, keyid)
            else:
                await run_sync(_untrust_key, keyid)
            self._show_snackbar(f"Key {'trusted' if trust else 'untrusted'}")
            self._build_current_view()
        except RuntimeError as e:
            self._show_snackbar(f"Failed: {e}")

    async def _import_key_file(self):
        def pick():
            try:
                import tkinter as tk
                from tkinter import filedialog
                root = tk.Tk()
                root.withdraw()
                root.lift()
                paths = list(filedialog.askopenfilenames(title="Select PGP key file(s)"))
                root.destroy()
                return paths
            except Exception:
                return []

        paths = await run_sync(pick)
        if not paths:
            return
        for p in paths:
            try:
                data = Path(p).read_bytes()
                await run_sync(_import_key, data)
                self._show_snackbar(f"Key imported from {Path(p).name}")
            except Exception as e:
                self._show_snackbar(f"Failed to import {Path(p).name}: {e}")
        self._build_current_view()

    async def _pick_convert_files(self):
        def pick():
            try:
                import tkinter as tk
                from tkinter import filedialog
                root = tk.Tk()
                root.withdraw()
                root.lift()
                paths = list(filedialog.askopenfilenames(title="Select files to convert"))
                root.destroy()
                return paths
            except Exception:
                return []

        paths = await run_sync(pick)
        if not paths:
            return
        base = self._data_root()
        img_dir = base / "convert/images"
        doc_dir = base / "convert/documents"
        img_dir.mkdir(parents=True, exist_ok=True)
        doc_dir.mkdir(parents=True, exist_ok=True)
        img_exts = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tiff", ".tif", ".webp"}
        doc_exts = {".pdf", ".docx", ".doc", ".txt"}
        for p in paths:
            src = Path(p)
            ext = src.suffix.lower()
            dest = (img_dir if ext in img_exts else doc_dir) / src.name
            shutil.copy2(str(src), str(dest))
        self._show_snackbar(f"{len(paths)} file(s) added")
        self._build_current_view()

    async def _convert_single(self, f: Path, ftype: str):
        from pcalc import converter as pconverter
        base = self._data_root()
        g3p_dir = base / "converted/g3p"
        txt_dir = base / "converted/txt"
        g3p_dir.mkdir(parents=True, exist_ok=True)
        txt_dir.mkdir(parents=True, exist_ok=True)

        self._show_snackbar(f"Converting {f.name}...")
        try:
            if ftype == "IMG":
                await run_sync(pconverter.convert_image, str(f), str(g3p_dir / (f.stem + ".g3p")), 16)
                self._show_snackbar(f"✅ {f.name} → G3P")
            elif ftype == "DOC":
                await run_sync(pconverter.convert_text, str(f), str(txt_dir / (f.stem + ".txt")))
                await run_sync(pconverter.convert_document_g3p, str(f), str(g3p_dir / f.stem))
                self._show_snackbar(f"✅ {f.name} → G3P + TXT")
            self._build_current_view()
        except Exception as e:
            self._show_snackbar(f"Conversion failed: {e}")

    async def _push_files(self):
        from pcalc import converter as pconverter
        calc = await run_sync(find_calculator)
        if not calc:
            self._show_snackbar("No calculator connected")
            return
        base = self._data_root()
        pushed = 0
        for sub in ("g3p", "txt"):
            d = base / "converted" / sub
            if not d.exists():
                continue
            dest_sub = "fotos" if sub == "g3p" else "textos"
            dest_dir = calc.mount_path / "pthings" / dest_sub
            dest_dir.mkdir(parents=True, exist_ok=True)
            for f in sorted(d.iterdir()):
                if not f.is_file():
                    continue
                dest = dest_dir / f.name
                try:
                    dest.write_bytes(f.read_bytes())
                    pushed += 1
                except OSError:
                    pass
        if pushed:
            ok = await self._confirm("Clean up?", f"{pushed} file(s) pushed. Delete from converted/?")
            if ok:
                import shutil
                for sub in ("g3p", "txt"):
                    d = base / "converted" / sub
                    if d.exists():
                        shutil.rmtree(str(d))
                        d.mkdir(parents=True, exist_ok=True)
                self._build_current_view()
            self._show_snackbar(f"✅ {pushed} file(s) pushed")
        else:
            self._show_snackbar("No files to push")

    async def _toggle_dark(self, dark: bool):
        self.page.theme_mode = ft.ThemeMode.DARK if dark else ft.ThemeMode.LIGHT
        self.page.theme = _create_theme()
        pconfig.set("theme_mode", "dark" if dark else "light")
        self.page.update()

    def _data_root(self):
        from pcalc import _data_root
        return _data_root()

    async def _refresh_installed_view(self):
        self._build_current_view()


# ── Entry Point ──────────────────────────────────────────────────────

def main():
    ft.app(target=PanCalcGUI().build)
