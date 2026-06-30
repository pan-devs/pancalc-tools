"""
pcalc/gui_views.py — Flet GUI view builders for PanCalc Tools.
References core PanCalcGUI via self.gui.
"""
from __future__ import annotations
import asyncio
import re
import shutil
from pathlib import Path
import flet as ft
from pcalc import theme as ptheme
from pcalc import library as plibrary
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
        self._section_locks = {
            "images": asyncio.Lock(),
            "text": asyncio.Lock(),
            "both": asyncio.Lock(),
        }
        self._processing_section = None
        self._selected_push_paths: set[str] = set()
    # ── 1. Registry View ───────────────────────────────────────────
    def _build_registry_view(self):
        g = self.gui
        
        # Load local addins
        local_addins = plibrary.get_all("addin")
        local_ids = {d.get("id") for d in local_addins if d.get("id")}
        local_filenames = {d.get("filename", "").lower() for d in local_addins if d.get("filename")}
        
        # Merge registry + local, with source indicator
        all_items = []
        for d in g.registry_data[:50]:
            if d.get("id") in local_ids or (d.get("filename") and d.get("filename").lower() in local_filenames):
                continue
            legacy_name = d.get("filename") or d.get("zip_file") or Path(d.get("download_url", "")).name
            if legacy_name and legacy_name.lower() in local_filenames:
                continue
            d = d.copy()
            d["_source"] = "registry"
            all_items.append(d)
        for d in local_addins:
            d = d.copy()
            d["_source"] = "local"
            d["_type"] = "addin"
            all_items.append(d)
        
        if not all_items:
            g._set_content(
                ft.Column([
                    ft.Text("Registry", size=20, weight=ft.FontWeight.BOLD),
                    ft.Container(height=10),
                    ft.Text("No add-ins loaded. Click the refresh button above.", color=ft.Colors.OUTLINE),
                ], expand=True)
            )
            return
        items = [self._build_registry_card(d) for d in all_items]
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
        reg_count = sum(1 for d in all_items if d.get("_source") == "registry")
        local_count = sum(1 for d in all_items if d.get("_source") == "local")
        g.registry_count.value = f"{reg_count} registry  ·  {local_count} local"
        g._set_content(
            ft.Column([
                ft.Row([
                    ft.Text("Registry", size=20, weight=ft.FontWeight.BOLD),
                    g.registry_count, ft.Container(expand=True), import_btn,
                ], alignment=ft.MainAxisAlignment.START),
                ft.Container(height=4),
                self._build_install_target(),
                ft.Container(
                    ft.Row([
                        ft.Icon(ft.Icons.TOUCH_APP, size=14, color=ft.Colors.PRIMARY),
                        ft.Text("Long-press a card to select, then drop on the install zone",
                                size=11, color=ft.Colors.PRIMARY),
                    ], tight=True),
                    visible=g._selection_mode,
                    padding=ft.Padding.only(top=4, bottom=4),
                ),
                ft.Container(height=4), grid,
            ], expand=True, scroll=ft.ScrollMode.AUTO)
        )
    def _build_registry_card(self, d: dict) -> ft.Control:
        g = self.gui
        name = d.get("name", d.get("id", "?"))
        aid = d.get("id", "?")
        ver = d.get("version", "")
        category = d.get("category", "")
        compatible = ", ".join(d.get("compatible", []))
        platform_info = _platform_badge(d)
        source = d.get("_source", "registry")
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
        if source == "local":
            tags.append(ft.Container(
                ft.Text("🏷️ Local", size=10, color=ft.Colors.ON_SECONDARY_CONTAINER),
                bgcolor=ft.Colors.SECONDARY_CONTAINER, border_radius=4,
                padding=ft.Padding.symmetric(vertical=2, horizontal=6)))
        else:
            tags.append(ft.Container(
                ft.Text("🌐 Registry", size=10, color=ft.Colors.ON_TERTIARY_CONTAINER),
                bgcolor=ft.Colors.TERTIARY_CONTAINER, border_radius=4,
                padding=ft.Padding.symmetric(vertical=2, horizontal=6)))
        is_installed = d.get("id", "") in getattr(g, "installed_addin_ids", set())
        inner = ft.Container(
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
        )
        is_selected = aid in g._selected_registry_ids
        if is_selected:
            inner = ft.Container(
                content=inner,
                border=ft.Border.all(2, ft.Colors.PRIMARY),
                border_radius=12,
                padding=2,
            )
        card = ft.Card(inner)
        def _on_click(e, d_=d):
            if g._selection_mode:
                if aid in g._selected_registry_ids:
                    g._selected_registry_ids.discard(aid)
                else:
                    g._selected_registry_ids.add(aid)
                if not g._selected_registry_ids:
                    g._selection_mode = False
                g._build_current_view()
            else:
                asyncio_create(g._show_addin_detail(d_))
        def _on_long_press(e):
            if g._selection_mode:
                g._selection_mode = False
                g._selected_registry_ids.clear()
            else:
                g._selection_mode = True
                g._selected_registry_ids.clear()
                g._selected_registry_ids.add(aid)
            g._build_current_view()
        wrap = ft.Container(
            content=card,
            on_click=_on_click,
            on_long_press=_on_long_press,
            ink=True,
        )
        is_local = source == "local"
        if is_local:
            drag_data = {
                "item_id": aid,
                "lib_type": d.get("_type", "addin"),
                "item_type": "local_library",
                "installable": True,
            }
            if g._selection_mode and aid in g._selected_registry_ids:
                all_ids = []
                all_lib_types = []
                for sid in g._selected_registry_ids:
                    lib = plibrary.get("addin", sid) or plibrary.get("game", sid)
                    if lib:
                        all_ids.append(sid)
                        all_lib_types.append(lib.get("_type", "addin"))
                if all_ids:
                    drag_data["all_ids"] = all_ids
                    drag_data["all_lib_types"] = all_lib_types
        else:
            drag_data = {"installable": True, "item_id": aid}
        if g._selection_mode and aid in g._selected_registry_ids:
            count = len(g._selected_registry_ids)
            feedback = ft.Container(
                ft.Text(f"📥 {count}", size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_PRIMARY),
                padding=10, bgcolor=ft.Colors.PRIMARY, border_radius=8,
            )
        else:
            feedback = ft.Container(
                ft.Text(f"📥 {name}", size=12, weight=ft.FontWeight.BOLD),
                padding=10, bgcolor=ft.Colors.SECONDARY_CONTAINER, border_radius=8,
            )
        return ft.Draggable(
            group="all_items",
            content=wrap,
            content_when_dragging=ft.Container(opacity=0.3, content=wrap),
            content_feedback=feedback,
            data=drag_data,
        )
    # ── 2. Games View ──────────────────────────────────────────────
    def _build_games_view(self):
        g = self.gui
        
        # Load local games
        local_games = plibrary.get_all("game")
        local_ids = {d.get("id") for d in local_games if d.get("id")}
        local_filenames = {d.get("filename", "").lower() for d in local_games if d.get("filename")}
        
        # Merge registry + local games
        all_items = []
        for d in g.games_data[:50]:
            if d.get("id") in local_ids or (d.get("filename") and d.get("filename").lower() in local_filenames):
                continue
            legacy_name = d.get("filename") or d.get("zip_file") or Path(d.get("download_url", "")).name
            if legacy_name and legacy_name.lower() in local_filenames:
                continue
            d = d.copy()
            d["_source"] = "registry"
            all_items.append(d)
        for d in local_games:
            d = d.copy()
            d["_source"] = "local"
            d["_type"] = "game"
            all_items.append(d)
        
        if not all_items:
            g._set_content(
                ft.Column([
                    ft.Text("Games", size=20, weight=ft.FontWeight.BOLD),
                    ft.Container(height=10),
                    ft.Text("No games available in registry.", color=ft.Colors.OUTLINE),
                ], expand=True)
            )
            return
        items = [self._build_registry_card(d) for d in all_items]
        grid = ft.GridView(
            controls=items, expand=True, runs_count=0, max_extent=320,
            child_aspect_ratio=2.2, spacing=10, run_spacing=10,
            padding=ft.Padding.only(right=8),
        )
        import_btn = ft.ElevatedButton(
            "📁 Import Local ROM", icon=ft.Icons.FILE_UPLOAD,
            on_click=lambda _: asyncio_create(g._pick_file_for_import("game")),
        )
        reg_count = sum(1 for d in all_items if d.get("_source") == "registry")
        local_count = sum(1 for d in all_items if d.get("_source") == "local")
        g.games_count.value = f"{reg_count} registry  ·  {local_count} local"
        g._set_content(
            ft.Column([
                ft.Row([
                    ft.Text("Games", size=20, weight=ft.FontWeight.BOLD),
                    g.games_count, ft.Container(expand=True), import_btn,
                ]),
                ft.Container(height=4),
                self._build_install_target(),
                ft.Container(
                    ft.Row([
                        ft.Icon(ft.Icons.TOUCH_APP, size=14, color=ft.Colors.PRIMARY),
                        ft.Text("Long-press a card to select, then drop on the install zone",
                                size=11, color=ft.Colors.PRIMARY),
                    ], tight=True),
                    visible=g._selection_mode,
                    padding=ft.Padding.only(top=4, bottom=4),
                ),
                ft.Container(height=4),
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
        # Build ID-to-path mapping for multi-delete via selection
        id_to_path: dict[str, str] = {}
        for fe in iter_calc_files(entries):
            if fe.addin:
                aid = fe.addin.get("id", "")
                if aid:
                    id_to_path[aid] = str(calc.mount_path / fe.name)
        for f in iter_calc_files(entries):
            if not f.addin:
                continue
            name = f.addin.get("name", f.addin.get("id", "?"))
            aid = f.addin.get("id", "")
            icon = _icon_for_addin(f.addin)
            is_selected = aid in g._selected_registry_ids
            full_path = str(calc.mount_path / f.name)
            list_tile = ft.ListTile(
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
            if is_selected:
                list_tile = ft.Container(
                    content=list_tile,
                    border=ft.Border.all(2, ft.Colors.PRIMARY),
                    border_radius=8,
                    padding=2,
                )
            def _on_click(e, aid=aid):
                if g._selection_mode:
                    if aid in g._selected_registry_ids:
                        g._selected_registry_ids.discard(aid)
                    else:
                        g._selected_registry_ids.add(aid)
                    if not g._selected_registry_ids:
                        g._selection_mode = False
                    g._build_current_view()
            def _on_long_press(e, aid=aid):
                if g._selection_mode:
                    g._selection_mode = False
                    g._selected_registry_ids.clear()
                else:
                    g._selection_mode = True
                    g._selected_registry_ids.clear()
                    g._selected_registry_ids.add(aid)
                g._build_current_view()
            wrap = ft.Container(
                content=list_tile,
                on_click=_on_click,
                on_long_press=_on_long_press,
                ink=True,
            )
            if g._selection_mode and aid in g._selected_registry_ids:
                count = len(g._selected_registry_ids)
                feedback = ft.Container(
                    ft.Text(f"🗑️ {count}", size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_ERROR),
                    padding=10, bgcolor=ft.Colors.ERROR_CONTAINER, border_radius=8,
                )
            else:
                feedback = ft.Container(
                    ft.Text(f"🗑️ {name}", size=12, weight=ft.FontWeight.BOLD),
                    padding=10, bgcolor=ft.Colors.ERROR_CONTAINER, border_radius=8,
                )
            if g._selection_mode and aid in g._selected_registry_ids:
                selected_paths = [id_to_path[sid] for sid in g._selected_registry_ids if sid in id_to_path]
                drag_data = {"all_paths": selected_paths, "item_type": "calculator_file"}
            else:
                drag_data = {"path": full_path, "item_type": "calculator_file"}
            rows.append(ft.Draggable(
                group="all_items",
                content=wrap,
                content_when_dragging=ft.Container(opacity=0.3, content=wrap),
                content_feedback=feedback,
                data=drag_data,
            ))
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
            list_tile = ft.ListTile(
                leading=ft.Icon(icon, color=ft.Colors.AMBER_ACCENT),
                title=ft.Text(f.stem, size=14, color=ft.Colors.AMBER_ACCENT),
                subtitle=ft.Text(f"orphan • {rel}", size=11, color=ft.Colors.OUTLINE),
                trailing=ft.IconButton(ft.Icons.DELETE, tooltip="Remove orphan",
                                       on_click=lambda _, p=f: asyncio_create(g._remove_orphan(p))),
            )
            fpath_str = str(f)
            is_selected = fpath_str in g._selected_registry_ids
            if is_selected:
                list_tile = ft.Container(
                    content=list_tile,
                    border=ft.Border.all(2, ft.Colors.PRIMARY),
                    border_radius=8,
                    padding=2,
                )
            def _on_orphan_click(e, p=fpath_str):
                if g._selection_mode:
                    if p in g._selected_registry_ids:
                        g._selected_registry_ids.discard(p)
                    else:
                        g._selected_registry_ids.add(p)
                    if not g._selected_registry_ids:
                        g._selection_mode = False
                    g._build_current_view()
            def _on_orphan_long_press(e, p=fpath_str):
                if g._selection_mode:
                    g._selection_mode = False
                    g._selected_registry_ids.clear()
                else:
                    g._selection_mode = True
                    g._selected_registry_ids.clear()
                    g._selected_registry_ids.add(p)
                g._build_current_view()
            wrap = ft.Container(
                content=list_tile,
                on_click=_on_orphan_click,
                on_long_press=_on_orphan_long_press,
                ink=True,
            )
            if g._selection_mode and fpath_str in g._selected_registry_ids:
                all_selected_paths = [x for x in g._selected_registry_ids if Path(x).exists()]
                orphan_data = {"all_paths": all_selected_paths, "item_type": "calculator_file"}
                orphan_feedback = ft.Container(
                    ft.Text(f"🗑️ {len(all_selected_paths)}", size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_ERROR),
                    padding=10, bgcolor=ft.Colors.ERROR_CONTAINER, border_radius=8,
                )
            else:
                orphan_data = {"path": fpath_str, "item_type": "calculator_file"}
                orphan_feedback = ft.Container(
                    ft.Text(f"🗑️ {f.stem}", size=12, weight=ft.FontWeight.BOLD),
                    padding=10, bgcolor=ft.Colors.ERROR_CONTAINER, border_radius=8,
                )
            rows.append(ft.Draggable(
                group="all_items",
                content=wrap,
                content_when_dragging=ft.Container(opacity=0.3, content=wrap),
                content_feedback=orphan_feedback,
                data=orphan_data,
            ))
        for sub in ("fotos", "textos"):
            d = calc.mount_path / "pthings" / sub
            if d.exists():
                for f in sorted(d.iterdir()):
                    if f.is_file():
                        list_tile = ft.ListTile(
                            leading=ft.Icon(ft.Icons.IMAGE if sub == "fotos" else ft.Icons.DESCRIPTION, size=20),
                            title=ft.Text(f.name, size=14),
                            subtitle=ft.Text(f"pthings/{sub}/", size=11, color=ft.Colors.OUTLINE),
                            trailing=ft.IconButton(ft.Icons.DELETE, tooltip="Delete",
                                                   on_click=lambda _, p=f: asyncio_create(g._remove_file(p))),
                        )
                        pfpath = str(f)
                        is_sel = pfpath in g._selected_registry_ids
                        if is_sel:
                            list_tile = ft.Container(
                                content=list_tile,
                                border=ft.Border.all(2, ft.Colors.PRIMARY),
                                border_radius=8,
                                padding=2,
                            )
                        def _on_pclick(e, p=pfpath):
                            if g._selection_mode:
                                if p in g._selected_registry_ids:
                                    g._selected_registry_ids.discard(p)
                                else:
                                    g._selected_registry_ids.add(p)
                                if not g._selected_registry_ids:
                                    g._selection_mode = False
                                g._build_current_view()
                        def _on_plong(e, p=pfpath):
                            if g._selection_mode:
                                g._selection_mode = False
                                g._selected_registry_ids.clear()
                            else:
                                g._selection_mode = True
                                g._selected_registry_ids.clear()
                                g._selected_registry_ids.add(p)
                            g._build_current_view()
                        wrap = ft.Container(
                            content=list_tile,
                            on_click=_on_pclick,
                            on_long_press=_on_plong,
                            ink=True,
                        )
                        if g._selection_mode and pfpath in g._selected_registry_ids:
                            all_sel = [x for x in g._selected_registry_ids if Path(x).exists()]
                            pdata = {"all_paths": all_sel, "item_type": "calculator_file"}
                            pfb = ft.Container(
                                ft.Text(f"🗑️ {len(all_sel)}", size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_ERROR),
                                padding=10, bgcolor=ft.Colors.ERROR_CONTAINER, border_radius=8,
                            )
                        else:
                            pdata = {"path": pfpath, "item_type": "calculator_file"}
                            pfb = ft.Container(
                                ft.Text(f"🗑️ {f.name}", size=12, weight=ft.FontWeight.BOLD),
                                padding=10, bgcolor=ft.Colors.ERROR_CONTAINER, border_radius=8,
                            )
                        rows.append(ft.Draggable(
                            group="all_items",
                            content=wrap,
                            content_when_dragging=ft.Container(opacity=0.3, content=wrap),
                            content_feedback=pfb,
                            data=pdata,
                        ))
        # ─── Local Library Section ───
        local_addins = plibrary.get_all("addin")
        local_games = plibrary.get_all("game")
        local_items = []
        for d in local_addins:
            d = d.copy()
            d["_type"] = "addin"
            local_items.append(d)
        for d in local_games:
            d = d.copy()
            d["_type"] = "game"
            local_items.append(d)
        
        # Filter out items already on calculator
        calc_ids = g.installed_addin_ids
        local_not_on_calc = [d for d in local_items if d.get("id") not in calc_ids]
        
        if local_not_on_calc:
            rows.append(ft.Divider())
            rows.append(ft.Text("🏷️ Local Library (not on calculator)", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.OUTLINE))
            for d in local_not_on_calc:
                name = d.get("name", d.get("id", "?"))
                aid = d.get("id", "?")
                item_type = d.get("_type", "addin")
                icon = ft.Icons.SPORTS_ESPORTS if item_type == "game" else ft.Icons.EXTENSION
                is_selected = aid in g._selected_registry_ids
                list_tile = ft.ListTile(
                    leading=ft.Icon(icon, color=ft.Colors.SECONDARY),
                    title=ft.Text(name, size=14, color=ft.Colors.SECONDARY),
                    subtitle=ft.Text(f"local • {item_type}", size=11, color=ft.Colors.OUTLINE),
                    trailing=ft.Row([
                        ft.IconButton(ft.Icons.CLOUD_UPLOAD, tooltip="Install to calculator",
                                      on_click=lambda _, a=d: asyncio_create(g._install_item(a, None))),
                        ft.IconButton(ft.Icons.DELETE, tooltip="Delete from local library",
                                      on_click=lambda _, a=d: asyncio_create(g._remove_local_library_item(a["id"], a["_type"]))),
                    ], tight=True),
                )
                if is_selected:
                    list_tile = ft.Container(
                        content=list_tile,
                        border=ft.Border.all(2, ft.Colors.PRIMARY),
                        border_radius=8,
                        padding=2,
                    )
                def _on_click(e, d_=d):
                    if g._selection_mode:
                        if aid in g._selected_registry_ids:
                            g._selected_registry_ids.discard(aid)
                        else:
                            g._selected_registry_ids.add(aid)
                        if not g._selected_registry_ids:
                            g._selection_mode = False
                        g._build_current_view()
                def _on_long_press(e):
                    if g._selection_mode:
                        g._selection_mode = False
                        g._selected_registry_ids.clear()
                    else:
                        g._selection_mode = True
                        g._selected_registry_ids.clear()
                        g._selected_registry_ids.add(aid)
                    g._build_current_view()
                wrap = ft.Container(
                    content=list_tile,
                    on_click=_on_click,
                    on_long_press=_on_long_press,
                    ink=True,
                )
                if g._selection_mode and aid in g._selected_registry_ids:
                    count = len(g._selected_registry_ids)
                    feedback = ft.Container(
                        ft.Text(f"📥 {count}", size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_PRIMARY),
                        padding=10, bgcolor=ft.Colors.PRIMARY, border_radius=8,
                    )
                else:
                    feedback = ft.Container(
                        ft.Text(f"🗑️ {name}", size=12, weight=ft.FontWeight.BOLD),
                        padding=10, bgcolor=ft.Colors.ERROR_CONTAINER, border_radius=8,
                    )
                drag_data = {"item_id": d["id"], "lib_type": item_type, "item_type": "local_library", "installable": True}
                if g._selection_mode and aid in g._selected_registry_ids:
                    all_ids = []
                    all_lib_types = []
                    for sid in g._selected_registry_ids:
                        lib = plibrary.get("addin", sid) or plibrary.get("game", sid)
                        if lib:
                            all_ids.append(sid)
                            all_lib_types.append(lib.get("_type", "addin"))
                    if all_ids:
                        drag_data["all_ids"] = all_ids
                        drag_data["all_lib_types"] = all_lib_types
                rows.append(ft.Draggable(
                    group="all_items",
                    content=wrap,
                    content_when_dragging=ft.Container(opacity=0.3, content=wrap),
                    content_feedback=feedback,
                    data=drag_data,
                ))
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
        img_exts = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tiff", ".tif", ".webp"}
        doc_exts = {".pdf", ".docx", ".doc", ".txt"}
        # ─── Input Section ───
        input_cards = []
        for f in img_files:
            input_cards.append(self._build_input_card(f, "IMG", img_dir))
        for f in doc_files:
            input_cards.append(self._build_input_card(f, "DOC", doc_dir))
        input_section = ft.Column([
            ft.Row([
                ft.Text("INPUT FILES", size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.OUTLINE),
                ft.Container(expand=True),
                ft.ElevatedButton("Select Files", icon=ft.Icons.FILE_OPEN,
                                  on_click=lambda _: asyncio_create(g._pick_convert_files())),
                ft.ElevatedButton("Refresh", icon=ft.Icons.REFRESH,
                                  on_click=lambda _: self._build_convert_view()),
            ]),
            ft.Container(height=8),
            ft.GridView(
                controls=input_cards if input_cards else [],
                expand=True, max_extent=200, child_aspect_ratio=1.2, spacing=8, run_spacing=8,
            ) if input_cards else ft.Container(
                ft.Column([
                    ft.Icon(ft.Icons.CLOUD_UPLOAD, size=48, color=ft.Colors.OUTLINE),
                    ft.Container(height=8),
                    ft.Text("No input files. Click 'Select Files' or drag & drop.", color=ft.Colors.OUTLINE),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, alignment=ft.MainAxisAlignment.CENTER),
                height=120, border=ft.Border.all(2, ft.Colors.OUTLINE), border_radius=10,
                alignment=ft.Alignment.CENTER, ink=True,
                on_click=lambda _: asyncio_create(g._pick_convert_files()),
            ),
            ft.Container(height=4),
            ft.Text("👇 Drag files below to convert", size=11, color=ft.Colors.OUTLINE, italic=True),
        ], tight=True)
        # ─── Converted Sections (3 Drop Targets) ───
        sections = [
            {"id": "images", "label": "📷 IMAGES (fotos)", "icon": ft.Icons.IMAGE, "color": "#4CAF50",
             "dest": "fotos", "ext": ".g3p", "files": conv_g3p, "ftype": "G3P"},
            {"id": "text", "label": "📄 TEXT (textos)", "icon": ft.Icons.DESCRIPTION, "color": "#2196F3",
             "dest": "textos", "ext": ".txt", "files": conv_txt, "ftype": "TXT"},
            {"id": "both", "label": "📷+📄 BOTH", "icon": ft.Icons.LAYERS, "color": "#9C27B0",
             "dest": "both", "exts": [".g3p", ".txt"], "files": [], "ftype": "BOTH"},
        ]
        converted_sections = []
        for sec in sections:
            converted_sections.append(self._build_converted_section(sec))
        # ─── Bottom Actions ───
        is_pushing = getattr(self, '_push_active', False)
        bottom_actions = ft.Row([
            ft.ElevatedButton(
                "Pushing..." if is_pushing else "Push Selected to Calculator",
                icon=ft.Icons.HOURGLASS_TOP if is_pushing else ft.Icons.UPLOAD_FILE,
                disabled=is_pushing,
                on_click=lambda _: asyncio_create(g._push_files()),
            ),
            ft.OutlinedButton("Delete Selected", icon=ft.Icons.DELETE,
                              disabled=is_pushing,
                              on_click=lambda _: asyncio_create(g._delete_converted_selection())),
            ft.Container(expand=True),
        ], alignment=ft.MainAxisAlignment.START)
        # Collect all converted paths for Select All
        all_conv_paths = [str(p) for p in conv_g3p] + [str(p) for p in conv_txt]
        all_selected = all(p in self._selected_push_paths for p in all_conv_paths) if all_conv_paths else False
        # Select All toggle
        def _on_select_all(e):
            if all_selected:
                self._selected_push_paths.difference_update(all_conv_paths)
            else:
                self._selected_push_paths.update(all_conv_paths)
            self._build_convert_view()
        select_all_btn = ft.Container(
            content=ft.Row([
                ft.Icon(
                    ft.Icons.CHECK_BOX if all_selected else ft.Icons.CHECK_BOX_OUTLINE_BLANK,
                    size=16, color=ft.Colors.PRIMARY,
                ),
                ft.Text("Select All" if not all_selected else "Deselect All",
                        size=11, color=ft.Colors.PRIMARY),
            ], tight=True),
            on_click=_on_select_all,
            ink=True,
        ) if all_conv_paths else ft.Container()
        # Equal width wrappers — each section grows downward naturally
        equal_sections = [ft.Container(content=s, expand=1) for s in converted_sections]
        g._set_content(
            ft.Column([
                ft.Text("Convert & Push", size=20, weight=ft.FontWeight.BOLD),
                ft.Container(height=4),
                input_section,
                ft.Container(height=8),
                ft.Divider(),
                ft.Container(height=4),
                ft.Row([
                    ft.Text("CONVERTED", size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.OUTLINE),
                    ft.Container(expand=True),
                    ft.Container(
                        ft.Row([
                            ft.Icon(ft.Icons.TOUCH_APP, size=14, color=ft.Colors.PRIMARY),
                            ft.Text("Selection mode: tap to toggle, long-press to exit",
                                    size=11, color=ft.Colors.PRIMARY),
                        ], tight=True),
                        visible=g._selection_mode,
                    ),
                    select_all_btn,
                    ft.Text("(drop here)", size=11, color=ft.Colors.OUTLINE),
                ]),
                ft.Container(height=4),
                ft.Row(equal_sections, spacing=8, vertical_alignment=ft.CrossAxisAlignment.START),
                ft.Container(height=8),
                ft.Divider(),
                ft.Container(height=4),
                bottom_actions,
            ], expand=True, scroll=ft.ScrollMode.AUTO)
        )
    def _build_input_card(self, f: Path, ftype: str, source_dir: Path) -> ft.Draggable:
        color_map = {"IMG": "#4CAF50", "DOC": "#FFEB3B"}
        is_image = ftype == "IMG"
        g = self.gui
        fpath = str(f)
        multi_sel = fpath in g._multi_selected
        
        inner = ft.Container(
            ft.Column([
                ft.Row([
                    ft.Icon(ft.Icons.IMAGE if is_image else ft.Icons.DESCRIPTION,
                            size=20, color=color_map.get(ftype, ft.Colors.OUTLINE)),
                    ft.Text(ftype, size=9, color=ft.Colors.ON_SURFACE,
                            weight=ft.FontWeight.BOLD,
                            bgcolor=color_map.get(ftype, ft.Colors.OUTLINE)),
                    ft.Container(expand=True),
                    ft.Text(_fmt_size(f.stat().st_size), size=9, color=ft.Colors.OUTLINE),
                ], alignment=ft.MainAxisAlignment.START),
                ft.Container(height=4),
                ft.Text(f.name, size=11, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS,
                        weight=ft.FontWeight.BOLD),
                ft.Container(height=4),
                ft.Row([
                    ft.Text(f"Drag to convert", size=9, color=ft.Colors.OUTLINE, italic=True),
                    ft.Container(expand=True),
                    ft.IconButton(
                        ft.Icons.DELETE, tooltip="Delete input file",
                        icon_size=16,
                        on_click=lambda _, p=f, d=source_dir: asyncio_create(g._delete_convert_input(p, d)),
                    ),
                ]),
            ], spacing=2, tight=True),
            padding=10,
        )
        card = ft.Card(inner)
        clk = ft.Container(
            content=card,
            on_click=lambda e: self._on_card_click(e, [fpath]),
            on_long_press=lambda e: self._on_card_long_press(e, [fpath]),
            ink=True,
        )
        if multi_sel:
            clk = ft.Container(
                content=clk,
                border=ft.Border.all(2, ft.Colors.PRIMARY),
                border_radius=12,
            )
        drag_all = self._get_multi_selected_drag_paths([fpath])
        count = len(drag_all)
        return ft.Draggable(
            group="all_items",
            content=clk,
            content_when_dragging=ft.Container(opacity=0.3, content=clk),
            content_feedback=ft.Container(
                ft.Row([
                    ft.Icon(ft.Icons.FOLDER_OPEN, size=16, color=ft.Colors.ON_SURFACE),
                    ft.Text(f"📦 {count}" if count > 1 else f"➡️ {ftype}: {f.name}",
                            size=12, weight=ft.FontWeight.BOLD),
                ], tight=True),
                padding=10,
                bgcolor=ft.Colors.PRIMARY_CONTAINER if count == 1 else ft.Colors.SECONDARY_CONTAINER,
                border_radius=8,
            ),
            data={"path": fpath, "all_paths": drag_all, "type": ftype,
                  "source_dir": str(source_dir), "item_type": "convert_input"},
        )
    def _build_converted_section(self, sec: dict) -> ft.DragTarget:
        files = sec["files"]
        is_both = sec["id"] == "both"
        section_id = sec["id"]
        
        # Group files by stem (for stacking multi-page documents)
        groups = self._group_files_by_stem(files, is_both)
        
        # Build cards for each group
        cards = []
        for stem, group_files in groups.items():
            if len(group_files) > 1:
                # Multiple files from same document - show as single stack card
                cards.append(self._build_expanded_group_card(stem, group_files, sec["ftype"], section_id))
            else:
                # Single file
                if is_both:
                    cards.append(self._build_converted_pair_card(group_files[0][0], group_files[0][1]))
                else:
                    cards.append(self._build_converted_card(group_files[0], sec["ftype"], section_id))
        
        # Processing overlay (hidden by default)
        processing_overlay = ft.Container(
            ft.Column([
                ft.ProgressRing(width=24, height=24, color=sec["color"]),
                ft.Container(height=4),
                ft.Text("Converting...", size=12, color=sec["color"]),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, alignment=ft.MainAxisAlignment.CENTER, tight=True),
            visible=False,
            alignment=ft.Alignment.CENTER,
            bgcolor=ft.Colors.SURFACE_CONTAINER,
            border_radius=8,
        )
        
        if cards:
            grid_view = ft.GridView(
                controls=cards,
                max_extent=200, child_aspect_ratio=1.2, spacing=6, run_spacing=6,
            )
        else:
            grid_view = ft.Container(
                ft.Column([
                    ft.Icon(ft.Icons.ARROW_DOWNWARD, size=32, color=ft.Colors.OUTLINE),
                    ft.Container(height=4),
                    ft.Text(f"Drop {sec['label'].split()[0].lower()} files here", color=ft.Colors.OUTLINE, size=11),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, alignment=ft.MainAxisAlignment.CENTER),
                height=100, border=ft.Border.all(2, sec["color"]), border_radius=8,
                bgcolor=sec["color"] + "15",
            )
        
        section_content = ft.Container(
            ft.Stack([
                ft.Column([
                    ft.Row([
                        ft.Icon(sec["icon"], size=18, color=sec["color"]),
                        ft.Text(sec["label"], size=13, weight=ft.FontWeight.BOLD, color=sec["color"]),
                        ft.Container(expand=True),
                        ft.Text(f"{len(cards)} item(s)", size=10, color=ft.Colors.OUTLINE),
                    ]),
                    ft.Container(height=4),
                    grid_view,
                ], tight=True, spacing=4),
                processing_overlay,
            ]),
            width=300,
            padding=10,
            border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=10,
            bgcolor=ft.Colors.SURFACE_CONTAINER,
        )
        
        # Store reference to processing overlay for this section
        if not hasattr(self, '_processing_overlays'):
            self._processing_overlays = {}
        self._processing_overlays[section_id] = processing_overlay
        
        return ft.DragTarget(
            group="all_items",
            content=section_content,
            on_accept=lambda e, s=sec: asyncio_create(self._on_convert_drop_async(e, s)),
            on_will_accept=lambda e, s=sec: self._on_will_accept(e, s),
            on_leave=lambda e, s=sec: self._on_drag_leave(e, s),
        )
    def _build_checkbox(self, selected: bool, paths: list[str]):
        """Custom clickable checkbox with guaranteed visibility."""
        def _make_content(sel: bool):
            return ft.Row([
                ft.Icon(
                    ft.Icons.CHECK_BOX if sel else ft.Icons.CHECK_BOX_OUTLINE_BLANK,
                    size=14, color=ft.Colors.PRIMARY,
                ),
                ft.Text("✓" if sel else "", size=12, color=ft.Colors.PRIMARY,
                        weight=ft.FontWeight.BOLD),
            ], tight=True)
        def _on_click(e):
            new_val = not e.control.data
            self._toggle_push_selection(paths, new_val)
            self._build_convert_view()
        return ft.Container(
            content=_make_content(selected),
            on_click=_on_click,
            data=selected,
            ink=True,
        )
    def _toggle_push_selection(self, paths: list[str], selected: bool):
        if selected:
            self._selected_push_paths.update(paths)
        else:
            self._selected_push_paths.difference_update(paths)
    def _on_card_click(self, e, paths: list[str]):
        """Click toggles multi-selection only when in selection mode."""
        g = self.gui
        if not g._selection_mode:
            return
        all_in = all(p in g._multi_selected for p in paths)
        if all_in:
            g._multi_selected.difference_update(paths)
        else:
            g._multi_selected.update(paths)
        if not g._multi_selected:
            g._selection_mode = False
        self._build_convert_view()
    def _on_card_long_press(self, e, paths: list[str]):
        """Long-press toggles selection mode on/off. Enters with this card selected."""
        g = self.gui
        if g._selection_mode:
            g._selection_mode = False
            g._multi_selected.clear()
        else:
            g._selection_mode = True
            g._multi_selected.clear()
            g._multi_selected.update(paths)
        self._build_convert_view()
    def _get_multi_selected_drag_paths(self, card_paths: list[str]) -> list[str]:
        """Return drag paths — all multi-selected if card is selected, else just this card's paths."""
        g = self.gui
        if not g._multi_selected:
            return card_paths
        card_selected = any(p in g._multi_selected for p in card_paths)
        if not card_selected:
            return card_paths
        return list(g._multi_selected)
    def _build_converted_card(self, f: Path, ftype: str, section_id: str) -> ft.Container:
        color_map = {"G3P": "#00BCD4", "TXT": "#E91E63", "BOTH": "#9C27B0"}
        is_g3p = ftype == "G3P"
        g = self.gui
        fpath = str(f)
        push_selected = fpath in self._selected_push_paths
        multi_sel = fpath in g._multi_selected
        
        inner = ft.Container(
            ft.Column([
                ft.Row([
                    ft.Icon(ft.Icons.IMAGE if is_g3p else ft.Icons.DESCRIPTION,
                            size=20, color=color_map.get(ftype, ft.Colors.OUTLINE)),
                    ft.Text(ftype, size=9, color=ft.Colors.ON_SURFACE,
                            weight=ft.FontWeight.BOLD,
                            bgcolor=color_map.get(ftype, ft.Colors.OUTLINE)),
                    ft.Container(expand=True),
                    ft.Text(_fmt_size(f.stat().st_size), size=9, color=ft.Colors.OUTLINE),
                ]),
                ft.Container(height=4),
                ft.Text(f.name, size=11, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS,
                        weight=ft.FontWeight.BOLD),
                ft.Container(height=4),
                ft.Row([
                    self._build_checkbox(push_selected, [fpath]),
                    ft.Text("Push", size=10, color=ft.Colors.OUTLINE),
                ]),
            ], spacing=2, tight=True),
            padding=10,
        )
        card = ft.Card(inner)
        clk = ft.Container(
            content=card,
            on_click=lambda e: self._on_card_click(e, [fpath]),
            on_long_press=lambda e: self._on_card_long_press(e, [fpath]),
            ink=True,
        )
        if multi_sel:
            clk = ft.Container(
                content=clk,
                border=ft.Border.all(2, ft.Colors.PRIMARY),
                border_radius=12,
            )
        drag_all = self._get_multi_selected_drag_paths([fpath])
        count = len(drag_all)
        return ft.Draggable(
            group="all_items",
            content=clk,
            content_when_dragging=ft.Container(opacity=0.3, content=clk),
            content_feedback=ft.Container(
                ft.Row([
                    ft.Icon(ft.Icons.FOLDER_OPEN, size=16, color=ft.Colors.ON_SURFACE),
                    ft.Text(f"🗑️ {count} files" if count > 1 else f"🗑️ {f.name}",
                            size=12, weight=ft.FontWeight.BOLD),
                ], tight=True),
                padding=10,
                bgcolor=ft.Colors.ERROR_CONTAINER if count == 1 else ft.Colors.TERTIARY_CONTAINER,
                border_radius=8,
            ),
            data={"path": fpath, "all_paths": drag_all, "section": section_id, "item_type": "converted"},
        )
    def _build_converted_pair_card(self, g3p_f: Path, txt_f: Path) -> ft.Draggable:
        g3p_path = str(g3p_f)
        txt_path = str(txt_f)
        both_paths = [g3p_path, txt_path]
        g = self.gui
        push_selected = all(p in self._selected_push_paths for p in both_paths)
        multi_sel = any(p in g._multi_selected for p in both_paths)
        
        inner = ft.Container(
            ft.Column([
                ft.Row([
                    ft.Icon(ft.Icons.LAYERS, size=20, color="#9C27B0"),
                    ft.Text("BOTH", size=9, color=ft.Colors.ON_SURFACE,
                            weight=ft.FontWeight.BOLD, bgcolor="#9C27B0"),
                    ft.Container(expand=True),
                    ft.Text(f"G3P: {_fmt_size(g3p_f.stat().st_size)} / TXT: {_fmt_size(txt_f.stat().st_size)}",
                            size=9, color=ft.Colors.OUTLINE),
                ]),
                ft.Container(height=4),
                ft.Text(f"{g3p_f.stem}", size=11, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS,
                        weight=ft.FontWeight.BOLD),
                ft.Container(height=4),
                ft.Row([
                    self._build_checkbox(push_selected, both_paths),
                    ft.Text("Push Both", size=10, color=ft.Colors.OUTLINE),
                ]),
            ], spacing=2, tight=True),
            padding=10,
        )
        card = ft.Card(inner)
        clk = ft.Container(
            content=card,
            on_click=lambda e: self._on_card_click(e, both_paths),
            on_long_press=lambda e: self._on_card_long_press(e, both_paths),
            ink=True,
        )
        if multi_sel:
            clk = ft.Container(
                content=clk,
                border=ft.Border.all(2, ft.Colors.PRIMARY),
                border_radius=12,
            )
        drag_all = self._get_multi_selected_drag_paths(both_paths)
        count = len(drag_all)
        return ft.Draggable(
            group="all_items",
            content=clk,
            content_when_dragging=ft.Container(opacity=0.3, content=clk),
            content_feedback=ft.Container(
                ft.Row([
                    ft.Icon(ft.Icons.FOLDER_OPEN, size=16, color=ft.Colors.ON_SURFACE),
                    ft.Text(f"🗑️ {count} files" if count > 1 else f"🗑️ {g3p_f.stem} (both)",
                            size=12, weight=ft.FontWeight.BOLD),
                ], tight=True),
                padding=10,
                bgcolor=ft.Colors.ERROR_CONTAINER if count == 1 else ft.Colors.TERTIARY_CONTAINER,
                border_radius=8,
            ),
            data={"path": g3p_path, "all_paths": drag_all, "section": "both", "item_type": "converted"},
        )
    def _on_will_accept(self, e, sec: dict):
        section_id = sec["id"]
        # Reject drop if section is currently processing
        if self._processing_section == section_id:
            return
        e.control.content.bgcolor = sec["color"] + "30"
        e.control.update()
    def _on_drag_leave(self, e, sec: dict):
        e.control.content.bgcolor = ft.Colors.SURFACE_CONTAINER
        e.control.update()
    async def _on_convert_drop_async(self, e: ft.DragTargetEvent, sec: dict):
        """Async drop handler with locking to prevent concurrent conversions."""
        section_id = sec["id"]
        
        # Check if already processing
        if self._processing_section == section_id:
            return
        
        if not e.src or not e.src.data:
            return
        
        data = e.src.data
        
        # Skip if already converted (only input files should be converted)
        if data.get("item_type") == "converted":
            return
        
        # Get all paths to convert — from all_paths or single path
        all_paths = data.get("all_paths", [data.get("path")])
        target_section = sec["id"]
        img_exts = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tiff", ".tif", ".webp"}
        doc_exts = {".pdf", ".docx", ".doc", ".txt"}
        
        # Filter to only existing input files
        to_convert = []
        for p_str in all_paths:
            p = Path(p_str)
            if not p.exists():
                continue
            ext = p.suffix.lower()
            if ext in img_exts:
                to_convert.append((p, "IMG"))
            elif ext in doc_exts:
                to_convert.append((p, "DOC"))
        
        if not to_convert:
            return
        
        # Acquire lock for this section
        lock = self._section_locks.get(section_id)
        if lock and lock.locked():
            self.gui._show_snackbar(f"Section {section_id} is busy, try again", type="warning")
            return
        
        async with self._section_locks[section_id]:
            self._processing_section = section_id
            
            # Hide source card immediately
            if e.src:
                e.src.visible = False
                try:
                    e.src.update()
                except Exception:
                    pass
            
            # Show processing overlay
            if hasattr(self, '_processing_overlays') and section_id in self._processing_overlays:
                overlay = self._processing_overlays[section_id]
                overlay.visible = True
                overlay.update()
            
            try:
                target_map = {"images": "images", "text": "text", "both": "both"}
                target = target_map.get(target_section, "both")
                for src_path, ftype in to_convert:
                    await self.gui._convert_single(src_path, ftype, target)
            finally:
                self._processing_section = None
                if hasattr(self, '_processing_overlays') and section_id in self._processing_overlays:
                    overlay = self._processing_overlays[section_id]
                    overlay.visible = False
                    try:
                        overlay.update()
                    except Exception:
                        pass
    def _group_files_by_stem(self, files, is_both: bool) -> dict[str, list]:
        """Group files by stem prefix, stripping trailing _NNN groups (e.g., part_01_001 -> part)."""
        groups = {}
        if is_both:
            # files is list of (g3p_f, txt_f) tuples
            for g3p_f, txt_f in files:
                stem = re.sub(r'(?:_\d+)+$', '', g3p_f.stem)
                groups.setdefault(stem, []).append((g3p_f, txt_f))
        else:
            for f in files:
                stem = re.sub(r'(?:_\d+)+$', '', f.stem)
                groups.setdefault(stem, []).append(f)
        return groups
    def _build_expanded_group_card(self, stem: str, group_files: list, ftype: str, section_id: str) -> ft.Draggable:
        """Build a single draggable card for a stack of files from the same document."""
        count = len(group_files)
        is_both = isinstance(group_files[0], tuple)
        color = "#9C27B0" if is_both else ("#00BCD4" if ftype == "G3P" else "#E91E63")
        icon = ft.Icons.LAYERS if is_both else (ft.Icons.IMAGE if ftype == "G3P" else ft.Icons.DESCRIPTION)
        g = self.gui
        
        # Collect all file paths in this stack
        if is_both:
            all_paths = [str(g3p_f) for g3p_f, _ in group_files] + [str(txt_f) for _, txt_f in group_files]
            first_g3p = str(group_files[0][0])
        else:
            all_paths = [str(f) for f in group_files]
            first_g3p = all_paths[0]
        
        sz = 0
        if is_both:
            for g3p_f, txt_f in group_files:
                sz += g3p_f.stat().st_size + txt_f.stat().st_size
        else:
            for f in group_files:
                sz += f.stat().st_size
        
        push_selected = all(p in self._selected_push_paths for p in all_paths)
        multi_sel = any(p in g._multi_selected for p in all_paths)
        
        page_label = f"{count} pages" if count > 1 else "1 page"
        inner = ft.Container(
            ft.Column([
                ft.Row([
                    ft.Icon(icon, size=20, color=color),
                    ft.Container(
                        ft.Text(f"{ftype}", size=9, weight=ft.FontWeight.BOLD),
                        bgcolor=color, border_radius=4,
                        padding=ft.Padding.symmetric(horizontal=4, vertical=1),
                    ),
                    ft.Container(expand=True),
                    ft.Text(f"{page_label} · {_fmt_size(sz)}", size=9, color=ft.Colors.OUTLINE),
                ]),
                ft.Container(height=2),
                ft.Row([
                    ft.Icon(ft.Icons.FOLDER_OPEN, size=14, color=ft.Colors.OUTLINE),
                    ft.Column([
                        ft.Text(f"{stem}", size=12, weight=ft.FontWeight.BOLD, expand=True),
                        ft.Text(f"{count} file(s) · original document",
                                size=9, color=ft.Colors.OUTLINE),
                    ], spacing=1, tight=True, expand=True),
                ]),
                ft.Container(height=2),
                ft.Row([
                    self._build_checkbox(push_selected, all_paths),
                    ft.Text(f"Push All ({count})", size=10, color=ft.Colors.OUTLINE),
                ]),
            ], spacing=2, tight=True),
            padding=10,
        )
        card = ft.Card(inner)
        clk = ft.Container(
            content=card,
            on_click=lambda e: self._on_card_click(e, all_paths),
            on_long_press=lambda e: self._on_card_long_press(e, all_paths),
            ink=True,
        )
        if multi_sel:
            clk = ft.Container(
                content=clk,
                border=ft.Border.all(2, ft.Colors.PRIMARY),
                border_radius=12,
            )
        drag_all = self._get_multi_selected_drag_paths(all_paths)
        drag_count = len(drag_all)
        return ft.Draggable(
            group="all_items",
            content=clk,
            content_when_dragging=ft.Container(opacity=0.3, content=clk),
            content_feedback=ft.Container(
                ft.Row([
                    ft.Icon(ft.Icons.FOLDER_OPEN, size=16, color=ft.Colors.ON_SURFACE),
                    ft.Text(f"🗑️ {drag_count} files" if drag_count > 1 else f"🗑️ {stem} ({count})",
                            size=12, weight=ft.FontWeight.BOLD),
                ], tight=True),
                padding=10,
                bgcolor=ft.Colors.ERROR_CONTAINER if drag_count == count else ft.Colors.TERTIARY_CONTAINER,
                border_radius=8,
            ),
            data={"path": first_g3p, "all_paths": drag_all, "section": section_id, "item_type": "converted"},
        )
    def _on_convert_hover(self, e: ft.HoverEvent):
        if not hasattr(self, '_drop_zone_border'):
            self._drop_zone_border = e.control.border
        if e.data == "true":
            e.control.border = ft.Border.all(3, ft.Colors.PRIMARY)
            e.control.bgcolor = ft.Colors.PRIMARY_CONTAINER
        else:
            e.control.border = self._drop_zone_border
            e.control.bgcolor = None
        e.control.update()
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
            expanded=False,
                    controls=children,
                ))
            else:
                size_str = _fmt_size(e.size)
                addin_name = e.addin.get("name", "") if e.addin else ""
                trailing = ft.Text(addin_name, size=11, color=ft.Colors.PRIMARY,
                                   weight=ft.FontWeight.BOLD) if addin_name else None
                tile = ft.ListTile(
                    leading=ft.Container(width=indent * 16 + 4),
                    title=ft.Text(e.name, size=13),
                    subtitle=ft.Text(size_str, size=11, color=ft.Colors.OUTLINE),
                    trailing=trailing,
                )
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
                leading=ft.Icon(ft.Icons.ERROR_OUTLINE, color=ft.Colors.AMBER_ACCENT),
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
            g._show_snackbar("Settings saved", type="success")
        async def reset_all():
            ok = await g._confirm("Reset", "Reset all settings to defaults?")
            if ok:
                __import__("pcalc.config", fromlist=["reset"]).reset()
                await asyncio.sleep(0.1)  # allow config file write to complete
                default_theme = __import__("pcalc.config", fromlist=["get"]).get("theme_mode")
                g.page.theme_mode = ft.ThemeMode.DARK if default_theme == "dark" else ft.ThemeMode.LIGHT
                g.page.theme = __import__("pcalc.gui", fromlist=["_create_theme"])._create_theme()
                g.page.update()
                self._build_settings_view()
                g._show_snackbar("Settings reset", type="success")
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
    # ── Install Drop Target ──────────────────────────────────────────
    def _build_install_target(self) -> ft.DragTarget:
        g = self.gui
        return ft.DragTarget(
            group="all_items",
            content=ft.Container(
                ft.Row([
                    ft.Icon(ft.Icons.DOWNLOAD, size=24, color=ft.Colors.PRIMARY),
                    ft.Text(" Drop selected addins/games here to install on calculator",
                            size=14, color=ft.Colors.PRIMARY, weight=ft.FontWeight.BOLD),
                ], alignment=ft.MainAxisAlignment.CENTER),
                padding=16,
                border=ft.Border.all(2, ft.Colors.PRIMARY),
                border_radius=12,
            ),
            on_accept=self._on_install_accept,
            on_will_accept=self._on_install_will_accept,
        )
    def _on_install_accept(self, e):
        """Handle drop on install target — multi-selection or single item."""
        if self.gui._selected_registry_ids:
            asyncio_create(self.gui._install_selected())
        else:
            # Single item drag: extract item_id from draggable data
            data = e.src.data if e.src else {}
            item_id = data.get("item_id", "")
            if item_id:
                asyncio_create(self.gui._install_selected(item_ids=[item_id]))
            else:
                self.gui._show_snackbar("Nothing to install", type="warning")
    def _on_install_will_accept(self, e):
        if e.data:
            e.control.content.bgcolor = ft.Colors.SECONDARY_CONTAINER
        else:
            e.control.content.bgcolor = None
        e.control.update()
# ── Helper to create tasks from lambda callbacks ────────────────────
def asyncio_create(coro):
    import asyncio
    return asyncio.create_task(coro)