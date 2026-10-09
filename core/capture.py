"""
Passive, high-performance screen capture module using mss.
Captures strictly the calibrated Region of Interest (ROI) with minimal CPU usage.
"""

import time
from typing import Dict, Any, Optional, Tuple
import mss
import numpy as np
import cv2

from core.dpi_utils import enable_dpi_awareness, get_screen_resolution, normalized_to_absolute, bottom_center_to_absolute


class ScreenMonitor:
    """
    Passive desktop screen monitor for a targeted Region of Interest (ROI).
    """

    def __init__(self, region_config: Dict[str, Any]):
        enable_dpi_awareness()
        self.sct = mss.MSS()
        self.screen_w, self.screen_h = get_screen_resolution()
        self.region_config = region_config
        self.roi: Dict[str, int] = {}
        self.update_roi(region_config)
        self.last_capture_time: float = 0.0
        self.last_latency_ms: float = 0.0

    def update_roi(self, region_config: Dict[str, Any]) -> None:
        """
        Updates the active bounding box based on configuration.
        Supports:
        - "bottom_center": Aspect-ratio invariant anchoring across Ultrawide, 16:9, and 16:10.
        - "normalized": Standard left/top percentage ratios.
        - "absolute": Raw pixel coordinates.
        """
        self.region_config = region_config
        mode = region_config.get("mode", "normalized")

        if mode == "bottom_center":
            cx_ratio = float(region_config.get("center_offset_ratio_x", 0.0))
            by_ratio = float(region_config.get("bottom_offset_ratio_y", 0.0))
            w_ratio = float(region_config.get("width_ratio", 0.76))
            h_ratio = float(region_config.get("height_ratio", 0.21))
            x, y, w, h = bottom_center_to_absolute(cx_ratio, by_ratio, w_ratio, h_ratio, self.screen_w, self.screen_h)
        elif mode == "normalized":
            nx = float(region_config.get("norm_x", 0.4))
            ny = float(region_config.get("norm_y", 0.75))
            nw = float(region_config.get("norm_w", 0.2))
            nh = float(region_config.get("norm_h", 0.15))
            x, y, w, h = normalized_to_absolute(nx, ny, nw, nh, self.screen_w, self.screen_h)
        else:
            x = int(region_config.get("abs_x", 0))
            y = int(region_config.get("abs_y", 0))
            w = int(region_config.get("abs_w", 300))
            h = int(region_config.get("abs_h", 200))

        # mss monitor dict format: {'top': y, 'left': x, 'width': w, 'height': h}
        self.roi = {"left": x, "top": y, "width": w, "height": h}

    def get_roi_bounds(self) -> Tuple[int, int, int, int]:
        """Returns (x, y, w, h) of active ROI."""
        return self.roi["left"], self.roi["top"], self.roi["width"], self.roi["height"]

    def grab_frame(self) -> np.ndarray:
        """
        Captures the configured ROI bounding box and returns an OpenCV BGR numpy array.
        Zero memory injection, passive desktop frame grab.
        """
        t0 = time.perf_counter()
        
        # Grab screenshot of ROI
        raw = self.sct.grab(self.roi)
        
        # Convert raw BGRA bytes to numpy array
        frame_bgra = np.array(raw, dtype=np.uint8)
        
        # Convert to standard OpenCV BGR (3 channels)
        frame_bgr = cv2.cvtColor(frame_bgra, cv2.COLOR_BGRA2BGR)
        
        self.last_capture_time = time.time()
        self.last_latency_ms = (time.perf_counter() - t0) * 1000.0
        return frame_bgr

    def close(self) -> None:
        """Release screen capture resources."""
        if self.sct:
            self.sct.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
