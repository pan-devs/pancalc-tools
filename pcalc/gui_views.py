"""
pcalc/gui_views.py — Flet GUI view builders for PanCalc Tools.
References core PanCalcGUI via self.gui.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import flet as ft

from pcalc import theme as ptheme
from pcalc.calculator import find_calculator
from pcalc.crypto import list_keys, official_key_info
from pcalc.installer import (
    _match_addin_by_filename,
    count_calc_files,
    iter_calc_files,
    walk_calc,
)

ADDIN_EXTS = {".g3a", ".g3e"}
GAME_EXTS = {".rom", ".bin", ".gba", ".nes", ".sms", ".gg"}
ALL_EXTS = ADDIN_EXTS | GAME_EXTS


def _icon_for_addin(d: dict) -> str:
    if d.get("emulator"):
        return ft.Icons.SPORTS_ESPORTS
    if d.get("category") == "games":
        return ft.Icons.SPORTS_ESPORTS
    return ft.Icons.EXTENSION


def _platform_badge(d: dict) -> str:
    if d.get("emulator"):
        return f"[{d.get('platform', '?')}] via {d['emulator']}"
    return ""


def _fmt_size(size: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


class ViewBuilder:
    def __init__(self, gui):
        self.gui = gui

    # ── 1. Registry View ───────────────────────────────────────────

    def _build_registry_view(self):
        g = self.gui
        if not g.registry_data:
            g._set_content(
                ft.Column([
                    ft.Text("Registry", size=20, weight=ft.FontWeight.BOLD),
                    ft.Container(height=10),
                    ft.Text("No add-ins loaded. Click the refresh button above.", color=ft.Colors.OUTLINE),
                ], expand=True)
            )
            return

        items = [self._build_registry_card(d) for d in g.registry_data[:50]]
        grid = ft.GridView(
            controls=items,
            expand=True, runs_count=0, max_extent=320,
            child_aspect_ratio=2.2, spacing=10, run_spacing=10,
            padding=ft.Padding.only(right=8),
        )
        import_btn = ft.ElevatedButton(
            "📁 Import Local Add-in", icon=ft.Icons.FILE_UPLOAD,
            on_click=lambda _: asyncio_create(g._pick_file_for_import("addin")),
        )
        g.registry_count.value = f"{len(g.registry_data)} add-ins"
        g._set_content(
            ft.Column([
                ft.Row([
                    ft.Text("Registry", size=20, weight=ft.FontWeight.BOLD),
                    g.registry_count, ft.Container(expand=True), import_btn,
                ], alignment=ft.MainAxisAlignment.START),
                ft.Container(height=8), grid,
            ], expand=True, scroll=ft.ScrollMode.AUTO)
        )

    def _build_registry_card(self, d: dict) -> ft.Card:
        g = self.gui
        name = d.get("name", d.get("id", "?"))
        aid = d.get("id", "?")
        ver = d.get("version", "")
        category = d.get("category", "")
        compatible = ", ".join(d.get("compatible", []))
        platform_info = _platform_badge(d)

        tags = []
        if category:
            tags.append(ft.Container(ft.Text(category, size=10), bgcolor=ft.Colors.SECONDARY_CONTAINER,
                                     border_radius=4, padding=ft.Padding.symmetric(vertical=2, horizontal=6)))
        if platform_info:
            tags.append(ft.Container(ft.Text(platform_info, size=10), bgcolor=ft.Colors.TERTIARY_CONTAINER,
                                     border_radius=4, padding=ft.Padding.symmetric(vertical=2, horizontal=6)))
        if compatible:
            tags.append(ft.Container(ft.Text(compatible, size=10), bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                                     border_radius=4, padding=ft.Padding.symmetric(vertical=2, horizontal=6)))

        is_installed = d.get("id", "") in getattr(g, "installed_addin_ids", set())
        return ft.Card(
            ft.Container(
                ft.Column([
                    ft.Row([
                        ft.Icon(_icon_for_addin(d), size=20),
                        ft.Text(name, weight=ft.FontWeight.BOLD, expand=True, size=14),
                        ft.Container(
                            ft.Text("install", size=10, color=ft.Colors.ON_PRIMARY),
                            bgcolor=ft.Colors.PRIMARY, border_radius=12,
                            padding=ft.Padding.symmetric(vertical=4, horizontal=10),
                        ) if not is_installed else ft.Text("✅", size=14),
                    ]),
                    ft.Row([ft.Text(aid, size=11, color=ft.Colors.OUTLINE)] +
                           ([ft.Text(f"v{ver}", size=11, color=ft.Colors.OUTLINE)] if ver else [])),
                    ft.Row(tags, wrap=True, spacing=4) if tags else ft.Container(),
                ], spacing=4, tight=True),
                padding=12,
                ink=True,
                on_click=lambda _, d=d: asyncio_create(g._show_addin_detail(d)),
            )
        )

    # ── 2. Games View ──────────────────────────────────────────────

    def _build_games_view(self):
        g = self.gui
        if not g.games_data:
            g._set_content(
                ft.Column([
                    ft.Text("Games", size=20, weight=ft.FontWeight.BOLD),
                    ft.Container(height=10),
                    ft.Text("No games available in registry.", color=ft.Colors.OUTLINE),
                ], expand=True)
            )
            return

        items = [self._build_registry_card(d) for d in g.games_data[:50]]
        grid = ft.GridView(
            controls=items, expand=True, runs_count=0, max_extent=320,
            child_aspect_ratio=2.2, spacing=10, run_spacing=10,
            padding=ft.Padding.only(right=8),
        )
        import_btn = ft.ElevatedButton(
            "📁 Import Local ROM", icon=ft.Icons.FILE_UPLOAD,
            on_click=lambda _: asyncio_create(g._pick_file_for_import("game")),
        )
        g._set_content(
            ft.Column([
                ft.Row([
                    ft.Text("Games", size=20, weight=ft.FontWeight.BOLD),
                    g.games_count, ft.Container(expand=True), import_btn,
                ]),
                ft.Container(height=8),
                ft.Text("Install emulators from Registry (e.g. Nesizm), then add ROMs here.",
                        size=12, color=ft.Colors.OUTLINE),
                grid,
            ], expand=True, scroll=ft.ScrollMode.AUTO)
        )

    # ── 3. Installed View ──────────────────────────────────────────

    def _build_installed_view(self):
        g = self.gui
        calc = find_calculator()
        if not calc:
            g._set_content(
                ft.Column([
                    ft.Text("Installed", size=20, weight=ft.FontWeight.BOLD),
                    ft.Container(height=10),
                    ft.Icon(ft.Icons.USB, size=48, color=ft.Colors.OUTLINE),
                    ft.Text("No calculator detected.", color=ft.Colors.OUTLINE),
                    ft.Text("Connect via USB (F1 mode).", size=12, color=ft.Colors.OUTLINE),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, expand=True)
            )
            return

        all_registry = g.registry_data + g.games_data
        entries = walk_calc(calc, all_registry)
        dcount = count_calc_files(entries)
        known = sum(1 for f in iter_calc_files(entries) if f.addin is not None)
        g.installed_addin_ids = {e.addin.get("id") for e in iter_calc_files(entries) if e.addin}

        matched_paths: set[str] = set()
        rows: list[ft.Control] = []

        for f in iter_calc_files(entries):
            if not f.addin:
                continue
            name = f.addin.get("name", f.addin.get("id", "?"))
            icon = _icon_for_addin(f.addin)
            rows.append(
                ft.ListTile(
                    leading=ft.Icon(icon),
                    title=ft.Text(name, size=14),
                    subtitle=ft.Text(f.name, size=11, color=ft.Colors.OUTLINE),
                    trailing=ft.Row([
                        ft.IconButton(ft.Icons.VERIFIED, tooltip="Verify",
                                      on_click=lambda _, a=f.addin, n=name: asyncio_create(g._verify_item(a, n))),
                        ft.IconButton(ft.Icons.DELETE, tooltip="Remove",
                                      on_click=lambda _, a=f.addin, n=name: asyncio_create(g._remove_item(a, n))),
                    ], tight=True),
                )
            )
            matched_paths.add(f.name)

        for f in sorted(calc.mount_path.rglob("*"), key=lambda p: p.name):
            if not f.is_file():
                continue
            if f.suffix.lower() not in ALL_EXTS:
                continue
            rel = str(f.relative_to(calc.mount_path))
            if rel in matched_paths:
                continue
            if _match_addin_by_filename(f.name, all_registry):
                continue
            icon = ft.Icons.EXTENSION if f.suffix.lower() in ADDIN_EXTS else ft.Icons.SPORTS_ESPORTS
            rows.append(
                ft.ListTile(
                    leading=ft.Icon(icon, color=ft.Colors.WARNING),
                    title=ft.Text(f.stem, size=14, color=ft.Colors.WARNING),
                    subtitle=ft.Text(f"orphan • {rel}", size=11, color=ft.Colors.OUTLINE),
                    trailing=ft.IconButton(ft.Icons.DELETE, tooltip="Remove orphan",
                                           on_click=lambda _, p=f: asyncio_create(g._remove_orphan(p))),
                )
            )

        for sub in ("fotos", "textos"):
            d = calc.mount_path / "pthings" / sub
            if d.exists():
                for f in sorted(d.iterdir()):
                    if f.is_file():
                        rows.append(
                            ft.ListTile(
                                leading=ft.Icon(ft.Icons.IMAGE if sub == "fotos" else ft.Icons.DESCRIPTION, size=20),
                                title=ft.Text(f.name, size=14),
                                subtitle=ft.Text(f"pthings/{sub}/", size=11, color=ft.Colors.OUTLINE),
                                trailing=ft.IconButton(ft.Icons.DELETE, tooltip="Delete",
                                                       on_click=lambda _, p=f: asyncio_create(g._remove_file(p))),
                            )
                        )

        list_view = ft.ListView(
            controls=rows if rows else [ft.Text("No files found on calculator", color=ft.Colors.OUTLINE)],
            expand=True, spacing=2, padding=ft.Padding.only(right=8),
        )

        g._set_content(
            ft.Column([
                ft.Row([
                    ft.Text("Installed", size=20, weight=ft.FontWeight.BOLD),
                    ft.Text(f"{known} add-ins  ·  {dcount} files", size=12, color=ft.Colors.OUTLINE),
                    ft.Container(expand=True),
                    ft.ElevatedButton("Refresh", icon=ft.Icons.REFRESH,
                                      on_click=lambda _: asyncio_create(g._scan_calculator())),
                ]),
                ft.Container(height=4),
                list_view,
            ], expand=True)
        )

    # ── 4. Convert View ────────────────────────────────────────────

    def _build_convert_view(self):
        g = self.gui
        base = g._data_root()
        img_dir = base / "convert/images"
        doc_dir = base / "convert/documents"
        g3p_dir = base / "converted/g3p"
        txt_dir = base / "converted/txt"
        for d in [img_dir, doc_dir, g3p_dir, txt_dir]:
            d.mkdir(parents=True, exist_ok=True)

        img_files = sorted(img_dir.iterdir()) if img_dir.exists() else []
        doc_files = sorted(doc_dir.iterdir()) if doc_dir.exists() else []
        conv_g3p = sorted(g3p_dir.iterdir()) if g3p_dir.exists() else []
        conv_txt = sorted(txt_dir.iterdir()) if txt_dir.exists() else []

        input_section = ft.Column([
            ft.Row([
                ft.Text("Input Files", size=16, weight=ft.FontWeight.BOLD),
                ft.Container(expand=True),
                ft.ElevatedButton("Select Files", icon=ft.Icons.FILE_OPEN,
                                  on_click=lambda _: asyncio_create(g._pick_convert_files())),
                ft.ElevatedButton("Refresh", icon=ft.Icons.REFRESH,
                                  on_click=lambda _: self._build_convert_view()),
            ]),
        ], tight=True)

        if img_files or doc_files:
            img_exts = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tiff", ".tif", ".webp"}
            input_grid = ft.GridView(
                controls=[self._convert_file_card(f, "IMG" if f.suffix.lower() in img_exts else "DOC")
                          for f in img_files + doc_files],
                expand=True, max_extent=200, child_aspect_ratio=1.2, spacing=8, run_spacing=8,
            )
        else:
            input_grid = ft.Container(
                ft.Column([
                    ft.Icon(ft.Icons.CLOUD_UPLOAD, size=48, color=ft.Colors.OUTLINE),
                    ft.Container(height=8),
                    ft.Text("Drop files here or click 'Select Files'", color=ft.Colors.OUTLINE),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, alignment=ft.MainAxisAlignment.CENTER),
                height=120, border=ft.Border.all(2, ft.Colors.OUTLINE), border_radius=10,
                alignment=ft.Alignment.CENTER, ink=True,
                on_click=lambda _: asyncio_create(g._pick_convert_files()),
            )

        conv_section = ft.Column([
            ft.Container(height=8),
            ft.Row([
                ft.Text("Converted", size=16, weight=ft.FontWeight.BOLD),
                ft.Container(expand=True),
                ft.ElevatedButton("Push Selected", icon=ft.Icons.UPLOAD_FILE,
                                  color=ft.Colors.ON_PRIMARY, bgcolor=ft.Colors.PRIMARY,
                                  on_click=lambda _: asyncio_create(g._push_files())),
            ]),
        ], tight=True)

        converted_all = conv_g3p + conv_txt
        conv_grid = ft.GridView(
            controls=[self._convert_file_card(f, "G3P" if f.suffix.lower() == ".g3p" else "TXT")
                      for f in converted_all],
            expand=True, max_extent=200, child_aspect_ratio=1.2, spacing=8, run_spacing=8,
        ) if converted_all else ft.Text("No converted files yet. Convert something first!",
                                        color=ft.Colors.OUTLINE, size=12)

        g._set_content(
            ft.Column([
                ft.Text("Convert & Push", size=20, weight=ft.FontWeight.BOLD),
                input_section, input_grid, conv_section, conv_grid,
            ], expand=True, scroll=ft.ScrollMode.AUTO)
        )

    def _convert_file_card(self, f: Path, ftype: str) -> ft.Card:
        color_map = {"IMG": ft.Colors.GREEN, "DOC": ft.Colors.YELLOW,
                     "G3P": ft.Colors.CYAN, "TXT": ft.Colors.MAGENTA}
        return ft.Card(
            ft.Container(
                ft.Column([
                    ft.Icon(ft.Icons.IMAGE if ftype in ("IMG",) else ft.Icons.DESCRIPTION,
                            size=24, color=color_map.get(ftype, ft.Colors.OUTLINE)),
                    ft.Text(f.name, size=11, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS,
                            weight=ft.FontWeight.BOLD),
                    ft.Text(_fmt_size(f.stat().st_size), size=10, color=ft.Colors.OUTLINE),
                    ft.Text(ftype, size=9, color=color_map.get(ftype, ft.Colors.OUTLINE)),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2, tight=True),
                padding=8,
                ink=True,
                on_click=lambda _, fp=f, ft_=ftype: asyncio_create(self.gui._convert_single(fp, ft_)),
            )
        )

    # ── 5. Catch View ──────────────────────────────────────────────

    def _build_catch_view(self):
        g = self.gui
        calc = find_calculator()
        if not calc:
            g._set_content(
                ft.Column([
                    ft.Text("Calculator Filesystem", size=20, weight=ft.FontWeight.BOLD),
                    ft.Container(height=10),
                    ft.Text("No calculator detected.", color=ft.Colors.OUTLINE),
                ], expand=True)
            )
            return

        all_registry = g.registry_data + g.games_data
        entries = walk_calc(calc, all_registry)
        nodes = self._build_tree_view(entries)

        g._set_content(
            ft.Column([
                ft.Row([
                    ft.Text(f"{calc.model} Filesystem", size=20, weight=ft.FontWeight.BOLD),
                    ft.Container(expand=True),
                    ft.Text(f"Free: {_fmt_size(calc.storage_free)} / {_fmt_size(calc.storage_total)}",
                            size=12, color=ft.Colors.OUTLINE),
                ]),
                ft.Container(height=8),
                ft.ListView(controls=nodes or [ft.Text("(empty)", color=ft.Colors.OUTLINE)],
                            expand=True, spacing=2),
            ], expand=True)
        )

    def _build_tree_view(self, entries, indent: int = 0) -> list[ft.Control]:
        controls = []
        for e in entries:
            if e.is_dir:
                children = self._build_tree_view(e.children or [], indent + 1)
                controls.append(ft.ExpansionTile(
                    title=ft.Row([
                        ft.Container(width=indent * 16),
                        ft.Text(f"📁 {e.name}", size=13),
                    ], tight=True),
                    initially_expanded=False,
                    controls=children,
                ))
            else:
                size_str = _fmt_size(e.size)
                addin_name = e.addin.get("name", "") if e.addin else ""
                tile = ft.ListTile(
                    leading=ft.Container(width=indent * 16 + 4),
                    title=ft.Text(e.name, size=13),
                    subtitle=ft.Text(size_str, size=11, color=ft.Colors.OUTLINE),
                )
                if addin_name:
                    tile.trailing = ft.Text(addin_name, size=11, color=ft.Colors.PRIMARY,
                                            weight=ft.FontWeight.BOLD)
                controls.append(tile)
        return controls

    # ── 6. PGP Keys View ───────────────────────────────────────────

    def _build_pgp_keys_view(self):
        g = self.gui
        official = official_key_info()
        others = [k for k in list_keys() if not k.get("official")]

        rows: list[ft.Control] = []

        if official:
            uid = official.get("uids", ["(no UID)"])[0]
            rows.append(ft.ListTile(
                leading=ft.Icon(ft.Icons.VERIFIED, color=ft.Colors.GREEN),
                title=ft.Text("Official Pan Devs Key", weight=ft.FontWeight.BOLD),
                subtitle=ft.Column([
                    ft.Text(uid, size=11),
                    ft.Text(f"Key ID: {official['keyid']}", size=10, color=ft.Colors.OUTLINE),
                    ft.Text(f"Fingerprint: {official['fingerprint']}", size=10, color=ft.Colors.OUTLINE),
                ], spacing=1, tight=True),
            ))
        else:
            rows.append(ft.ListTile(
                leading=ft.Icon(ft.Icons.ERROR_OUTLINE, color=ft.Colors.WARNING),
                title=ft.Text("Official Pan Devs Key not loaded"),
                subtitle=ft.Text("Will be downloaded automatically when needed.", size=11),
            ))

        rows.append(ft.Divider())

        if others:
            rows.append(ft.Text("Other Keys", size=14, weight=ft.FontWeight.BOLD))
            for k in others:
                uid = k.get("uids", ["(no UID)"])[0]
                rows.append(ft.ListTile(
                    leading=ft.Icon(ft.Icons.KEY),
                    title=ft.Text(uid, size=13),
                    subtitle=ft.Column([
                        ft.Text(f"Key ID: {k['keyid']}", size=10, color=ft.Colors.OUTLINE),
                        ft.Text(f"Status: {'✅ Trusted' if k['trusted'] else '❌ Untrusted'}", size=10),
                    ], spacing=1, tight=True),
                    trailing=ft.FilledTonalButton(
                        "Trust" if not k["trusted"] else "Untrust",
                        on_click=lambda _, kid=k["keyid"], t=not k["trusted"]:
                            asyncio_create(g._toggle_trust(kid, t)),
                    ),
                ))
        else:
            rows.append(ft.Text("No other keys imported.", size=12, color=ft.Colors.OUTLINE))

        import_btn = ft.ElevatedButton("Import Key", icon=ft.Icons.FILE_UPLOAD,
                                       on_click=lambda _: asyncio_create(g._import_key_file()))
        g._set_content(
            ft.Column([
                ft.Row([
                    ft.Text("PGP Keys", size=20, weight=ft.FontWeight.BOLD),
                    ft.Container(expand=True), import_btn,
                    ft.ElevatedButton("Refresh", icon=ft.Icons.REFRESH,
                                      on_click=lambda _: self._build_pgp_keys_view()),
                ]),
                ft.Container(height=8),
                ft.ListView(controls=rows, expand=True, spacing=2),
            ], expand=True)
        )

    # ── 7. Settings View ───────────────────────────────────────────

    def _build_settings_view(self):
        g = self.gui
        config_data = __import__("pcalc.config", fromlist=["get_all"]).get_all()

        registry_url = ft.TextField(
            label="Registry URL", value=config_data.get("registry_url", ""), width=500,
            helper="URL to the registry JSON file",
        )
        cache_ttl = ft.TextField(
            label="Cache TTL (hours)", value=str(config_data.get("cache_ttl_hours", 6)), width=120,
            keyboard_type=ft.KeyboardType.NUMBER,
        )
        auto_update = ft.Switch(label="Auto-update registry on launch",
                                value=config_data.get("auto_update", True))
        confirm_install = ft.Switch(label="Confirm before installing",
                                    value=config_data.get("confirm_install", True))
        confirm_remove = ft.Switch(label="Confirm before removing",
                                   value=config_data.get("confirm_remove", True))
        dark_mode = ft.Switch(
            label="Dark mode",
            value=__import__("pcalc.config", fromlist=["get"]).get("theme_mode") == "dark",
            on_change=lambda e: asyncio_create(g._toggle_dark(e.control.value)),
        )

        async def save():
            __import__("pcalc.config", fromlist=["set"]).set("registry_url", registry_url.value)
            try:
                __import__("pcalc.config", fromlist=["set"]).set("cache_ttl_hours", int(cache_ttl.value))
            except ValueError:
                pass
            __import__("pcalc.config", fromlist=["set"]).set("auto_update", auto_update.value)
            __import__("pcalc.config", fromlist=["set"]).set("confirm_install", confirm_install.value)
            __import__("pcalc.config", fromlist=["set"]).set("confirm_remove", confirm_remove.value)
            g._show_snackbar("Settings saved")

        async def reset_all():
            ok = await g._confirm("Reset", "Reset all settings to defaults?")
            if ok:
                __import__("pcalc.config", fromlist=["reset"]).reset()
                self._build_settings_view()
                g._show_snackbar("Settings reset")

        from pcalc import __version__
        g._set_content(
            ft.Column([
                ft.Text("Settings", size=20, weight=ft.FontWeight.BOLD),
                ft.Container(height=8),
                ft.Text("Appearance", size=16, weight=ft.FontWeight.BOLD),
                dark_mode, ft.Divider(),
                ft.Text("Registry", size=16, weight=ft.FontWeight.BOLD),
                registry_url, ft.Container(height=8), cache_ttl, auto_update, ft.Divider(),
                ft.Text("Behavior", size=16, weight=ft.FontWeight.BOLD),
                confirm_install, confirm_remove, ft.Divider(),
                ft.Row([
                    ft.FilledButton("Save", icon=ft.Icons.SAVE,
                                    on_click=lambda _: asyncio_create(save())),
                    ft.OutlinedButton("Reset to Defaults", icon=ft.Icons.RESTORE,
                                      on_click=lambda _: asyncio_create(reset_all())),
                ]),
                ft.Container(height=20),
                ft.Text(f"PanCalc Tools v{__version__}", size=11, color=ft.Colors.OUTLINE),
            ], expand=True, scroll=ft.ScrollMode.AUTO)
        )


# ── Helper to create tasks from lambda callbacks ────────────────────

def asyncio_create(coro):
    import asyncio
    return asyncio.create_task(coro)
