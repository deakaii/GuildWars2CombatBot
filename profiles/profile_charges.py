"""
Character Profile: 5-Charge / Pip System.
Monitors top-left charge indicators (charges 1 through 5) and prioritizes burst spender actions.
"""

from profiles.base_profile import BaseCharacterProfile
from behaviors.base import BaseBehavior
from core.detector import VisualDetector, DetectionResult
from core.input_controller import InputController
from core.hud_zones import HudZones


class FullChargeSpenderBehavior(BaseBehavior):
    """Fires a high-priority spender (e.g. 'F1') when charges are full (5 charges)."""
    def __init__(self):
        super().__init__(name="SpendFullCharges", priority=100, cooldown_seconds=1.0)

    def evaluate_condition(self, frame, detector):
        # Inspect top-left mechanic zone for the full charge indicator or color
        mech_zone = HudZones.get_zone(frame, "mechanic")
        # Can check template (e.g. 'charge_5_full.png') or color brightness in charge pip 5
        res = detector.match_template(mech_zone, "charge_5_full.png", threshold=0.78)
        return res.matched, res

    def execute_action(self, input_ctrl: InputController) -> bool:
        print("[ChargeProfile] 5/5 Charges Full! Firing Burst -> Pressing 'F1'")
        return input_ctrl.press_key("f1")


class ChargeBuilderBehavior(BaseBehavior):
    """Standard rotation builder when charges are not full."""
    def __init__(self):
        super().__init__(name="ChargeBuilder", priority=50, cooldown_seconds=2.0)

    def evaluate_condition(self, frame, detector):
        weapon_zone = HudZones.get_zone(frame, "weapon_bar")
        res = detector.match_template(weapon_zone, "skill_2.png", threshold=0.78)
        return res.matched, res

    def execute_action(self, input_ctrl: InputController) -> bool:
        print("[ChargeProfile] Builder Ready -> Pressing '2'")
        return input_ctrl.press_key("2")


class ProfileCharges(BaseCharacterProfile):
    def __init__(self):
        super().__init__(name="ChargeCharacter", signature_template="signature_charges.png")

    def setup_behaviors(self, detector: VisualDetector) -> None:
        self.register_behavior(FullChargeSpenderBehavior())
        self.register_behavior(ChargeBuilderBehavior())
