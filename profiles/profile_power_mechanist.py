"""
Power Mechanist Character Profile.
Implements the exact combat rotation:
1. Skill Reference Guide:
   [Rifle Burst] 1
   [Blunderbuss] 2
   [Net Shot] 3
   [Overcharged Shot] 4
   [Jump Shot] 5 (Ground-targeted double-tap)
   [Throw mine] E (Ground-targeted double-tap)

2. Opener Sequence (Strict ordered sequence):
   [Net Shot] 3 -> [Blunderbuss] 2 -> [Overcharged Shot] 4 -> [Jump Shot] 5 (double-tap)

3. Off-Cooldown Priority Loop (Looping Rotation):
   1. Blunderbuss (Rifle 2)
   2. Net Shot (Rifle 3)
   3. Overcharged Shot (Rifle 4)
   4. Jump Shot (Rifle 5, ground-targeted double-tap)
   5. Throw Mine (Utility E, ground-targeted double-tap)
   6. Rifle Burst (Auto-Attack 1, passive filler)

4. Mech Priority List (Off-GCD / Independent track):
   Core Reactor Shot F2 -> Jade Mortar F3 -> Spark Revolver F1 -> Overclock Signet T
"""

import time
from typing import Optional, List
from profiles.base_profile import BaseCharacterProfile
from behaviors.base import BaseBehavior
from core.detector import VisualDetector
from core.input_controller import InputController
from core.cooldown_detector import UniversalCooldownDetector
from core.rotation_framework import RotationStateMachine, RotationAction, RotationPhase


class PowerMechanistRotationBehavior(BaseBehavior):
    """
    Main rotation behavior managing the Opener and Looping Rotation state machine.
    """
    def __init__(self):
        super().__init__(name="PowerMechanistRotation", priority=100, cooldown_seconds=0.25)
        self.state_machine = RotationStateMachine("Power Mechanist", cancel_slip_probability=0.15)
        self.cooldown_detector = UniversalCooldownDetector(profession="engineer", spec="mechanist")
        self.pending_action: Optional[RotationAction] = None
        self._setup_rotation()

    def _setup_rotation(self):
        # -------------------------------------------------------------
        # 1. Opener Sequence (Runs once on pull)
        # Order: [Net Shot] -> [Blunderbuss] -> [Overcharged Shot] -> [Jump Shot]
        # -------------------------------------------------------------
        opener = [
            RotationAction("Net Shot (Rifle 3)", "3", cooldown=8.0, cast_delay=0.4, cancellable=True),
            RotationAction("Blunderbuss (Rifle 2)", "2", cooldown=8.0, cast_delay=0.5, cancellable=True),
            RotationAction("Overcharged Shot (Rifle 4)", "4", cooldown=12.0, cast_delay=0.65, cancellable=True),
            RotationAction("Jump Shot (Rifle 5)", "5", cooldown=18.0, cast_delay=0.85, cancellable=False, double_tap=True),
        ]
        self.state_machine.set_opener_sequence(opener)

        # -------------------------------------------------------------
        # 2. Looping Rotation: Use skills off Cooldown by Priority
        # P: 90 Blunderbuss (Rifle 2)
        # P: 80 Net Shot (Rifle 3)
        # P: 70 Overcharged Shot (Rifle 4)
        # P: 60 Jump Shot (Rifle 5)   -> Ground-targeted double-tap!
        # P: 50 Throw Mine (Utility E) -> Ground-targeted double-tap!
        # P: 20 Rifle Burst (Auto-Attack 1) -> Passive auto-attack filler
        # -------------------------------------------------------------
        loop_skills = [
            RotationAction("Blunderbuss (Rifle 2)", "2", cooldown=8.0, cast_delay=0.5, priority=90, cancellable=True),
            RotationAction("Net Shot (Rifle 3)", "3", cooldown=8.0, cast_delay=0.4, priority=80, cancellable=True),
            RotationAction("Overcharged Shot (Rifle 4)", "4", cooldown=12.0, cast_delay=0.65, priority=70, cancellable=True),
            RotationAction("Jump Shot (Rifle 5)", "5", cooldown=18.0, cast_delay=0.85, priority=60, cancellable=False, double_tap=True),
            RotationAction("Throw Mine (Utility E)", "e", cooldown=15.0, cast_delay=0.35, priority=50, cancellable=True, double_tap=True),
            RotationAction("Rifle Burst (Auto-Attack 1)", "1", cooldown=1.2, cast_delay=0.4, priority=20, cancellable=True, is_auto_attack=True),
        ]
        self.state_machine.set_loop_skills(loop_skills)

        # -------------------------------------------------------------
        # 3. Mech Priority List (Off-GCD / Independent track)
        # -------------------------------------------------------------
        mech_skills = [
            RotationAction("Core Reactor Shot (F2)", "f2", cooldown=15.0, cast_delay=0.0, priority=95, is_instant=True),
            RotationAction("Jade Mortar (F3)", "f3", cooldown=20.0, cast_delay=0.0, priority=90, is_instant=True),
            RotationAction("Spark Revolver (F1)", "f1", cooldown=8.0, cast_delay=0.0, priority=85, is_instant=True),
            RotationAction("Overclock Signet (T)", "t", cooldown=70.0, cast_delay=0.3, priority=40, is_instant=False),
        ]
        self.state_machine.set_mech_skills(mech_skills)

    def evaluate_condition(self, frame, detector):
        now = time.time()

        def is_action_ready_filter(act: RotationAction) -> bool:
            if frame is None or frame.size == 0:
                return True
            key_clean = act.key.lower()
            slot_id = self.cooldown_detector.resolve_slot_id(key_clean)
            if slot_id in self.cooldown_detector.slots:
                return self.cooldown_detector.is_slot_ready(frame, slot_id)
            return True

        if self.state_machine.phase == RotationPhase.OPENER:
            next_action = self.state_machine.get_next_action(now)
        else:
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
        print(f"[PowerMechanist] {phase_tag} {action.name} -> Key '{action.key}'{dt_tag}")
        success = input_ctrl.press_key(action.key, double_tap=action.double_tap)
        self.state_machine.record_action_cast(action, time.time())
        return success


class ProfilePowerMechanist(BaseCharacterProfile):
    """
    Complete Profile for Engineer -> Mechanist -> Power Mechanist.
    """
    def __init__(self):
        super().__init__(name="Power Mechanist", signature_template="signature_mech.png")
        self.rotation_behavior = PowerMechanistRotationBehavior()

    def setup_behaviors(self, detector: VisualDetector) -> None:
        self.register_behavior(self.rotation_behavior)

    def reset_rotation(self) -> None:
        """Resets to Opener on new engagement."""
        self.rotation_behavior.state_machine.reset_to_opener()
