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
from profiles.simple_rotation import SimpleRotationProfile, load_simple_rotation, rotation_path
from core.rotation_parser import (
    parse_build_rotation,
    delete_build,
    load_database,
    save_build,
    ingest_llm_payload,
    STANDARDIZED_LLM_TEMPLATE
)
from tools.rotation_editor import RotationEditorDialog


class BuildIngestionDialog(tk.Toplevel):
    """
    Dedicated Build Ingestion Modal.
    Allows pasting LLM output (JSON/YAML) with immediate parsing,
    validation summary breakdown (strict_rotation / priority_loop / hybrid, weapon swaps, etc.),
    and 1-click database save & activation.
    """
    def __init__(
        self,
        parent,
        db_path: str,
        default_prof: str,
        default_spec: str,
        on_save_callback
    ):
        super().__init__(parent)
        self.title("📥 Ingest Rotation from LLM")
        sw = parent.winfo_screenwidth()
        sh = parent.winfo_screenheight()
        dlg_w = min(880, sw - 60)
        dlg_h = min(720, sh - 80)
        self.geometry(f"{dlg_w}x{dlg_h}")
        self.minsize(min(700, sw - 60), min(540, sh - 80))
        self.configure(bg="#181825")
        self.transient(parent)
        self.grab_set()

        self.db_path = db_path
        self.default_prof = default_prof
        self.default_spec = default_spec
        self.on_save_callback = on_save_callback

        self.parsed_result: Optional[Dict[str, Any]] = None

        self._build_ui()
        self.center_window(parent)

    def center_window(self, parent):
        self.update_idletasks()
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        px = parent.winfo_rootx()
        py = parent.winfo_rooty()
        w = self.winfo_width()
        h = self.winfo_height()
        x = max(0, px + (pw - w) // 2)
        y = max(0, py + (ph - h) // 2)
        self.geometry(f"+{x}+{y}")

    def _build_ui(self):
        container = tk.Frame(self, bg="#181825", padx=16, pady=14)
        container.pack(fill="both", expand=True)

        # Header
        hdr = tk.Frame(container, bg="#181825")
        hdr.pack(fill="x", pady=(0, 6))

        lbl_title = tk.Label(
            hdr,
            text="INGEST COMBAT BUILD FROM LLM",
            font=("Segoe UI", 11, "bold"),
            fg="#89b4fa",
            bg="#181825"
        )
        lbl_title.pack(side="left")

        btn_copy = tk.Button(
            hdr,
            text="📋 Copy LLM Template",
            font=("Segoe UI", 8, "bold"),
            bg="#313244",
            fg="#a6e3a1",
            activebackground="#45475a",
            bd=0,
            padx=10,
            pady=4,
            cursor="hand2",
            command=self._copy_template
        )
        btn_copy.pack(side="right")

        lbl_sub = tk.Label(
            container,
            text="Paste the JSON or YAML payload returned by ChatGPT, Claude, Gemini, or any LLM. The parser automatically extracts strict rotations, priority loops, hybrid sequences, weapon swaps (~), double-taps, and auto-attack windows.",
            font=("Segoe UI", 8),
            fg="#a6adc8",
            bg="#181825",
            justify="left",
            wraplength=720
        )
        lbl_sub.pack(anchor="w", pady=(0, 8))

        # Text input
        txt_frame = tk.Frame(container, bg="#1e1e2e")
        txt_frame.pack(fill="both", expand=True)

        self.txt_payload = tk.Text(
            txt_frame,
            font=("Consolas", 9),
            bg="#1e1e2e",
            fg="#cdd6f4",
            insertbackground="white",
            bd=0,
            wrap="none",
            height=12
        )
        sb_v = ttk.Scrollbar(txt_frame, orient="vertical", command=self.txt_payload.yview)
        sb_h = ttk.Scrollbar(txt_frame, orient="horizontal", command=self.txt_payload.xview)
        self.txt_payload.configure(yscrollcommand=sb_v.set, xscrollcommand=sb_h.set)
        sb_v.pack(side="right", fill="y")
        sb_h.pack(side="bottom", fill="x")
        self.txt_payload.pack(fill="both", expand=True, padx=4, pady=4)

        # Action bar with Parse button
        parse_bar = tk.Frame(container, bg="#181825")
        parse_bar.pack(fill="x", pady=(8, 4))

        self.btn_parse = tk.Button(
            parse_bar,
            text="✔  Parse & Validate Payload",
            font=("Segoe UI", 9, "bold"),
            bg="#89b4fa",
            fg="#11111b",
            activebackground="#b4befe",
            bd=0,
            padx=14,
            pady=6,
            cursor="hand2",
            command=self._on_parse
        )
        self.btn_parse.pack(side="left")

        # Summary preview card
        self.card_summary = tk.Frame(container, bg="#1e1e2e", bd=1, relief="solid")
        self.card_summary.pack(fill="x", pady=(6, 8))
        self.card_summary.pack_forget()

        self.lbl_card_title = tk.Label(
            self.card_summary,
            text="VALIDATED ROTATION SUMMARY",
            font=("Segoe UI", 9, "bold"),
            fg="#a6e3a1",
            bg="#1e1e2e"
        )
        self.lbl_card_title.pack(anchor="w", padx=12, pady=(8, 4))

        self.lbl_card_details = tk.Label(
            self.card_summary,
            text="",
            font=("Segoe UI", 8),
            fg="#cdd6f4",
            bg="#1e1e2e",
            justify="left",
            wraplength=720
        )
        self.lbl_card_details.pack(anchor="w", padx=12, pady=(0, 8))

        # Bottom buttons
        footer = tk.Frame(container, bg="#181825")
        footer.pack(fill="x", side="bottom", pady=(4, 0))

        self.btn_save = tk.Button(
            footer,
            text="💾  Save to Database & Activate",
            font=("Segoe UI", 10, "bold"),
            bg="#a6e3a1",
            fg="#11111b",
            activebackground="#94e2d5",
            bd=0,
            padx=16,
            pady=8,
            cursor="hand2",
            command=self._on_save_and_activate,
            state="disabled"
        )
        self.btn_save.pack(side="right", padx=(8, 0))

        self.btn_open_editor = tk.Button(
            footer,
            text="✏  Open in Rotation Editor",
            font=("Segoe UI", 9, "bold"),
            bg="#313244",
            fg="#89b4fa",
            activebackground="#45475a",
            bd=0,
            padx=12,
            pady=8,
            cursor="hand2",
            command=self._on_open_editor,
            state="disabled"
        )
        self.btn_open_editor.pack(side="right", padx=(8, 0))

        tk.Button(
            footer,
            text="Close",
            font=("Segoe UI", 9),
            bg="#313244",
            fg="#cdd6f4",
            activebackground="#45475a",
            bd=0,
            padx=14,
            pady=8,
            cursor="hand2",
            command=self.destroy
        ).pack(side="right")

    def _copy_template(self):
        try:
            self.clipboard_clear()
            self.clipboard_append(STANDARDIZED_LLM_TEMPLATE)
            messagebox.showinfo(
                "Prompt Copied",
                "Standardized LLM Prompt Template copied to clipboard!\n\nPaste it into ChatGPT, Claude, Gemini, or any LLM along with your rotation guide.",
                parent=self
            )
        except Exception as e:
            messagebox.showerror("Clipboard Error", f"Failed to copy prompt: {e}", parent=self)

    def _on_parse(self):
        raw = self.txt_payload.get("1.0", tk.END).strip()
        if not raw:
            messagebox.showwarning("Empty Input", "Please paste JSON or YAML rotation text first.", parent=self)
            return

        try:
            self.parsed_result = ingest_llm_payload(raw)
            sm = self.parsed_result["summary"]
            p_name = self.parsed_result["profession"] or self.default_prof
            s_name = self.parsed_result["elite_spec"] or self.default_spec
            r_type = self.parsed_result["rotation_type"].upper()

            details_text = (
                f"• Build: {self.parsed_result['name']}  |  Profession: {p_name} > {s_name}  |  Type: {r_type}\n"
                f"• Tracks: Opener: {sm['opener_count']} steps  |  Loop: {sm['loop_count']} steps  |  "
                f"Priority List: {sm['priority_count']} skills  |  Mechanics: {sm['mechanics_count']} skills\n"
                f"• Detected Capabilities: {sm['weapon_swaps']} Weapon Swaps (~)  |  "
                f"{sm['double_taps']} Ground-Target Double-Taps  |  {sm['auto_attacks']} Auto-Attack Windows"
            )

            self.lbl_card_details.config(text=details_text)
            self.card_summary.pack(fill="x", pady=(6, 8))
            self.btn_save.config(state="normal")
            self.btn_open_editor.config(state="normal")

            messagebox.showinfo("Validation Success", f"Successfully parsed '{self.parsed_result['name']}' ({r_type}) with {sm['total_actions']} total actions!", parent=self)

        except Exception as e:
            self.card_summary.pack_forget()
            self.btn_save.config(state="disabled")
            self.btn_open_editor.config(state="disabled")
            messagebox.showerror("Parsing Failure", f"Failed to parse rotation payload:\n\n{e}", parent=self)

    def _on_save_and_activate(self):
        if not self.parsed_result:
            return
        b_data = self.parsed_result["build_data"]
        prof = self.parsed_result["profession"] or self.default_prof
        spec = self.parsed_result["elite_spec"] or self.default_spec

        if not prof or not spec:
            messagebox.showwarning("Missing Profession/Spec", "Please specify Profession and Elite Specialization before saving.", parent=self)
            return

        try:
            success = save_build(self.db_path, prof, spec, b_data)
            if success:
                self.on_save_callback(prof, spec, b_data)
                self.destroy()
            else:
                messagebox.showerror("Save Error", f"Failed to save build to {self.db_path}", parent=self)
        except Exception as e:
            messagebox.showerror("Save Error", f"Failed to save build: {e}", parent=self)

    def _on_open_editor(self):
        if not self.parsed_result:
            return
        b_data = self.parsed_result["build_data"]
        prof = self.parsed_result["profession"] or self.default_prof
        spec = self.parsed_result["elite_spec"] or self.default_spec
        self.destroy()
        RotationEditorDialog(
            self.master,
            self.db_path,
            prof,
            spec,
            build_data=b_data,
            on_save_callback=self.on_save_callback
        )


class ModernBotGUI:
    def __init__(self, root: tk.Tk):
        enable_dpi_awareness()
        self.root = root
        self.root.title("Antigrav | Prioritization Logic Engine")

        # Responsive window sizing adapted to display resolution and DPI scaling
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()

        if sh >= 1400:
            target_w, target_h = 1180, 940
        elif sh >= 1050:
            target_w, target_h = 1080, 880
        else:
            target_w = min(1020, sw - 40)
            target_h = min(800, sh - 60)

        min_w = min(960, sw - 40)
        min_h = min(780, sh - 60)

        pos_x = max(0, (sw - target_w) // 2)
        pos_y = max(0, (sh - target_h) // 2)

        self.root.geometry(f"{target_w}x{target_h}+{pos_x}+{pos_y}")
        self.root.minsize(min_w, min_h)
        self.root.configure(bg="#181825")

        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.db_path = os.path.join(self.base_dir, "config", "professions_database.yaml")
        self.settings_path = os.path.join(self.base_dir, "config", "settings.yaml")
        self.config_path = self.settings_path

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
            font=("Segoe UI", 10),
            padding=6,
        )
        style.map("Dark.TCombobox", fieldbackground=[("readonly", "#313244")])

        # Style Combobox dropdown listbox popups
        self.root.option_add("*TCombobox*Listbox.font", ("Segoe UI", 10))
        self.root.option_add("*TCombobox*Listbox.background", "#1e1e2e")
        self.root.option_add("*TCombobox*Listbox.foreground", "#cdd6f4")
        self.root.option_add("*TCombobox*Listbox.selectBackground", "#45475a")
        self.root.option_add("*TCombobox*Listbox.selectForeground", "#89b4fa")

        # Treeview styling for rotation table
        style.configure(
            "Dark.Treeview",
            background="#1e1e2e",
            foreground="#cdd6f4",
            fieldbackground="#1e1e2e",
            rowheight=28,
            font=("Segoe UI", 10),
            bordercolor="#313244"
        )
        style.configure("Dark.Treeview.Heading", background="#313244", foreground="#89b4fa", font=("Segoe UI", 10, "bold"))
        style.map("Dark.Treeview", background=[("selected", "#45475a")])

        # Notebook styling
        style.configure("Dark.TNotebook", background="#1e1e2e", borderwidth=0)
        style.configure("Dark.TNotebook.Tab", background="#313244", foreground="#cdd6f4", font=("Segoe UI", 9, "bold"), padding=[12, 5])
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

        card_select.columnconfigure(0, weight=1)
        card_select.columnconfigure(1, weight=1)
        card_select.columnconfigure(2, weight=1)

        # Profession
        tk.Label(card_select, text="1. Profession:", font=("Segoe UI", 9, "bold"), fg="#cdd6f4", bg="#1e1e2e").grid(row=1, column=0, sticky="w", padx=14, pady=2)
        self.cb_profession = ttk.Combobox(card_select, style="Dark.TCombobox", state="readonly")
        self.cb_profession.grid(row=2, column=0, padx=14, pady=(0, 14), sticky="ew")
        self.cb_profession.bind("<<ComboboxSelected>>", self.on_profession_changed)

        # Elite Spec
        tk.Label(card_select, text="2. Elite Specialization:", font=("Segoe UI", 9, "bold"), fg="#cdd6f4", bg="#1e1e2e").grid(row=1, column=1, sticky="w", padx=14, pady=2)
        self.cb_elitespec = ttk.Combobox(card_select, style="Dark.TCombobox", state="readonly")
        self.cb_elitespec.grid(row=2, column=1, padx=14, pady=(0, 14), sticky="ew")
        self.cb_elitespec.bind("<<ComboboxSelected>>", self.on_elitespec_changed)

        # Build
        tk.Label(card_select, text="3. Combat Build:", font=("Segoe UI", 9, "bold"), fg="#cdd6f4", bg="#1e1e2e").grid(row=1, column=2, sticky="w", padx=14, pady=2)
        self.cb_build = ttk.Combobox(card_select, style="Dark.TCombobox", state="readonly")
        self.cb_build.grid(row=2, column=2, padx=14, pady=(0, 14), sticky="ew")
        self.cb_build.bind("<<ComboboxSelected>>", self.on_build_changed)

        # 4. Activity Log Console (packed at bottom before mid_frame so it is never squashed)
        log_frame = tk.Frame(self.root, bg="#1e1e2e")
        log_frame.pack(fill="x", side="bottom", padx=16, pady=(4, 12))

        lbl_log = tk.Label(log_frame, text="LIVE ACTIVITY LOG", font=("Segoe UI", 9, "bold"), fg="#89b4fa", bg="#1e1e2e")
        lbl_log.pack(anchor="w", padx=12, pady=(6, 2))

        self.txt_log = tk.Text(
            log_frame,
            height=4,
            bg="#11111b",
            fg="#a6adc8",
            font=("Consolas", 9),
            bd=0,
            padx=8,
            pady=4
        )
        self.txt_log.pack(fill="both", expand=True, padx=12, pady=(0, 8))

        # 3. Middle Section: Rotation Table & Controls (expands to fill all remaining vertical space)
        mid_frame = tk.Frame(self.root, bg="#181825")
        mid_frame.pack(fill="both", expand=True, padx=16, pady=4)

        # Right Column: Macro Controls & Utilities (packed on right FIRST to guarantee reserved width)
        right_panel = tk.Frame(mid_frame, bg="#1e1e2e", width=300)
        right_panel.pack(side="right", fill="y", padx=(8, 0))

        # Left Column: Rotation Hierarchy Preview & Editor Controls (expands to fill remaining width)
        left_panel = tk.Frame(mid_frame, bg="#1e1e2e")
        left_panel.pack(side="left", fill="both", expand=True, padx=(0, 8))

        # Header with title and Rotation Management buttons
        header_rot = tk.Frame(left_panel, bg="#1e1e2e")
        header_rot.pack(fill="x", padx=12, pady=(10, 6))

        lbl_rot = tk.Label(header_rot, text="ACTIVE ROTATION HIERARCHY", font=("Segoe UI", 10, "bold"), fg="#89b4fa", bg="#1e1e2e")
        lbl_rot.pack(side="left")

        # Action Buttons: 📋 Copy Template, 📥 Ingest, ➕ New, ✏ Edit, 🗑 Delete
        self.btn_del_rot = tk.Button(
            header_rot,
            text="🗑 Delete",
            font=("Segoe UI", 9, "bold"),
            bg="#313244",
            fg="#f38ba8",
            activebackground="#45475a",
            bd=0,
            padx=9,
            pady=5,
            cursor="hand2",
            command=self.delete_selected_rotation
        )
        self.btn_del_rot.pack(side="right", padx=(4, 0))

        self.btn_edit_rot = tk.Button(
            header_rot,
            text="✏ Edit",
            font=("Segoe UI", 9, "bold"),
            bg="#313244",
            fg="#a6e3a1",
            activebackground="#45475a",
            bd=0,
            padx=9,
            pady=5,
            cursor="hand2",
            command=self.launch_edit_rotation
        )
        self.btn_edit_rot.pack(side="right", padx=(4, 0))

        self.btn_new_rot = tk.Button(
            header_rot,
            text="➕ New",
            font=("Segoe UI", 9, "bold"),
            bg="#313244",
            fg="#89b4fa",
            activebackground="#45475a",
            bd=0,
            padx=9,
            pady=5,
            cursor="hand2",
            command=self.launch_new_rotation
        )
        self.btn_new_rot.pack(side="right", padx=(4, 0))

        self.btn_ingest = tk.Button(
            header_rot,
            text="📥 Ingest",
            font=("Segoe UI", 9, "bold"),
            bg="#313244",
            fg="#f9e2af",
            activebackground="#45475a",
            bd=0,
            padx=9,
            pady=5,
            cursor="hand2",
            command=self.launch_ingest_rotation
        )
        self.btn_ingest.pack(side="right", padx=(4, 0))

        self.btn_copy_template = tk.Button(
            header_rot,
            text="📋 Copy Template",
            font=("Segoe UI", 9, "bold"),
            bg="#313244",
            fg="#94e2d5",
            activebackground="#45475a",
            bd=0,
            padx=9,
            pady=5,
            cursor="hand2",
            command=self.copy_llm_template
        )
        self.btn_copy_template.pack(side="right")

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
        self.tree_opener.column("step", width=45, minwidth=40, anchor="center")
        self.tree_opener.column("name", width=220, minwidth=160, anchor="w")
        self.tree_opener.column("key", width=60, minwidth=50, anchor="center")
        self.tree_opener.column("delay", width=80, minwidth=65, anchor="center")
        self.tree_opener.column("flags", width=140, minwidth=100, anchor="w")
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
        self.tree_loop.column("step", width=45, minwidth=40, anchor="center")
        self.tree_loop.column("name", width=220, minwidth=160, anchor="w")
        self.tree_loop.column("key", width=60, minwidth=50, anchor="center")
        self.tree_loop.column("delay", width=80, minwidth=65, anchor="center")
        self.tree_loop.column("flags", width=140, minwidth=100, anchor="w")
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
        self.tree_prio.column("priority", width=65, minwidth=55, anchor="center")
        self.tree_prio.column("name", width=220, minwidth=160, anchor="w")
        self.tree_prio.column("key", width=60, minwidth=50, anchor="center")
        self.tree_prio.column("cooldown", width=80, minwidth=65, anchor="center")
        self.tree_prio.column("flags", width=140, minwidth=100, anchor="w")
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
        self.tree_mech.column("priority", width=65, minwidth=55, anchor="center")
        self.tree_mech.column("name", width=220, minwidth=160, anchor="w")
        self.tree_mech.column("key", width=60, minwidth=50, anchor="center")
        self.tree_mech.column("cooldown", width=80, minwidth=65, anchor="center")
        self.tree_mech.column("flags", width=140, minwidth=100, anchor="w")
        sb_m = ttk.Scrollbar(self.pane_mech, orient="vertical", command=self.tree_mech.yview)
        self.tree_mech.configure(yscrollcommand=sb_m.set)
        self.tree_mech.pack(side="left", fill="both", expand=True)
        sb_m.pack(side="right", fill="y")

        # Backward compatibility reference
        self.tree_rotation = self.tree_prio

        # Right Column Controls
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
            padx=12,
            pady=7,
            cursor="hand2",
            command=self.reset_opener
        )
        self.btn_reset.pack(fill="x", padx=14, pady=4)

        lbl_calib = tk.Label(right_panel, text="VISION & CALIBRATION", font=("Segoe UI", 10, "bold"), fg="#89b4fa", bg="#1e1e2e")
        lbl_calib.pack(anchor="w", padx=14, pady=(14, 6))

        # Quick Utility Buttons
        btn_autodetect = tk.Button(
            right_panel,
            text="⚡  Auto-Detect HUD Bounds",
            font=("Segoe UI", 9, "bold"),
            bg="#89b4fa",
            fg="#11111b",
            activebackground="#b4befe",
            bd=0,
            padx=12,
            pady=7,
            cursor="hand2",
            command=self.auto_detect_hud
        )
        btn_autodetect.pack(fill="x", padx=14, pady=4)

        btn_fcalib = tk.Button(
            right_panel,
            text="🖱  Locate F-Skills (presses each)",
            font=("Segoe UI", 9, "bold"),
            bg="#313244",
            fg="#f9e2af",
            activebackground="#45475a",
            bd=0,
            padx=12,
            pady=7,
            cursor="hand2",
            command=self.calibrate_mech_by_press
        )
        btn_fcalib.pack(fill="x", padx=14, pady=4)

        btn_rotation_file = tk.Button(
            right_panel,
            text="📝  Edit Rotation File",
            font=("Segoe UI", 9, "bold"),
            bg="#313244",
            fg="#cba6f7",
            activebackground="#45475a",
            bd=0,
            padx=12,
            pady=7,
            cursor="hand2",
            command=self.edit_rotation_file
        )
        btn_rotation_file.pack(fill="x", padx=14, pady=4)

        btn_hud = tk.Button(
            right_panel,
            text="👁  Open Live HUD Preview",
            font=("Segoe UI", 9, "bold"),
            bg="#313244",
            fg="#cdd6f4",
            activebackground="#45475a",
            bd=0,
            padx=12,
            pady=7,
            cursor="hand2",
            command=self.launch_hud
        )
        btn_hud.pack(fill="x", padx=14, pady=4)

        self.btn_bar_calib = tk.Button(
            right_panel,
            text="🎯  Calibrate Bars & Resources",
            font=("Segoe UI", 9, "bold"),
            bg="#313244",
            fg="#a6e3a1",
            activebackground="#45475a",
            bd=0,
            padx=12,
            pady=7,
            cursor="hand2",
            command=self.launch_bar_calibrator
        )
        self.btn_bar_calib.pack(fill="x", padx=14, pady=4)

        btn_calib = tk.Button(
            right_panel,
            text="⚙  Calibrate Screen Region",
            font=("Segoe UI", 9, "bold"),
            bg="#313244",
            fg="#cdd6f4",
            activebackground="#45475a",
            bd=0,
            padx=12,
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
        lbl_hint.pack(side="bottom", pady=(10, 14))

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
        if hasattr(self, "btn_bar_calib"):
            self.btn_bar_calib.config(text=f"🎯  Calibrate ({prof} - {spec})")
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

        def fmt_key(act):
            if act.key in ["~", "`"] or "weapon swap" in act.name.lower():
                return "Swap (~)"
            return act.key

        # 1. Opener
        for i, act in enumerate(parsed["opener"], start=1):
            flags = []
            if act.key in ["~", "`"] or "weapon swap" in act.name.lower(): flags.append("Swap (~)")
            if act.double_tap: flags.append("Double-Tap")
            if not act.cancellable: flags.append("No-Cancel")
            self.tree_opener.insert("", tk.END, values=(f"#{i}", act.name, fmt_key(act), f"{act.cast_delay}s", ", ".join(flags) if flags else "-"))

        # 2. Loop
        for i, act in enumerate(parsed["loop"], start=1):
            flags = []
            if act.key in ["~", "`"] or "weapon swap" in act.name.lower(): flags.append("Swap (~)")
            if act.is_auto_attack: flags.append("Auto-Attack")
            if act.double_tap: flags.append("Double-Tap")
            if act.is_instant and "Swap (~)" not in flags: flags.append("Instant")
            self.tree_loop.insert("", tk.END, values=(f"#{i}", act.name, fmt_key(act), f"{act.cast_delay}s", ", ".join(flags) if flags else "-"))

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
            try:
                profile = self._create_profile_by_name(prof, build_name)
            except ValueError as e:
                self.log_message(f"[Rotation Error] {e}")
                messagebox.showerror("Rotation Error", str(e), parent=self.root)
                return
            profile.setup_behaviors(detector)
            for b in profile.behaviors:
                self.active_engine.register_behavior(b)
            self.log_message(f"Active rotation engine updated to [{profile.name}]. Ready for [F9]!")

    def copy_llm_template(self):
        """Copies the standardized LLM prompt template to the clipboard."""
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(STANDARDIZED_LLM_TEMPLATE)
            self.log_message("Copied Standardized LLM Prompt Template to clipboard!")
            messagebox.showinfo(
                "Template Copied",
                "Standardized LLM Prompt Template copied to clipboard!\n\nPaste it into ChatGPT, Claude, Gemini, or any LLM along with your rotation guide.",
                parent=self.root
            )
        except Exception as e:
            messagebox.showerror("Clipboard Error", f"Failed to copy template: {e}", parent=self.root)

    def launch_ingest_rotation(self):
        """Launches the dedicated LLM build ingestion dialog."""
        prof = self.cb_profession.get()
        spec = self.cb_elitespec.get()
        BuildIngestionDialog(
            self.root,
            self.db_path,
            default_prof=prof,
            default_spec=spec,
            on_save_callback=self._on_rotation_saved
        )

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

        # A simple rotation file for this spec (config/rotations/{profession}_{spec}.yaml) wins
        try:
            simple = load_simple_rotation(prof, spec)
            if simple:
                profile = SimpleRotationProfile(simple, profession=prof, spec=spec)
        except ValueError as e:
            raise ValueError(f"Rotation file {os.path.basename(rotation_path(prof, spec))}: {e}") from e
        if simple:
            self.log_message(f"Using rotation file {os.path.basename(rotation_path(prof, spec))}: {simple.summary()}")
            return profile
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
                self.log_message(f"Engine ENGAGED for [{profile.name}]. Cadence: {int(self.active_engine.base_tick_interval * 1000)}ms.")

            # Main engine loop in background thread
            while self.active_engine.running and not self.input_ctrl.is_stopped():
                is_active = self.input_ctrl.is_active()

                # Sync GUI status with input_ctrl state
                if not is_active and "ACTIVE" in self.lbl_status.cget("text"):
                    self.root.after(0, self._update_status_standby)
                elif is_active and "STANDBY" in self.lbl_status.cget("text"):
                    self.root.after(0, self._update_status_active)

                if is_active:
                    # If user is tabbed out of Guild Wars 2, throttle loop to conserve CPU
                    if hasattr(self.input_ctrl, "is_game_focused") and not self.input_ctrl.is_game_focused():
                        time.sleep(0.12)
                        continue

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

    def auto_detect_hud(self):
        """Automatically scans the display, locates the GW2 health orb, and sets the tight HUD region."""
        try:
            from core.hud_detector import AutoHUDDetector
            from core.dpi_utils import get_screen_resolution, bottom_center_to_absolute
            screen_w, screen_h = get_screen_resolution()
            success, msg, bc = AutoHUDDetector.auto_calibrate_and_save(
                settings_path=self.settings_path,
                profession=self.cb_profession.get() or None,
                spec=self.cb_elitespec.get() or None,
            )
            if not success or not bc:
                self.log_message(f"[Auto-Detect HUD] {msg}")
                messagebox.showwarning("Auto-Detection Notice", msg, parent=self.root)
                return

            self.settings = self._load_yaml(self.settings_path)
            if self.active_engine and hasattr(self.active_engine, "monitor") and self.active_engine.monitor:
                self.active_engine.monitor.update_roi(bc)

            rx, ry, rw, rh = bottom_center_to_absolute(
                bc["center_offset_ratio_x"],
                bc["bottom_offset_ratio_y"],
                bc["width_ratio"],
                bc["height_ratio"],
                screen_w,
                screen_h
            )
            self.log_message(f"[Auto-Detect HUD] {msg} Screen ROI: [{rx}, {ry}, {rw}x{rh}]")
            title = "HUD & Skill Squares Auto-Detection" if success else "Auto-Detection Notice"
            info = (
                f"{msg}\n\n"
                f"Calibrated Screen ROI: [{rx}, {ry}, {rw}x{rh}]\n"
                f"Screen: {screen_w}x{screen_h}\n"
                f"Mode: bottom_center (Aspect-Ratio Invariant)\n\n"
                f"Visual verification saved to: scratch/detected_skill_squares.png"
            )
            messagebox.showinfo(title, info, parent=self.root)
        except Exception as e:
            self.log_message(f"[Auto-Detect HUD Error]: {e}")
            messagebox.showerror("Auto-Detection Error", f"Failed to run auto-detection: {e}", parent=self.root)

    def edit_rotation_file(self):
        """Opens (creating if needed) config/rotations/{profession}_{spec}.yaml in the default editor."""
        prof = self.cb_profession.get()
        spec = self.cb_elitespec.get()
        if not prof or not spec:
            messagebox.showwarning("Rotation File", "Select a profession and elite spec first.", parent=self.root)
            return
        path = rotation_path(prof, spec)
        if not os.path.exists(path):
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(
                    f"# {prof} / {spec} rotation\n"
                    "# Skill-bar numbers: 1-5 weapon, 6 heal, 7-9 utilities, 0 elite, swap = weapon swap.\n"
                    "# Your keybinds are applied automatically.\n\n"
                    f"name: {spec}\n\n"
                    "# Press each skill whenever it's ready; the first listed goes first.\n"
                    "priority: [2, 3, 4, 5]\n\n"
                    "# Ground-targeted skills: pressed twice, this many seconds apart.\n"
                    "double_tap: {}\n\n"
                    "# Skills cancelled if anything is cast over them: hold this many seconds.\n"
                    "no_interrupt: {}\n\n"
                    "# Skills that can be pressed back-to-back (the second one queues).\n"
                    "queue_together: []\n"
                )
            self.log_message(f"Created starter rotation file {os.path.basename(path)}.")
        try:
            os.startfile(path)
        except Exception as e:
            messagebox.showerror("Rotation File", f"Could not open {path}: {e}", parent=self.root)
            return
        self.log_message(f"Opened {os.path.basename(path)}. Save it, then re-select the build (or restart the engine) to apply.")

    def calibrate_mech_by_press(self):
        """Presses each F-skill of the selected spec and locates its slot from the cooldown overlay."""
        prof = self.cb_profession.get()
        spec = self.cb_elitespec.get()
        if not prof or not spec:
            messagebox.showwarning("Locate F-Skills", "Select a profession and elite spec first.", parent=self.root)
            return
        if not messagebox.askokcancel(
            "Locate F-Skills",
            f"This switches to Guild Wars 2 and presses each {prof} / {spec} profession skill once "
            "(they will go on cooldown), then finds each slot by its cooldown overlay.\n\n"
            "Target an enemy (e.g. a training golem) first so the skills can fire.\n"
            "Press F12 to abort.",
            parent=self.root,
        ):
            return

        def worker():
            from core.mech_press_calibrator import run_press_calibration
            log = lambda m: self.root.after(0, self.log_message, m)
            try:
                ok, msg, _ = run_press_calibration(prof, spec, settings_path=self.settings_path, log=log)
            except Exception as e:
                ok, msg = False, f"F-skill calibration failed: {e}"
            log(f"[Locate F-Skills] {msg}")
            show = messagebox.showinfo if ok else messagebox.showwarning
            self.root.after(0, lambda: show("Locate F-Skills", msg, parent=self.root))

        self.log_message(f"[Locate F-Skills] Starting for {prof} / {spec}...")
        threading.Thread(target=worker, daemon=True).start()

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
        subprocess.Popen(cmd, cwd=self.base_dir)
        self.log_message(f"Launched Live Diagnostic HUD for [{prof} > {spec}].")

    def launch_bar_calibrator(self):
        """Launches the interactive multi-slot equidistant grid calibrator in a separate process with active spec."""
        import subprocess
        python_exe = sys.executable
        main_py = os.path.join(self.base_dir, "main.py")
        prof = self.cb_profession.get()
        spec = self.cb_elitespec.get()
        cmd = [python_exe, main_py, "--calibrate-bar"]
        if prof:
            cmd.extend(["--profession", prof])
        if spec:
            cmd.extend(["--spec", spec])
        subprocess.Popen(cmd, cwd=self.base_dir)
        self.log_message(f"Launched Action Bar Grid Calibrator for [{prof} > {spec}].")

    def launch_calibrator(self):
        """Launches the visual region calibrator in a separate process."""
        import subprocess
        python_exe = sys.executable
        main_py = os.path.join(self.base_dir, "main.py")
        subprocess.Popen([python_exe, main_py, "--calibrate"], cwd=self.base_dir)
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
