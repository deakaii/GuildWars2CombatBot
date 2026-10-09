"""
Interactive Rotation Editor Dialog with Bulk LLM Import & Responsive Resizing.
Allows creating, editing, reordering, deleting, and importing combat rotations partitioned into:
1. Opener Sequence (Strict order, runs once)
2. Rotation Loop (Rigid sequential cycle with weapon swaps & auto yields)
3. Priority List (Off-cooldown dynamic priority hierarchy)
4. Mechanic Skills (Off-GCD instant-cast pet commands, virtues, etc.)

Writes directly to professions_database.yaml with automatic timestamped backups.
"""

import os
import sys
import copy
import json
import yaml
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Dict, List, Any, Optional, Callable

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.rotation_parser import (
    load_database,
    save_build,
    dict_to_action,
    action_to_dict,
    parse_build_rotation,
    ingest_llm_payload,
    STANDARDIZED_LLM_TEMPLATE
)


DEFAULT_LLM_PROMPT = STANDARDIZED_LLM_TEMPLATE


class SkillEditDialog(tk.Toplevel):
    """
    Sub-dialog for creating or editing an individual combat action / skill.
    """
    def __init__(self, parent, skill_data: Optional[Dict[str, Any]] = None, section_type: str = "priority_list"):
        super().__init__(parent)
        self.title("Edit Skill Action" if skill_data else "Add Skill Action")
        self.geometry("480x540")
        self.minsize(400, 440)
        self.resizable(True, True)
        self.configure(bg="#181825")
        self.transient(parent)
        self.grab_set()

        self.section_type = section_type
        self.result: Optional[Dict[str, Any]] = None

        data = skill_data or {}
        self.var_name = tk.StringVar(value=data.get("name", ""))
        self.var_key = tk.StringVar(value=data.get("key", "1"))
        self.var_priority = tk.IntVar(value=int(data.get("priority", 50)))
        self.var_cooldown = tk.DoubleVar(value=float(data.get("cooldown", 0.0)))
        self.var_cast_delay = tk.DoubleVar(value=float(data.get("cast_delay", 0.45)))
        self.var_double_tap = tk.BooleanVar(value=bool(data.get("double_tap", False)))
        self.var_is_auto = tk.BooleanVar(value=bool(data.get("is_auto_attack", False)))
        self.var_is_instant = tk.BooleanVar(value=bool(data.get("is_instant", False)))
        self.var_cancellable = tk.BooleanVar(value=bool(data.get("cancellable", True)))

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
        main = tk.Frame(self, bg="#181825", padx=20, pady=16)
        main.pack(fill="both", expand=True)

        header = tk.Label(
            main,
            text=f"ACTION CONFIGURATION ({self.section_type.upper()})",
            font=("Segoe UI", 10, "bold"),
            fg="#89b4fa",
            bg="#181825"
        )
        header.pack(anchor="w", pady=(0, 14))

        form = tk.Frame(main, bg="#1e1e2e", padx=14, pady=14)
        form.pack(fill="x")
        form.columnconfigure(1, weight=1)

        # Name
        tk.Label(form, text="Skill / Action Name:", font=("Segoe UI", 9, "bold"), fg="#cdd6f4", bg="#1e1e2e").grid(row=0, column=0, sticky="w", pady=4)
        ent_name = tk.Entry(form, textvariable=self.var_name, font=("Segoe UI", 9), bg="#313244", fg="#cdd6f4", insertbackground="white")
        ent_name.grid(row=0, column=1, sticky="ew", padx=8, pady=4)

        # Key
        tk.Label(form, text="Simulated Key:", font=("Segoe UI", 9, "bold"), fg="#cdd6f4", bg="#1e1e2e").grid(row=1, column=0, sticky="w", pady=4)
        ent_key = tk.Entry(form, textvariable=self.var_key, font=("Segoe UI", 9), bg="#313244", fg="#cdd6f4", insertbackground="white", width=10)
        ent_key.grid(row=1, column=1, sticky="w", padx=8, pady=4)

        # Priority
        tk.Label(form, text="Priority Weight (0-120):", font=("Segoe UI", 9, "bold"), fg="#cdd6f4", bg="#1e1e2e").grid(row=2, column=0, sticky="w", pady=4)
        ent_prio = tk.Spinbox(form, from_=0, to=120, textvariable=self.var_priority, font=("Segoe UI", 9), bg="#313244", fg="#cdd6f4", width=8)
        ent_prio.grid(row=2, column=1, sticky="w", padx=8, pady=4)

        # Cooldown
        tk.Label(form, text="Base Cooldown (s):", font=("Segoe UI", 9, "bold"), fg="#cdd6f4", bg="#1e1e2e").grid(row=3, column=0, sticky="w", pady=4)
        ent_cd = tk.Entry(form, textvariable=self.var_cooldown, font=("Segoe UI", 9), bg="#313244", fg="#cdd6f4", insertbackground="white", width=10)
        ent_cd.grid(row=3, column=1, sticky="w", padx=8, pady=4)

        # Cast Delay
        tk.Label(form, text="Cast / Channel Lock (s):", font=("Segoe UI", 9, "bold"), fg="#cdd6f4", bg="#1e1e2e").grid(row=4, column=0, sticky="w", pady=4)
        ent_delay = tk.Entry(form, textvariable=self.var_cast_delay, font=("Segoe UI", 9), bg="#313244", fg="#cdd6f4", insertbackground="white", width=10)
        ent_delay.grid(row=4, column=1, sticky="w", padx=8, pady=4)

        # Checkboxes Frame
        chk_frame = tk.Frame(main, bg="#1e1e2e", padx=14, pady=10)
        chk_frame.pack(fill="x", pady=(12, 0))

        tk.Checkbutton(
            chk_frame,
            text="Double-Tap Ground Target (55-75ms inter-tap lock)",
            variable=self.var_double_tap,
            font=("Segoe UI", 9),
            fg="#cdd6f4",
            bg="#1e1e2e",
            selectcolor="#313244",
            activebackground="#1e1e2e",
            activeforeground="#cdd6f4"
        ).pack(anchor="w", pady=2)

        tk.Checkbutton(
            chk_frame,
            text="Passive Auto-Attack (Yields to native game attack chain)",
            variable=self.var_is_auto,
            font=("Segoe UI", 9),
            fg="#cdd6f4",
            bg="#1e1e2e",
            selectcolor="#313244",
            activebackground="#1e1e2e",
            activeforeground="#cdd6f4"
        ).pack(anchor="w", pady=2)

        tk.Checkbutton(
            chk_frame,
            text="Instant Cast (Off-GCD / No Channel Interruption)",
            variable=self.var_is_instant,
            font=("Segoe UI", 9),
            fg="#cdd6f4",
            bg="#1e1e2e",
            selectcolor="#313244",
            activebackground="#1e1e2e",
            activeforeground="#cdd6f4"
        ).pack(anchor="w", pady=2)

        tk.Checkbutton(
            chk_frame,
            text="Cancellable Channel (~15% Human Slip Clipping Allowed)",
            variable=self.var_cancellable,
            font=("Segoe UI", 9),
            fg="#cdd6f4",
            bg="#1e1e2e",
            selectcolor="#313244",
            activebackground="#1e1e2e",
            activeforeground="#cdd6f4"
        ).pack(anchor="w", pady=2)

        # Bottom Buttons
        btn_frame = tk.Frame(main, bg="#181825")
        btn_frame.pack(fill="x", side="bottom", pady=(16, 0))

        tk.Button(
            btn_frame,
            text="✔  Save Action",
            font=("Segoe UI", 10, "bold"),
            bg="#a6e3a1",
            fg="#11111b",
            activebackground="#94e2d5",
            bd=0,
            padx=14,
            pady=6,
            cursor="hand2",
            command=self._on_save
        ).pack(side="right", padx=(8, 0))

        tk.Button(
            btn_frame,
            text="Cancel",
            font=("Segoe UI", 9),
            bg="#313244",
            fg="#cdd6f4",
            activebackground="#45475a",
            bd=0,
            padx=12,
            pady=6,
            cursor="hand2",
            command=self.destroy
        ).pack(side="right")

    def _on_save(self):
        name = self.var_name.get().strip()
        key = self.var_key.get().strip()
        if not name:
            messagebox.showwarning("Validation Error", "Skill name cannot be empty.", parent=self)
            return
        if not key:
            messagebox.showwarning("Validation Error", "Simulated key cannot be empty.", parent=self)
            return

        try:
            cd = float(self.var_cooldown.get())
            delay = float(self.var_cast_delay.get())
            prio = int(self.var_priority.get())
        except ValueError:
            messagebox.showwarning("Validation Error", "Cooldown, Cast Delay, and Priority must be valid numbers.", parent=self)
            return

        action = dict_to_action({
            "name": name,
            "key": key,
            "priority": prio,
            "cooldown": cd,
            "cast_delay": delay,
            "double_tap": self.var_double_tap.get(),
            "is_auto_attack": self.var_is_auto.get(),
            "is_instant": self.var_is_instant.get(),
            "cancellable": self.var_cancellable.get(),
        })
        self.result = action_to_dict(action)
        self.destroy()


class LLMImportDialog(tk.Toplevel):
    """
    Modal dialog for pasting JSON/YAML output generated by LLMs (ChatGPT, Claude, Gemini).
    Parses and populates rotation tracks directly into the Rotation Editor.
    """
    def __init__(self, parent):
        super().__init__(parent)
        self.title("📋 Import Rotation from LLM / JSON / YAML")
        self.geometry("740x580")
        self.minsize(580, 440)
        self.resizable(True, True)
        self.configure(bg="#181825")
        self.transient(parent)
        self.grab_set()

        self.imported_data: Optional[Dict[str, Any]] = None
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

        header_frame = tk.Frame(container, bg="#181825")
        header_frame.pack(fill="x", pady=(0, 8))

        lbl_title = tk.Label(
            header_frame,
            text="PASTE LLM ROTATION PAYLOAD (JSON / YAML)",
            font=("Segoe UI", 10, "bold"),
            fg="#89b4fa",
            bg="#181825"
        )
        lbl_title.pack(side="left")

        btn_copy_prompt = tk.Button(
            header_frame,
            text="📋 Copy LLM Prompt Template",
            font=("Segoe UI", 8, "bold"),
            bg="#313244",
            fg="#a6e3a1",
            activebackground="#45475a",
            bd=0,
            padx=10,
            pady=4,
            cursor="hand2",
            command=self._copy_prompt_template
        )
        btn_copy_prompt.pack(side="right")

        lbl_instruct = tk.Label(
            container,
            text="Paste the JSON or YAML object returned by ChatGPT / Claude / Gemini below. The editor will automatically extract Opener, Loop, Priority List, and Mechanic tracks.",
            font=("Segoe UI", 8),
            fg="#a6adc8",
            bg="#181825",
            justify="left",
            wraplength=700
        )
        lbl_instruct.pack(anchor="w", pady=(0, 8))

        # Text area with scrollbar
        txt_frame = tk.Frame(container, bg="#1e1e2e")
        txt_frame.pack(fill="both", expand=True)

        self.txt_payload = tk.Text(
            txt_frame,
            font=("Consolas", 9),
            bg="#1e1e2e",
            fg="#cdd6f4",
            insertbackground="white",
            bd=0,
            wrap="none"
        )
        sb_v = ttk.Scrollbar(txt_frame, orient="vertical", command=self.txt_payload.yview)
        sb_h = ttk.Scrollbar(txt_frame, orient="horizontal", command=self.txt_payload.xview)
        self.txt_payload.configure(yscrollcommand=sb_v.set, xscrollcommand=sb_h.set)

        sb_v.pack(side="right", fill="y")
        sb_h.pack(side="bottom", fill="x")
        self.txt_payload.pack(fill="both", expand=True, padx=4, pady=4)

        # Footer Buttons
        footer = tk.Frame(container, bg="#181825")
        footer.pack(fill="x", side="bottom", pady=(12, 0))

        tk.Button(
            footer,
            text="✔  Parse & Load Payload",
            font=("Segoe UI", 10, "bold"),
            bg="#a6e3a1",
            fg="#11111b",
            activebackground="#94e2d5",
            bd=0,
            padx=16,
            pady=8,
            cursor="hand2",
            command=self._on_parse_payload
        ).pack(side="right", padx=(8, 0))

        tk.Button(
            footer,
            text="Cancel",
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

    def _copy_prompt_template(self):
        try:
            self.clipboard_clear()
            self.clipboard_append(DEFAULT_LLM_PROMPT)
            messagebox.showinfo(
                "Prompt Copied",
                "The LLM Prompt Template has been copied to your clipboard!\nPaste it into ChatGPT / Claude / Gemini along with any rotation webpage text.",
                parent=self
            )
        except Exception as e:
            messagebox.showerror("Clipboard Error", f"Failed to copy prompt: {e}", parent=self)

    def _on_parse_payload(self):
        raw = self.txt_payload.get("1.0", tk.END).strip()
        if not raw:
            messagebox.showwarning("Empty Input", "Please paste JSON or YAML text into the text area.", parent=self)
            return

        try:
            parsed = ingest_llm_payload(raw)
            self.imported_data = parsed["build_data"]
            self.destroy()
        except Exception as e:
            messagebox.showerror("Parsing Failure", f"Failed to parse rotation payload:\n\n{e}", parent=self)
            return


class RotationEditorDialog(tk.Toplevel):
    """
    Comprehensive Responsive Rotation Editor for managing Opener, Rigid Loop, Priority List,
    and Mechanic Tracks in professions_database.yaml.
    """
    def __init__(
        self,
        parent,
        db_path: str,
        profession: str,
        elite_spec: str,
        build_data: Optional[Dict[str, Any]] = None,
        on_save_callback: Optional[Callable[[str, str, Dict[str, Any]], None]] = None
    ):
        super().__init__(parent)
        self.db_path = db_path
        self.profession = profession
        self.elite_spec = elite_spec
        self.on_save_callback = on_save_callback

        is_new = build_data is None
        self.title("➕ Create New Rotation" if is_new else f"✏ Edit Rotation: {build_data.get('name', 'Custom')}")
        self.geometry("980x740")
        self.minsize(650, 480)
        self.resizable(True, True)
        self.configure(bg="#181825")
        self.transient(parent)
        self.grab_set()

        # Build state
        data = copy.deepcopy(build_data) if build_data else {}
        self.var_build_name = tk.StringVar(value=data.get("name", "New Combat Build"))
        self.var_build_desc = tk.StringVar(value=data.get("description", "Custom rotation profile"))
        self.var_rotation_type = tk.StringVar(value=data.get("rotation_type", "priority_list"))

        # Working skill action lists
        parsed = parse_build_rotation(data)
        self.opener_skills: List[Dict[str, Any]] = [action_to_dict(a) for a in parsed["opener"]]
        self.loop_skills: List[Dict[str, Any]] = [action_to_dict(a) for a in parsed["loop"]]
        self.prio_skills: List[Dict[str, Any]] = [action_to_dict(a) for a in parsed["priority_list"]]
        self.mech_skills: List[Dict[str, Any]] = [action_to_dict(a) for a in parsed["mechanic_skills"]]

        self._init_styles()
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

    def _init_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Editor.TNotebook", background="#181825", borderwidth=0)
        style.configure("Editor.TNotebook.Tab", background="#313244", foreground="#cdd6f4", font=("Segoe UI", 9, "bold"), padding=[14, 6])
        style.map("Editor.TNotebook.Tab", background=[("selected", "#1e1e2e")], foreground=[("selected", "#89b4fa")])

    def _build_ui(self):
        container = tk.Frame(self, bg="#181825", padx=16, pady=14)
        container.pack(fill="both", expand=True)

        # Header Info Card
        header_card = tk.Frame(container, bg="#1e1e2e", padx=14, pady=12)
        header_card.pack(fill="x", pady=(0, 10))
        header_card.columnconfigure(1, weight=1)

        tk.Label(
            header_card,
            text=f"TARGET: {self.profession.upper()} > {self.elite_spec.upper()}",
            font=("Segoe UI", 10, "bold"),
            fg="#89b4fa",
            bg="#1e1e2e"
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))

        # LLM Bulk Import Button
        btn_import_llm = tk.Button(
            header_card,
            text="📋  Import from LLM / JSON",
            font=("Segoe UI", 9, "bold"),
            bg="#313244",
            fg="#a6e3a1",
            activebackground="#45475a",
            bd=0,
            padx=12,
            pady=4,
            cursor="hand2",
            command=self._launch_llm_import
        )
        btn_import_llm.grid(row=0, column=3, sticky="e", pady=(0, 6))

        # Build Name
        tk.Label(header_card, text="Build Name:", font=("Segoe UI", 9, "bold"), fg="#cdd6f4", bg="#1e1e2e").grid(row=1, column=0, sticky="w", pady=2)
        ent_name = tk.Entry(header_card, textvariable=self.var_build_name, font=("Segoe UI", 9), bg="#313244", fg="#cdd6f4", insertbackground="white", width=28)
        ent_name.grid(row=1, column=1, sticky="w", padx=8, pady=2)

        # Rotation Type
        tk.Label(header_card, text="Rotation Engine Type:", font=("Segoe UI", 9, "bold"), fg="#cdd6f4", bg="#1e1e2e").grid(row=1, column=2, sticky="w", padx=(16, 0), pady=2)
        cb_type = ttk.Combobox(header_card, textvariable=self.var_rotation_type, values=["priority_list", "rigid_loop", "hybrid"], state="readonly", width=16)
        cb_type.grid(row=1, column=3, sticky="w", padx=8, pady=2)

        # Description
        tk.Label(header_card, text="Description:", font=("Segoe UI", 9, "bold"), fg="#cdd6f4", bg="#1e1e2e").grid(row=2, column=0, sticky="w", pady=2)
        ent_desc = tk.Entry(header_card, textvariable=self.var_build_desc, font=("Segoe UI", 9), bg="#313244", fg="#cdd6f4", insertbackground="white")
        ent_desc.grid(row=2, column=1, columnspan=3, sticky="ew", padx=8, pady=2)

        # Notebook for rotation components
        self.notebook = ttk.Notebook(container, style="Editor.TNotebook")
        self.notebook.pack(fill="both", expand=True)

        # 1. Opener Tab
        self.tab_opener = tk.Frame(self.notebook, bg="#1e1e2e", padx=10, pady=10)
        self.notebook.add(self.tab_opener, text="1. Opener Sequence")
        self.ref_refresh_opener = self._build_ordered_tab(self.tab_opener, self.opener_skills, is_opener=True)

        # 2. Rigid Loop Tab
        self.tab_loop = tk.Frame(self.notebook, bg="#1e1e2e", padx=10, pady=10)
        self.notebook.add(self.tab_loop, text="2. Rotation Loop (Rigid)")
        self.ref_refresh_loop = self._build_ordered_tab(self.tab_loop, self.loop_skills, is_opener=False)

        # 3. Priority List Tab
        self.tab_prio = tk.Frame(self.notebook, bg="#1e1e2e", padx=10, pady=10)
        self.notebook.add(self.tab_prio, text="3. Priority List (Off-CD)")
        self.ref_refresh_prio = self._build_priority_tab(self.tab_prio, self.prio_skills, is_mech=False)

        # 4. Mechanic Tab
        self.tab_mech = tk.Frame(self.notebook, bg="#1e1e2e", padx=10, pady=10)
        self.notebook.add(self.tab_mech, text="4. Mechanic / Pet Skills (Off-GCD)")
        self.ref_refresh_mech = self._build_priority_tab(self.tab_mech, self.mech_skills, is_mech=True)

        # Bottom Controls
        footer = tk.Frame(container, bg="#181825")
        footer.pack(fill="x", side="bottom", pady=(12, 0))

        tk.Button(
            footer,
            text="💾  Save Rotation to DB",
            font=("Segoe UI", 10, "bold"),
            bg="#a6e3a1",
            fg="#11111b",
            activebackground="#94e2d5",
            bd=0,
            padx=16,
            pady=8,
            cursor="hand2",
            command=self._on_save_database
        ).pack(side="right", padx=(8, 0))

        tk.Button(
            footer,
            text="Cancel",
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

    # -------------------------------------------------------------
    # Ordered Tabs (Opener & Rigid Loop) with Up / Down reordering
    # -------------------------------------------------------------
    def _build_ordered_tab(self, parent: tk.Frame, skills_list: List[Dict[str, Any]], is_opener: bool):
        cols = ("step", "name", "key", "delay", "cooldown", "flags")

        tree_frame = tk.Frame(parent, bg="#1e1e2e")
        tree_frame.pack(side="left", fill="both", expand=True, padx=(0, 10))

        tree = ttk.Treeview(tree_frame, columns=cols, show="headings", style="Dark.Treeview", height=10)
        tree.heading("step", text="#")
        tree.heading("name", text="Action Name")
        tree.heading("key", text="Key")
        tree.heading("delay", text="Cast Delay")
        tree.heading("cooldown", text="Cooldown")
        tree.heading("flags", text="Execution Flags")

        tree.column("step", width=45, anchor="center")
        tree.column("name", width=240, anchor="w")
        tree.column("key", width=60, anchor="center")
        tree.column("delay", width=80, anchor="center")
        tree.column("cooldown", width=80, anchor="center")
        tree.column("flags", width=180, anchor="w")

        # Scrollbar integration
        sb = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        # Reordering & Action buttons
        btn_panel = tk.Frame(parent, bg="#1e1e2e", width=130)
        btn_panel.pack(side="right", fill="y")

        def refresh_table():
            for item in tree.get_children():
                tree.delete(item)
            for i, s in enumerate(skills_list, start=1):
                flags = []
                if s.get("double_tap"):
                    flags.append("Double-Tap")
                if s.get("is_auto_attack"):
                    flags.append("Auto-Attack")
                if s.get("is_instant"):
                    flags.append("Instant")
                if not s.get("cancellable", True):
                    flags.append("No-Cancel")
                tree.insert(
                    "",
                    tk.END,
                    values=(
                        f"#{i}",
                        s.get("name", ""),
                        s.get("key", ""),
                        f"{s.get('cast_delay', 0.45)}s",
                        f"{s.get('cooldown', 0.0)}s",
                        ", ".join(flags) if flags else "-"
                    )
                )

        def move_up():
            sel = tree.selection()
            if not sel:
                return
            idx = tree.index(sel[0])
            if idx > 0:
                skills_list[idx - 1], skills_list[idx] = skills_list[idx], skills_list[idx - 1]
                refresh_table()
                new_item = tree.get_children()[idx - 1]
                tree.selection_set(new_item)

        def move_down():
            sel = tree.selection()
            if not sel:
                return
            idx = tree.index(sel[0])
            if idx < len(skills_list) - 1:
                skills_list[idx], skills_list[idx + 1] = skills_list[idx + 1], skills_list[idx]
                refresh_table()
                new_item = tree.get_children()[idx + 1]
                tree.selection_set(new_item)

        def add_step():
            sec_name = "Opener" if is_opener else "Rigid Loop"
            dlg = SkillEditDialog(self, section_type=sec_name)
            self.wait_window(dlg)
            if dlg.result:
                skills_list.append(dlg.result)
                refresh_table()

        def edit_step():
            sel = tree.selection()
            if not sel:
                return
            idx = tree.index(sel[0])
            sec_name = "Opener" if is_opener else "Rigid Loop"
            dlg = SkillEditDialog(self, skill_data=skills_list[idx], section_type=sec_name)
            self.wait_window(dlg)
            if dlg.result:
                skills_list[idx] = dlg.result
                refresh_table()

        def delete_step():
            sel = tree.selection()
            if not sel:
                return
            idx = tree.index(sel[0])
            del skills_list[idx]
            refresh_table()

        def add_swap():
            skills_list.append({
                "name": "Weapon Swap (~)",
                "key": "~",
                "cast_delay": 0.15,
                "cooldown": 9.8,
                "is_instant": True
            })
            refresh_table()

        tk.Button(btn_panel, text="▲  Move Up", font=("Segoe UI", 9, "bold"), bg="#313244", fg="#cdd6f4", bd=0, pady=5, cursor="hand2", command=move_up).pack(fill="x", pady=3)
        tk.Button(btn_panel, text="▼  Move Down", font=("Segoe UI", 9, "bold"), bg="#313244", fg="#cdd6f4", bd=0, pady=5, cursor="hand2", command=move_down).pack(fill="x", pady=3)
        tk.Frame(btn_panel, bg="#45475a", height=1).pack(fill="x", pady=6)
        tk.Button(btn_panel, text="➕  Add Step", font=("Segoe UI", 9, "bold"), bg="#89b4fa", fg="#11111b", bd=0, pady=6, cursor="hand2", command=add_step).pack(fill="x", pady=3)
        tk.Button(btn_panel, text="🔄  Add Swap (~)", font=("Segoe UI", 9, "bold"), bg="#a6e3a1", fg="#11111b", bd=0, pady=5, cursor="hand2", command=add_swap).pack(fill="x", pady=3)
        tk.Button(btn_panel, text="✏  Edit Step", font=("Segoe UI", 9), bg="#313244", fg="#cdd6f4", bd=0, pady=5, cursor="hand2", command=edit_step).pack(fill="x", pady=3)
        tk.Button(btn_panel, text="🗑  Delete Step", font=("Segoe UI", 9), bg="#313244", fg="#f38ba8", bd=0, pady=5, cursor="hand2", command=delete_step).pack(fill="x", pady=3)

        refresh_table()
        return refresh_table

    # -------------------------------------------------------------
    # Priority Tabs (Priority List & Mechanic Track)
    # -------------------------------------------------------------
    def _build_priority_tab(self, parent: tk.Frame, skills_list: List[Dict[str, Any]], is_mech: bool):
        cols = ("prio", "name", "key", "cooldown", "delay", "flags")

        tree_frame = tk.Frame(parent, bg="#1e1e2e")
        tree_frame.pack(side="left", fill="both", expand=True, padx=(0, 10))

        tree = ttk.Treeview(tree_frame, columns=cols, show="headings", style="Dark.Treeview", height=10)
        tree.heading("prio", text="Priority")
        tree.heading("name", text="Action Name")
        tree.heading("key", text="Key")
        tree.heading("cooldown", text="Cooldown")
        tree.heading("delay", text="Cast Delay")
        tree.heading("flags", text="Execution Flags")

        tree.column("prio", width=65, anchor="center")
        tree.column("name", width=240, anchor="w")
        tree.column("key", width=60, anchor="center")
        tree.column("cooldown", width=80, anchor="center")
        tree.column("delay", width=80, anchor="center")
        tree.column("flags", width=180, anchor="w")

        # Scrollbar integration
        sb = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        btn_panel = tk.Frame(parent, bg="#1e1e2e", width=130)
        btn_panel.pack(side="right", fill="y")

        def refresh_table():
            for item in tree.get_children():
                tree.delete(item)
            skills_list.sort(key=lambda x: x.get("priority", 50), reverse=True)
            for s in skills_list:
                flags = []
                if s.get("double_tap"):
                    flags.append("Double-Tap")
                if s.get("is_auto_attack"):
                    flags.append("Auto-Attack")
                if s.get("is_instant"):
                    flags.append("Instant")
                if not s.get("cancellable", True):
                    flags.append("No-Cancel")
                tree.insert(
                    "",
                    tk.END,
                    values=(
                        f"P: {s.get('priority', 50)}",
                        s.get("name", ""),
                        s.get("key", ""),
                        f"{s.get('cooldown', 0.0)}s",
                        f"{s.get('cast_delay', 0.45)}s",
                        ", ".join(flags) if flags else "-"
                    )
                )

        def add_skill():
            sec_name = "Mechanic Track" if is_mech else "Priority List"
            dlg = SkillEditDialog(self, section_type=sec_name)
            self.wait_window(dlg)
            if dlg.result:
                skills_list.append(dlg.result)
                refresh_table()

        def edit_skill():
            sel = tree.selection()
            if not sel:
                return
            idx = tree.index(sel[0])
            sec_name = "Mechanic Track" if is_mech else "Priority List"
            dlg = SkillEditDialog(self, skill_data=skills_list[idx], section_type=sec_name)
            self.wait_window(dlg)
            if dlg.result:
                skills_list[idx] = dlg.result
                refresh_table()

        def delete_skill():
            sel = tree.selection()
            if not sel:
                return
            idx = tree.index(sel[0])
            del skills_list[idx]
            refresh_table()

        tk.Button(btn_panel, text="➕  Add Skill", font=("Segoe UI", 9, "bold"), bg="#89b4fa", fg="#11111b", bd=0, pady=6, cursor="hand2", command=add_skill).pack(fill="x", pady=3)
        tk.Button(btn_panel, text="✏  Edit Skill", font=("Segoe UI", 9), bg="#313244", fg="#cdd6f4", bd=0, pady=5, cursor="hand2", command=edit_skill).pack(fill="x", pady=3)
        tk.Button(btn_panel, text="🗑  Delete Skill", font=("Segoe UI", 9), bg="#313244", fg="#f38ba8", bd=0, pady=5, cursor="hand2", command=delete_skill).pack(fill="x", pady=3)

        refresh_table()
        return refresh_table

    # -------------------------------------------------------------
    # LLM Bulk Import Launcher
    # -------------------------------------------------------------
    def _launch_llm_import(self):
        dlg = LLMImportDialog(self)
        self.wait_window(dlg)
        if dlg.imported_data:
            parsed = parse_build_rotation(dlg.imported_data)
            self.var_build_name.set(dlg.imported_data.get("name", self.var_build_name.get()))
            self.var_build_desc.set(dlg.imported_data.get("description", self.var_build_desc.get()))
            self.var_rotation_type.set(parsed["rotation_type"])

            # Replace current skills
            self.opener_skills.clear()
            self.opener_skills.extend([action_to_dict(a) for a in parsed["opener"]])

            self.loop_skills.clear()
            self.loop_skills.extend([action_to_dict(a) for a in parsed["loop"]])

            self.prio_skills.clear()
            self.prio_skills.extend([action_to_dict(a) for a in parsed["priority_list"]])

            self.mech_skills.clear()
            self.mech_skills.extend([action_to_dict(a) for a in parsed["mechanic_skills"]])

            # Refresh all UI tables
            if hasattr(self, "ref_refresh_opener"): self.ref_refresh_opener()
            if hasattr(self, "ref_refresh_loop"): self.ref_refresh_loop()
            if hasattr(self, "ref_refresh_prio"): self.ref_refresh_prio()
            if hasattr(self, "ref_refresh_mech"): self.ref_refresh_mech()

            total_imported = len(parsed["opener"]) + len(parsed["loop"]) + len(parsed["priority_list"]) + len(parsed["mechanic_skills"])
            messagebox.showinfo(
                "Import Successful",
                f"Successfully parsed and loaded {total_imported} skill actions from LLM payload!",
                parent=self
            )

    # -------------------------------------------------------------
    # Save to Database Handler
    # -------------------------------------------------------------
    def _on_save_database(self):
        build_name = self.var_build_name.get().strip()
        if not build_name:
            messagebox.showwarning("Validation Error", "Build Name cannot be empty.", parent=self)
            return

        build_dict: Dict[str, Any] = {
            "name": build_name,
            "description": self.var_build_desc.get().strip(),
            "rotation_type": self.var_rotation_type.get(),
            "opener": self.opener_skills,
            "loop": self.loop_skills,
            "priority_list": self.prio_skills,
            "mechanic_skills": self.mech_skills,
        }

        try:
            success = save_build(self.db_path, self.profession, self.elite_spec, build_dict)
            if success:
                messagebox.showinfo(
                    "Rotation Saved",
                    f"Successfully saved rotation '{build_name}' for [{self.profession} > {self.elite_spec}]!\nAn automated backup was created in config/backups/.",
                    parent=self
                )
                if self.on_save_callback:
                    self.on_save_callback(self.profession, self.elite_spec, build_dict)
                self.destroy()
            else:
                messagebox.showerror("Save Error", "Failed to write updated build to database.", parent=self)
        except Exception as e:
            messagebox.showerror("Save Error", f"An error occurred: {e}", parent=self)


if __name__ == "__main__":
    root = tk.Tk()
    root.title("Rotation Editor Preview")
    root.geometry("300x150")
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db_file = os.path.join(base_dir, "config", "professions_database.yaml")

    def test_open():
        db = load_database(db_file)
        b = db.get("professions", {}).get("Engineer", {}).get("elite_specs", {}).get("Mechanist", {}).get("builds", [None])[0]
        dlg = RotationEditorDialog(root, db_file, "Engineer", "Mechanist", build_data=b)

    tk.Button(root, text="Launch Editor for Power Mechanist", command=test_open).pack(pady=40)
    root.mainloop()
