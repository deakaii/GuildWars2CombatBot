"""
Character Profile: Mech Engineer.
Features top-left Mech command F-skills, mech health monitoring, and weapon rotation.
"""

from profiles.base_profile import BaseCharacterProfile
from behaviors.behavior_one import BehaviorOne
from behaviors.base import BaseBehavior
from core.detector import VisualDetector, DetectionResult
from core.input_controller import InputController
from core.hud_zones import HudZones


class MechCommandBehavior(BaseBehavior):
    """Monitors the red glowing indicator in the mechanic zone and presses F6."""
    def __init__(self):
        super().__init__(name="MechAttackOrder", priority=90, cooldown_seconds=2.0)

    def evaluate_condition(self, frame, detector):
        # Only inspect the top-left mechanic zone!
        mech_zone = HudZones.get_zone(frame, "mechanic")
        res = detector.match_template(mech_zone, "red_dot.png", threshold=0.75)
        return res.matched, res

    def execute_action(self, input_ctrl: InputController) -> bool:
        print(f"[MechProfile] Mech attack command ready -> Pressing 'F6'")
        return input_ctrl.press_key("f6")


class ProfileMech(BaseCharacterProfile):
    def __init__(self):
        super().__init__(name="MechEngineer", signature_template="signature_mech.png")

    def setup_behaviors(self, detector: VisualDetector) -> None:
        # Priority 100: Weapon Skill 1 trigger
        b1_cfg = {
            "name": "AutoAttack_1",
            "priority": 100,
            "cooldown": 1.5,
            "key_to_press": "1",
            "condition_type": "template",
            "template_filename": "skill_1.png",
            "confidence_threshold": 0.80
        }
        self.register_behavior(BehaviorOne(b1_cfg))
        
        # Priority 90: Mech F-Skill Command
        self.register_behavior(MechCommandBehavior())
