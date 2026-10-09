"""
Behavior 1: Complete end-to-end implementation.
Reads visual condition (multi-scale template match or color profile) and presses target key.
"""

from typing import Tuple, Any, Dict
import numpy as np

from behaviors.base import BaseBehavior
from core.detector import VisualDetector, DetectionResult
from core.input_controller import InputController


class BehaviorOne(BaseBehavior):
    """
    First concrete behavior rule.
    Monitors for a specific visual trigger icon / cue in the ROI and presses a key.
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(
            name=config.get("name", "BehaviorOne"),
            priority=int(config.get("priority", 100)),
            cooldown_seconds=float(config.get("cooldown", 3.0)),
        )
        self.config = config
        self.key_to_press = str(config.get("key_to_press", "1"))
        self.condition_type = config.get("condition_type", "template")
        
        # Template matching options
        self.template_filename = config.get("template_filename", "trigger_icon.png")
        self.confidence_threshold = float(config.get("confidence_threshold", 0.82))
        self.multi_scale = bool(config.get("multi_scale", True))
        scale_range = config.get("scale_range", [0.8, 1.25])
        self.scale_range = (float(scale_range[0]), float(scale_range[1]))
        self.scale_steps = int(config.get("scale_steps", 5))

    def evaluate_condition(self, frame: np.ndarray, detector: VisualDetector) -> Tuple[bool, DetectionResult]:
        """
        Evaluates whether the trigger condition is met in the current frame.
        """
        if self.condition_type == "template":
            result = detector.match_template(
                frame=frame,
                template_name=self.template_filename,
                threshold=self.confidence_threshold,
                multi_scale=self.multi_scale,
                scale_range=self.scale_range,
                scale_steps=self.scale_steps
            )
            self.last_result = result
            return result.matched, result

        elif self.condition_type == "color_threshold":
            # Example default: look for high intensity / highlighted area
            lower = self.config.get("lower_bgr", [20, 20, 180])
            upper = self.config.get("upper_bgr", [100, 100, 255])
            min_ratio = float(self.config.get("min_pixel_ratio", 0.05))
            result = detector.check_color_threshold(frame, tuple(lower), tuple(upper), min_ratio)
            self.last_result = result
            return result.matched, result

        return False, DetectionResult(matched=False, confidence=0.0)

    def execute_action(self, input_controller: InputController) -> bool:
        """
        Dispatches the configured DirectInput key press.
        """
        print(f"\n[ACTION] [{self.name}] Priority {self.priority} TRIGGERED -> Pressing key '{self.key_to_press}'")
        return input_controller.press_key(self.key_to_press)
