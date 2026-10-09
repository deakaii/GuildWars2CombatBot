"""
Dynamic Configurable Character Profile.
Ingests any standardized rotation definition from professions_database.yaml
and drives the universal RotationStateMachine and UniversalCooldownDetector
without requiring hand-coded Python profile scripts.
"""

import time
from typing import Optional, Dict, Any
from profiles.base_profile import BaseCharacterProfile
from behaviors.base import BaseBehavior
from core.detector import VisualDetector
from core.input_controller import InputController
from core.cooldown_detector import UniversalCooldownDetector
from core.resource_detector import UniversalResourceDetector
from core.rotation_framework import RotationStateMachine, RotationAction, RotationPhase
from core.rotation_parser import parse_build_rotation


class ConfigurableRotationBehavior(BaseBehavior):
    """
    Universal rotation behavior executing Opener, Rigid Loop, and/or Priority List
    parsed dynamically from a standardized build dictionary.
    """
    def __init__(self, build_data: Dict[str, Any], profession: str = "", spec: str = ""):
        name = build_data.get("name", "CustomRotation")
        super().__init__(name=f"{name}Behavior", priority=100, cooldown_seconds=0.25)

        self.build_name = name
        self.profession = profession
        self.spec = spec
        self.state_machine = RotationStateMachine(name, cancel_slip_probability=0.15)
        self.cooldown_detector = UniversalCooldownDetector(profession=profession, spec=spec)
        self.resource_detector = UniversalResourceDetector(spec_config=build_data)
        self.pending_action: Optional[RotationAction] = None

        self._configure_rotation(build_data)

    def _configure_rotation(self, build_data: Dict[str, Any]) -> None:
        """Parses and populates Opener, Loop, Priority List, and Mechanic tracks."""
        parsed = parse_build_rotation(build_data)
        self.rotation_type = parsed["rotation_type"]

        # 1. Opener
        if parsed["opener"]:
            self.state_machine.set_opener_sequence(parsed["opener"])

        # 2. Sequential Loop (Rigid)
        if parsed["loop"]:
            self.state_machine.set_loop_sequence(parsed["loop"])

        # 3. Dynamic Priority List (Off-Cooldown)
        if parsed["priority_list"]:
            self.state_machine.set_loop_skills(parsed["priority_list"])

        # 4. Mechanic track (Off-GCD)
        if parsed["mechanic_skills"]:
            self.state_machine.set_mech_skills(parsed["mechanic_skills"])

    def evaluate_condition(self, frame, detector):
        now = time.time()

        def is_action_ready_filter(act: RotationAction) -> bool:
            if act.is_auto_attack:
                return True
            if frame is None or frame.size == 0:
                return True

            # 1. Slot cooldown check via visual shader signatures
            key_clean = act.key.lower()
            slot_id = self.cooldown_detector.resolve_slot_id(key_clean)
            if slot_id in self.cooldown_detector.slots:
                if not self.cooldown_detector.is_slot_ready(frame, slot_id):
                    return False

            # 2. Resource prerequisites (charges, pips, energy, life force)
            if act.min_resource is not None:
                if not self.resource_detector.is_resource_sufficient(frame, act.min_resource):
                    return False

            if act.max_resource is not None:
                if not self.resource_detector.is_resource_under(frame, act.max_resource):
                    return False

            return True

        next_action = self.state_machine.get_next_action(now, is_action_ready_fn=is_action_ready_filter)

        if not next_action:
            self.pending_action = None
            return False, None

        self.pending_action = next_action
        return True, next_action

    def execute_action(self, input_ctrl: InputController) -> bool:
        now = time.time()
        action = self.pending_action or self.state_machine.get_next_action(now)
        self.pending_action = None
        if not action:
            return False

        phase_tag = f"[{self.state_machine.phase.value}]"
        dt_tag = " [Double-Tap Ground Target]" if action.double_tap else ""
        print(f"[{self.build_name}] {phase_tag} {action.name} -> Key '{action.key}'{dt_tag}")
        success = input_ctrl.press_key(action.key, double_tap=action.double_tap)
        self.state_machine.record_action_cast(action, time.time())
        return success


class ConfigurableProfile(BaseCharacterProfile):
    """
    Universal Profile wrapper for any build dynamically defined in YAML.
    """
    def __init__(self, build_data: Dict[str, Any], profession: str = "", spec: str = ""):
        name = build_data.get("name", "Custom Profile")
        super().__init__(name=name, signature_template="signature_mech.png")
        self.rotation_behavior = ConfigurableRotationBehavior(build_data, profession, spec)

    def setup_behaviors(self, detector: VisualDetector) -> None:
        self.register_behavior(self.rotation_behavior)

    def reset_rotation(self) -> None:
        """Resets combat state to Opener."""
        self.rotation_behavior.state_machine.reset_to_opener()
