"""
Core Guardian Character Profile (Sword/Focus + Greatsword).
Implements the exact combat rotation:
1. Opening Burst on Sword/Focus: Shield of Wrath (5) -> Sword of Justice (E) ->
   Ray of Judgment (4) -> Symbol of Blades (2) -> Zealot's Defense (3) -> Weapon Swap (`)
2. Greatsword Loop: Symbol of Resolution (4) -> Whirling Wrath (2) -> Sword of Justice (E) ->
   Binding Blade (5) -> Leap of Faith (3) -> Passive Auto-Attacks -> Whirling Wrath (2) ->
   Symbol of Resolution (4) -> Sword of Justice (E) -> Weapon Swap (`)
3. Sword/Focus Loop: Zealot's Defense (3) -> Ray of Judgment (4) -> Symbol of Blades (2) ->
   Passive Auto-Attacks -> Symbol of Blades (2) -> Zealot's Defense (3) -> Weapon Swap (`)
4. Virtue Weaving (Off-GCD / Instant Cast): Virtue of Justice (F1), Virtue of Resolve (F2),
   Virtue of Courage (F3) weaved dynamically during burst windows.

CRITICAL ANTI-DETECTION & REALISM RULE:
The game already auto-attacks continuously in melee range. This profile NEVER spams the '1'
key repeatedly. It allows the game to cycle auto-attacks passively, and naturally cancels the
auto-attack chain the instant a higher-priority skill becomes visually ready on screen!
"""

import time
from typing import Optional, List
from profiles.base_profile import BaseCharacterProfile
from behaviors.base import BaseBehavior
from core.detector import VisualDetector
from core.input_controller import InputController
from core.cooldown_detector import UniversalCooldownDetector
from core.rotation_framework import RotationStateMachine, RotationAction, RotationPhase


class CoreGuardianRotationBehavior(BaseBehavior):
    """
    Main rotation behavior managing Core Guardian Sword/Focus and Greatsword state machine.
    """

    def __init__(self):
        super().__init__(name="CoreGuardianRotation", priority=100, cooldown_seconds=0.25)
        self.state_machine = RotationStateMachine("Core Guardian DPS", cancel_slip_probability=0.15)
        self.cooldown_detector = UniversalCooldownDetector(profession="guardian")
        
        # Track active weapon set: "sword_focus" or "greatsword"
        self.active_weapon_set = "sword_focus"
        self.last_weapon_swap_time = 0.0
        self.weapon_swap_cooldown = 9.8  # Standard in-combat weapon swap cooldown
        self.pending_action: Optional[RotationAction] = None

        self._setup_rotation()

    def _setup_rotation(self):
        # -------------------------------------------------------------
        # 1. Opening Sequence (Starts on Sword / Focus, runs exactly once)
        # -------------------------------------------------------------
        opener = [
            RotationAction("Shield of Wrath (Focus 5)", "5", cooldown=35.0, cast_delay=0.5, cancellable=True),
            RotationAction("Sword of Justice (Utility R)", "r", cooldown=15.0, cast_delay=0.3, cancellable=True, double_tap=True),
            RotationAction("Ray of Judgment (Focus 4)", "4", cooldown=13.0, cast_delay=0.5, cancellable=True),
            RotationAction("Symbol of Punishment / Blades (Skill 2)", "2", cooldown=8.0, cast_delay=0.4, cancellable=True, double_tap=True),
            RotationAction("Zealot's Defense (Sword 3)", "3", cooldown=12.0, cast_delay=1.8, cancellable=True),
            RotationAction("Weapon Swap to Greatsword", "`", cooldown=9.8, cast_delay=0.15, is_instant=True),
        ]
        self.state_machine.set_opener_sequence(opener)

        # -------------------------------------------------------------
        # 2. Sequential Looping Rotation (RE-RUNS INDEFINITELY UNTIL STOPPED)
        # Follows the exact Greatsword -> Sword/Focus combat cadence:
        # Yields to game's native auto-attacks during specified auto chains!
        # -------------------------------------------------------------
        loop_sequence = [
            # === GREATSWORD PHASE ===
            RotationAction("Symbol of Resolution (GS 4)", "4", cooldown=12.0, cast_delay=0.6, cancellable=True),
            RotationAction("Whirling Wrath (GS 2)", "2", cooldown=8.0, cast_delay=1.5, cancellable=True),
            RotationAction("Sword of Justice (Utility R)", "r", cooldown=15.0, cast_delay=0.3, cancellable=True, double_tap=True),
            RotationAction("Binding Blade (GS 5)", "5", cooldown=20.0, cast_delay=0.5, cancellable=True),
            RotationAction("Leap of Faith (GS 3)", "3", cooldown=12.0, cast_delay=0.8, cancellable=False),
            # Passive Auto-Attacks: Strike / Vengeful Strike / Wrathful Strike x2 (Yields without spamming '1')
            RotationAction("GS Auto-Attacks (Strike x2)", "1", cooldown=0.0, cast_delay=2.2, is_auto_attack=True),
            RotationAction("Whirling Wrath (GS 2)", "2", cooldown=8.0, cast_delay=1.5, cancellable=True),
            RotationAction("Symbol of Resolution (GS 4)", "4", cooldown=12.0, cast_delay=0.6, cancellable=True),
            # Passive Auto-Attack: Strike x1
            RotationAction("GS Auto-Attack (Strike x1)", "1", cooldown=0.0, cast_delay=1.0, is_auto_attack=True),
            RotationAction("Sword of Justice (Utility R)", "r", cooldown=15.0, cast_delay=0.3, cancellable=True, double_tap=True),
            # Swap to Sword/Focus
            RotationAction("Weapon Swap to Sword/Focus", "`", cooldown=9.8, cast_delay=0.15, is_instant=True),

            # === SWORD / FOCUS PHASE ===
            RotationAction("Zealot's Defense (Sword 3)", "3", cooldown=12.0, cast_delay=1.8, cancellable=True),
            RotationAction("Ray of Judgment (Focus 4)", "4", cooldown=13.0, cast_delay=0.5, cancellable=True),
            RotationAction("Symbol of Punishment / Blades (Skill 2)", "2", cooldown=8.0, cast_delay=0.4, cancellable=True, double_tap=True),
            # Passive Auto-Attacks: Sword of Wrath / Sword Arc / Sword Wave x5 (~4.5s natural cycle)
            RotationAction("Sword Auto-Attacks (Chains x5)", "1", cooldown=0.0, cast_delay=4.5, is_auto_attack=True),
            RotationAction("Symbol of Punishment / Blades (Skill 2)", "2", cooldown=8.0, cast_delay=0.4, cancellable=True, double_tap=True),
            RotationAction("Zealot's Defense (Sword 3)", "3", cooldown=12.0, cast_delay=1.8, cancellable=True),
            RotationAction("Shield of Wrath (Focus 5)", "5", cooldown=35.0, cast_delay=0.5, cancellable=True),
            # Swap back to Greatsword (Loop finishes and automatically re-runs from Step 1!)
            RotationAction("Weapon Swap to Greatsword", "`", cooldown=9.8, cast_delay=0.15, is_instant=True),
        ]
        self.state_machine.set_loop_sequence(loop_sequence)

        # -------------------------------------------------------------
        # 3. Off-GCD Virtues & Buffs (Weaved dynamically during burst windows)
        # Priority Order: F1 (Justice / M5) > F2 (Resolve / M4) > F3 (Courage / Shift+M5) > Advance! (E)
        # -------------------------------------------------------------
        virtues = [
            RotationAction("Virtue of Justice (F1 / M5)", "f1", cooldown=0.8, cast_delay=0.0, priority=100, is_instant=True),
            RotationAction("Virtue of Resolve (F2 / M4)", "f2", cooldown=0.8, cast_delay=0.0, priority=60, is_instant=True),
            RotationAction("Virtue of Courage (F3 / Shift+M5)", "f3", cooldown=0.8, cast_delay=0.0, priority=50, is_instant=True),
            RotationAction("Advance! (Utility E)", "e", cooldown=20.0, cast_delay=0.0, priority=45, is_instant=True),
        ]
        self.state_machine.set_mech_skills(virtues)

    def evaluate_condition(self, frame, detector):
        now = time.time()

        # Visual readiness filter for real-time priority candidate selection
        def is_action_ready_filter(act: RotationAction) -> bool:
            if act.is_auto_attack:
                return True
            if act.key == "`":
                # Weapon swap: check if weapon swap internal cooldown has passed
                return (now - self.last_weapon_swap_time) >= self.weapon_swap_cooldown
            if frame is None or frame.size == 0:
                return True
            slot_id = self.cooldown_detector.resolve_slot_id(act.key)
            if slot_id in self.cooldown_detector.slots:
                return self.cooldown_detector.is_slot_ready(frame, slot_id)
            return True

        next_action = self.state_machine.get_next_action(now, is_action_ready_fn=is_action_ready_filter)

        if not next_action:
            # In Auto-Attack or channel delay: safely yield
            self.pending_action = None
            return False, None

        self.pending_action = next_action
        return True, next_action

    def execute_action(self, input_ctrl: InputController) -> bool:
        now = time.time()
        action = self.pending_action or self.state_machine.get_next_action(now)
        if not action:
            return False

        loop_num = self.state_machine.loop_iteration
        phase_tag = f"[{self.state_machine.phase.value} #{loop_num}]"

        # Handle Passive Auto-Attack step: Do NOT send keystroke '1'
        if action.is_auto_attack:
            print(f"[CoreGuardian] {phase_tag} (Auto-Attacking: naturally cycling attack chain)")
            self.state_machine.record_action_cast(action, now)
            return True

        # Handle Weapon Swap
        if action.key == "`":
            print(f"[CoreGuardian] {phase_tag} >>> WEAPON SWAP (` key) <<<")
            success = input_ctrl.press_key("`")
            self.state_machine.record_action_cast(action, now)
            self.last_weapon_swap_time = now
            self.active_weapon_set = "greatsword" if self.active_weapon_set == "sword_focus" else "sword_focus"
            print(f"  -> Active set: {self.active_weapon_set.upper()}")
            time.sleep(0.08)
            return success

        # Execute standard skill or Virtue (supports double_tap for ground-targeted skills)
        dt_tag = " [Double-Tap Ground Target]" if action.double_tap else ""
        print(f"[CoreGuardian] {phase_tag} {action.name} -> Key '{action.key}'{dt_tag}")
        success = input_ctrl.press_key(action.key, double_tap=action.double_tap)
        self.state_machine.record_action_cast(action, now)

        # Aftercast clipping check:
        if "zealot" in action.name.lower() or "ray of judgment" in action.name.lower():
            time.sleep(0.04)

        return success


class ProfileCoreGuardian(BaseCharacterProfile):
    """
    Complete Character Profile for Guardian -> Core -> Core Guardian DPS.
    """
    def __init__(self):
        super().__init__(name="Core Guardian DPS", signature_template=None)
        self.rotation_behavior = CoreGuardianRotationBehavior()

    def setup_behaviors(self, detector: VisualDetector) -> None:
        self.register_behavior(self.rotation_behavior)

    def reset_rotation(self) -> None:
        """Resets to Opener on new engagement."""
        self.rotation_behavior.state_machine.reset_to_opener()
        self.rotation_behavior.active_weapon_set = "sword_focus"
