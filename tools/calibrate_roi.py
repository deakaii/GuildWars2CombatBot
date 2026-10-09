"""
Interactive Screen Region Calibrator & Template Snapper.
Lets you click and drag a rectangle over your screen to set the Region of Interest (ROI).
Saves both physical pixel coordinates AND resolution-independent normalized ratios (0.0-1.0)
so the configuration automatically works across different screen resolutions!
Also lets you save the selected area directly as a reference template image.
"""

import os
import sys
import yaml
import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk, ImageGrab

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.dpi_utils import enable_dpi_awareness, get_screen_resolution, absolute_to_normalized


class RegionCalibrator:
    def __init__(self, config_path: str = "config/settings.yaml"):
        enable_dpi_awareness()
        self.config_path = self._resolve_path(config_path)
        self.screen_w, self.screen_h = get_screen_resolution()
        
        # Take a snapshot of the current screen to display
        print(f"[Calibrator] Primary display resolution: {self.screen_w}x{self.screen_h}")
        print("[Calibrator] Capturing screen snapshot for selection...")
        try:
            self.screenshot = ImageGrab.grab(bbox=(0, 0, self.screen_w, self.screen_h))
        except Exception:
            import mss
            with mss.MSS() as sct:
                raw = sct.grab({'left': 0, 'top': 0, 'width': self.screen_w, 'height': self.screen_h})
                self.screenshot = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
        
        # Selection coordinates
        self.start_x = None
        self.start_y = None
        self.cur_x = None
        self.cur_y = None
        self.rect_id = None
        self.text_id = None

        # Build full-screen overlay
        self.root = tk.Tk()
        self.root.title("Antigrav Screen Calibrator")
        self.root.attributes("-fullscreen", True)
        self.root.attributes("-topmost", True)
        self.root.config(cursor="cross")

        self.canvas = tk.Canvas(self.root, cursor="cross", width=self.screen_w, height=self.screen_h)
        self.canvas.pack(fill="both", expand=True)

        self.tk_image = ImageTk.PhotoImage(self.screenshot)
        self.canvas.create_image(0, 0, anchor="nw", image=self.tk_image)

        # Instructions Banner at top
        banner_text = (
            " DRAG A BOX OVER THE SCREEN REGION TO MONITOR \n"
            "• Release mouse to set ROI | Press [ENTER] to save ROI | Press [T] to save as Template Image | Press [ESC] to Cancel"
        )
        self.canvas.create_rectangle(0, 0, self.screen_w, 55, fill="#1e1e2e", outline="#3b4252")
        self.canvas.create_text(
            self.screen_w // 2, 27,
            text=banner_text,
            fill="#a6e3a1",
            font=("Consolas", 12, "bold"),
            justify="center"
        )

        # Event bindings
        self.canvas.bind("<ButtonPress-1>", self.on_button_press)
        self.canvas.bind("<B1-Motion>", self.on_move_press)
        self.canvas.bind("<ButtonRelease-1>", self.on_button_release)
        self.root.bind("<Return>", self.save_roi)
        self.root.bind("<t>", self.save_as_template)
        self.root.bind("<T>", self.save_as_template)
        self.root.bind("<Escape>", lambda e: self.root.destroy())

        self.selected_bbox = None  # (x, y, w, h)

    def _resolve_path(self, rel_path: str) -> str:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base_dir, rel_path)

    def on_button_press(self, event):
        self.start_x = event.x
        self.start_y = event.y
        if self.rect_id:
            self.canvas.delete(self.rect_id)
        if self.text_id:
            self.canvas.delete(self.text_id)

    def on_move_press(self, event):
        self.cur_x, self.cur_y = event.x, event.y
        if self.rect_id:
            self.canvas.delete(self.rect_id)
        if self.text_id:
            self.canvas.delete(self.text_id)

        # Draw highlight rectangle
        self.rect_id = self.canvas.create_rectangle(
            self.start_x, self.start_y, self.cur_x, self.cur_y,
            outline="#f38ba8", width=3
        )
        
        # Dimensions preview
        x = min(self.start_x, self.cur_x)
        y = min(self.start_y, self.cur_y)
        w = abs(self.cur_x - self.start_x)
        h = abs(self.cur_y - self.start_y)
        
        info = f"{w}x{h} px"
        self.text_id = self.canvas.create_text(
            x + w // 2, max(20, y - 12),
            text=info, fill="#f9e2af", font=("Consolas", 11, "bold")
        )

    def on_button_release(self, event):
        self.cur_x, self.cur_y = event.x, event.y
        x = min(self.start_x, self.cur_x)
        y = min(self.start_y, self.cur_y)
        w = abs(self.cur_x - self.start_x)
        h = abs(self.cur_y - self.start_y)

        if w < 5 or h < 5:
            print("[Calibrator] Box too small, ignored.")
            return

        self.selected_bbox = (x, y, w, h)
        nx, ny, nw, nh = absolute_to_normalized(x, y, w, h, self.screen_w, self.screen_h)

        print("\n" + "-" * 50)
        print(f"  Selected Region: x={x}, y={y}, w={w}, h={h}")
        print(f"  Normalized: norm_x={nx}, norm_y={ny}, norm_w={nw}, norm_h={nh}")
        print("  Press [ENTER] to save ROI to config/settings.yaml")
        print("  Press [T] to save selected crop as reference template image")
        print("  Press [ESC] to exit")
        print("-" * 50)

    def save_roi(self, event=None):
        if not self.selected_bbox:
            messagebox.showwarning("Notice", "Please drag a box over your screen first.")
            return

        x, y, w, h = self.selected_bbox
        nx, ny, nw, nh = absolute_to_normalized(x, y, w, h, self.screen_w, self.screen_h)

        # Load existing config
        if os.path.exists(self.config_path):
            with open(self.config_path, "r") as f:
                cfg = yaml.safe_load(f) or {}
        else:
            cfg = {}

        if "region" not in cfg:
            cfg["region"] = {}

        cfg["region"]["mode"] = "normalized"
        cfg["region"]["norm_x"] = nx
        cfg["region"]["norm_y"] = ny
        cfg["region"]["norm_w"] = nw
        cfg["region"]["norm_h"] = nh
        cfg["region"]["abs_x"] = x
        cfg["region"]["abs_y"] = y
        cfg["region"]["abs_w"] = w
        cfg["region"]["abs_h"] = h
        cfg["region"]["reference_resolution"] = {"width": self.screen_w, "height": self.screen_h}

        with open(self.config_path, "w") as f:
            yaml.safe_dump(cfg, f, default_flow_style=False, sort_keys=False)

        print(f"[Calibrator] Successfully saved ROI to {self.config_path}!")
        messagebox.showinfo("Saved", f"ROI successfully calibrated!\nNormalized: ({nx}, {ny}, {nw}, {nh})\nSaved to settings.yaml")
        self.root.destroy()

    def save_as_template(self, event=None):
        if not self.selected_bbox:
            messagebox.showwarning("Notice", "Please drag a box over your trigger icon first.")
            return

        x, y, w, h = self.selected_bbox
        crop = self.screenshot.crop((x, y, x + w, y + h))

        templates_dir = self._resolve_path("config/templates")
        os.makedirs(templates_dir, exist_ok=True)
        out_path = os.path.join(templates_dir, "trigger_icon.png")

        crop.save(out_path)
        print(f"[Calibrator] Saved reference template image to {out_path} ({w}x{h} px)")
        messagebox.showinfo("Template Saved", f"Saved trigger icon template to:\n{out_path}\n({w}x{h} px)")

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    calibrator = RegionCalibrator()
    calibrator.run()
