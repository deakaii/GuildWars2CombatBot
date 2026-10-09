"""
Modern GUI Launcher with Profession, Elite Spec, and Build Dropdowns.
Features dark-mode aesthetics, dynamic build rotation preview, live console log,
and integrated macro controls (F9 Start, F10 Pause, F12 Stop).
"""

import os
import sys
import yaml
import threading
import time
import random
import tkinter as tk
from tkinter import ttk, messagebox

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.dpi_utils import enable_dpi_awareness
from core.capture import ScreenMonitor
from core.detector import VisualDetector
from core.input_controller import InputController
from core.engine import PrioritizationEngine
from profiles.profile_power_mechanist import ProfilePowerMechanist
from profiles.profile_core_guardian import ProfileCoreGuardian
from profiles.profile_charges import ProfileCharges
from profiles.profile_mech import ProfileMech
from profiles.configurable_profile import ConfigurableProfile
from core.rotation_parser import parse_build_rotation, delete_build, load_database
from tools.rotation_editor import RotationEditorDialog


class ModernBotGUI:
    def __init__(self, root: tk.Tk):
        enable_dpi_awareness()
        self.root = root
        self.root.title("Antigrav | Prioritization Logic Engine")
        self.root.geometry("880x720")
        self.root.minsize(800, 650)
        self.root.configure(bg="#181825")

        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.db_path = os.path.join(self.base_dir, "config", "professions_database.yaml")
        self.settings_path = os.path.join(self.base_dir, "config", "settings.yaml")

        self.db = self._load_yaml(self.db_path)
        self.settings = self._load_yaml(self.settings_path)

        # Engine thread controls
        self.engine_thread: Optional[threading.Thread] = None
        self.active_engine: Optional[PrioritizationEngine] = None
        self.input_ctrl: Optional[InputController] = None
        self.start_in_standby = True

        # Set Window Icon
        ico_path = os.path.join(self.base_dir, "assets", "bot_icon.ico")
        if os.path.exists(ico_path):
            try:
                self.root.iconbitmap(ico_path)
            except Exception:
                pass

        self._init_styles()
        self._build_ui()
        self._populate_professions()

        # Handle window close
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # Auto-arm engine in STANDBY mode on launch so F9 is live in background immediately!
        self.root.after(350, self._auto_arm_standby)

    def _load_yaml(self, path: str) -> dict:
        if os.path.exists(path):
            with open(path, "r") as f:
                return yaml.safe_load(f) or {}
        return {}

    def _init_styles(self):
        style = ttk.Style()
        style.theme_use("clam")

        # Configure Combobox style
        style.configure(
            "Dark.TCombobox",
            fieldbackground="#313244",
            background="#45475a",
            foreground="#cdd6f4",
            arrowcolor="#89b4fa",
            bordercolor="#45475a",
            lightcolor="#45475a",
            darkcolor="#45475a",
            padding=6,
        )
        style.map("Dark.TCombobox", fieldbackground=[("readonly", "#313244")])

        # Treeview styling for rotation table
        style.configure(
            "Dark.Treeview",
            background="#1e1e2e",
            foreground="#cdd6f4",
            fieldbackground="#1e1e2e",
            rowheight=26,
            font=("Segoe UI", 10),
            bordercolor="#313244"
        )
        style.configure("Dark.Treeview.Heading", background="#313244", foreground="#89b4fa", font=("Segoe UI", 10, "bold"))
        style.map("Dark.Treeview", background=[("selected", "#45475a")])

        # Notebook styling
        style.configure("Dark.TNotebook", background="#1e1e2e", borderwidth=0)
        style.configure("Dark.TNotebook.Tab", background="#313244", foreground="#cdd6f4", font=("Segoe UI", 9, "bold"), padding=[10, 4])
        style.map("Dark.TNotebook.Tab", background=[("selected", "#181825")], foreground=[("selected", "#89b4fa")])

    def _build_ui(self):
        # 1. Header Banner
        header = tk.Frame(self.root, bg="#1e1e2e", height=75)
        header.pack(fill="x", side="top", padx=0, pady=0)

        title_frame = tk.Frame(header, bg="#1e1e2e")
        title_frame.pack(side="left", padx=20, pady=12)

        lbl_title = tk.Label(
            title_frame,
            text="ANTIGRAV PRIORITIZATION ENGINE",
            font=("Segoe UI", 15, "bold"),
            fg="#cdd6f4",
            bg="#1e1e2e"
        )
        lbl_title.pack(anchor="w")

        lbl_sub = tk.Label(
            title_frame,
            text="Passive Vision & Priority Decision Loop • 9 Professions / 36 Elite Specs",
            font=("Segoe UI", 9),
            fg="#a6adc8",
            bg="#1e1e2e"
        )
        lbl_sub.pack(anchor="w")

        # Status Pill
        self.lbl_status = tk.Label(
            header,
            text="● STANDBY (F9 to Start)",
            font=("Segoe UI", 11, "bold"),
            fg="#f9e2af",
            bg="#313244",
            padx=16,
            pady=8
        )
        self.lbl_status.pack(side="right", padx=20, pady=16)

        # 2. Dropdown Selection Card
        card_select = tk.Frame(self.root, bg="#1e1e2e", bd=1, relief="solid")
        card_select.pack(fill="x", padx=16, pady=12)

        card_title = tk.Label(
            card_select,
            text="CHARACTER & BUILD CONFIGURATION",
            font=("Segoe UI", 10, "bold"),
            fg="#89b4fa",
            bg="#1e1e2e"
        )
        card_title.grid(row=0, column=0, columnspan=3, sticky="w", padx=14, pady=(10, 8))

        # Profession
        tk.Label(card_select, text="1. Profession:", font=("Segoe UI", 9, "bold"), fg="#cdd6f4", bg="#1e1e2e").grid(row=1, column=0, sticky="w", padx=14, pady=2)
        self.cb_profession = ttk.Combobox(card_select, style="Dark.TCombobox", state="readonly", width=22)
        self.cb_profession.grid(row=2, column=0, padx=14, pady=(0, 14), sticky="w")
        self.cb_profession.bind("<<ComboboxSelected>>", self.on_profession_changed)

        # Elite Spec
        tk.Label(card_select, text="2. Elite Specialization:", font=("Segoe UI", 9, "bold"), fg="#cdd6f4", bg="#1e1e2e").grid(row=1, column=1, sticky="w", padx=14, pady=2)
        self.cb_elitespec = ttk.Combobox(card_select, style="Dark.TCombobox", state="readonly", width=22)
        self.cb_elitespec.grid(row=2, column=1, padx=14, pady=(0, 14), sticky="w")
        self.cb_elitespec.bind("<<ComboboxSelected>>", self.on_elitespec_changed)

        # Build
        tk.Label(card_select, text="3. Combat Build:", font=("Segoe UI", 9, "bold"), fg="#cdd6f4", bg="#1e1e2e").grid(row=1, column=2, sticky="w", padx=14, pady=2)
        self.cb_build = ttk.Combobox(card_select, style="Dark.TCombobox", state="readonly", width=24)
        self.cb_build.grid(row=2, column=2, padx=14, pady=(0, 14), sticky="w")
        self.cb_build.bind("<<ComboboxSelected>>", self.on_build_changed)

        # 3. Middle Section: Rotation Table & Controls
        mid_frame = tk.Frame(self.root, bg="#181825")
        mid_frame.pack(fill="both", expand=True, padx=16, pady=4)

        # Left Column: Rotation Hierarchy Preview & Editor Controls
        left_panel = tk.Frame(mid_frame, bg="#1e1e2e")
        left_panel.pack(side="left", fill="both", expand=True, padx=(0, 8))

        # Header with title and Rotation Management buttons
        header_rot = tk.Frame(left_panel, bg="#1e1e2e")
        header_rot.pack(fill="x", padx=12, pady=(10, 6))

        lbl_rot = tk.Label(header_rot, text="ACTIVE ROTATION HIERARCHY", font=("Segoe UI", 10, "bold"), fg="#89b4fa", bg="#1e1e2e")
        lbl_rot.pack(side="left")

        # Action Buttons: ➕ New, ✏ Edit, 🗑 Delete
        self.btn_del_rot = tk.Button(
            header_rot,
            text="🗑 Delete",
            font=("Segoe UI", 8, "bold"),
            bg="#313244",
            fg="#f38ba8",
            activebackground="#45475a",
            bd=0,
            padx=8,
            pady=3,
            cursor="hand2",
            command=self.delete_selected_rotation
        )
        self.btn_del_rot.pack(side="right", padx=(4, 0))

        self.btn_edit_rot = tk.Button(
            header_rot,
            text="✏ Edit",
            font=("Segoe UI", 8, "bold"),
            bg="#313244",
            fg="#a6e3a1",
            activebackground="#45475a",
            bd=0,
            padx=8,
            pady=3,
            cursor="hand2",
            command=self.launch_edit_rotation
        )
        self.btn_edit_rot.pack(side="right", padx=(4, 0))

        self.btn_new_rot = tk.Button(
            header_rot,
            text="➕ New",
            font=("Segoe UI", 8, "bold"),
            bg="#313244",
            fg="#89b4fa",
            activebackground="#45475a",
            bd=0,
            padx=8,
            pady=3,
            cursor="hand2",
            command=self.launch_new_rotation
        )
        self.btn_new_rot.pack(side="right")

        # Partitioned Notebook Preview: Opener, Loop, Priority List, Mechanics
        self.rot_notebook = ttk.Notebook(left_panel, style="Dark.TNotebook")
        self.rot_notebook.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        # Tab 1: Opener
        self.pane_opener = tk.Frame(self.rot_notebook, bg="#1e1e2e")
        self.rot_notebook.add(self.pane_opener, text="1. Opener")
        self.tree_opener = ttk.Treeview(self.pane_opener, columns=("step", "name", "key", "delay", "flags"), show="headings", style="Dark.Treeview", height=7)
        self.tree_opener.heading("step", text="#")
        self.tree_opener.heading("name", text="Action Name")
        self.tree_opener.heading("key", text="Key")
        self.tree_opener.heading("delay", text="Delay")
        self.tree_opener.heading("flags", text="Flags")
        self.tree_opener.column("step", width=40, anchor="center")
        self.tree_opener.column("name", width=190, anchor="w")
        self.tree_opener.column("key", width=50, anchor="center")
        self.tree_opener.column("delay", width=65, anchor="center")
        self.tree_opener.column("flags", width=110, anchor="w")
        sb_o = ttk.Scrollbar(self.pane_opener, orient="vertical", command=self.tree_opener.yview)
        self.tree_opener.configure(yscrollcommand=sb_o.set)
        self.tree_opener.pack(side="left", fill="both", expand=True)
        sb_o.pack(side="right", fill="y")

        # Tab 2: Loop
        self.pane_loop = tk.Frame(self.rot_notebook, bg="#1e1e2e")
        self.rot_notebook.add(self.pane_loop, text="2. Loop")
        self.tree_loop = ttk.Treeview(self.pane_loop, columns=("step", "name", "key", "delay", "flags"), show="headings", style="Dark.Treeview", height=7)
        self.tree_loop.heading("step", text="#")
        self.tree_loop.heading("name", text="Action Name")
        self.tree_loop.heading("key", text="Key")
        self.tree_loop.heading("delay", text="Delay")
        self.tree_loop.heading("flags", text="Flags")
        self.tree_loop.column("step", width=40, anchor="center")
        self.tree_loop.column("name", width=190, anchor="w")
        self.tree_loop.column("key", width=50, anchor="center")
        self.tree_loop.column("delay", width=65, anchor="center")
        self.tree_loop.column("flags", width=110, anchor="w")
        sb_l = ttk.Scrollbar(self.pane_loop, orient="vertical", command=self.tree_loop.yview)
        self.tree_loop.configure(yscrollcommand=sb_l.set)
        self.tree_loop.pack(side="left", fill="both", expand=True)
        sb_l.pack(side="right", fill="y")

        # Tab 3: Priority List
        self.pane_prio = tk.Frame(self.rot_notebook, bg="#1e1e2e")
        self.rot_notebook.add(self.pane_prio, text="3. Priority List")
        self.tree_prio = ttk.Treeview(self.pane_prio, columns=("priority", "name", "key", "cooldown", "flags"), show="headings", style="Dark.Treeview", height=7)
        self.tree_prio.heading("priority", text="Priority")
        self.tree_prio.heading("name", text="Action Name")
        self.tree_prio.heading("key", text="Key")
        self.tree_prio.heading("cooldown", text="Cooldown")
        self.tree_prio.heading("flags", text="Flags")
        self.tree_prio.column("priority", width=60, anchor="center")
        self.tree_prio.column("name", width=190, anchor="w")
        self.tree_prio.column("key", width=50, anchor="center")
        self.tree_prio.column("cooldown", width=70, anchor="center")
        self.tree_prio.column("flags", width=110, anchor="w")
        sb_p = ttk.Scrollbar(self.pane_prio, orient="vertical", command=self.tree_prio.yview)
        self.tree_prio.configure(yscrollcommand=sb_p.set)
        self.tree_prio.pack(side="left", fill="both", expand=True)
        sb_p.pack(side="right", fill="y")

        # Tab 4: Mechanics
        self.pane_mech = tk.Frame(self.rot_notebook, bg="#1e1e2e")
        self.rot_notebook.add(self.pane_mech, text="4. Mechanics")
        self.tree_mech = ttk.Treeview(self.pane_mech, columns=("priority", "name", "key", "cooldown", "flags"), show="headings", style="Dark.Treeview", height=7)
        self.tree_mech.heading("priority", text="Priority")
        self.tree_mech.heading("name", text="Action Name")
        self.tree_mech.heading("key", text="Key")
        self.tree_mech.heading("cooldown", text="Cooldown")
        self.tree_mech.heading("flags", text="Flags")
        self.tree_mech.column("priority", width=60, anchor="center")
        self.tree_mech.column("name", width=190, anchor="w")
        self.tree_mech.column("key", width=50, anchor="center")
        self.tree_mech.column("cooldown", width=70, anchor="center")
        self.tree_mech.column("flags", width=110, anchor="w")
        sb_m = ttk.Scrollbar(self.pane_mech, orient="vertical", command=self.tree_mech.yview)
        self.tree_mech.configure(yscrollcommand=sb_m.set)
        self.tree_mech.pack(side="left", fill="both", expand=True)
        sb_m.pack(side="right", fill="y")

        # Backward compatibility reference
        self.tree_rotation = self.tree_prio

        # Right Column: Macro Controls & Utilities
        right_panel = tk.Frame(mid_frame, bg="#1e1e2e", width=260)
        right_panel.pack(side="right", fill="both", padx=(8, 0))

        lbl_ctrl = tk.Label(right_panel, text="MACRO CONTROLS", font=("Segoe UI", 10, "bold"), fg="#89b4fa", bg="#1e1e2e")
        lbl_ctrl.pack(anchor="w", padx=14, pady=(10, 8))

        # Big Buttons
        self.btn_toggle = tk.Button(
            right_panel,
            text="▶  START BOT (F9)",
            font=("Segoe UI", 11, "bold"),
            bg="#a6e3a1",
            fg="#11111b",
            activebackground="#94e2d5",
            bd=0,
            padx=14,
            pady=10,
            cursor="hand2",
            command=self.toggle_bot
        )
        self.btn_toggle.pack(fill="x", padx=14, pady=6)

        self.btn_pause = tk.Button(
            right_panel,
            text="⏸  PAUSE (F10)",
            font=("Segoe UI", 10, "bold"),
            bg="#f9e2af",
            fg="#11111b",
            activebackground="#fab387",
            bd=0,
            padx=14,
            pady=8,
            cursor="hand2",
            command=self.pause_bot
        )
        self.btn_pause.pack(fill="x", padx=14, pady=6)

        self.btn_reset = tk.Button(
            right_panel,
            text="↺  Reset to Opener",
            font=("Segoe UI", 9, "bold"),
            bg="#313244",
            fg="#cdd6f4",
            activebackground="#45475a",
            bd=0,
            padx=10,
            pady=7,
            cursor="hand2",
            command=self.reset_opener
        )
        self.btn_reset.pack(fill="x", padx=14, pady=4)

        # Quick Utility Buttons
        btn_hud = tk.Button(
            right_panel,
            text="👁  Open Live HUD Preview",
            font=("Segoe UI", 9, "bold"),
            bg="#313244",
            fg="#cdd6f4",
            activebackground="#45475a",
            bd=0,
            padx=10,
            pady=7,
            cursor="hand2",
            command=self.launch_hud
        )
        btn_hud.pack(fill="x", padx=14, pady=(12, 4))

        btn_bar_calib = tk.Button(
            right_panel,
            text="📐  Calibrate Skill Bars (Grid)",
            font=("Segoe UI", 9, "bold"),
            bg="#313244",
            fg="#a6e3a1",
            activebackground="#45475a",
            bd=0,
            padx=10,
            pady=7,
            cursor="hand2",
            command=self.launch_bar_calibrator
        )
        btn_bar_calib.pack(fill="x", padx=14, pady=4)

        btn_calib = tk.Button(
            right_panel,
            text="⚙  Calibrate Screen Region",
            font=("Segoe UI", 9, "bold"),
            bg="#313244",
            fg="#cdd6f4",
            activebackground="#45475a",
            bd=0,
            padx=10,
            pady=7,
            cursor="hand2",
            command=self.launch_calibrator
        )
        btn_calib.pack(fill="x", padx=14, pady=4)

        # Keybind hint
        lbl_hint = tk.Label(
            right_panel,
            text="Hotkeys active anywhere:\n[F9] Start • [F10] Pause • [F12] Stop",
            font=("Segoe UI", 8),
            fg="#9399b2",
            bg="#1e1e2e",
            justify="center"
        )
        lbl_hint.pack(side="bottom", pady=10)

        # 4. Activity Log Console
        log_frame = tk.Frame(self.root, bg="#1e1e2e", height=130)
        log_frame.pack(fill="x", side="bottom", padx=16, pady=(4, 14))

        lbl_log = tk.Label(log_frame, text="LIVE ACTIVITY LOG", font=("Segoe UI", 9, "bold"), fg="#89b4fa", bg="#1e1e2e")
        lbl_log.pack(anchor="w", padx=12, pady=(6, 2))

        self.txt_log = tk.Text(
            log_frame,
            height=5,
            bg="#11111b",
            fg="#a6adc8",
            font=("Consolas", 9),
            bd=0,
            padx=8,
            pady=4
        )
        self.txt_log.pack(fill="both", expand=True, padx=12, pady=(0, 8))
        self.log_message("System initialized. Calibrated HUD loaded (2560x1600). Ready.")

    def log_message(self, msg: str):
        t = time.strftime("%H:%M:%S")
        self.txt_log.insert(tk.END, f"[{t}] {msg}\n")
        self.txt_log.see(tk.END)

    def _populate_professions(self):
        profs = list(self.db.get("professions", {}).keys())
        self.cb_profession["values"] = profs
        last_prof = self.settings.get("last_selected", {}).get("profession", "Guardian")
        if last_prof in profs:
            self.cb_profession.set(last_prof)
        elif "Guardian" in profs:
            self.cb_profession.set("Guardian")
        elif "Engineer" in profs:
            self.cb_profession.set("Engineer")
        elif profs:
            self.cb_profession.set(profs[0])
        self.on_profession_changed()

    def on_profession_changed(self, event=None):
        prof = self.cb_profession.get()
        specs = list(self.db.get("professions", {}).get(prof, {}).get("elite_specs", {}).keys())
        self.cb_elitespec["values"] = specs
        last_spec = self.settings.get("last_selected", {}).get("elite_spec", "")
        if last_spec in specs:
            self.cb_elitespec.set(last_spec)
        elif "Core" in specs:
            self.cb_elitespec.set("Core")
        elif "Mechanist" in specs:
            self.cb_elitespec.set("Mechanist")
        elif specs:
            self.cb_elitespec.set(specs[0])
        else:
            self.cb_elitespec.set("")
        self.on_elitespec_changed()

    def on_elitespec_changed(self, event=None):
        prof = self.cb_profession.get()
        spec = self.cb_elitespec.get()
        builds_list = self.db.get("professions", {}).get(prof, {}).get("elite_specs", {}).get(spec, {}).get("builds", [])
        build_names = [b.get("name", "Custom") for b in builds_list]
        self.cb_build["values"] = build_names
        last_build = self.settings.get("last_selected", {}).get("build", "")
        if last_build in build_names:
            self.cb_build.set(last_build)
        elif "Core Guardian DPS" in build_names:
            self.cb_build.set("Core Guardian DPS")
        elif "Power Mechanist" in build_names:
            self.cb_build.set("Power Mechanist")
        elif build_names:
            self.cb_build.set(build_names[0])
        else:
            self.cb_build.set("")
        self.on_build_changed()

    def on_build_changed(self, event=None):
        prof = self.cb_profession.get()
        spec = self.cb_elitespec.get()
        build_name = self.cb_build.get()

        # Clear all sub-tables
        for tree in (self.tree_opener, self.tree_loop, self.tree_prio, self.tree_mech):
            for item in tree.get_children():
                tree.delete(item)

        builds_list = self.db.get("professions", {}).get(prof, {}).get("elite_specs", {}).get(spec, {}).get("builds", [])
        target_build = None
        for b in builds_list:
            if b.get("name") == build_name:
                target_build = b
                break

        if not target_build:
            self.log_message(f"Selected build: {prof} > {spec} > {build_name}")
            return

        # Parse standardized rotation components
        parsed = parse_build_rotation(target_build)

        # 1. Opener
        for i, act in enumerate(parsed["opener"], start=1):
            flags = []
            if act.double_tap: flags.append("Double-Tap")
            if not act.cancellable: flags.append("No-Cancel")
            self.tree_opener.insert("", tk.END, values=(f"#{i}", act.name, act.key, f"{act.cast_delay}s", ", ".join(flags) if flags else "-"))

        # 2. Loop
        for i, act in enumerate(parsed["loop"], start=1):
            flags = []
            if act.is_auto_attack: flags.append("Auto-Attack")
            if act.double_tap: flags.append("Double-Tap")
            if act.is_instant: flags.append("Instant")
            self.tree_loop.insert("", tk.END, values=(f"#{i}", act.name, act.key, f"{act.cast_delay}s", ", ".join(flags) if flags else "-"))

        # 3. Priority List
        for act in sorted(parsed["priority_list"], key=lambda x: x.priority, reverse=True):
            flags = []
            if act.double_tap: flags.append("Double-Tap")
            if act.is_auto_attack: flags.append("Auto-Attack")
            self.tree_prio.insert("", tk.END, values=(f"P: {act.priority}", act.name, act.key, f"{act.cooldown}s", ", ".join(flags) if flags else "-"))

        # 4. Mechanics
        for act in sorted(parsed["mechanic_skills"], key=lambda x: x.priority, reverse=True):
            flags = ["Instant"] if act.is_instant else []
            self.tree_mech.insert("", tk.END, values=(f"P: {act.priority}", act.name, act.key, f"{act.cooldown}s", ", ".join(flags) if flags else "-"))

        # Update tab labels with counts
        self.rot_notebook.tab(0, text=f"1. Opener ({len(parsed['opener'])})")
        self.rot_notebook.tab(1, text=f"2. Loop ({len(parsed['loop'])})")
        self.rot_notebook.tab(2, text=f"3. Priority ({len(parsed['priority_list'])})")
        self.rot_notebook.tab(3, text=f"4. Mechanics ({len(parsed['mechanic_skills'])})")

        # Select primary tab
        if parsed["opener"]:
            self.rot_notebook.select(0)
        elif parsed["loop"]:
            self.rot_notebook.select(1)
        elif parsed["priority_list"]:
            self.rot_notebook.select(2)

        total_skills = len(parsed['opener']) + len(parsed['loop']) + len(parsed['priority_list']) + len(parsed['mechanic_skills'])
        self.log_message(f"Loaded '{build_name}' ({parsed['rotation_type'].upper()}) with {total_skills} skills across tracks.")

        # Persist selection
        self.settings["last_selected"] = {
            "profession": prof,
            "elite_spec": spec,
            "build": build_name
        }
        try:
            with open(self.settings_path, "w") as f:
                yaml.safe_dump(self.settings, f, default_flow_style=False)
        except Exception:
            pass

        # If engine is already running, dynamically swap active profile
        if self.active_engine:
            self.active_engine.behaviors.clear()
            detector = self.active_engine.detector
            profile = self._create_profile_by_name(prof, build_name)
            profile.setup_behaviors(detector)
            for b in profile.behaviors:
                self.active_engine.register_behavior(b)
            self.log_message(f"Active rotation engine updated to [{profile.name}]. Ready for [F9]!")

    def launch_new_rotation(self):
        """Launches the interactive rotation editor to create a new rotation for the active spec."""
        prof = self.cb_profession.get()
        spec = self.cb_elitespec.get()
        if not prof or not spec:
            messagebox.showwarning("Selection Required", "Please select a Profession and Elite Specialization first.", parent=self.root)
            return
        RotationEditorDialog(
            self.root,
            self.db_path,
            prof,
            spec,
            build_data=None,
            on_save_callback=self._on_rotation_saved
        )

    def launch_edit_rotation(self):
        """Launches the interactive rotation editor loaded with the currently selected rotation."""
        prof = self.cb_profession.get()
        spec = self.cb_elitespec.get()
        build_name = self.cb_build.get()
        builds_list = self.db.get("professions", {}).get(prof, {}).get("elite_specs", {}).get(spec, {}).get("builds", [])
        target_build = None
        for b in builds_list:
            if b.get("name", "").strip().lower() == build_name.strip().lower():
                target_build = b
                break

        if not target_build:
            messagebox.showwarning("Selection Required", "Please select an existing combat build to edit.", parent=self.root)
            return

        RotationEditorDialog(
            self.root,
            self.db_path,
            prof,
            spec,
            build_data=target_build,
            on_save_callback=self._on_rotation_saved
        )

    def delete_selected_rotation(self):
        """Prompts for confirmation and deletes the selected rotation from the database."""
        prof = self.cb_profession.get()
        spec = self.cb_elitespec.get()
        build_name = self.cb_build.get()
        if not build_name:
            return

        confirmed = messagebox.askyesno(
            "Confirm Deletion",
            f"Are you sure you want to delete the rotation '{build_name}' for [{prof} > {spec}]?\nAn automatic backup will be created in config/backups/.",
            parent=self.root
        )
        if confirmed:
            success = delete_build(self.db_path, prof, spec, build_name)
            if success:
                self.log_message(f"Deleted rotation '{build_name}'.")
                self.db = self._load_yaml(self.db_path)
                self.on_elitespec_changed()
            else:
                messagebox.showerror("Error", f"Failed to delete '{build_name}'.", parent=self.root)

    def _on_rotation_saved(self, prof: str, spec: str, build_dict: dict):
        """Callback invoked when a rotation is saved in the editor."""
        self.db = self._load_yaml(self.db_path)
        build_name = build_dict.get("name", "")
        self.log_message(f"Saved rotation '{build_name}' for [{prof} > {spec}] to database.")

        # Refresh build dropdown values
        builds_list = self.db.get("professions", {}).get(prof, {}).get("elite_specs", {}).get(spec, {}).get("builds", [])
        build_names = [b.get("name", "Custom") for b in builds_list]
        self.cb_build["values"] = build_names
        if build_name in build_names:
            self.cb_build.set(build_name)
        self.on_build_changed()

    def _create_profile_by_name(self, prof: str, build_name: str):
        spec = self.cb_elitespec.get()
        builds_list = self.db.get("professions", {}).get(prof, {}).get("elite_specs", {}).get(spec, {}).get("builds", [])
        target_build = None
        for b in builds_list:
            if b.get("name", "").strip().lower() == build_name.strip().lower():
                target_build = b
                break

        # Standardized rotation schema -> use ConfigurableProfile dynamically!
        if target_build:
            if "opener" in target_build or "loop" in target_build or "priority_list" in target_build:
                return ConfigurableProfile(target_build, profession=prof, spec=spec)

        b_low = build_name.lower()
        p_low = prof.lower()
        if "guardian" in b_low or "guardian" in p_low:
            return ProfileCoreGuardian()
        elif "mechanist" in b_low or "engineer" in p_low:
            return ProfilePowerMechanist()
        if target_build:
            return ConfigurableProfile(target_build, profession=prof, spec=spec)
        return ProfilePowerMechanist()

    def _auto_arm_standby(self):
        """Automatically initializes engine and hotkey listeners in STANDBY mode on app launch."""
        if not self.engine_thread or not self.engine_thread.is_alive():
            self.log_message("Arming background engine in STANDBY mode...")
            self.start_in_standby = True
            self.engine_thread = threading.Thread(target=self._run_engine_worker, daemon=True)
            self.engine_thread.start()

    def toggle_bot(self):
        """Starts or engages the automation engine."""
        if self.input_ctrl:
            self.input_ctrl.reset_emergency_stop()

        if self.engine_thread and self.engine_thread.is_alive() and self.active_engine and self.input_ctrl:
            if not self.input_ctrl.is_active():
                self.input_ctrl.engage()
                self._update_status_active()
                self.log_message("Action Loop ENGAGED (F9). Ready and monitoring.")
            return

        # Start or resurrect engine in background thread
        self.log_message("Starting Prioritization Engine background thread...")
        self.start_in_standby = False
        self._update_status_active()

        self.engine_thread = threading.Thread(target=self._run_engine_worker, daemon=True)
        self.engine_thread.start()

    def pause_bot(self):
        """Pauses the action execution into standby."""
        if self.input_ctrl:
            self.input_ctrl.disengage("GUI Pause")
            self._update_status_standby()
            self.log_message("Action Loop PAUSED into Standby (F10). Zero inputs will be sent.")

    def reset_opener(self):
        """Resets active rotation state machine back to the opening burst sequence."""
        if self.active_engine:
            for b in self.active_engine.behaviors:
                if hasattr(b, "state_machine"):
                    b.state_machine.reset_to_opener()
                    if hasattr(b, "active_weapon_set"):
                        b.active_weapon_set = "sword_focus"
                    if hasattr(b, "last_weapon_swap_time"):
                        b.last_weapon_swap_time = 0.0
            self.log_message("Combat state reset to OPENER. Press [F9] in-game to start fresh!")

    def _update_status_active(self):
        self.lbl_status.config(text="● ACTIVE & MONITORING", fg="#a6e3a1", bg="#313244")
        self.btn_toggle.config(text="✔  ACTIVE (F9)", bg="#94e2d5")

    def _update_status_standby(self):
        self.lbl_status.config(text="● STANDBY (Press F9 in-game)", fg="#f9e2af", bg="#313244")
        self.btn_toggle.config(text="▶  ENGAGE (F9)", bg="#a6e3a1")

    def _run_engine_worker(self):
        try:
            templates_dir = os.path.join(self.base_dir, "config", "templates")
            monitor = ScreenMonitor(self.settings.get("region", {}))
            detector = VisualDetector(templates_dir=templates_dir)
            ctrl_cfg = self.settings.get("control", {})
            self.input_ctrl = InputController(self.settings.get("stealth", {}), ctrl_cfg)

            self.active_engine = PrioritizationEngine(
                config=self.settings,
                monitor=monitor,
                detector=detector,
                input_controller=self.input_ctrl
            )

            # Load selected profile
            selected_build = self.cb_build.get()
            selected_prof = self.cb_profession.get()
            profile = self._create_profile_by_name(selected_prof, selected_build)

            profile.setup_behaviors(detector)
            for b in profile.behaviors:
                self.active_engine.register_behavior(b)

            self.active_engine.running = True

            # If arming in standby on launch, start paused so F9 is armed
            if self.start_in_standby:
                self.input_ctrl.disengage("Initial Standby")
                self.root.after(0, self._update_status_standby)
                self.log_message(f"Engine armed in STANDBY for [{profile.name}]. Press [F9] in-game to start!")
            else:
                self.root.after(0, self._update_status_active)
                self.log_message(f"Engine ENGAGED for [{profile.name}]. Cadence: 250ms.")

            # Main engine loop in background thread
            while self.active_engine.running and not self.input_ctrl.is_stopped():
                is_active = self.input_ctrl.is_active()

                # Sync GUI status with input_ctrl state
                if not is_active and "ACTIVE" in self.lbl_status.cget("text"):
                    self.root.after(0, self._update_status_standby)
                elif is_active and "STANDBY" in self.lbl_status.cget("text"):
                    self.root.after(0, self._update_status_active)

                if is_active:
                    t_start = time.perf_counter()
                    triggered = self.active_engine.run_tick()
                    if triggered:
                        self.root.after(0, lambda t=triggered: self.log_message(f"ACTION: {t}"))

                    # Humanized cadence jitter
                    jitter = random.uniform(
                        self.active_engine.tick_jitter[0],
                        self.active_engine.tick_jitter[1]
                    )
                    elapsed = time.perf_counter() - t_start
                    sleep_time = max(0.015, (self.active_engine.base_tick_interval + jitter) - elapsed)
                    time.sleep(sleep_time)
                else:
                    # In Standby, sleep lightly to yield CPU while hotkey listener is active
                    time.sleep(0.04)

        except Exception as e:
            self.log_message(f"[Error in Engine]: {e}")
        finally:
            self.root.after(0, self._update_status_standby)

    def launch_hud(self):
        """Launches the read-only live preview HUD in a separate process with active duo coordinates."""
        import subprocess
        python_exe = sys.executable
        main_py = os.path.join(self.base_dir, "main.py")
        prof = self.cb_profession.get()
        spec = self.cb_elitespec.get()
        cmd = [python_exe, main_py, "--hud"]
        if prof:
            cmd.extend(["--profession", prof])
        if spec:
            cmd.extend(["--spec", spec])
        subprocess.Popen(cmd)
        self.log_message(f"Launched Live Diagnostic HUD for [{prof} > {spec}].")

    def launch_bar_calibrator(self):
        """Launches the interactive multi-slot equidistant grid calibrator in a separate process."""
        import subprocess
        python_exe = sys.executable
        main_py = os.path.join(self.base_dir, "main.py")
        subprocess.Popen([python_exe, main_py, "--calibrate-bar"])
        self.log_message("Launched Action Bar Equidistant Grid Calibrator.")

    def launch_calibrator(self):
        """Launches the visual region calibrator in a separate process."""
        import subprocess
        python_exe = sys.executable
        main_py = os.path.join(self.base_dir, "main.py")
        subprocess.Popen([python_exe, main_py, "--calibrate"])
        self.log_message("Launched Screen Region Calibrator.")

    def on_close(self):
        if self.input_ctrl:
            self.input_ctrl.trigger_emergency_stop()
        self.root.destroy()


def start_gui():
    root = tk.Tk()
    app = ModernBotGUI(root)
    root.mainloop()


if __name__ == "__main__":
    start_gui()
