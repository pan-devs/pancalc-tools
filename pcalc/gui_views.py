"""
pcalc/gui_views.py — Flet GUI view builders for PanCalc Tools.
References core PanCalcGUI via self.gui.
"""
from __future__ import annotations
import asyncio
import re
import shutil
from collections import defaultdict
from pathlib import Path
import flet as ft
from pcalc import config as pconfig
from pcalc import library as plibrary
from pcalc import updater as pupdater
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
GLOW_COLOR = "#8D6E63"  # brown — unified glow for all drop zones
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
def _restore_overlay(overlay, state: dict):
    """Repopulate a freshly-built overlay container from a saved conversion state."""
    prog = getattr(overlay, "_prog", None)
    if not prog:
        return
    try:
        total = max(state.get("total", 1), 1)
        done = max(state.get("done", 0), 0)
        value = min(done / total, 1.0)
        prog["ring"].value = value
        prog["pct"].value = f"{round(value * 100)}%"
        prog["time"].value = state.get("sub", "")
        prog["log"].controls.clear()
        for line in state.get("logs", [])[-30:]:
            prog["log"].controls.append(ft.Text(line, size=10))
    except Exception:
        pass
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
        self._card_refs: dict[str, ft.Control] = {}
        self._processing_overlays: dict[str, ft.Container] = {}
        self._converted_grids: dict[str, dict] = {}
        self._conversion_state: dict[str, dict] = {}

    _CARD_HOVER_SHADOW = ft.BoxShadow(
        spread_radius=2, blur_radius=24,
        color=ft.Colors.BLACK38, offset=ft.Offset(0, 8),
    )
    _HOVER_TEXT_FACTOR = 1.15
    _HOVER_BASE_ATTR = "_hover_base_size"

    _CARD_WID = 320
    _CARD_HGT = 145
    _CONV_WID = 200
    _CONV_HGT = 167

    def _on_card_hover(self, e: ft.ControlEvent):
        ctl = e.control
        hovering = e.data == "true"
        ctl.scale = 1.08 if hovering else 1.0
        ctl.shadow = self._CARD_HOVER_SHADOW.copy() if hovering else None
        self._scale_card_texts(ctl, self._HOVER_TEXT_FACTOR if hovering else 1.0)
        ctl.update()

    def _scale_card_texts(self, root, factor):
        stack = [root]
        while stack:
            node = stack.pop()
            if isinstance(node, ft.Text):
                base = getattr(node, self._HOVER_BASE_ATTR, None)
                if base is None:
                    base = node.size if node.size is not None else 14
                    setattr(node, self._HOVER_BASE_ATTR, base)
                node.size = round(base * factor)
                continue
            raw = getattr(node, "content", None)
            if isinstance(raw, (list, tuple)):
                stack.extend(raw)
            elif raw is not None and not isinstance(raw, (str, int, float, bool)):
                stack.append(raw)
            controls = getattr(node, "controls", None)
            if controls:
                stack.extend(controls)

    def _on_selection_drag_start(self, e: ft.DragStartEvent):
        g = self.gui
        if not g._selection_mode:
            return
        for c in self._card_refs.values():
            c.opacity = 1.0
        data = e.control.data
        if not isinstance(data, dict):
            g.page.update()
            return
        # Determine which selection set to use.  Convert cards are keyed by
        # path and selected via _multi_selected; installed/registry cards
        # are keyed by item_id / file path and selected via
        # _selected_registry_ids.  Both may carry "all_paths" in multi-select
        # drag data, so we probe _selected_registry_ids first.
        paths = data.get("all_paths", [])
        if any(p in g._selected_registry_ids for p in paths):
            sel = g._selected_registry_ids
        elif paths:
            sel = g._multi_selected
        elif "item_id" in data or "aid" in data:
            sel = g._selected_registry_ids
        else:
            sel = g._multi_selected
        # Identify the dragged card so we can skip dimming it.
        dragged = data.get("path") or data.get("item_id") or data.get("aid")
        dragged_wrap = None
        if dragged is None:
            # Group tiles register multiple keys pointing at the same wrap
            # container; find the wrap that matches the Draggable's content.
            dragged_wrap = e.control.content
        for key in list(sel):
            if key == dragged:
                continue
            c = self._card_refs.get(key)
            if c is not None:
                if dragged_wrap is not None and c is dragged_wrap:
                    continue
                c.opacity = 0.3
        g.page.update()

    def _on_selection_drag_complete(self, e: ft.DragEndEvent):
        for c in self._card_refs.values():
            c.opacity = 1.0
        self.gui._build_current_view()
    
    def _resolve_item_info(self, key: str) -> tuple[str, str]:
        g = self.gui
        from pathlib import Path
        
        # 1. Comprobar si es una ruta de archivo (local o en calculadora)
        if "/" in key or "\\" in key or key.endswith((".g3p", ".txt", ".bin")):
            path = Path(key)
            name = path.name
            ext = path.suffix.lower()
            parts = [p.lower() for p in path.parts]
            
            if "fotos" in parts or ext in (".g3p", ".png", ".jpg", ".jpeg", ".bmp"):
                section = "Photos (Calc)" if "fotos" in parts else "Images (Local)"
            elif "textos" in parts or ext in (".txt", ".pdf", ".doc", ".docx"):
                section = "Texts (Calc)" if "textos" in parts else "Docs (Local)"
            else:
                section = "Files (Calc)" if "pthings" in parts else "Files (Local)"
            return name, section
            
        # 2. Comprobar si es un add-in en la librería local
        lib = plibrary.get(key)
        if lib:
            name = lib.get("name") or lib.get("filename") or key
            section = lib.get("type", "addin").capitalize()
            if section == "Addin":
                section = "Add-in"
            return name, section
            
        # 3. Comprobar si es un add-in en el registro online
        reg_item = next((item for item in g.registry_data if item.get("id") == key), None)
        if reg_item:
            name = reg_item.get("name") or reg_item.get("filename") or key
            section = "Registry Add-in"
            return name, section
            
        # 4. Fallback por defecto
        return key, "Item"

    def _make_drag_feedback(self, count: int, name: str = "",
                            breakdown: dict[str, int] | None = None,
                            local_counts: dict[str, int] | None = None,
                            card: ft.Control | None = None) -> ft.Container | None:
        if count <= 1:
            if card is not None:
                return ft.Container(content=card, opacity=1.0)
            return None

        # Recopilar información de todos los elementos seleccionados
        g = self.gui
        items_info = []
        
        # Coleccionar de la selección de registro/librería local/calc
        if g._selection_mode and g._selected_registry_ids:
            for sid in g._selected_registry_ids:
                items_info.append(self._resolve_item_info(sid))
        # Coleccionar de la selección múltiple del convertidor
        elif g._multi_selected:
            for fpath in g._multi_selected:
                items_info.append(self._resolve_item_info(fpath))
                
        # Fallback si no hay selección global activa pero se pasa un nombre en el argumento
        if not items_info:
            fallback_sec = "Files"
            if breakdown:
                fallback_sec = list(breakdown.keys())[0] if breakdown else "Files"
            items_info.append((name or "Item", fallback_sec))
            
        # Construir contenido de la tarjeta de arrastre múltiple
        card_content = [
            ft.Row([
                ft.Icon(ft.Icons.DRAG_INDICATOR, size=18, color=ft.Colors.PRIMARY),
                ft.Text(f"Dragging {count} items", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.PRIMARY),
            ], spacing=6),
            ft.Container(height=4),
        ]
        
        # Mostrar hasta 4 elementos con sus nombres y secciones
        for item_name, item_section in items_info[:4]:
            card_content.append(
                ft.Row([
                    ft.Icon(ft.Icons.LABEL_OUTLINE, size=14, color=ft.Colors.OUTLINE),
                    ft.Text(item_name, size=11, weight=ft.FontWeight.BOLD, expand=True, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                    ft.Container(
                        ft.Text(item_section, size=8, color=ft.Colors.ON_SECONDARY_CONTAINER, weight=ft.FontWeight.BOLD),
                        bgcolor=ft.Colors.SECONDARY_CONTAINER,
                        border_radius=4,
                        padding=ft.Padding.symmetric(horizontal=4, vertical=1),
                    )
                ], spacing=4)
            )
            
        # Si hay más de 4 elementos, añadir el indicador correspondiente
        remaining = count - len(items_info[:4])
        if remaining > 0:
            card_content.append(
                ft.Row([
                    ft.Container(width=18),
                    ft.Text(f"+ {remaining} more items...", size=10, color=ft.Colors.OUTLINE, italic=True),
                ])
            )
            
        feedback_card = ft.Card(
            content=ft.Container(
                content=ft.Column(card_content, spacing=3, tight=True),
                padding=10,
                width=280,
                border_radius=8,
                bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
            )
        )
        
        return ft.Container(
            content=feedback_card,
            opacity=0.9,
        )
    # ── 1. Registry View ───────────────────────────────────────────
    def _build_registry_view(self):
        self._card_refs.clear()
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
                    ft.Text("The catalog is downloading or not yet available. Please wait, then click Refresh.", color=ft.Colors.OUTLINE),
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
                    visible=True,
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
            width=self._CARD_WID, height=self._CARD_HGT,
            ink=True,
            border_radius=12,
            animate=ft.Animation(160, ft.AnimationCurve.EASE_OUT),
            animate_scale=ft.Animation(160, ft.AnimationCurve.EASE_OUT),
            on_hover=self._on_card_hover,
        )
        if aid:
            self._card_refs[aid] = wrap
        is_local = source == "local"
        if is_local:
            if g._selection_mode and aid in g._selected_registry_ids:
                all_ids = []
                all_lib_types = []
                for sid in g._selected_registry_ids:
                    lib = plibrary.get(sid)
                    if lib:
                        all_ids.append(sid)
                        all_lib_types.append(lib.get("type", "addin"))
            else:
                all_ids = [aid]
                all_lib_types = [d.get("_type", "addin")]
            drag_data = {
                "item_id": aid,
                "lib_type": d.get("_type", "addin"),
                "item_type": "local_library",
                "installable": True,
                "all_ids": all_ids,
                "all_lib_types": all_lib_types,
            }
        else:
            drag_data = {"installable": True, "item_id": aid}
            all_ids = []
            all_lib_types = []

        if g._selection_mode and aid in g._selected_registry_ids:
            all_ids = []
            all_lib_types = []
            for sid in g._selected_registry_ids:
                lib = plibrary.get(sid)
                if lib:
                    all_ids.append(sid)
                    all_lib_types.append(lib.get("type", "addin"))
            if all_ids:
                drag_data["all_ids"] = all_ids
                drag_data["all_lib_types"] = all_lib_types
                drag_data["item_type"] = "local_library"
        if g._selection_mode and aid in g._selected_registry_ids:
            bd: dict[str, int] = {}
            lc: dict[str, int] = {}
            for sid in g._selected_registry_ids:
                lib = plibrary.get(sid)
                if lib:
                    t = lib.get("type", "addin") + "s"
                    bd[t] = bd.get(t, 0) + 1
                    lc[t] = lc.get(t, 0) + 1
            feedback = self._make_drag_feedback(len(g._selected_registry_ids), "", bd, lc)
        else:
            feedback = self._make_drag_feedback(1, name, card=wrap)
        return ft.Draggable(
            group="all_items",
            content=wrap,
            content_when_dragging=ft.Container(opacity=0.3, content=wrap),
            content_feedback=feedback,
            on_drag_start=self._on_selection_drag_start,
            on_drag_complete=self._on_selection_drag_complete,
            data=drag_data,
        )
    # ── 2. Games View ──────────────────────────────────────────────
    def _build_games_view(self):
        self._card_refs.clear()
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
                    ft.Text("The game catalog is downloading or not yet available. Please wait, then click Refresh.", color=ft.Colors.OUTLINE),
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
                    visible=True,
                    padding=ft.Padding.only(top=4, bottom=4),
                ),
                ft.Container(height=4),
                ft.Text("Install emulators from Registry (e.g. Nesizm), then add ROMs here.",
                        size=12, color=ft.Colors.OUTLINE),
                grid,
            ], expand=True, scroll=ft.ScrollMode.AUTO)
        )
    def _build_installed_group_tile(self, stem: str, group_files: list, sub: str,
                                      all_del_paths: list, all_del_ids: list, all_del_types: list,
                                      del_count: int, del_breakdown: dict, del_local: dict) -> ft.Draggable:
        g = self.gui
        count = len(group_files)
        all_paths = [str(f) for f in group_files]
        total_size = sum(f.stat().st_size for f in group_files)
        icon = ft.Icons.IMAGE if sub == "fotos" else ft.Icons.DESCRIPTION
        color = "#00BCD4" if sub == "fotos" else "#E91E63"
        first_name = group_files[0].name
        last_name = group_files[-1].name
        any_selected = any(p in g._selected_registry_ids for p in all_paths)

        label = f"{count} files" if count != 1 else "1 file"
        list_tile = ft.ListTile(
            leading=ft.Icon(ft.Icons.LAYERS, size=20, color=color),
            title=ft.Text(f"{stem} [{label}]", size=14, weight=ft.FontWeight.BOLD if any_selected else None),
            subtitle=ft.Text(f"{first_name} → {last_name} • {_fmt_size(total_size)}", size=11, color=ft.Colors.OUTLINE),
        )
        if any_selected:
            list_tile = ft.Container(
                content=list_tile,
                border=ft.Border.all(2, ft.Colors.PRIMARY),
                border_radius=8,
                padding=2,
            )
        list_tile = ft.Card(list_tile)

        def _on_group_click(e):
            if g._selection_mode:
                if any_selected:
                    for p in all_paths:
                        g._selected_registry_ids.discard(p)
                else:
                    for p in all_paths:
                        g._selected_registry_ids.add(p)
                if not g._selected_registry_ids:
                    g._selection_mode = False
                g._build_current_view()

        def _on_group_long_press(e):
            if g._selection_mode:
                g._selection_mode = False
                g._selected_registry_ids.clear()
            else:
                g._selection_mode = True
                g._selected_registry_ids.clear()
                for p in all_paths:
                    g._selected_registry_ids.add(p)
            g._build_current_view()

        wrap = ft.Container(
            content=list_tile,
            on_click=_on_group_click,
            on_long_press=_on_group_long_press,
            width=self._CARD_WID, height=self._CARD_HGT,
            ink=True,
            border_radius=12,
            animate=ft.Animation(160, ft.AnimationCurve.EASE_OUT),
            animate_scale=ft.Animation(160, ft.AnimationCurve.EASE_OUT),
            on_hover=self._on_card_hover,
        )
        for p in all_paths:
            self._card_refs[p] = wrap
        if g._selection_mode and any_selected:
            gdata = {"all_paths": all_del_paths, "all_ids": all_del_ids, "all_lib_types": all_del_types, "item_type": "calculator_file"}
            gfb = self._make_drag_feedback(del_count, "", del_breakdown, del_local)
        else:
            gdata = {"all_paths": all_paths, "item_type": "calculator_file"}
            gfb = self._make_drag_feedback(count, f"{stem} ({count})", {"files": count} if count > 1 else None, card=wrap)
        return ft.Draggable(
            group="all_items",
            content=wrap,
            content_when_dragging=ft.Container(opacity=0.3, content=wrap),
            content_feedback=gfb,
            on_drag_start=self._on_selection_drag_start,
            on_drag_complete=self._on_selection_drag_complete,
            data=gdata,
        )

    async def _remove_group_files(self, files: list):
        g = self.gui
        names = [f.name for f in files]
        if pconfig.get("confirm_remove"):
            ok = await g._confirm("Delete", f"Delete {len(files)} file(s)?\n" + "\n".join(names))
            if not ok:
                return
        deleted = 0
        for f in files:
            try:
                f.unlink()
                deleted += 1
            except OSError:
                pass
        if deleted:
            g._show_snackbar(f"🗑️ {deleted} file(s) deleted", type="success")
            g._build_current_view()

    # ── 3. Installed View ──────────────────────────────────────────
    def _build_installed_view(self):
        self._card_refs.clear()
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
        g.installed_addin_ids = {e.addin.get("id") for e in iter_calc_files(entries) if e.addin}
        matched_paths: set[str] = set()
        addin_rows: list[ft.Control] = []
        games_rows: list[ft.Control] = []
        pthings_rows: list[ft.Control] = []
        n_addin_matched = 0
        n_game_matched = 0
        # Build ID-to-paths mapping for multi-delete via selection
        # (one addin may span several files, e.g. KhiCAS → g3a + ac2)
        id_to_paths: dict[str, list[str]] = defaultdict(list)
        for fe in iter_calc_files(entries):
            if fe.addin:
                aid = fe.addin.get("id", "")
                if aid:
                    id_to_paths[aid].append(str(calc.mount_path / fe.name))
        # Unified deletable items for selection mode — same list used by ALL card builders
        all_deletable_paths: list[str] = []
        all_deletable_ids: list[str] = []
        all_deletable_types: list[str] = []
        if g._selection_mode:
            for sid in list(g._selected_registry_ids):
                if sid in id_to_paths:
                    all_deletable_paths.extend(id_to_paths[sid])
                elif Path(sid).exists():
                    all_deletable_paths.append(sid)
                else:
                    lib = plibrary.get(sid)
                    if lib:
                        all_deletable_ids.append(sid)
                        all_deletable_types.append(lib.get("type", "addin"))
        _del_count = len(all_deletable_paths) + len(all_deletable_ids)
        _del_breakdown: dict[str, int] = {}
        _del_local: dict[str, int] = {}
        if _del_count:
            if all_deletable_paths:
                _del_breakdown["files"] = len(all_deletable_paths)
            for tid, ttype in zip(all_deletable_ids, all_deletable_types):
                label = ttype + "s"
                _del_breakdown[label] = _del_breakdown.get(label, 0) + 1
                _del_local[label] = _del_local.get(label, 0) + 1
        # Group matched files by addin id so multi-file addins (e.g. KhiCAS
        # → g3a + ac2) render as ONE card.
        addin_groups: dict[str, dict] = {}
        for fe in iter_calc_files(entries):
            if not fe.addin:
                continue
            aid = fe.addin.get("id", "")
            if not aid:
                continue
            group = addin_groups.setdefault(aid, {"addin": fe.addin, "files": []})
            group["files"].append(fe)

        for aid, group in addin_groups.items():
            addin = group["addin"]
            files = group["files"]
            for fe in files:
                matched_paths.add(fe.name)
            name = addin.get("name", addin.get("id", "?"))
            icon = _icon_for_addin(addin)
            is_game = bool(addin.get("emulator") or addin.get("category") == "games")
            game_color = "#ed55a1" if is_game else None
            if is_game:
                n_game_matched += 1
            else:
                n_addin_matched += 1
            is_selected = aid in g._selected_registry_ids
            file_subtitle = " · ".join(fe.name for fe in files)
            all_paths = [str(calc.mount_path / fe.name) for fe in files]
            list_tile = ft.ListTile(
                leading=ft.Icon(icon, color=game_color),
                title=ft.Text(name, size=14, color=game_color),
                subtitle=ft.Text(file_subtitle, size=11, color=ft.Colors.OUTLINE),
                trailing=ft.Row([
                    ft.IconButton(ft.Icons.VERIFIED, tooltip="Verify",
                                  icon_color=game_color,
                                  on_click=lambda _, a=addin, n=name: asyncio_create(g._verify_item(a, n))),
                ], tight=True),
            )
            if is_selected:
                list_tile = ft.Container(
                    content=list_tile,
                    border=ft.Border.all(2, ft.Colors.PRIMARY),
                    border_radius=8,
                    padding=2,
                )
            list_tile = ft.Card(list_tile)
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
                width=self._CARD_WID, height=self._CARD_HGT,
                ink=True,
                border_radius=12,
                animate=ft.Animation(160, ft.AnimationCurve.EASE_OUT),
                animate_scale=ft.Animation(160, ft.AnimationCurve.EASE_OUT),
                on_hover=self._on_card_hover,
            )
            if aid:
                self._card_refs[aid] = wrap
            if g._selection_mode and aid in g._selected_registry_ids:
                feedback = self._make_drag_feedback(_del_count, "", _del_breakdown, _del_local)
            else:
                feedback = self._make_drag_feedback(1, name, card=wrap)
            if g._selection_mode and aid in g._selected_registry_ids:
                drag_data = {"all_paths": all_deletable_paths, "all_ids": all_deletable_ids, "all_lib_types": all_deletable_types, "item_type": "calculator_file"}
            else:
                drag_data = {"all_paths": all_paths, "item_type": "calculator_file"}
            (games_rows if is_game else addin_rows).append(ft.Draggable(
                group="all_items",
                content=wrap,
                content_when_dragging=ft.Container(opacity=0.3, content=wrap),
                content_feedback=feedback,
                on_drag_start=self._on_selection_drag_start,
                on_drag_complete=self._on_selection_drag_complete,
                data=drag_data,
            ))
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
            ext = f.suffix.lower()
            is_game_orphan = ext in GAME_EXTS
            if is_game_orphan:
                n_game_matched += 1
            else:
                n_addin_matched += 1
            icon = ft.Icons.EXTENSION if ext in ADDIN_EXTS else ft.Icons.SPORTS_ESPORTS
            list_tile = ft.ListTile(
                leading=ft.Icon(icon, color=ft.Colors.AMBER_ACCENT),
                title=ft.Text(f.stem, size=14, color=ft.Colors.AMBER_ACCENT),
                subtitle=ft.Text(f"orphan • {rel}", size=11, color=ft.Colors.OUTLINE),
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
            list_tile = ft.Card(list_tile)
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
                width=self._CARD_WID, height=self._CARD_HGT,
                ink=True,
                border_radius=12,
                animate=ft.Animation(160, ft.AnimationCurve.EASE_OUT),
                animate_scale=ft.Animation(160, ft.AnimationCurve.EASE_OUT),
                on_hover=self._on_card_hover,
            )
            self._card_refs[fpath_str] = wrap
            if g._selection_mode and fpath_str in g._selected_registry_ids:
                orphan_data = {"all_paths": all_deletable_paths, "all_ids": all_deletable_ids, "all_lib_types": all_deletable_types, "item_type": "calculator_file"}
                orphan_feedback = self._make_drag_feedback(_del_count, "", _del_breakdown, _del_local)
            else:
                orphan_data = {"path": fpath_str, "item_type": "calculator_file"}
                orphan_feedback = self._make_drag_feedback(1, f.stem, card=wrap)
            (games_rows if is_game_orphan else addin_rows).append(ft.Draggable(
                group="all_items",
                content=wrap,
                content_when_dragging=ft.Container(opacity=0.3, content=wrap),
                content_feedback=orphan_feedback,
            on_drag_start=self._on_selection_drag_start,
            on_drag_complete=self._on_selection_drag_complete,
                data=orphan_data,
            ))
        for sub in ("fotos", "textos"):
            d = calc.mount_path / "pthings" / sub
            if d.exists():
                pfiles = [f for f in sorted(d.iterdir()) if f.is_file()]
                if not pfiles:
                    continue
                groups: dict[str, list] = defaultdict(list)
                for f in pfiles:
                    stem = re.sub(r'(?:_\d+)+$', '', f.stem)
                    groups[stem].append(f)
                for stem, gfiles in groups.items():
                    if len(gfiles) == 1:
                        f = gfiles[0]
                        list_tile = ft.ListTile(
                            leading=ft.Icon(ft.Icons.IMAGE if sub == "fotos" else ft.Icons.DESCRIPTION, size=20),
                            title=ft.Text(f.name, size=14),
                            subtitle=ft.Text(f"pthings/{sub}/", size=11, color=ft.Colors.OUTLINE),
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
                        list_tile = ft.Card(list_tile)
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
                            width=self._CARD_WID, height=self._CARD_HGT,
                            ink=True,
                            border_radius=12,
                            animate=ft.Animation(160, ft.AnimationCurve.EASE_OUT),
                            animate_scale=ft.Animation(160, ft.AnimationCurve.EASE_OUT),
                            on_hover=self._on_card_hover,
                        )
                        self._card_refs[pfpath] = wrap
                        if g._selection_mode and pfpath in g._selected_registry_ids:
                            pdata = {"all_paths": all_deletable_paths, "all_ids": all_deletable_ids, "all_lib_types": all_deletable_types, "item_type": "calculator_file"}
                            pfb = self._make_drag_feedback(_del_count, "", _del_breakdown, _del_local)
                        else:
                            pdata = {"path": pfpath, "item_type": "calculator_file"}
                            pfb = self._make_drag_feedback(1, f.name, card=wrap)
                        pthings_rows.append(ft.Draggable(
                            group="all_items",
                            content=wrap,
                            content_when_dragging=ft.Container(opacity=0.3, content=wrap),
                            content_feedback=pfb,
                            on_drag_start=self._on_selection_drag_start,
                            on_drag_complete=self._on_selection_drag_complete,
                            data=pdata,
                        ))
                    else:
                        pthings_rows.append(self._build_installed_group_tile(
                            stem, gfiles, sub,
                            all_deletable_paths, all_deletable_ids, all_deletable_types,
                            _del_count, _del_breakdown, _del_local,
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
            addin_rows.append(ft.Divider())
            addin_rows.append(ft.Text("🏷️ Local Library (not on calculator)", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.OUTLINE))
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
                    ], tight=True),
                )
                if is_selected:
                    list_tile = ft.Container(
                        content=list_tile,
                        border=ft.Border.all(2, ft.Colors.PRIMARY),
                        border_radius=8,
                        padding=2,
                    )
                list_tile = ft.Card(list_tile)
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
                    width=self._CARD_WID, height=self._CARD_HGT,
                    ink=True,
                    border_radius=12,
                    animate=ft.Animation(160, ft.AnimationCurve.EASE_OUT),
                    animate_scale=ft.Animation(160, ft.AnimationCurve.EASE_OUT),
                    on_hover=self._on_card_hover,
                )
                self._card_refs[aid] = wrap
                if g._selection_mode and aid in g._selected_registry_ids:
                    feedback = self._make_drag_feedback(_del_count, "", _del_breakdown, _del_local)
                else:
                    feedback = self._make_drag_feedback(1, name, card=wrap)
                if g._selection_mode and aid in g._selected_registry_ids:
                    _all_ids = all_deletable_ids or [aid]
                    _all_types = all_deletable_types or [item_type]
                else:
                    _all_ids = [aid]
                    _all_types = [item_type]
                drag_data = {
                    "item_id": d["id"], "lib_type": item_type,
                    "item_type": "local_library", "installable": True,
                    "all_ids": _all_ids, "all_lib_types": _all_types,
                }
                if g._selection_mode and aid in g._selected_registry_ids:
                    if all_deletable_paths:
                        drag_data["all_paths"] = all_deletable_paths
                addin_rows.append(ft.Draggable(
                    group="all_items",
                    content=wrap,
                    content_when_dragging=ft.Container(opacity=0.3, content=wrap),
                    content_feedback=feedback,
                    on_drag_start=self._on_selection_drag_start,
                    on_drag_complete=self._on_selection_drag_complete,
                    data=drag_data,
                ))
        def _col_with_header(header: str, rows: list, empty_txt: str) -> ft.Column:
            controls: list[ft.Control] = [ft.Text(header, size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.OUTLINE)]
            if rows:
                controls.extend(rows)
            else:
                controls.append(ft.Text(empty_txt, size=12, color=ft.Colors.OUTLINE))
            return ft.Column(controls=controls, expand=True, spacing=2)

        left_col = _col_with_header("Addins", addin_rows, "No addins found on calculator")
        mid_col = _col_with_header("Games", games_rows, "No games found on calculator")
        right_col = _col_with_header("Pthings", pthings_rows, "No pthings")
        g._set_content(
            ft.Column([
                ft.Row([
                    ft.Text("Installed", size=20, weight=ft.FontWeight.BOLD),
                    ft.Text(f"{n_addin_matched} add-ins · {n_game_matched} games · {dcount} files", size=12, color=ft.Colors.OUTLINE),
                    ft.Container(expand=True),
                    ft.ElevatedButton("Refresh", icon=ft.Icons.REFRESH,
                                      on_click=lambda _: asyncio_create(g._scan_calculator())),
                ]),
                ft.Container(height=4),
                ft.Row([left_col, mid_col, right_col], expand=True, vertical_alignment=ft.CrossAxisAlignment.START),
            ], expand=True)
        )
    # ── 4. Convert View ────────────────────────────────────────────
    def _build_convert_view(self):
        g = self.gui
        self._card_refs.clear()
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
                ft.Text("INPUT FILES", size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
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
                    ft.Icon(ft.Icons.CLOUD_UPLOAD, size=48, color=ft.Colors.ON_SURFACE),
                    ft.Container(height=8),
                    ft.Text("No input files. Click 'Select Files' or drag & drop.", color=ft.Colors.ON_SURFACE),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, alignment=ft.MainAxisAlignment.CENTER),
                height=120, border=ft.Border.all(2, GLOW_COLOR), border_radius=10,
                alignment=ft.Alignment.CENTER, ink=True,
                on_click=lambda _: asyncio_create(g._pick_convert_files()),
            ),
            ft.Container(height=4),
            ft.Text("👇 Drag files below to convert", size=11, color=ft.Colors.ON_SURFACE, italic=True),
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
                    ft.Text("CONVERTED", size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                    ft.Container(expand=True),
                    ft.Row([
                        ft.Icon(ft.Icons.TOUCH_APP, size=14, color=ft.Colors.PRIMARY),
                        ft.Text("Long-press a card to select, then drop on Push or Trash",
                                size=11, color=ft.Colors.PRIMARY),
                    ], tight=True),
                ]),
                ft.Container(height=4),
                ft.Row(equal_sections, spacing=8, vertical_alignment=ft.CrossAxisAlignment.START),
                ft.Container(height=8),
                ft.Divider(),
                ft.Container(height=4),
                self._build_push_target(),
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
                    ft.Text(ftype, size=9, color=color_map.get(ftype, ft.Colors.ON_SURFACE),
                            weight=ft.FontWeight.BOLD),
                    ft.Container(expand=True),
                    ft.Text(_fmt_size(f.stat().st_size), size=9, color=ft.Colors.ON_SURFACE),
                ], alignment=ft.MainAxisAlignment.START),
                ft.Container(height=4),
                ft.Text(f.name, size=11, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS,
                        weight=ft.FontWeight.BOLD),
                ft.Container(height=4),
                ft.Row([
                    ft.Text(f"Drag to convert", size=9, color=ft.Colors.ON_SURFACE, italic=True),
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
            width=self._CONV_WID, height=self._CONV_HGT,
            border_radius=12,
            animate=ft.Animation(160, ft.AnimationCurve.EASE_OUT),
            animate_scale=ft.Animation(160, ft.AnimationCurve.EASE_OUT),
            on_hover=self._on_card_hover,
        )
        if multi_sel:
            clk = ft.Container(
                content=clk,
                border=ft.Border.all(2, ft.Colors.PRIMARY),
                width=self._CONV_WID, height=self._CONV_HGT,
                border_radius=12,
                animate=ft.Animation(160, ft.AnimationCurve.EASE_OUT),
                animate_scale=ft.Animation(160, ft.AnimationCurve.EASE_OUT),
                on_hover=self._on_card_hover,
            )
        drag_all = self._get_multi_selected_drag_paths([fpath])
        count = len(drag_all)
        self._card_refs[fpath] = clk
        return ft.Draggable(
            group="all_items",
            content=clk,
            content_when_dragging=ft.Container(opacity=0.3, content=clk),
            content_feedback=self._make_drag_feedback(count, f"{ftype}: {f.name}", {"files": count} if count > 1 else None, card=clk),
            data={"path": fpath, "all_paths": drag_all, "type": ftype,
                  "source_dir": str(source_dir), "item_type": "convert_input"},
            on_drag_start=self._on_selection_drag_start,
            on_drag_complete=self._on_selection_drag_complete,
        )
    def _build_converted_section(self, sec: dict) -> ft.Control:
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
        
        # Processing overlay (hidden by default) — % on the left, live log on the
        # right. Fixed size so it lays out cleanly when shown inside the Stack.
        _prog_ring = ft.ProgressRing(width=46, height=46, color=sec["color"], value=0)
        _prog_pct = ft.Text("0%", size=22, color=sec["color"],
                            weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER)
        _prog_sub = ft.Text("", size=10, color=ft.Colors.ON_SURFACE,
                            text_align=ft.TextAlign.CENTER)
        _prog_log = ft.ListView(
            spacing=1, padding=ft.Padding.symmetric(horizontal=6, vertical=4),
            height=110, width=170, auto_scroll=True,
        )
        processing_overlay = ft.Container(
            ft.Row([
                ft.Column([
                    _prog_ring,
                    _prog_pct,
                    _prog_sub,
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                   alignment=ft.MainAxisAlignment.CENTER, tight=True, spacing=2),
                ft.VerticalDivider(width=1),
                _prog_log,
            ], alignment=ft.MainAxisAlignment.CENTER, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            visible=False,
            alignment=ft.Alignment.CENTER,
            width=330, height=130,
            bgcolor=ft.Colors.SURFACE_CONTAINER,
            border=ft.Border.all(1, sec["color"]),
            border_radius=10,
        )
        # Stash progress widgets so the async converter can update them
        processing_overlay._prog = {
            "ring": _prog_ring, "file": _prog_pct,
            "pct": _prog_pct, "time": _prog_sub, "log": _prog_log,
        }
        # Always a GridView so cards can be appended in real time (empty is fine)
        grid_view = ft.GridView(
            controls=cards,
            max_extent=200, child_aspect_ratio=1.2, spacing=6, run_spacing=6,
        )
        self._converted_grids[section_id] = {
            "grid": grid_view,
            "sec": sec,
            "is_both": is_both,
            "ftype": sec["ftype"],
        }
        
        # Drop zone: only the grid / empty area — glow must be centred here.
        # When empty, show a subtle hint behind the (transparent) GridView so it
        # can still receive live cards without losing the "drop here" affordance.
        _empty_hint = None
        if not cards:
            _empty_hint = ft.Container(
                ft.Column([
                    ft.Icon(ft.Icons.ARROW_DOWNWARD, size=32, color=sec["color"]),
                    ft.Container(height=4),
                    ft.Text(f"Drop {sec['label'].split()[0].lower()} files here", color=sec["color"], size=11),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, alignment=ft.MainAxisAlignment.CENTER),
                expand=True,
            )
        _stack_parts = [_empty_hint] if _empty_hint else []
        _stack_parts += [grid_view, processing_overlay]
        drop_zone_content = ft.Stack(_stack_parts, expand=True)
        def _badge(g, sid=section_id):
            n = len(getattr(g, "_multi_selected", set()) or [])
            return (n or 1, f"input → {sid}")
        def _accept(e, s=sec):
            asyncio_create(self._on_convert_drop_async(e, s))
        drop_target = DropZone(
            self.gui, drop_zone_content,
            color=GLOW_COLOR, dest=f"converter ({'fotos' if sec['id']=='images' else 'textos' if sec['id']=='text' else 'both'})",
            badge_fn=_badge, on_accept=_accept, border_radius=8,
        ).build()
        
        # Store reference to processing overlay for this section.
        # If this section is mid-conversion (user navigated away and back),
        # keep the new overlay visible with current progress so the spinner
        # doesn't vanish.
        if not hasattr(self, '_processing_overlays'):
            self._processing_overlays = {}
        self._processing_overlays[section_id] = processing_overlay
        state = self._conversion_state.get(section_id)
        if getattr(self, '_processing_section', None) == section_id or (state and state.get("active")):
            processing_overlay.visible = True
            if state:
                _restore_overlay(processing_overlay, state)
        
        # Full section: header row + DropZone (grid only)
        return ft.Container(
            ft.Column([
                ft.Row([
                    ft.Icon(sec["icon"], size=18, color=sec["color"]),
                    ft.Text(sec["label"], size=13, weight=ft.FontWeight.BOLD, color=sec["color"]),
                    ft.Container(expand=True),
                    ft.Text(f"{len(cards)} item(s)", size=10, color=ft.Colors.ON_SURFACE),
                ]),
                ft.Container(height=4),
                drop_target,
            ], tight=True, spacing=4),
            expand=True,
            padding=10,
            border=ft.Border.all(1, sec["color"]),
            border_radius=10,
        )
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
        multi_sel = fpath in g._multi_selected
        
        inner = ft.Container(
            ft.Column([
                ft.Row([
                    ft.Icon(ft.Icons.IMAGE if is_g3p else ft.Icons.DESCRIPTION,
                            size=20, color=color_map.get(ftype, ft.Colors.OUTLINE)),
                    ft.Text(ftype, size=9, color=color_map.get(ftype, ft.Colors.ON_SURFACE),
                            weight=ft.FontWeight.BOLD),
                    ft.Container(expand=True),
                    ft.Text(_fmt_size(f.stat().st_size), size=9, color=ft.Colors.ON_SURFACE),
                ]),
                ft.Container(height=4),
                ft.Text(f.name, size=11, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS,
                        weight=ft.FontWeight.BOLD),
            ], spacing=2, tight=True),
            padding=10,
        )
        card = ft.Card(inner)
        clk = ft.Container(
            content=card,
            on_click=lambda e: self._on_card_click(e, [fpath]),
            on_long_press=lambda e: self._on_card_long_press(e, [fpath]),
            ink=True,
            width=self._CONV_WID, height=self._CONV_HGT,
            border_radius=12,
            animate=ft.Animation(160, ft.AnimationCurve.EASE_OUT),
            animate_scale=ft.Animation(160, ft.AnimationCurve.EASE_OUT),
            on_hover=self._on_card_hover,
        )
        if multi_sel:
            clk = ft.Container(
                content=clk,
                border=ft.Border.all(2, ft.Colors.PRIMARY),
                width=self._CONV_WID, height=self._CONV_HGT,
                border_radius=12,
                animate=ft.Animation(160, ft.AnimationCurve.EASE_OUT),
                animate_scale=ft.Animation(160, ft.AnimationCurve.EASE_OUT),
                on_hover=self._on_card_hover,
            )
        drag_all = self._get_multi_selected_drag_paths([fpath])
        count = len(drag_all)
        self._card_refs[fpath] = clk
        return ft.Draggable(
            group="all_items",
            content=clk,
            content_when_dragging=ft.Container(opacity=0.3, content=clk),
            content_feedback=self._make_drag_feedback(count, f.name, {"files": count} if count > 1 else None, card=clk),
            data={"path": fpath, "all_paths": drag_all, "section": section_id, "item_type": "converted"},
            on_drag_start=self._on_selection_drag_start,
            on_drag_complete=self._on_selection_drag_complete,
        )
    def _build_converted_pair_card(self, g3p_f: Path, txt_f: Path) -> ft.Draggable:
        g3p_path = str(g3p_f)
        txt_path = str(txt_f)
        both_paths = [g3p_path, txt_path]
        g = self.gui
        multi_sel = any(p in g._multi_selected for p in both_paths)
        
        inner = ft.Container(
            ft.Column([
                ft.Row([
                    ft.Icon(ft.Icons.LAYERS, size=20, color="#9C27B0"),
                    ft.Text("BOTH", size=9, color="#9C27B0",
                            weight=ft.FontWeight.BOLD),
                    ft.Container(expand=True),
                    ft.Text(f"G3P: {_fmt_size(g3p_f.stat().st_size)} / TXT: {_fmt_size(txt_f.stat().st_size)}",
                            size=9, color=ft.Colors.ON_SURFACE),
                ]),
                ft.Container(height=4),
                ft.Text(f"{g3p_f.stem}", size=11, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS,
                        weight=ft.FontWeight.BOLD),
                ft.Container(height=4),
                ft.Row([
                    ft.Text("Drag to Push / Trash", size=10, color=ft.Colors.OUTLINE),
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
            width=self._CONV_WID, height=self._CONV_HGT,
            border_radius=12,
            animate=ft.Animation(160, ft.AnimationCurve.EASE_OUT),
            animate_scale=ft.Animation(160, ft.AnimationCurve.EASE_OUT),
            on_hover=self._on_card_hover,
        )
        if multi_sel:
            clk = ft.Container(
                content=clk,
                border=ft.Border.all(2, ft.Colors.PRIMARY),
                width=self._CONV_WID, height=self._CONV_HGT,
                border_radius=12,
                animate=ft.Animation(160, ft.AnimationCurve.EASE_OUT),
                animate_scale=ft.Animation(160, ft.AnimationCurve.EASE_OUT),
                on_hover=self._on_card_hover,
            )
        drag_all = self._get_multi_selected_drag_paths(both_paths)
        count = len(drag_all)
        self._card_refs[g3p_path] = clk
        self._card_refs[txt_path] = clk
        return ft.Draggable(
            group="all_items",
            content=clk,
            content_when_dragging=ft.Container(opacity=0.3, content=clk),
            content_feedback=self._make_drag_feedback(count, f"{g3p_f.stem} (both)", {"files": count} if count > 1 else None, card=clk),
            data={"path": g3p_path, "all_paths": drag_all, "section": "both", "item_type": "converted"},
            on_drag_start=self._on_selection_drag_start,
            on_drag_complete=self._on_selection_drag_complete,
        )
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
            overlay = self._processing_overlays.get(section_id)
            prog = getattr(overlay, '_prog', None) if overlay else None
            if overlay:
                overlay.visible = True
                if prog:
                    prog["ring"].value = 0
                    prog["pct"].value = "0%"
                    prog["time"].value = "Preparing..."
                    prog["file"].value = "0%"
                    prog["log"].controls.clear()
                overlay.update()
            
            import time as _time
            t0 = _time.monotonic()
            total = len(to_convert)
            # Keep conversion state so the overlay can be restored if the user
            # navigates away and back mid-batch.
            self._conversion_state[section_id] = {
                "active": True, "total": total, "done": 0,
                "sub": "Preparing...", "logs": [],
            }
            try:
                target_map = {"images": "images", "text": "text", "both": "both"}
                target = target_map.get(target_section, "both")
                loop = asyncio.get_running_loop()
                for i, (src_path, ftype) in enumerate(to_convert, 1):
                    # Update progress UI for frame start — single overlay.update()
                    pct_val = (i - 1) / total
                    elapsed = _time.monotonic() - t0
                    if i > 1 and elapsed > 0:
                        remaining = elapsed / (i - 1) * (total - i + 1)
                        m, s = divmod(int(remaining), 60)
                        time_left = f"~{m}m {s}s left" if m else f"~{s}s left"
                    else:
                        time_left = "calculating..."
                    sub = f"{i}/{total} · {src_path.name} · {time_left}"
                    if prog:
                        prog["ring"].value = pct_val
                        prog["pct"].value = f"{round(pct_val * 100)}%"
                        prog["time"].value = sub
                    state = self._conversion_state.get(section_id)
                    if state:
                        state["sub"] = sub

                    def _file_progress(frac, idx=i, name=src_path.name):
                        """Called from the worker thread — marshal UI update to the event loop.
                        A negative frac means 'indeterminate' (e.g. a single-blocking OCR
                        call): the ring switches to an animated spinner until a normal
                        fraction arrives."""
                        indet = frac < 0
                        gfrac = None if indet else (idx - 1 + frac) / total

                        def _apply(ff=gfrac, ii=idx, nn=name, indet=indet):
                            if prog:
                                if indet:
                                    prog["ring"].value = None
                                    prog["pct"].value = "…"
                                    prog["time"].value = "OCR en curso…"
                                else:
                                    prog["ring"].value = ff
                                    prog["pct"].value = f"{round(ff * 100)}%"
                                    prog["time"].value = f"{ii}/{total} · {nn}"
                            if overlay:
                                try:
                                    overlay.update()
                                except Exception:
                                    pass
                        try:
                            loop.call_soon_threadsafe(_apply)
                        except Exception:
                            pass

                    generated = await self.gui._convert_single(
                        src_path, ftype, target, on_progress=_file_progress)

                    # Live log line(s) per generated file + live cards in the grid
                    if prog:
                        prog["ring"].value = i / total
                        prog["pct"].value = f"{round(i / total * 100)}%"
                        prog["time"].value = f"{i}/{total} · done"
                    self._live_append_converted(section_id, generated)
                    for out in generated:
                        line = f"✓ {out.name}"
                        if prog:
                            prog["log"].controls.append(ft.Text(line, size=10))
                        if state:
                            state["logs"].append(line)
                    state["done"] = i
                    if overlay:
                        try:
                            overlay.update()
                        except Exception:
                            pass
                        # Let Flet flush the update to the client before the next
                        # (possibly long, GIL-bound) conversion, so %/logs render live.
                        try:
                            await asyncio.sleep(0.02)
                        except Exception:
                            pass
            finally:
                self._processing_section = None
                st = self._conversion_state.get(section_id)
                if st:
                    st["active"] = False
                if overlay:
                    overlay.visible = False
                    try:
                        overlay.update()
                    except Exception:
                        pass
                # Single rebuild reaggregates multi-page stacks and refreshes lists
                self.gui._build_current_view()
    def _live_append_converted(self, section_id: str, generated: list):
        """Append freshly-generated files as cards to the live grid, no view rebuild."""
        cmeta = self._converted_grids.get(section_id)
        if not cmeta:
            return
        grid = cmeta["grid"]
        if not generated:
            return
        g3p = [p for p in generated if p.suffix.lower() == ".g3p"]
        txt = [p for p in generated if p.suffix.lower() == ".txt"]
        try:
            if section_id == "both" and g3p and txt:
                grid.controls.append(self._build_converted_pair_card(g3p[0], txt[0]))
            else:
                for p in g3p:
                    grid.controls.append(self._build_converted_card(p, "G3P", "images"))
                for p in txt:
                    grid.controls.append(self._build_converted_card(p, "TXT", "text"))
            grid.update()
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
        
        multi_sel = any(p in g._multi_selected for p in all_paths)
        
        page_label = f"{count} pages" if count > 1 else "1 page"
        inner = ft.Container(
            ft.Column([
                ft.Row([
                    ft.Icon(icon, size=20, color=color),
                    ft.Text(f"{ftype}", size=9, weight=ft.FontWeight.BOLD, color=color),
                    ft.Container(expand=True),
                    ft.Text(f"{page_label} · {_fmt_size(sz)}", size=9, color=ft.Colors.ON_SURFACE),
                ]),
                ft.Container(height=2),
                ft.Row([
                    ft.Icon(ft.Icons.FOLDER_OPEN, size=14, color=ft.Colors.ON_SURFACE),
                    ft.Column([
                        ft.Text(f"{stem}", size=12, weight=ft.FontWeight.BOLD, expand=True),
                        ft.Text(f"{count} file(s) · original document",
                                size=9, color=ft.Colors.ON_SURFACE),
                    ], spacing=1, tight=True, expand=True),
                ]),
                ft.Container(height=2),
                ft.Row([
                    ft.Text(f"Drag to Push / Trash ({count})", size=10, color=ft.Colors.OUTLINE),
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
            width=self._CONV_WID, height=self._CONV_HGT,
            border_radius=12,
            animate=ft.Animation(160, ft.AnimationCurve.EASE_OUT),
            animate_scale=ft.Animation(160, ft.AnimationCurve.EASE_OUT),
            on_hover=self._on_card_hover,
        )
        if multi_sel:
            clk = ft.Container(
                content=clk,
                border=ft.Border.all(2, ft.Colors.PRIMARY),
                width=self._CONV_WID, height=self._CONV_HGT,
                border_radius=12,
                animate=ft.Animation(160, ft.AnimationCurve.EASE_OUT),
                animate_scale=ft.Animation(160, ft.AnimationCurve.EASE_OUT),
                on_hover=self._on_card_hover,
            )
        drag_all = self._get_multi_selected_drag_paths(all_paths)
        drag_count = len(drag_all)
        for _p in all_paths:
            self._card_refs[_p] = clk
        return ft.Draggable(
            group="all_items",
            content=clk,
            content_when_dragging=ft.Container(opacity=0.3, content=clk),
            content_feedback=self._make_drag_feedback(drag_count, f"{stem} ({count})", {"files": drag_count} if drag_count > 1 else None, card=clk),
            data={"path": first_g3p, "all_paths": drag_all, "section": section_id, "item_type": "converted"},
            on_drag_start=self._on_selection_drag_start,
            on_drag_complete=self._on_selection_drag_complete,
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
                        ft.Text(f"Status: {'Trusted' if k['trusted'] else 'Untrusted'}", size=10),
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
        check_updates = ft.Switch(label="Check for new app version on launch",
                                  value=config_data.get("check_updates", True))
        confirm_install = ft.Switch(label="Confirm before installing",
                                    value=config_data.get("confirm_install", True))
        confirm_remove = ft.Switch(label="Confirm before removing",
                                   value=config_data.get("confirm_remove", True))
        confirm_push = ft.Switch(label="Confirm before pushing",
                                 value=config_data.get("confirm_push", True))
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
            __import__("pcalc.config", fromlist=["set"]).set("check_updates", check_updates.value)
            __import__("pcalc.config", fromlist=["set"]).set("confirm_install", confirm_install.value)
            __import__("pcalc.config", fromlist=["set"]).set("confirm_remove", confirm_remove.value)
            __import__("pcalc.config", fromlist=["set"]).set("confirm_push", confirm_push.value)
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
        g._set_content(
            ft.Column([
                ft.Text("Settings", size=20, weight=ft.FontWeight.BOLD),
                ft.Container(height=8),
                ft.Text(f"PanCalc Tools v{pupdater.current_version()}", size=11, color=ft.Colors.OUTLINE),
                ft.TextButton("github.com/pan-devs/pancalc-tools", url="https://github.com/pan-devs/pancalc-tools"),
                ft.Container(height=8),
                ft.Text("Appearance", size=16, weight=ft.FontWeight.BOLD),
                dark_mode, ft.Divider(),
                ft.Text("Registry", size=16, weight=ft.FontWeight.BOLD),
                registry_url, ft.Container(height=8), cache_ttl, auto_update, ft.Divider(),
                ft.Text("Behavior", size=16, weight=ft.FontWeight.BOLD),
                confirm_install, confirm_remove, confirm_push,
                ft.Text("Updates", size=16, weight=ft.FontWeight.BOLD),
                check_updates,
                ft.OutlinedButton("Check for Updates", icon=ft.Icons.SYSTEM_UPDATE,
                                  on_click=lambda _: asyncio_create(g._check_updates(manual=True))),
                ft.Divider(),
                ft.Row([
                    ft.FilledButton("Save", icon=ft.Icons.SAVE,
                                    on_click=lambda _: asyncio_create(save())),
                    ft.OutlinedButton("Reset to Defaults", icon=ft.Icons.RESTORE,
                                      on_click=lambda _: asyncio_create(reset_all())),
                ]),
            ], expand=True, scroll=ft.ScrollMode.AUTO)
        )
    # ── Install Drop Target ──────────────────────────────────────────
    def _build_install_target(self) -> ft.Control:
        g = self.gui
        # Like trash (vertical column) + like convert (idle border/bgcolor)
        content = ft.Container(
            ft.Column([
                ft.Icon(ft.Icons.DOWNLOAD, size=28, color=ft.Colors.PRIMARY),
                ft.Container(height=4),
                ft.Text("Drop here to install", size=14, color=ft.Colors.PRIMARY,
                        weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER),
                ft.Text("selected addins / games → calculator", size=11,
                        color=ft.Colors.OUTLINE, text_align=ft.TextAlign.CENTER),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER,
               alignment=ft.MainAxisAlignment.CENTER, tight=True, spacing=2),
            padding=12,
            border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=10,
            bgcolor=ft.Colors.SURFACE_CONTAINER,
            alignment=ft.Alignment.CENTER,
        )
        def _badge(gg):
            n = len(getattr(gg, "_selected_registry_ids", set()))
            return (n or 1, "registry/local selection")
        return DropZone(
            g, content,
            color=GLOW_COLOR, dest="calculator",
            badge_fn=_badge, on_accept=self._on_install_accept, border_radius=12,
            expand=True,
        ).build()
    def _on_install_accept(self, e):
        """Handle drop on install target — multi-selection or single item."""
        data = e.src.data if e.src else {}
        dragged_id = data.get("item_id", "")
        g = self.gui
        if dragged_id and dragged_id in g._selected_registry_ids:
            asyncio_create(g._install_selected())
        elif dragged_id:
            asyncio_create(g._install_selected(item_ids=[dragged_id]))
        else:
            g._show_snackbar("Nothing to install", type="warning")
    def _build_push_target(self) -> ft.Control:
        """Drop zone for pushing converted files (g3p/txt) to the calculator."""
        g = self.gui
        content = ft.Container(
            ft.Column([
                ft.Icon(ft.Icons.UPLOAD_FILE, size=28, color=ft.Colors.PRIMARY),
                ft.Container(height=4),
                ft.Text("Drop here to Push to calculator", size=14, color=ft.Colors.PRIMARY,
                        weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER),
                ft.Text("converted g3p / txt → calculator pthings", size=11,
                        color=ft.Colors.OUTLINE, text_align=ft.TextAlign.CENTER),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER,
               alignment=ft.MainAxisAlignment.CENTER, tight=True, spacing=2),
            padding=12,
            border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=10,
            bgcolor=ft.Colors.SURFACE_CONTAINER,
            alignment=ft.Alignment.CENTER,
        )
        def _badge(gg):
            n = len(getattr(gg, "_multi_selected", set()))
            return (n or 1, "converted → calculator")
        return DropZone(
            g, content,
            color=GLOW_COLOR, dest="calculator (push)",
            badge_fn=_badge, on_accept=self._on_push_accept, border_radius=12,
            expand=True,
        ).build()
    def _on_push_accept(self, e):
        """Push converted files dropped on the zone. Only g3p/txt converted paths."""
        data = e.src.data if e.src else {}
        paths = data.get("all_paths") or []
        if not paths and data.get("path"):
            paths = [data["path"]]
        item_type = data.get("item_type")
        allowed_exts = {".g3p", ".txt"}
        converted = [
            p for p in paths
            if item_type == "converted"
            and Path(p).suffix.lower() in allowed_exts
            and Path(p).exists()
        ]
        if not converted:
            self.gui._show_snackbar("Nothing to push (drop a converted g3p/txt here)", type="warning")
            return
        asyncio_create(self.gui._push_files(converted))
# ── Helper to create tasks from lambda callbacks ────────────────────
def asyncio_create(coro):
    import asyncio
    return asyncio.create_task(coro)


class DropZone:
    """Reusable drop target with 3-stage progressive feedback + copy-shift badge.

    Stages (idle → hover → armed):
      * idle   — resting state (thin outline, no glow, badge hidden)
      * hover  — a drag is over the zone: colored border + soft glow
      * armed  — after ~ARM_DELAY s over the zone: intense glow + copy-shift
                 badge showing what will be dropped inside.

    The drop logic is injected via `on_accept`; this class only manages the
    pre-drop visual feedback. It wraps `content` in a Stack so an overlay and
    a floating badge can be layered on top without disturbing the content.
    """

    IDLE, HOVER, ARMED = 0, 1, 2
    ARM_DELAY = 0.24  # seconds held over the zone before arming

    def __init__(
        self,
        gui,
        content: ft.Control,
        *,
        color: str,
        dest: str,
        badge_fn=None,
        on_accept=None,
        group: str = "all_items",
        border_radius: int = 10,
        expand: bool = False,
    ):
        self._gui = gui
        self._content = content
        self._color = color
        self._dest = dest
        self._badge_fn = badge_fn or (lambda g: (1, ""))
        self._accept_cb = on_accept
        self._group = group
        self._border_radius = border_radius
        self._expand = expand
        self._state = self.IDLE
        self._timer = None

        # Derived visuals held here so callbacks and rebuilds stay in sync.
        self._overlay: ft.Container | None = None
        self._badge: ft.Container | None = None
        self._target: ft.DragTarget | None = None

    # ── badge helpers ────────────────────────────────────────────────
    def _resolve_badge(self) -> tuple[int, str]:
        try:
            count, label = self._badge_fn(self._gui)
            return max(1, count or 1), label or ""
        except Exception:
            return 1, ""

    def _badge_text(self) -> str:
        count, _ = self._resolve_badge()
        noun = "item" if count == 1 else "items"
        return f"Copy {count} {noun} to {self._dest}"

    # ── state application ────────────────────────────────────────────
    def _set_state(self, state: int):
        if state == self._state:
            return
        self._state = state
        if self._gui.page is None or self._overlay is None:
            return
        self._apply_state()
        try:
            self._overlay.update()
            if self._badge is not None:
                self._badge.update()
            self._target.update()
        except Exception:
            pass

    def _apply_state(self):
        base = self._color
        # identical reactivity to trash — only base colour differs (light blue for install)
        if self._state == self.ARMED:
            self._overlay.bgcolor = self._with_alpha(base, 0.10)
            self._overlay.border = ft.Border.all(3, base)
            self._overlay.shadow = ft.BoxShadow(
                blur_radius=28, spread_radius=4,
                color=self._with_alpha(base, 0.85),
                offset=ft.Offset(0, 0),
            )
            self._overlay.scale = 1.012
        elif self._state == self.HOVER:
            self._overlay.bgcolor = self._with_alpha(base, 0.14)
            self._overlay.border = ft.Border.all(2, self._with_alpha(base, 0.70))
            self._overlay.shadow = ft.BoxShadow(
                blur_radius=14, spread_radius=1,
                color=self._with_alpha(base, 0.35),
                offset=ft.Offset(0, 0),
            )
            self._overlay.scale = 1.008
        else:  # IDLE
            self._overlay.bgcolor = None
            self._overlay.border = None
            self._overlay.shadow = None
            self._overlay.scale = 1.0
        # badge visibility
        if self._badge is not None and self._badge.content is not None:
            self._badge.visible = self._state == self.ARMED
            self._badge.opacity = 1.0 if self._state == self.ARMED else 0.6

    @staticmethod
    def _hex_alpha(factor: float) -> str:
        a = round(factor * 255)
        return f"{a:02X}"

    @staticmethod
    def _with_alpha(color, factor: float):
        """Apply alpha to a color for Flet/Flutter, which parses hex as #AARRGGBB."""
        if isinstance(color, str) and color.startswith("#") and len(color) == 7:
            a = DropZone._hex_alpha(factor)
            return f"#{a}{color[1:]}"
        value = getattr(color, "value", None)
        if value is not None:
            try:
                return ft.Colors.with_opacity(factor, value)
            except Exception:
                pass
        return color

    # ── DragTarget callbacks ─────────────────────────────────────────
    def _on_will_accept(self, e):
        if e.data in (True, "true"):
            self._set_state(self.HOVER)
            self._arm_progress()
        else:
            self._set_state(self.HOVER)
        self._gui.page.update()

    def _on_move(self, e):
        # hold hover while moving; the arm timer keeps running so the zone
        # settles into ARM once the user lingers.
        if self._state == self.IDLE:
            self._set_state(self.HOVER)

    def _on_leave(self, e):
        self._cancel_timer()
        self._set_state(self.IDLE)
        try:
            self._gui.page.update()
        except Exception:
            pass

    def _arm_progress(self):
        self._cancel_timer()
        self._timer = asyncio.create_task(self._arm_after())

    async def _arm_after(self):
        try:
            await asyncio.sleep(self.ARM_DELAY)
            self._set_state(self.ARMED)
            self._refresh_badge_text()
            self._gui.page.update()
        except asyncio.CancelledError:
            pass

    def _refresh_badge_text(self):
        if self._badge is None:
            return
        try:
            text = self._badge.content.controls[1]
            text.value = self._badge_text()
        except Exception:
            pass

    def _cancel_timer(self):
        if self._timer is not None and not self._timer.done():
            self._timer.cancel()
        self._timer = None

    # ── builder ──────────────────────────────────────────────────────
    def build(self) -> ft.DragTarget:
        radius = self._border_radius
        # overlay (fills the zone) — decorative only, must not swallow the drop
        self._overlay = ft.Container(
            left=0, top=0, right=0, bottom=0,
            border_radius=radius,
            animate=ft.Animation(170, ft.AnimationCurve.EASE_OUT),
            animate_scale=ft.Animation(170, ft.AnimationCurve.EASE_OUT),
            ignore_interactions=True,
        )
        # badge (copy-shift) — centered pill floating near the top edge
        icon = ft.Icon(ft.Icons.CONTENT_COPY, size=14, color=ft.Colors.ON_PRIMARY)
        label = ft.Text(self._badge_text(), size=11, color=ft.Colors.ON_PRIMARY, weight=ft.FontWeight.BOLD)
        self._badge = ft.Container(
            ft.Row([icon, label], spacing=6, tight=True),
            padding=ft.Padding.symmetric(horizontal=12, vertical=6),
            bgcolor=self._color,
            border_radius=20,
            shadow=ft.BoxShadow(blur_radius=12, spread_radius=1, color=self._with_alpha(self._color, 0.5), offset=ft.Offset(0, 2)),
            visible=False,
            opacity=0.0,
            animate=ft.Animation(150, ft.AnimationCurve.EASE_OUT),
            animate_opacity=ft.Animation(150, ft.AnimationCurve.EASE_OUT),
        )
        badge_wrapper = ft.Container(
            ft.Row([self._badge], alignment=ft.MainAxisAlignment.CENTER),
            left=0, right=0, top=0,
            padding=ft.Padding.only(top=8),
            ignore_interactions=True,
        )
        # expand=True → full-width bar (install) covering the zone length,
        # with the same tight glow/reactivity as trash (overlay matches Stack).
        content_layer = self._content
        if self._expand:
            # Let the content fill the full-width Stack; inner Container keeps
            # its own alignment (centered Column like trash).
            content_layer = ft.Container(content_layer, expand=True)
        stack = ft.Stack(
            [content_layer, self._overlay, badge_wrapper],
            expand=self._expand,
            clip_behavior=ft.ClipBehavior.NONE,
        )
        self._target = ft.DragTarget(
            group=self._group,
            content=stack,
            on_will_accept=self._on_will_accept,
            on_accept=self._on_accept,
            on_leave=self._on_leave,
            on_move=self._on_move,
        )
        return self._target

    # ── accept callback wrapper ──────────────────────────────────────
    def _on_accept(self, e):
        # Always reset to idle first so a drop can never leave the zone stuck
        # lit up, then run the injected business logic (may no-op for items
        # that cannot actually be dropped here).
        self._cancel_timer()
        self._set_state(self.IDLE)
        if self._accept_cb is not None:
            self._accept_cb(e)