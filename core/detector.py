"""
Perception and visual detection module.
Provides multi-scale template matching (resolution-robust) and color/pixel thresholding.
"""

from dataclasses import dataclass
from typing import Optional, Tuple, List, Dict, Any
import os
import cv2
import numpy as np


@dataclass
class DetectionResult:
    matched: bool
    confidence: float
    location: Optional[Tuple[int, int]] = None  # (x, y) relative to ROI
    bounding_box: Optional[Tuple[int, int, int, int]] = None  # (x, y, w, h)
    best_scale: float = 1.0


class VisualDetector:
    """
    Evaluates visual cues from captured frames using OpenCV.
    """

    def __init__(self, templates_dir: str = "config/templates"):
        self.templates_dir = templates_dir
        self._template_cache: Dict[str, np.ndarray] = {}

    def load_template(self, filename: str) -> Optional[np.ndarray]:
        """Loads and caches a template image in BGR format."""
        if filename in self._template_cache:
            return self._template_cache[filename]

        path = os.path.join(self.templates_dir, filename)
        if not os.path.isabs(path) and not os.path.exists(path):
            # Check relative to base directory
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            alt_path = os.path.join(base_dir, self.templates_dir, filename)
            if os.path.exists(alt_path):
                path = alt_path

        if not os.path.exists(path):
            return None

        tpl = cv2.imread(path, cv2.IMREAD_COLOR)
        if tpl is not None:
            self._template_cache[filename] = tpl
        return tpl

    def match_template(
        self,
        frame: np.ndarray,
        template_name: str,
        threshold: float = 0.80,
        multi_scale: bool = True,
        scale_range: Tuple[float, float] = (0.8, 1.25),
        scale_steps: int = 5
    ) -> DetectionResult:
        """
        Performs normalized cross-correlation template matching.
        If multi_scale=True, evaluates multiple scales to support different screen resolutions.
        """
        template = self.load_template(template_name)
        if template is None or frame is None:
            return DetectionResult(matched=False, confidence=0.0)

        f_h, f_w = frame.shape[:2]
        t_h, t_w = template.shape[:2]

        if t_h > f_h or t_w > f_w:
            # Template larger than frame; try downscaling
            scales = list(np.linspace(min(f_h / t_h, f_w / t_w) * 0.9, 0.5, scale_steps))
        elif multi_scale:
            scales = list(np.linspace(scale_range[0], scale_range[1], scale_steps))
            if 1.0 not in scales:
                scales.append(1.0)
            scales.sort()
        else:
            scales = [1.0]

        best_score = -1.0
        best_loc = None
        best_scale = 1.0
        best_size = (t_w, t_h)

        for scale in scales:
            sw = int(t_w * scale)
            sh = int(t_h * scale)

            if sw <= 0 or sh <= 0 or sw > f_w or sh > f_h:
                continue

            resized = cv2.resize(template, (sw, sh), interpolation=cv2.INTER_AREA if scale < 1.0 else cv2.INTER_LINEAR)
            res = cv2.matchTemplate(frame, resized, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(res)

            if max_val > best_score:
                best_score = float(max_val)
                best_loc = max_loc
                best_scale = float(scale)
                best_size = (sw, sh)

        matched = best_score >= threshold
        bbox = (best_loc[0], best_loc[1], best_size[0], best_size[1]) if best_loc else None

        return DetectionResult(
            matched=matched,
            confidence=round(best_score, 4),
            location=best_loc,
            bounding_box=bbox,
            best_scale=round(best_scale, 3)
        )

    def check_color_threshold(
        self,
        frame: np.ndarray,
        lower_bgr: Tuple[int, int, int],
        upper_bgr: Tuple[int, int, int],
        min_pixel_ratio: float = 0.05
    ) -> DetectionResult:
        """
        Checks if a percentage of pixels in the frame fall within a specific color range.
        Great for detecting glowing indicators, active cooldown rings, or alert boxes.
        """
        if frame is None or frame.size == 0:
            return DetectionResult(matched=False, confidence=0.0)

        lower = np.array(lower_bgr, dtype=np.uint8)
        upper = np.array(upper_bgr, dtype=np.uint8)
        mask = cv2.inRange(frame, lower, upper)

        matching_pixels = cv2.countNonZero(mask)
        total_pixels = frame.shape[0] * frame.shape[1]
        ratio = matching_pixels / max(1, total_pixels)

        return DetectionResult(
            matched=ratio >= min_pixel_ratio,
            confidence=round(ratio, 4)
        )
