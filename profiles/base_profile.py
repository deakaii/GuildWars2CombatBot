"""
Base abstract class for Character Profiles.
Enables supporting multiple characters (up to 8+) each with their own
unique mechanic HUD systems, skills, and prioritization behaviors.
"""

from abc import ABC, abstractmethod
from typing import List, Optional
import numpy as np

from behaviors.base import BaseBehavior
from core.detector import VisualDetector


class BaseCharacterProfile(ABC):
    """
    Encapsulates all logic, behaviors, and visual signatures for a specific character.
    """

    def __init__(self, name: str, signature_template: Optional[str] = None):
        self.name = name
        self.signature_template = signature_template
        self.behaviors: List[BaseBehavior] = []

    def register_behavior(self, behavior: BaseBehavior) -> None:
        """Adds a behavior rule to this character's rotation."""
        self.behaviors.append(behavior)
        self.behaviors.sort(key=lambda b: b.priority, reverse=True)

    def is_active_character(self, mechanic_frame: np.ndarray, detector: VisualDetector) -> bool:
        """
        Auto-detection: Checks if this character's unique signature icon/resource
        is present in the top-left mechanic zone.
        """
        if not self.signature_template:
            return False

        res = detector.match_template(
            frame=mechanic_frame,
            template_name=self.signature_template,
            threshold=0.75,
            multi_scale=True
        )
        return res.matched

    @abstractmethod
    def setup_behaviors(self, detector: VisualDetector) -> None:
        """Defines and registers all priority rules for this character."""
        pass
