"""
Base abstract class for all behavior rules in the prioritization loop.
"""

from abc import ABC, abstractmethod
from typing import Tuple, Any, Optional
import time
import random
import numpy as np

from core.detector import VisualDetector
from core.input_controller import InputController


class BaseBehavior(ABC):
    """
    Abstract behavior rule.
    Subclasses define their visual evaluation logic and input actions.
    """

    def __init__(
        self,
        name: str,
        priority: int,
        cooldown_seconds: float,
        cooldown_jitter_ratio: float = 0.05
    ):
        self.name = name
        self.priority = priority
        self.base_cooldown = cooldown_seconds
        self.cooldown_jitter_ratio = cooldown_jitter_ratio
        
        self.last_triggered_time: float = 0.0
        self.active_cooldown: float = cooldown_seconds
        self.times_triggered: int = 0
        self.last_result: Optional[Any] = None

    def is_on_cooldown(self, current_time: float) -> bool:
        """Returns True if the behavior is still in its cooldown period."""
        return (current_time - self.last_triggered_time) < self.active_cooldown

    def remaining_cooldown(self, current_time: float) -> float:
        """Returns the remaining cooldown time in seconds."""
        rem = self.active_cooldown - (current_time - self.last_triggered_time)
        return max(0.0, rem)

    def trigger(self, input_controller: InputController) -> bool:
        """
        Executes the behavior action and computes the next fuzzy cooldown.
        """
        now = time.time()
        success = self.execute_action(input_controller)
        
        if success:
            self.last_triggered_time = now
            self.times_triggered += 1
            # Add fuzzy jitter to cooldown to eliminate robotic intervals
            margin = self.base_cooldown * self.cooldown_jitter_ratio
            self.active_cooldown = max(0.1, self.base_cooldown + random.uniform(-margin, margin))
        
        return success

    @abstractmethod
    def evaluate_condition(self, frame: np.ndarray, detector: VisualDetector) -> Tuple[bool, Any]:
        """
        Examines the captured frame.
        Returns (matched: bool, context_data: Any).
        """
        pass

    @abstractmethod
    def execute_action(self, input_controller: InputController) -> bool:
        """
        Dispatches the simulated input (keyboard/mouse).
        Returns True if action was successfully executed.
        """
        pass
