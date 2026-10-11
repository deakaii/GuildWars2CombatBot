"""
Interactive Action Bar & Multi-Slot Equidistant Grid Calibrator.
Allows you to click and drag a rectangle over any skill bar (e.g. 5 weapon skills,
3 mechanic/virtue skills, or 5 utility skills).
Automatically divides the selected rectangle into N equidistant boxes, displays
live visual previews with labels ([1], [2], [3], [4], [5]), and saves pixel-perfect
normalized coordinates to config/settings.yaml and config/professions_database.yaml.
"""

import os
import sys
import yaml
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk, ImageGrab
from typing import List, Tuple, Dict, Any, Optional

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.dpi_utils import enable_dpi_awareness, get_screen_resolution, absolute_to_normalized, absolute_to_bottom_center


class BarGridCalibrator:
    """
    Interactive full-screen overlay tool to calibrate skill bar slots with equidistant subdivision.
    """

    PRESETS = {
        "weapon_swap": {
            "name": "Weapon Swap Icon (~ / `) (1 slot)",
            "count": 1,
            "keys": ["weapon_swap"],
            "labels": ["Weapon Swap (~)"],
            "badges": ["Swap (~)"],
            "is_mechanic": False
        },
        "weapon": {
            "name": "Weapon Skills 1 - 5 (5 slots)",
            "count": 5,
            "keys": ["weapon_1", "weapon_2", "weapon_3", "weapon_4", "weapon_5"],
            "labels": ["Skill 1", "Skill 2", "Skill 3", "Skill 4", "Skill 5"],
            "badges": ["1", "2", "3", "4", "5"],
            "is_mechanic": False
        },
        "mechanic_5": {
            "name": "Mechanic Bar F1 - F5 (5 slots: Chrono, Virtuoso, Scourge)",
            "count": 5,
            "keys": ["mech_f1", "mech_f2", "mech_f3", "mech_f4", "mech_f5"],
            "labels": ["Mech F1", "Mech F2", "Mech F3", "Mech F4", "Mech F5"],
            "badges": ["F1", "F2", "F3", "F4", "F5"],
            "is_mechanic": True
        },
        "mechanic_4": {
            "name": "Mechanic Bar F1 - F4 (4 slots: Ele Attunements, Core Mesmer)",
            "count": 4,
            "keys": ["mech_f1", "mech_f2", "mech_f3", "mech_f4"],
            "labels": ["Mech F1", "Mech F2", "Mech F3", "Mech F4"],
            "badges": ["F1", "F2", "F3", "F4"],
            "is_mechanic": True
        },
        "mechanic_virtues": {
            "name": "Guardian Virtues F1 - F3 / M5, M4 (3 slots)",
            "count": 3,
            "keys": ["mech_f1", "mech_f2", "mech_f3"],
            "labels": ["Virtue 1 (M5 / F1)", "Virtue 2 (M4 / F2)", "Virtue 3 (Shift+M5 / F3)"],
            "badges": ["V1 (M5)", "V2 (M4)", "V3 (Shift+M5)"],
            "is_mechanic": True
        },
        "mechanic_mech": {
            "name": "Jade Mech Commands F1 - F3 (3 slots)",
            "count": 3,
            "keys": ["mech_f1", "mech_f2", "mech_f3"],
            "labels": ["Mech F1 (M5)", "Mech F2 (M4)", "Mech F3 (Shift+M5)"],
            "badges": ["M1 (M5)", "M2 (M4)", "M3 (Shift+M5)"],
            "is_mechanic": True
        },
        "pips_3": {
            "name": "Resource Pips (3 pips: Chronomancer Clones, Warrior Adrenaline)",
            "count": 3,
            "keys": ["pip_1", "pip_2", "pip_3"],
            "labels": ["Pip 1", "Pip 2", "Pip 3"],
            "badges": ["Pip 1", "Pip 2", "Pip 3"],
            "is_mechanic": False,
            "is_resource": True,
            "resource_type": "discrete_pips",
            "max_pips": 3
        },
        "pips_5": {
            "name": "Resource Pips (5 pips: Virtuoso Blades, Deadeye Malice)",
            "count": 5,
            "keys": ["pip_1", "pip_2", "pip_3", "pip_4", "pip_5"],
            "labels": ["Pip 1", "Pip 2", "Pip 3", "Pip 4", "Pip 5"],
            "badges": ["Pip 1", "Pip 2", "Pip 3", "Pip 4", "Pip 5"],
            "is_mechanic": False,
            "is_resource": True,
            "resource_type": "discrete_pips",
            "max_pips": 5
        },
        "gauge_bar": {
            "name": "Resource Gauge (Fill Bar: Necro Life Force, Revenant Energy)",
            "count": 1,
            "keys": ["resource_gauge"],
            "labels": ["Resource Gauge"],
            "badges": ["Gauge"],
            "is_mechanic": False,
            "is_resource": True,
            "resource_type": "continuous_gauge"
        },
        "utility": {
            "name": "Utility Bar Q - Elite M3 (5 slots)",
            "count": 5,
            "keys": ["heal", "utility_1", "utility_2", "utility_3", "elite"],
            "labels": ["Heal (Q)", "Utility 1 (E)", "Utility 2 (R)", "Utility 3 (T)", "Elite (M3)"],
            "badges": ["Heal(Q)", "U1(E)", "U2(R)", "U3(T)", "Elite(M3)"],
            "is_mechanic": False
        },
        "custom": {
            "name": "Custom Count & Labels...",
            "count": 5,
            "keys": [],
            "labels": [],
            "badges": [],
            "is_mechanic": False
        }
    }

    def __init__(self, config_path: str = "config/settings.yaml", profession: Optional[str] = None, spec: Optional[str] = None):
        enable_dpi_awareness()
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.config_path = os.path.join(self.base_dir, config_path)
        self.db_path = os.path.join(self.base_dir, "config", "professions_database.yaml")
        
        self.screen_w, self.screen_h = get_screen_resolution()
        self.resolution_tag = f"{self.screen_w}x{self.screen_h}"
        print(f"[BarCalibrator] Primary display resolution: {self.screen_w}x{self.screen_h} (Tag: {self.resolution_tag})")

        # Resolve profession and spec
        settings_temp = {}
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r") as f:
                    settings_temp = yaml.safe_load(f) or {}
            except Exception:
                pass
        
        last_sel = settings_temp.get("last_selected", {})
        self.profession = (profession or last_sel.get("profession") or "Engineer").strip()
        self.spec = (spec or last_sel.get("elite_spec") or "Mechanist").strip()

        # Load active spec configuration (resolution-aware)
        from core.spec_manager import load_spec_config
        self.spec_config = load_spec_config(self.profession, self.spec, resolution_tag=self.resolution_tag)

        # Dynamically inject spec-specific preset if available
        if self.spec_config:
            m_bar = self.spec_config.get("mechanic_bar", {})
            f_count = m_bar.get("f_slots_count", 0)
            if f_count > 0:
                keys = [f"mech_f{i+1}" for i in range(f_count)]
                labels_dict = m_bar.get("labels", {})
                labels = [labels_dict.get(k, f"F{i+1}") for i, k in enumerate(keys)]
                badges = [labels_dict.get(k, f"F{i+1}")[:8] for i, k in enumerate(keys)]
                spec_preset_key = f"active_{self.profession.lower()}_{self.spec.lower()}"
                self.PRESETS = {
                    spec_preset_key: {
                        "name": f"★ Active Spec: {self.profession.title()} {self.spec.title()} ({f_count} slots)",
                        "count": f_count,
                        "keys": keys,
                        "labels": labels,
                        "badges": badges,
                        "is_mechanic": True
                    },
                    **self.PRESETS
                }
                self.selected_preset_key = spec_preset_key
                self.slot_count = f_count
            elif self.spec.lower() == "mechanist":
                self.selected_preset_key = "mechanic_mech"
                self.slot_count = 3

        # Capture frozen desktop snapshot
        try:
            self.screenshot = ImageGrab.grab(bbox=(0, 0, self.screen_w, self.screen_h))
        except Exception:
            import mss
            with mss.MSS() as sct:
                raw = sct.grab({'left': 0, 'top': 0, 'width': self.screen_w, 'height': self.screen_h})
                self.screenshot = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")

        # Selection state
        self.start_x = None
        self.start_y = None
        self.cur_x = None
        self.cur_y = None
        self.is_dragging = False

        # Current selection bounding box: (x, y, w, h)
        self.current_bbox: Optional[Tuple[int, int, int, int]] = None
        self.current_slots: List[Dict[str, Any]] = []

        # Persistent history of calibrated bars in this session
        self.saved_bars: List[List[Dict[str, Any]]] = []

        # Canvas item IDs for active drawing
        self.drag_rect_id = None
        self.slot_rect_ids: List[int] = []
        self.slot_text_ids: List[int] = []
        self.slot_badge_ids: List[int] = []
        self.persistent_ids: List[int] = []

        # Settings
        if not hasattr(self, "selected_preset_key"):
            self.selected_preset_key = "weapon"
            self.slot_count = 5
        self.inner_padding_pct = 5.0  # 5% inner padding to avoid border glow/vfx

        # Build full-screen overlay UI
        self.root = tk.Tk()
        self.root.title("Action Bar Equidistant Grid Calibrator")
        self.root.attributes("-fullscreen", True)
        self.root.attributes("-topmost", True)
        self.root.config(cursor="cross")

        self.canvas = tk.Canvas(self.root, cursor="cross", width=self.screen_w, height=self.screen_h, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        self.tk_image = ImageTk.PhotoImage(self.screenshot)
        self.canvas.create_image(0, 0, anchor="nw", image=self.tk_image)

        # Instructions Header Banner
        self._draw_header()

        # Floating Control Card (appears once a box is dragged)
        self.panel_frame: Optional[tk.Frame] = None

        # Bindings
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_motion)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.root.bind("<Escape>", lambda e: self.root.destroy())
        self.root.bind("<Return>", lambda e: self.save_current_bar())
        self.root.bind("<w>", lambda e: self._quick_set_preset("weapon"))
        self.root.bind("<W>", lambda e: self._quick_set_preset("weapon"))
        self.root.bind("<m>", lambda e: self._quick_set_preset("mechanic_virtues"))
        self.root.bind("<M>", lambda e: self._quick_set_preset("mechanic_virtues"))
        self.root.bind("<u>", lambda e: self._quick_set_preset("utility"))
        self.root.bind("<U>", lambda e: self._quick_set_preset("utility"))

    def _draw_header(self):
        banner_h = 58
        self.canvas.create_rectangle(0, 0, self.screen_w, banner_h, fill="#181825", outline="#313244", width=2)
        title_text = f"📐 ACTION BAR GRID CALIBRATOR • {self.profession.title()} - {self.spec.title()} [{self.resolution_tag}]"
        info_text = "Drag a rectangle over ANY skill bar or resource • Select preset in floating card • Saved directly to monitor profile!"
        self.canvas.create_text(
            self.screen_w // 2, 20,
            text=title_text,
            fill="#a6e3a1",
            font=("Segoe UI", 12, "bold")
        )
        self.canvas.create_text(
            self.screen_w // 2, 42,
            text=info_text,
            fill="#cdd6f4",
            font=("Segoe UI", 9)
        )

    def on_press(self, event):
        # Ignore clicks inside control panel if open
        if self.panel_frame and self.panel_frame.winfo_containing(event.x_root, event.y_root):
            return

        self.start_x = event.x
        self.start_y = event.y
        self.is_dragging = True
        self._clear_active_preview()
        if self.panel_frame:
            self.panel_frame.destroy()
            self.panel_frame = None

    def on_motion(self, event):
        if not self.is_dragging:
            return
        self.cur_x = event.x
        self.cur_y = event.y

        if self.drag_rect_id:
            self.canvas.delete(self.drag_rect_id)

        # Draw outer bounding box during drag
        self.drag_rect_id = self.canvas.create_rectangle(
            self.start_x, self.start_y, self.cur_x, self.cur_y,
            outline="#89b4fa", width=2, dash=(6, 4)
        )

    def on_release(self, event):
        if not self.is_dragging:
            return
        self.is_dragging = False
        self.cur_x = event.x
        self.cur_y = event.y

        x = min(self.start_x, self.cur_x)
        y = min(self.start_y, self.cur_y)
        w = abs(self.cur_x - self.start_x)
        h = abs(self.cur_y - self.start_y)

        if w < 20 or h < 15:
            # Clicked without dragging or box too tiny
            if self.drag_rect_id:
                self.canvas.delete(self.drag_rect_id)
                self.drag_rect_id = None
            return

        self.current_bbox = (x, y, w, h)
        self._compute_and_render_slots()
        self._show_control_panel(x, y, w, h)

    def _quick_set_preset(self, preset_key: str):
        if preset_key in self.PRESETS:
            self.selected_preset_key = preset_key
            self.slot_count = self.PRESETS[preset_key]["count"]
            if self.current_bbox:
                self._compute_and_render_slots()
                if self.panel_frame:
                    self._show_control_panel(*self.current_bbox)

    def _compute_and_render_slots(self):
        if not self.current_bbox:
            return

        self._clear_active_preview()
        x, y, w, h = self.current_bbox
        n = max(1, self.slot_count)

        preset = self.PRESETS.get(self.selected_preset_key, self.PRESETS["weapon"])
        keys = preset.get("keys", [])
        badges = preset.get("badges", [])
        labels = preset.get("labels", [])

        # Outer highlight rectangle
        self.drag_rect_id = self.canvas.create_rectangle(
            x, y, x + w, y + h,
            outline="#89b4fa", width=3
        )

        col_w = w / n
        pad_ratio = max(0.0, min(0.20, self.inner_padding_pct / 100.0))

        self.current_slots = []

        for i in range(n):
            col_x = x + i * col_w
            pad_x = col_w * pad_ratio
            pad_y = h * pad_ratio

            slot_x = int(col_x + pad_x)
            slot_y = int(y + pad_y)
            slot_w = max(4, int(col_w - 2 * pad_x))
            slot_h = max(4, int(h - 2 * pad_y))

            # Default key and badge fallback
            if i < len(keys):
                slot_key = keys[i]
            else:
                slot_key = f"slot_{i + 1}"

            if i < len(badges):
                badge_text = badges[i]
            else:
                badge_text = f"{i + 1}"

            if i < len(labels):
                label_text = labels[i]
            else:
                label_text = f"Skill {i + 1}"

            self.current_slots.append({
                "key": slot_key,
                "label": label_text,
                "badge": badge_text,
                "abs_bbox": (slot_x, slot_y, slot_w, slot_h)
            })

            # Draw green equidistant box
            rect_id = self.canvas.create_rectangle(
                slot_x, slot_y, slot_x + slot_w, slot_y + slot_h,
                outline="#a6e3a1", width=2, fill="#a6e3a1", stipple="gray25"
            )
            self.slot_rect_ids.append(rect_id)

            # Badge pill at top of each box
            badge_bg = self.canvas.create_rectangle(
                slot_x + 2, slot_y - 22, slot_x + slot_w - 2, slot_y - 3,
                fill="#181825", outline="#a6e3a1", width=1
            )
            self.slot_badge_ids.append(badge_bg)

            text_id = self.canvas.create_text(
                slot_x + slot_w // 2, slot_y - 12,
                text=f"[{badge_text}]",
                fill="#a6e3a1",
                font=("Consolas", 10, "bold")
            )
            self.slot_text_ids.append(text_id)

            # Dimensions below
            dim_id = self.canvas.create_text(
                slot_x + slot_w // 2, slot_y + slot_h + 10,
                text=f"{slot_w}x{slot_h}",
                fill="#f9e2af",
                font=("Consolas", 8)
            )
            self.slot_text_ids.append(dim_id)

    def _clear_active_preview(self):
        if self.drag_rect_id:
            self.canvas.delete(self.drag_rect_id)
            self.drag_rect_id = None
        for r_id in self.slot_rect_ids:
            self.canvas.delete(r_id)
        self.slot_rect_ids.clear()
        for b_id in self.slot_badge_ids:
            self.canvas.delete(b_id)
        self.slot_badge_ids.clear()
        for t_id in self.slot_text_ids:
            self.canvas.delete(t_id)
        self.slot_text_ids.clear()

    def _show_control_panel(self, x: int, y: int, w: int, h: int):
        if self.panel_frame:
            self.panel_frame.destroy()

        # Position panel comfortably near the selection without going off screen
        panel_w = 440
        panel_h = 240
        panel_x = max(20, min(self.screen_w - panel_w - 20, x + w // 2 - panel_w // 2))
        panel_y = y - panel_h - 30
        if panel_y < 70:
            panel_y = y + h + 25
        if panel_y + panel_h > self.screen_h - 20:
            panel_y = max(70, self.screen_h - panel_h - 30)

        self.panel_frame = tk.Frame(
            self.root,
            bg="#1e1e2e",
            highlightbackground="#89b4fa",
            highlightthickness=2,
            padx=14,
            pady=10
        )
        self.panel_frame.place(x=panel_x, y=panel_y, width=panel_w, height=panel_h)

        # Header
        lbl_title = tk.Label(
            self.panel_frame,
            text=f"DIVIDE BAR INTO {self.slot_count} EQUIDISTANT SLOTS",
            font=("Segoe UI", 10, "bold"),
            fg="#a6e3a1",
            bg="#1e1e2e"
        )
        lbl_title.pack(anchor="w", pady=(0, 6))

        # Preset Dropdown
        row_preset = tk.Frame(self.panel_frame, bg="#1e1e2e")
        row_preset.pack(fill="x", pady=3)
        tk.Label(row_preset, text="Bar Preset:", font=("Segoe UI", 9), fg="#cdd6f4", bg="#1e1e2e", width=12, anchor="w").pack(side="left")

        preset_names = [p["name"] for p in self.PRESETS.values()]
        cb_preset = ttk.Combobox(row_preset, values=preset_names, state="readonly", font=("Segoe UI", 9))
        current_name = self.PRESETS.get(self.selected_preset_key, {}).get("name", preset_names[0])
        cb_preset.set(current_name)
        cb_preset.pack(side="left", fill="x", expand=True)

        # Count & Margin Spinboxes
        row_inputs = tk.Frame(self.panel_frame, bg="#1e1e2e")
        row_inputs.pack(fill="x", pady=4)

        tk.Label(row_inputs, text="Slots (N):", font=("Segoe UI", 9), fg="#cdd6f4", bg="#1e1e2e").pack(side="left")
        spin_count = tk.Spinbox(row_inputs, from_=1, to=10, width=4, font=("Segoe UI", 9, "bold"), bg="#313244", fg="#cdd6f4", bd=0)
        spin_count.delete(0, "end")
        spin_count.insert(0, str(self.slot_count))
        spin_count.pack(side="left", padx=(4, 16))

        tk.Label(row_inputs, text="Inner Margin %:", font=("Segoe UI", 9), fg="#cdd6f4", bg="#1e1e2e").pack(side="left")
        spin_pad = tk.Spinbox(row_inputs, from_=0, to=20, width=4, font=("Segoe UI", 9), bg="#313244", fg="#cdd6f4", bd=0)
        spin_pad.delete(0, "end")
        spin_pad.insert(0, str(int(self.inner_padding_pct)))
        spin_pad.pack(side="left", padx=4)

        # Reactive update callbacks
        def on_preset_change(event=None):
            sel_text = cb_preset.get()
            for k, p in self.PRESETS.items():
                if p["name"] == sel_text:
                    self.selected_preset_key = k
                    self.slot_count = p["count"]
                    spin_count.delete(0, "end")
                    spin_count.insert(0, str(self.slot_count))
                    break
            self._compute_and_render_slots()
            lbl_title.config(text=f"DIVIDE BAR INTO {self.slot_count} EQUIDISTANT SLOTS")

        def on_count_change():
            try:
                val = int(spin_count.get())
                self.slot_count = max(1, min(12, val))
                self._compute_and_render_slots()
                lbl_title.config(text=f"DIVIDE BAR INTO {self.slot_count} EQUIDISTANT SLOTS")
            except Exception:
                pass

        def on_pad_change():
            try:
                val = float(spin_pad.get())
                self.inner_padding_pct = max(0.0, min(25.0, val))
                self._compute_and_render_slots()
            except Exception:
                pass

        cb_preset.bind("<<ComboboxSelected>>", on_preset_change)
        spin_count.config(command=on_count_change)
        spin_count.bind("<KeyRelease>", lambda e: on_count_change())
        spin_pad.config(command=on_pad_change)
        spin_pad.bind("<KeyRelease>", lambda e: on_pad_change())

        # Coordinates info label
        lbl_info = tk.Label(
            self.panel_frame,
            text=f"Bar Box: {w}x{h} px at ({x}, {y}) | Slot width: ~{w // self.slot_count} px",
            font=("Segoe UI", 8),
            fg="#9399b2",
            bg="#1e1e2e"
        )
        lbl_info.pack(anchor="w", pady=4)

        # Buttons
        btn_row = tk.Frame(self.panel_frame, bg="#1e1e2e")
        btn_row.pack(fill="x", side="bottom", pady=(8, 0))

        btn_save = tk.Button(
            btn_row,
            text="✔  Save & Apply This Bar",
            font=("Segoe UI", 9, "bold"),
            bg="#a6e3a1",
            fg="#11111b",
            activebackground="#94e2d5",
            bd=0,
            padx=12,
            pady=6,
            cursor="hand2",
            command=self.save_current_bar
        )
        btn_save.pack(side="left", padx=(0, 6))

        btn_clear = tk.Button(
            btn_row,
            text="⟲ Redraw",
            font=("Segoe UI", 9),
            bg="#45475a",
            fg="#cdd6f4",
            activebackground="#585b70",
            bd=0,
            padx=10,
            pady=6,
            cursor="hand2",
            command=self._clear_active_preview
        )
        btn_clear.pack(side="left", padx=4)

        btn_done = tk.Button(
            btn_row,
            text="✕ Done / Exit",
            font=("Segoe UI", 9),
            bg="#313244",
            fg="#f38ba8",
            activebackground="#45475a",
            bd=0,
            padx=10,
            pady=6,
            cursor="hand2",
            command=lambda: self.root.destroy()
        )
        btn_done.pack(side="right")

    def save_current_bar(self):
        if not self.current_slots or not self.current_bbox:
            messagebox.showwarning("Notice", "Please drag a rectangle over your skill bar first.")
            return

        # Load existing settings
        settings = {}
        if os.path.exists(self.config_path):
            with open(self.config_path, "r") as f:
                settings = yaml.safe_load(f) or {}

        region = settings.get("region", {})
        mode = region.get("mode", "bottom_center" if "width_ratio" in region else "normalized")
        if mode == "bottom_center" and "width_ratio" in region:
            cx_ratio = float(region.get("center_offset_ratio_x", 0.0))
            by_ratio = float(region.get("bottom_offset_ratio_y", 0.0))
            w_ratio = float(region.get("width_ratio", 0.76))
            h_ratio = float(region.get("height_ratio", 0.21))
            hud_x, hud_y, hud_w, hud_h = bottom_center_to_absolute(
                cx_ratio, by_ratio, w_ratio, h_ratio, self.screen_w, self.screen_h
            )
        elif mode == "normalized" and "norm_w" in region:
            nx = float(region.get("norm_x", 0.4))
            ny = float(region.get("norm_y", 0.75))
            nw = float(region.get("norm_w", 0.2))
            nh = float(region.get("norm_h", 0.15))
            hud_x, hud_y, hud_w, hud_h = normalized_to_absolute(nx, ny, nw, nh, self.screen_w, self.screen_h)
        else:
            hud_x = int(region.get("abs_x", 0))
            hud_y = int(region.get("abs_y", 0))
            hud_w = int(region.get("abs_w", self.screen_w))
            hud_h = int(region.get("abs_h", self.screen_h))

        # Check if the calibrated bar is outside current HUD region.
        # If so, automatically expand/adjust the HUD region so it encloses all slots!
        bx, by, bw, bh = self.current_bbox
        needs_hud_expand = False
        new_hud_x = hud_x
        new_hud_y = hud_y
        new_hud_r = hud_x + hud_w
        new_hud_b = hud_y + hud_h

        if bx < hud_x or by < hud_y or (bx + bw) > (hud_x + hud_w) or (by + bh) > (hud_y + hud_h):
            needs_hud_expand = True
            new_hud_x = max(0, min(hud_x, bx - 12))
            new_hud_y = max(0, min(hud_y, by - 12))
            new_hud_r = min(self.screen_w, max(hud_x + hud_w, bx + bw + 12))
            new_hud_b = min(self.screen_h, max(hud_y + hud_h, by + bh + 12))
            hud_x = new_hud_x
            hud_y = new_hud_y
            hud_w = new_hud_r - new_hud_x
            hud_h = new_hud_b - new_hud_y

            # Update settings region with normalized and bottom-center anchor parameters
            nx, ny, nw, nh = absolute_to_normalized(hud_x, hud_y, hud_w, hud_h, self.screen_w, self.screen_h)
            bc_params = absolute_to_bottom_center(hud_x, hud_y, hud_w, hud_h, self.screen_w, self.screen_h)
            region.update(bc_params)
            region["abs_x"] = hud_x
            region["abs_y"] = hud_y
            region["abs_w"] = hud_w
            region["abs_h"] = hud_h
            region["norm_x"] = nx
            region["norm_y"] = ny
            region["norm_w"] = nw
            region["norm_h"] = nh
            region["reference_resolution"] = {"width": self.screen_w, "height": self.screen_h}
            settings["region"] = region
            print(f"[BarCalibrator] Auto-expanded HUD Region to enclose bar: {hud_w}x{hud_h} at ({hud_x}, {hud_y}) [Bottom-Center Anchored]")

        if "calibrated_slots" not in settings:
            settings["calibrated_slots"] = {}

        preset_info = self.PRESETS.get(self.selected_preset_key, {})
        is_mech = preset_info.get("is_mechanic", False)
        is_res = preset_info.get("is_resource", False)
        mech_coords: Dict[str, List[float]] = {}

        # Handle resource calibration (e.g. 3 or 5 pips or gauge bar)
        if is_res:
            if "calibrated_resources" not in settings:
                settings["calibrated_resources"] = {}
            res_type = preset_info.get("resource_type", "discrete_pips")
            rel_bx = round((bx - hud_x) / float(hud_w), 4)
            rel_by = round((by - hud_y) / float(hud_h), 4)
            rel_bw = round(bw / float(hud_w), 4)
            rel_bh = round(bh / float(hud_h), 4)
            res_bbox = [rel_bx, rel_by, rel_bw, rel_bh]
            settings["calibrated_resources"][res_type] = res_bbox

            # Persist to spec config file (resolution-specific + generic)
            if hasattr(self, "spec_config") and self.spec_config:
                from core.spec_manager import save_spec_config
                res_dict = self.spec_config.setdefault("resource", {})
                res_dict["type"] = res_type
                res_dict["bbox"] = res_bbox
                if "max_pips" in preset_info:
                    res_dict["max_pips"] = preset_info["max_pips"]
                save_spec_config(self.profession, self.spec, self.spec_config, resolution_tag=self.resolution_tag)
                save_spec_config(self.profession, self.spec, self.spec_config)
                print(f"[BarCalibrator] Saved resource bbox for [{self.profession} > {self.spec}] to spec YAMLs")

            # Persist to active spec in professions_database.yaml
            if os.path.exists(self.db_path):
                try:
                    with open(self.db_path, "r") as f:
                        db = yaml.safe_load(f) or {}
                    spec_entry = db.get("professions", {}).get(self.profession, {}).get("elite_specs", {}).get(self.spec, {})
                    if spec_entry:
                        res_dict = spec_entry.setdefault("resource", {})
                        res_dict["type"] = res_type
                        res_dict["bbox"] = res_bbox
                        if "max_pips" in preset_info:
                            res_dict["max_pips"] = preset_info["max_pips"]
                        with open(self.db_path, "w") as f:
                            yaml.safe_dump(db, f, default_flow_style=False, sort_keys=False)
                        print(f"[BarCalibrator] Updated resource bbox in {self.db_path}")
                except Exception as e:
                    print(f"[BarCalibrator] Note: Could not update resource bbox in database YAML: {e}")

        saved_keys = []
        for slot in self.current_slots:
            sx, sy, sw, sh = slot["abs_bbox"]
            k = slot["key"]

            # Normalized relative to the HUD frame
            rel_nx = round((sx - hud_x) / float(hud_w), 4)
            rel_ny = round((sy - hud_y) / float(hud_h), 4)
            rel_nw = round(sw / float(hud_w), 4)
            rel_nh = round(sh / float(hud_h), 4)

            coord_tuple = [rel_nx, rel_ny, rel_nw, rel_nh]
            settings["calibrated_slots"][k] = coord_tuple
            saved_keys.append(k)

            if is_mech:
                mech_coords[k] = coord_tuple

        # Save to settings.yaml
        with open(self.config_path, "w") as f:
            yaml.safe_dump(settings, f, default_flow_style=False, sort_keys=False)

        # If mechanic bar, also save to resolution-specific and generic spec YAML
        if is_mech:
            if hasattr(self, "spec_config") and self.spec_config:
                from core.spec_manager import save_spec_config
                m_bar = self.spec_config.setdefault("mechanic_bar", {})
                existing_m_slots = m_bar.setdefault("slots", {})
                existing_m_slots.update(mech_coords)
                m_bar["f_slots_count"] = max(m_bar.get("f_slots_count", len(existing_m_slots)), len(existing_m_slots))
                save_spec_config(self.profession, self.spec, self.spec_config, resolution_tag=self.resolution_tag)
                save_spec_config(self.profession, self.spec, self.spec_config)
                print(f"[BarCalibrator] Saved mechanic slots to config/specs/{self.profession.lower()}_{self.spec.lower()}_{self.resolution_tag}.yaml")

            if os.path.exists(self.db_path):
                try:
                    with open(self.db_path, "r") as f:
                        db = yaml.safe_load(f) or {}
                    prof_data = db.get("professions", {}).get(self.profession, {})
                    specs = prof_data.get("elite_specs", {})
                    if self.spec in specs:
                        specs[self.spec]["mechanic_slots"] = mech_coords
                        with open(self.db_path, "w") as f:
                            yaml.safe_dump(db, f, default_flow_style=False, sort_keys=False)
                        print(f"[BarCalibrator] Updated mechanic_slots in {self.db_path}")
                except Exception as e:
                    print(f"[BarCalibrator] Note: Could not update database YAML: {e}")

        # Make current boxes persistent on canvas so user can see they are saved
        self._freeze_current_bar_on_canvas()

        # Destroy floating panel and notify user
        if self.panel_frame:
            self.panel_frame.destroy()
            self.panel_frame = None

        res_file_name = f"{self.profession.lower()}_{self.spec.lower()}_{self.resolution_tag}.yaml"
        msg = (
            f"Successfully calibrated {len(saved_keys)} slots for [{self.profession.title()} - {self.spec.title()}]!\n"
            f"Slots: {', '.join(saved_keys)}\n\n"
            f"✓ Monitor Profile ({self.resolution_tag}): config/specs/{res_file_name}\n"
            f"✓ System Settings: config/settings.yaml\n\n"
            f"You can now drag another rectangle (e.g. Weapon Swap, Utility, or Resource) or press [ESC] to finish!"
        )
        print(f"[BarCalibrator] {msg}")
        messagebox.showinfo("Bar Calibrated", msg)

    def _freeze_current_bar_on_canvas(self):
        """Converts currently selected slots into a persistent green outline on screen."""
        if not self.current_slots:
            return

        for slot in self.current_slots:
            sx, sy, sw, sh = slot["abs_bbox"]
            b_text = slot["badge"]

            # Persistent dimmed cyan outline
            pid = self.canvas.create_rectangle(
                sx, sy, sx + sw, sy + sh,
                outline="#94e2d5", width=2, dash=(3, 3)
            )
            self.persistent_ids.append(pid)

            tid = self.canvas.create_text(
                sx + sw // 2, sy + sh // 2,
                text=b_text,
                fill="#94e2d5",
                font=("Consolas", 11, "bold")
            )
            self.persistent_ids.append(tid)

        self._clear_active_preview()
        self.saved_bars.append(list(self.current_slots))
        self.current_slots.clear()
        self.current_bbox = None

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Action Bar Equidistant Grid Calibrator")
    parser.add_argument("--config", default="config/settings.yaml")
    parser.add_argument("--profession", default=None)
    parser.add_argument("--spec", default=None)
    args = parser.parse_args()
    calibrator = BarGridCalibrator(config_path=args.config, profession=args.profession, spec=args.spec)
    calibrator.run()
