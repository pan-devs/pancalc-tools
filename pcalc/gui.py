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
from pcalc.gui_views import GLOW_COLOR
from pcalc.crypto import import_key as _import_key
from pcalc.crypto import (
    list_keys,
    official_key_info,
    trust_key as _trust_key,
    untrust_key as _untrust_key,
)
from pcalc.gui_views import ViewBuilder, DropZone
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
def debug_log(msg: str):
    try:
        with open("/home/goduserr/Git/pan-devs/pancalc-tools/pcalc_debug.log", "a", encoding="utf-8") as f:
            f.write(f"[DEBUG] {msg}\n")
    except Exception:
        pass
async def run_sync(fn, *args, **kwargs):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: fn(*args, **kwargs))
def _do_push_sync(selected: set[str], mount_path: Path) -> tuple[list[str], list[str]]:
    """Sync copy loop — runs in a thread so the UI stays responsive."""
    from pcalc import library as plibrary
    pushed_paths: list[str] = []
    errors: list[str] = []
    for fpath in selected:
        src = Path(fpath)
        if not src.exists():
            continue
        sub = "g3p" if src.suffix.lower() == ".g3p" else "txt"
        dest_sub = "fotos" if sub == "g3p" else "textos"
        dest_dir = mount_path / "pthings" / dest_sub
        try:
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest = dest_dir / plibrary._sanitize(src.name)
            dest.write_bytes(src.read_bytes())
            pushed_paths.append(fpath)
        except OSError as e:
            errors.append(f"Failed to copy {src.name}: {e}")
    return pushed_paths, errors
def asyncio_create(coro):
    return asyncio.create_task(coro)
def _create_theme() -> ft.Theme:
    from pcalc.theme import PRIMARY, ACCENT, SUCCESS, ERROR, WARNING
    return ft.Theme(
        color_scheme=ft.ColorScheme(
            primary=PRIMARY,
            on_primary=ft.Colors.WHITE,
            primary_container=PRIMARY + "33",
            on_primary_container=PRIMARY,
            secondary=ACCENT,
            on_secondary=ft.Colors.WHITE,
            secondary_container=ACCENT + "33",
            on_secondary_container=ACCENT,
            tertiary=SUCCESS,
            on_tertiary=ft.Colors.WHITE,
            tertiary_container=SUCCESS + "33",
            on_tertiary_container=SUCCESS,
            error=ERROR,
            on_error=ft.Colors.WHITE,
            error_container=ERROR + "33",
            on_error_container=ERROR,
            surface=ft.Colors.SURFACE,
            on_surface=ft.Colors.ON_SURFACE,
            surface_container_highest=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            outline=ft.Colors.OUTLINE,
            outline_variant=ft.Colors.OUTLINE_VARIANT,
        ),
        use_material3=True,
    )
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
        self._ctrl_held = False
        self._multi_selected: set[str] = set()
        self._selected_registry_ids: set[str] = set()
        self._selection_mode = False
        self._confirm_busy = False
        self._installing = False
        self._trashing = False
        self._undo_snapshot: list[dict] = []
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
        page.on_keyboard_event = self._on_keyboard
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
        self.file_picker = ft.FilePicker()
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
            expand=True,
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
        # Trash bin at bottom of sidebar
        trash_content = ft.Container(
            ft.Column([
                ft.Icon(ft.Icons.DELETE, size=28, color=ft.Colors.ERROR),
                ft.Text("Trash", size=11, color=ft.Colors.ERROR),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=4),
            padding=12, border_radius=8,
            alignment=ft.Alignment.CENTER,
        )
        def _trash_badge(g):
            n = len(getattr(g, "_selected_registry_ids", set())) + len(getattr(g, "_multi_selected", set()))
            return (n or 1, "marked for deletion")
        # The whole sidebar is the trash drop zone: dropping anywhere on the
        # bar (not just the icon at the bottom) arms the "delete" state, while
        # the nav rail stays tappable.
        side_column = ft.Column([
            self.nav_rail,
            ft.Container(
                content=trash_content,
                padding=ft.Padding.only(top=8, bottom=8, left=8, right=8),
            ),
        ], expand=True)
        self.trash_zone = DropZone(
            self, side_column,
            color="#FF3B30", dest="trash",
            badge_fn=_trash_badge,
            on_accept=lambda e: asyncio_create(self._on_trash_drop(e)),
            border_radius=8,
            expand=True,
        )
        self.trash_target = self.trash_zone.build()
        self.content_area = ft.Column(expand=True, scroll=ft.ScrollMode.AUTO)
        page.add(ft.Row([
            ft.Container(
                content=self.trash_target,
                width=73,
            ),
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
                    self._show_snackbar(f"Init error: {exc}", type="error")
                except Exception:
                    pass
        task.add_done_callback(_init_done)
        asyncio.create_task(self._background_scanner_loop())
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
                    self._show_snackbar(f"Init error: {e}", type="error")
                except Exception:
                    pass
            raise
    async def _on_window_event(self, e: ft.WindowEvent):
        if e.type in (ft.WindowEventType.RESIZED, ft.WindowEventType.MOVED):
            pconfig.set("window_width", self.page.window.width)
            pconfig.set("window_height", self.page.window.height)
    def _on_keyboard(self, e: ft.KeyboardEvent):
        self._ctrl_held = e.ctrl
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
    def _show_snackbar(self, text: str, type: str = "info",
                       action_text: str | None = None, action_cb=None):
        if not self.page:
            return
        # Accent colors aligned with the Pan Devs palette
        accent_colors = {
            "info":    ptheme.PRIMARY,    # olive green
            "success": ptheme.SUCCESS,    # sage green
            "warning": ptheme.ACCENT,     # amber gold
            "error":   "#C62828",         # deep red (legible)
        }
        icons = {
            "info":    ft.Icons.INFO_OUTLINE,
            "success": ft.Icons.CHECK_CIRCLE_OUTLINE,
            "warning": ft.Icons.WARNING_AMBER_OUTLINED,
            "error":   ft.Icons.ERROR_OUTLINE,
        }
        accent = accent_colors.get(type, ptheme.PRIMARY)
        icon = icons.get(type, ft.Icons.INFO_OUTLINE)
        
        snack = ft.SnackBar(
            content=ft.Row([
                ft.Container(
                    width=4, height=32,
                    bgcolor=accent, border_radius=2,
                ),
                ft.Icon(icon, color=accent, size=20),
                ft.Text(text, color=ft.Colors.ON_SURFACE, expand=True, size=13),
            ], spacing=10, tight=True),
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
            duration=6000 if action_text else 4000,
            behavior=ft.SnackBarBehavior.FLOATING,
            show_close_icon=True,
            close_icon_color=ft.Colors.OUTLINE,
        )
        if action_text:
            snack.action = action_text
            snack.action_color = accent
            if action_cb:
                snack.on_action = lambda e: action_cb()
        self.page.show_dialog(snack)
    def _show_notification(self, text: str, type: str = "info", action_text: str | None = None, action_cb=None):
        """Show a persistent Banner notification (for errors/warnings that need attention)."""
        if not self.page:
            return
        accent_colors = {
            "info":    ptheme.PRIMARY,
            "success": ptheme.SUCCESS,
            "warning": ptheme.ACCENT,
            "error":   "#C62828",
        }
        icons = {
            "info":    ft.Icons.INFO,
            "success": ft.Icons.CHECK_CIRCLE,
            "warning": ft.Icons.WARNING,
            "error":   ft.Icons.ERROR,
        }
        accent = accent_colors.get(type, ptheme.PRIMARY)
        icon = icons.get(type, ft.Icons.INFO)
        
        actions = [ft.TextButton("Dismiss", on_click=lambda _: self._dismiss_banner(banner),
                                 style=ft.ButtonStyle(color=accent))]
        if action_text and action_cb:
            actions.insert(0, ft.TextButton(action_text, on_click=action_cb,
                                            style=ft.ButtonStyle(color=accent)))
        
        banner = ft.Banner(
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
            leading=ft.Icon(icon, color=accent, size=40),
            content=ft.Text(text, color=ft.Colors.ON_SURFACE, size=14),
            actions=actions,
            force_actions_below=True,
        )
        self.page.banner = banner
        banner.open = True
        self.page.update()
    def _dismiss_banner(self, banner: ft.Banner):
        banner.open = False
        self.page.update()
    async def _confirm(self, title: str, message: str) -> bool:
        debug_log(f"Entering _confirm with title='{title}', message='{message}'")
        if self._confirm_busy:
            debug_log("Another confirm dialog is active, dismissing it first")
            # Cancel the previous dialog by setting result to False
            self._dlg_result = False
            await asyncio.sleep(0.1)  # let the previous loop pick up the result
        self._confirm_busy = True
        try:
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
            self.page.show_dialog(dlg)
            debug_log("Confirm dialog shown, entering loop...")
            while self._dlg_result is None:
                await asyncio.sleep(0.05)
            result = self._dlg_result
            debug_log(f"Loop finished, returning result={result}")
            return result
        finally:
            self._confirm_busy = False
    def _dlg_close(self, dlg, result):
        debug_log(f"_dlg_close called with result={result}")
        self._dlg_result = result
        dlg.open = False
        dlg.update()
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
        self._show_snackbar("Updating registry...", type="info")
        try:
            await run_sync(lambda: pregistry.get_registry(force=True))
            await run_sync(lambda: pregistry.get_games(force=True))
            self._show_snackbar("Registry updated", type="success")
        except RuntimeError as e:
            self._show_snackbar(f"Failed: {e}", type="error")
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
            self._show_snackbar("No calculator to eject", type="warning")
            return
        await run_sync(eject_calc, calc)
        self._show_snackbar("Calculator ejected", type="success")
        await self._scan_calculator()
    # ── First-run wizard ────────────────────────────────────────────
    async def _show_first_run_wizard(self):
        PAGE_COUNT = 3
        current = [0]
        wizard_container = ft.Column(width=400, horizontal_alignment=ft.CrossAxisAlignment.CENTER)
        dlg = ft.AlertDialog(content=wizard_container, modal=True)
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
                            content.append(ft.Text(f"{calc.model} detected!", weight=ft.FontWeight.BOLD))
                        else:
                            content.append(ft.Icon(ft.Icons.ERROR_OUTLINE, size=64, color=ft.Colors.RED))
                            content.append(ft.Text("No calculator detected"))
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
                if not dlg.open:
                    self.page.show_dialog(dlg)
                else:
                    dlg.update()
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
            if not dlg.open:
                self.page.show_dialog(dlg)
            else:
                dlg.update()
        def _next():
            current[0] = min(current[0] + 1, PAGE_COUNT - 1)
            render()
        def _finish():
            dlg.open = False
            dlg.update()
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
        def _close_detail(_):
            dlg.open = False
            dlg.update()
        dlg = ft.AlertDialog(
            title=ft.Text(name),
            content=ft.Column(lines, width=450, tight=True, scroll=ft.ScrollMode.AUTO),
            actions=[
                ft.TextButton("Close", on_click=_close_detail),
                ft.FilledButton("Install", on_click=lambda _: asyncio.create_task(self._install_item(d, dlg))),
            ],
        )
        self.page.show_dialog(dlg)
        while dlg.open:
            await asyncio.sleep(0.05)
    async def _install_item(self, d: dict, dlg: ft.AlertDialog | None = None):
        debug_log(f"_install_item called for id='{d.get('id')}'")
        if dlg:
            debug_log("Closing detail dialog...")
            dlg.open = False
            dlg.update()
            await asyncio.sleep(0.1)  # allow detail dialog close to complete
        if pconfig.get("confirm_install"):
            debug_log("confirm_install is enabled, showing confirmation...")
            ok = await self._confirm("Install", f"Install '{d.get('name', d.get('id', '?'))}' to calculator?")
            debug_log(f"confirm result ok={ok}")
            if not ok:
                return
        calc = await run_sync(find_calculator)
        if not calc:
            self._show_snackbar("No calculator connected", type="warning")
            return
        self._show_snackbar(f"Installing {d.get('name', '?')}...", type="info")
        try:
            await run_sync(install, d, calc)
            self._show_snackbar(f"{d.get('name', '?')} installed", type="success")
            if self.current_view_index in (0, 1):
                self._build_current_view()
        except RuntimeError as e:
            self._show_snackbar(f"Failed: {e}", type="error")
    async def _install_selected(self, _e=None, item_ids: list[str] | None = None):
        """Install all items in _selected_registry_ids, or given item_ids."""
        debug_log(f"_install_selected called with item_ids={item_ids}")
        if self._installing:
            debug_log("Already installing, ignoring duplicate call")
            return
        self._installing = True
        try:
            await self._install_selected_inner(item_ids=item_ids)
        finally:
            self._installing = False
    async def _install_selected_inner(self, item_ids: list[str] | None = None):
        if item_ids is not None:
            ids_to_install = item_ids
        else:
            ids_to_install = list(self._selected_registry_ids)
        debug_log(f"ids_to_install={ids_to_install}")
        if not ids_to_install:
            self._show_snackbar("No items selected — long-press to select items first", type="info")
            return
        if pconfig.get("confirm_install"):
            debug_log("confirm_install is enabled, showing confirmation...")
            ok = await self._confirm("Install", f"Install {len(ids_to_install)} item(s) to calculator?")
            debug_log(f"confirm result ok={ok}")
            if not ok:
                return
        calc = await run_sync(find_calculator)
        if not calc:
            self._show_snackbar("No calculator connected", type="warning")
            return
        ok_count = 0
        for item_id in ids_to_install:
            # Resolve from registry_data, games_data, or local library
            d = None
            for rd in self.registry_data:
                if rd.get("id") == item_id:
                    d = rd.copy()
                    d["_source"] = "registry"
                    break
            if d is None:
                for gd in self.games_data:
                    if gd.get("id") == item_id:
                        d = gd.copy()
                        d["_source"] = "game"
                        break
            if d is None:
                lib = plibrary.get("addin", item_id)
                if lib:
                    d = lib.copy()
                    d["local_path"] = lib.get("local_path")
                    d["_source"] = "local"
            if d is None:
                lib = plibrary.get("game", item_id)
                if lib:
                    d = lib.copy()
                    d["local_path"] = lib.get("local_path")
                    d["_source"] = "local"
            if d is None:
                continue
            try:
                from pcalc.installer import install
                name = d.get("name", item_id)
                self._show_snackbar(f"Installing {name}...", type="info")
                await run_sync(install, d, calc)
                ok_count += 1
            except RuntimeError as exc:
                self._show_snackbar(f"Failed {name}: {exc}", type="error")
        if ok_count:
            self._show_snackbar(f"Installed {ok_count} item(s)", type="success")
        elif ids_to_install:
            self._show_snackbar("No installable items in selection", type="info")
        if item_ids is None:
            self._selected_registry_ids.clear()
        self._selection_mode = False
        if self.current_view_index in (0, 1):
            self._build_current_view()
    async def _pick_file_for_import(self, item_type: str):
        exts = ["g3a", "g3e"] if item_type == "addin" else ["rom", "bin", "gba", "nes", "sms", "gg"]
        files = await self.file_picker.pick_files(
            allow_multiple=True,
            dialog_title=f"Select {item_type} file(s)",
            file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=exts,
        )
        if files:
            paths = [f.path for f in files]
            await self._handle_import(paths, item_type)
    async def _handle_import(self, paths: list[str], item_type: str):
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
        if imported:
            self._show_snackbar(f"{imported} file(s) imported to library", type="success")
        else:
            self._show_snackbar("No valid files imported", type="warning")
        await self._load_registry_data()
        if self.current_view_index in (0, 1):
            self._build_current_view()
    async def _verify_item(self, addin: dict, name: str):
        calc = await run_sync(find_calculator)
        if not calc:
            self._show_snackbar("No calculator", type="warning")
            return
        try:
            ok = await run_sync(verify_addin, addin, calc)
            self._show_snackbar(f"{name} {'OK' if ok else 'FAILED'}", type="success" if ok else "error")
        except RuntimeError as e:
            self._show_snackbar(f"Verify failed: {e}", type="error")
    async def _remove_item(self, addin: dict, name: str):
        if pconfig.get("confirm_remove"):
            ok = await self._confirm("Remove", f"Remove '{name}' from calculator?")
            if not ok:
                return
        calc = await run_sync(find_calculator)
        if not calc:
            self._show_snackbar("No calculator", type="warning")
            return
        try:
            await run_sync(remove, addin["id"], calc)
            self._show_snackbar(f"🗑️ {name} removed", type="success")
            self._build_current_view()
        except RuntimeError as e:
            self._show_snackbar(f"Failed: {e}", type="error")
    async def _remove_orphan(self, path: Path):
        if pconfig.get("confirm_remove"):
            ok = await self._confirm("Remove Orphan", f"Delete '{path.name}' and associated save files?")
            if not ok:
                return
        try:
            path.unlink()
            from pcalc.installer import _clean_save_files
            await run_sync(_clean_save_files, path)
            self._show_snackbar(f"🗑️ {path.name} removed", type="success")
            self._build_current_view()
        except OSError as e:
            self._show_snackbar(f"Failed: {e}", type="error")
    async def _remove_file(self, path: Path):
        if pconfig.get("confirm_remove"):
            ok = await self._confirm("Delete", f"Delete '{path.name}' from calculator?")
            if not ok:
                return
        try:
            path.unlink()
            self._show_snackbar(f"🗑️ {path.name} deleted", type="success")
            self._build_current_view()
        except OSError as e:
            self._show_snackbar(f"Failed: {e}", type="error")
    async def _toggle_trust(self, keyid: str, trust: bool):
        try:
            if trust:
                await run_sync(_trust_key, keyid)
            else:
                await run_sync(_untrust_key, keyid)
            self._show_snackbar(f"Key {'trusted' if trust else 'untrusted'}", type="success")
            self._build_current_view()
        except RuntimeError as e:
            self._show_snackbar(f"Failed: {e}", type="error")
    async def _import_key_file(self):
        files = await self.file_picker.pick_files(
            allow_multiple=True,
            dialog_title="Select PGP key file(s)",
            file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=["asc", "gpg", "pgp", "key", "pub"],
        )
        if files:
            paths = [f.path for f in files]
            for p in paths:
                try:
                    data = Path(p).read_bytes()
                    await run_sync(_import_key, data)
                    self._show_snackbar(f"Key imported from {Path(p).name}", type="success")
                except Exception as e:
                    self._show_notification(f"Failed to import {Path(p).name}: {e}", type="error")
            self._build_current_view()
    async def _pick_convert_files(self):
        files = await self.file_picker.pick_files(
            allow_multiple=True,
            dialog_title="Select files to convert",
            file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=["png", "jpg", "jpeg", "bmp", "gif", "tiff", "tif", "webp",
                                "pdf", "docx", "doc", "txt"],
        )
        if files:
            paths = [f.path for f in files]
            await self._handle_convert_pick(paths)
    async def _handle_convert_pick(self, paths: list[str]):
        base = self._data_root()
        img_dir = base / "convert/images"
        doc_dir = base / "convert/documents"
        img_dir.mkdir(parents=True, exist_ok=True)
        doc_dir.mkdir(parents=True, exist_ok=True)
        img_exts = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tiff", ".tif", ".webp"}
        doc_exts = {".pdf", ".docx", ".doc", ".txt"}
        added = 0
        for p in paths:
            src = Path(p)
            ext = src.suffix.lower()
            dest = (img_dir if ext in img_exts else doc_dir) / src.name
            try:
                shutil.copy2(str(src), str(dest))
                added += 1
            except OSError:
                pass
        if added:
            self._show_snackbar(f"{added} file(s) added for conversion", type="success")
        else:
            self._show_snackbar("No files added", type="warning")
        self._build_current_view()
    async def _convert_single(self, f: Path, ftype: str, target_section: str = "both",
                              on_progress=None) -> list:
        """Convert a single file. Calls on_progress(file_frac) with 0.0..1.0 progress
        for THIS file as strips/pages are produced (called from a worker thread)."""
        from pcalc import converter as pconverter
        base = self._data_root()
        g3p_dir = base / "converted/g3p"
        txt_dir = base / "converted/txt"
        g3p_dir.mkdir(parents=True, exist_ok=True)
        txt_dir.mkdir(parents=True, exist_ok=True)
        self._show_snackbar(f"Converting {f.name} → {target_section}...", type="info")

        g3p_want = target_section in ("images", "both")
        txt_want = target_section in ("text", "both")
        units_total = int(g3p_want) + int(txt_want)
        units_done = 0

        def _report(unit_frac: float):
            if not on_progress:
                return
            try:
                ffrac = (units_done + unit_frac) / max(units_total, 1)
                on_progress(min(max(ffrac, 0.0), 1.0))
            except Exception:
                pass

        def _mk_cb():
            def cb(done: int, total: int):
                _report((done / total) if total else 1.0)
            return cb

        generated = []
        try:
            success = False
            if ftype == "IMG":
                if g3p_want:
                    out = g3p_dir / (f.stem + ".g3p")
                    await run_sync(pconverter.convert_image, str(f), str(out), 16, "auto", 16, _mk_cb())
                    units_done += 1
                    _report(1.0)
                    generated.append(out)
                    success = True
                if txt_want:
                    out = txt_dir / (f.stem + ".txt")
                    await run_sync(pconverter.convert_text, str(f), str(out), _mk_cb())
                    units_done += 1
                    _report(1.0)
                    generated.append(out)
                    success = True
            elif ftype == "DOC":
                if g3p_want:
                    out = g3p_dir / f.stem
                    await run_sync(pconverter.convert_document_g3p, str(f), str(out), 16, 16, _mk_cb())
                    units_done += 1
                    _report(1.0)
                    generated.append(out)
                    success = True
                if txt_want:
                    out = txt_dir / (f.stem + ".txt")
                    await run_sync(pconverter.convert_text, str(f), str(out), _mk_cb())
                    units_done += 1
                    _report(1.0)
                    generated.append(out)
                    success = True

            if success:
                # Delete source file after successful conversion
                try:
                    f.unlink()
                except OSError:
                    pass
                self._show_snackbar(f"{f.name} → {target_section}", type="success")
            else:
                self._show_snackbar(f"⚠️ {f.name}: no conversion for {target_section}", type="warning")
        except Exception as e:
            self._show_notification(f"Conversion failed: {e}", type="error")
        return generated
    async def _push_files(self, paths: list[str] | None = None):
        # Prevent concurrent pushes
        if getattr(self, '_pushing', False):
            self._show_snackbar("Push already in progress", type="warning")
            return
        if paths is not None:
            selected = list(paths)
        else:
            selected = sorted(self.views._selected_push_paths)
        if not selected:
            self._show_snackbar("No files selected. Check the files you want to push.", type="warning")
            return
        if pconfig.get("confirm_push"):
            debug_log("confirm_push is enabled, showing confirmation...")
            ok = await self._confirm("Push", f"Push {len(selected)} file(s) to calculator?")
            debug_log(f"confirm result ok={ok}")
            if not ok:
                return
        self._pushing = True
        calc = await run_sync(find_calculator)
        if not calc:
            self._pushing = False
            self._show_snackbar("No calculator connected", type="warning")
            return
        # Show "Pushing..." state on button
        self.views._push_active = True
        self._build_current_view()
        pushed_paths, errors = await run_sync(_do_push_sync, selected, calc.mount_path)
        # Auto-delete pushed files BEFORE rebuilding view
        if pushed_paths:
            for fpath in pushed_paths:
                src = Path(fpath)
                if src.exists():
                    src.unlink()
            self.views._selected_push_paths.difference_update(pushed_paths)
        self._pushing = False
        self.views._push_active = False
        self._selection_mode = False
        self._multi_selected.difference_update(pushed_paths)
        self._build_current_view()
        if errors:
            self._show_notification("Errors: " + "; ".join(errors), type="error")
        if pushed_paths:
            self._show_snackbar(f"{len(pushed_paths)} file(s) pushed and deleted", type="success")
        elif not errors:
            self._show_snackbar("No valid selected files found.", type="warning")
    async def _toggle_dark(self, dark: bool):
        self.page.theme_mode = ft.ThemeMode.DARK if dark else ft.ThemeMode.LIGHT
        self.page.theme = _create_theme()
        pconfig.set("theme_mode", "dark" if dark else "light")
        self._build_current_view()
        self.page.update()
    def _data_root(self):
        from pcalc import _data_root
        return _data_root()
    async def _remove_local_library_item(self, item_id: str, item_type: str):
        """Remove an item from the local library."""
        try:
            from pcalc import library as plibrary
            ok = plibrary.remove(item_id)
            if ok:
                self._show_snackbar(f"Deleted from local library", type="success")
            else:
                self._show_snackbar(f"Item not found", type="warning")
        except Exception as e:
            self._show_notification(f"Failed to delete: {e}", type="error")
        await self._load_registry_data()
        self._build_current_view()
    async def _delete_convert_input(self, path: Path, source_dir: Path):
        """Delete an input file from convert/ folder."""
        try:
            full_path = source_dir / path.name
            if full_path.exists():
                full_path.unlink()
                self._multi_selected.discard(str(full_path))
                self._show_snackbar(f"Deleted input file: {path.name}", type="success")
            else:
                self._show_snackbar(f"File not found", type="warning")
        except Exception as e:
            self._show_notification(f"Failed to delete: {e}", type="error")
        self._build_current_view()
    # ── Undo helpers ────────────────────────────────────────────────
    def _reset_undo(self):
        self._undo_snapshot = []

    def _snap_file(self, path: Path):
        """Snapshot a file that is about to be deleted so it can be restored."""
        try:
            if path.exists() and path.is_file():
                self._undo_snapshot.append({"kind": "file", "path": str(path), "data": path.read_bytes()})
        except OSError:
            pass

    def _snap_save_companions(self, rom_path: Path):
        """Snapshot companion save/state files that _clean_save_files will delete."""
        from pcalc.installer import SAVE_EXTS
        stem = rom_path.stem
        parent = rom_path.parent
        candidates = []
        for ext in SAVE_EXTS:
            candidates.append(rom_path.with_suffix(ext))
            candidates.append(Path(str(rom_path) + ext))
        try:
            for f in parent.iterdir():
                if f.is_file() and f.suffix.lower() in SAVE_EXTS and f.stem.lower() == stem.lower():
                    candidates.append(f)
        except OSError:
            pass
        for p in candidates:
            self._snap_file(p)

    def _snap_library(self, entry: dict):
        """Snapshot a local library entry + its physical file before removal."""
        data = None
        lp = entry.get("local_path", "")
        if lp:
            try:
                p = Path(lp)
                if p.exists() and p.is_file():
                    data = p.read_bytes()
            except OSError:
                data = None
        self._undo_snapshot.append({"kind": "lib", "entry": entry, "data": data})

    async def _undo_trash(self):
        """Restore every file/library item captured during the last trash action."""
        from pcalc import library as plibrary
        snapshot = list(reversed(self._undo_snapshot))
        self._reset_undo()
        restored_files = 0
        restored_lib = 0
        try:
            for op in snapshot:
                try:
                    if op["kind"] == "file":
                        p = Path(op["path"])
                        p.parent.mkdir(parents=True, exist_ok=True)
                        p.write_bytes(op["data"] or b"")
                        restored_files += 1
                    elif op["kind"] == "lib":
                        ok = plibrary.restore(op["entry"], op["data"])
                        if ok:
                            restored_lib += 1
                except OSError:
                    pass
            if self.page:
                self._show_snackbar(f"Undid: restored {restored_files} file(s), {restored_lib} library item(s)",
                                    type="success")
        except Exception:
            pass
        if restored_files or restored_lib:
            await self._load_registry_data()
        self._build_current_view()
    async def _on_trash_drop(self, e: ft.DragTargetEvent):
        """Handle drop onto trash bin - delete item based on type."""
        debug_log("_on_trash_drop called")
        if self._trashing:
            debug_log("Already trashing, ignoring duplicate call")
            return
        if not e.src or not e.src.data:
            debug_log("No e.src or e.src.data, aborting trash drop")
            return
        self._trashing = True
        try:
            await self._on_trash_drop_inner(e)
        finally:
            self._trashing = False
    async def _on_trash_drop_inner(self, e: ft.DragTargetEvent):
        
        data = e.src.data
        item_type = data.get("item_type", "unknown")
        self._reset_undo()
        debug_log(f"Trash drop data={data}, item_type={item_type}")
        
        # Extract ALL types of deletable items from drag data
        all_paths = data.get("all_paths", None)
        if not all_paths:
            single = data.get("path", None)
            all_paths = [single] if single else []
        all_ids = data.get("all_ids", None)
        
        debug_log(f"all_paths={all_paths}, all_ids={all_ids}")
        
        if not all_paths and not all_ids and item_type not in ("convert_input", "converted"):
            debug_log("No deletable items, aborting")
            return
        
        # Handle convert_input/converted first (different cleanup logic)
        if item_type in ("convert_input", "converted"):
            deletable = [p for p in all_paths if Path(p).exists()]
            if pconfig.get("confirm_remove"):
                ok = await self._confirm("Delete", f"Delete {len(deletable)} converted file(s)?")
                if not ok:
                    return
            deleted = 0
            for p in all_paths:
                pp = Path(p)
                if pp.exists():
                    self._snap_file(pp)
                    pp.unlink()
                    deleted += 1
            if deleted:
                self.views._selected_push_paths.difference_update(all_paths)
                self._multi_selected.difference_update(all_paths)
                self._show_snackbar(
                    f"Deleted {deleted} file(s)", type="success",
                    action_text="UNDO",
                    action_cb=lambda: asyncio_create(self._undo_trash()),
                )
            else:
                self._show_snackbar("No files found to delete.", type="warning")
            self._selection_mode = False
            self._build_current_view()
            return
        
        # Confirmation dialog
        if pconfig.get("confirm_remove"):
            debug_log("confirm_remove is enabled, showing confirmation...")
            if all_ids and not all_paths:
                ok = await self._confirm("Delete Local", f"Delete {len(all_ids)} item(s) from local library?")
            elif all_paths and not all_ids:
                ok = await self._confirm("Delete", f"Delete {len(all_paths)} file(s)?")
            else:
                ok = await self._confirm("Delete", f"Delete {len(all_paths)} file(s) + {len(all_ids)} local item(s)?")
            debug_log(f"confirm result ok={ok}")
            if not ok:
                return
        
        need_registry_reload = False
        
        # Capture local library entries first so their physical files aren't
        # double-snapshotted when they also appear in all_paths.
        lib_snapshot_paths = set()
        if all_ids:
            for item_id in all_ids:
                entry = plibrary.get(item_id)
                if entry:
                    self._snap_library(entry)
                    lp = entry.get("local_path", "")
                    if lp:
                        lib_snapshot_paths.add(str(Path(lp)))
        
        # Delete calculator files (matched addins, orphans, pthings)
        if all_paths:
            from pcalc.installer import _clean_save_files
            for p in all_paths:
                pp = Path(p)
                if str(pp) in lib_snapshot_paths:
                    continue
                if pp.exists():
                    self._snap_file(pp)
                    try:
                        pp.unlink()
                    except OSError:
                        pass
                self._snap_save_companions(pp)
                await run_sync(_clean_save_files, pp)
            self._multi_selected.difference_update(all_paths)
            self._selected_registry_ids.clear()
        
        # Delete local library items
        if all_ids:
            count = 0
            for item_id in all_ids:
                ok = plibrary.remove(item_id)
                if ok:
                    count += 1
                self._multi_selected.discard(item_id)
                self._selected_registry_ids.discard(item_id)
            if count:
                need_registry_reload = True
        
        self._selection_mode = False
        # Always clear selection state so surviving (non-deleted) items never
        # render with the leftover "selected" border after a trash action.
        self._selected_registry_ids.clear()
        self._multi_selected.clear()
        if need_registry_reload:
            await self._load_registry_data()
        if all_ids or all_paths:
            self._build_current_view()
        if self._undo_snapshot:
            self._show_snackbar(
                f"Deleted {len(self._undo_snapshot)} item(s)", type="success",
                action_text="UNDO",
                action_cb=lambda: asyncio_create(self._undo_trash()),
            )
    async def _refresh_installed_view(self):
        self._build_current_view()
    async def _background_scanner_loop(self):
        last_mount = None
        last_free = None
        
        while True:
            await asyncio.sleep(2.0)
            try:
                calc = await run_sync(find_calculator)
                status_changed = False
                if calc is None:
                    if last_mount is not None:
                        status_changed = True
                    last_mount = None
                    last_free = None
                else:
                    if last_mount != str(calc.mount_path) or last_free != calc.storage_free:
                        status_changed = True
                    last_mount = str(calc.mount_path)
                    last_free = calc.storage_free
                
                # Update status UI safely ONLY if changed
                if status_changed and self.page:
                    if calc:
                        self.status_leading.content = ft.Icon(ft.Icons.CHECK_CIRCLE, color=ft.Colors.GREEN, size=16)
                        self.status_label.value = f"{calc.model}  {_fmt_size(calc.storage_free)} free"
                    else:
                        self.status_leading.content = ft.Icon(ft.Icons.ERROR_OUTLINE, color=ft.Colors.RED, size=16)
                        self.status_label.value = "No calculator"
                    
                    # Auto-refresh if currently on Installed (index 2) or Convert (index 3) view
                    if self.current_view_index in (2, 3):
                        self._build_current_view()
                    else:
                        self.page.update()
            except Exception:
                pass
# ── Entry Point ──────────────────────────────────────────────────────
def main():
    ft.app(target=PanCalcGUI().build)