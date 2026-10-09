"""
Rotation Framework: Opener and Looping Rotation Engine.
Provides a universal state machine for all character builds:
1. Opener Sequence (deterministic ordered execution upon engaging)
2. Looping Rotation (priority queue + combo follow-ups + kit/weapon swap management)
3. Off-GCD / Secondary Priority Track (e.g. Mech commands)
"""

from enum import Enum
from typing import List, Dict, Optional, Callable, Any
import time


class RotationPhase(Enum):
    OPENER = "OPENER"
    LOOP = "LOOP"


class RotationAction:
    """Represents an individual combat action in a rotation."""
    def __init__(
        self,
        name: str,
        key: str,
        cooldown: float,
        requires_kit: Optional[str] = None,
        kit_toggle_key: str = "r",
        cast_delay: float = 0.45,
        priority: int = 50,
        is_instant: bool = False,
        cancellable: bool = True,
        is_auto_attack: bool = False,
        double_tap: bool = False,
        min_resource: Optional[float] = None,
        max_resource: Optional[float] = None,
        resource_type: Optional[str] = None
    ):
        self.name = name
        self.key = key
        self.cooldown = cooldown
        self.requires_kit = requires_kit
        self.kit_toggle_key = kit_toggle_key
        self.cast_delay = cast_delay
        self.priority = priority
        self.is_instant = is_instant
        self.cancellable = cancellable
        self.is_auto_attack = is_auto_attack
        self.double_tap = double_tap
        self.min_resource = float(min_resource) if min_resource is not None else None
        self.max_resource = float(max_resource) if max_resource is not None else None
        self.resource_type = resource_type
        self.last_cast_time: float = 0.0

    def is_off_cooldown(self, current_time: float) -> bool:
        return (current_time - self.last_cast_time) >= self.cooldown

    def record_cast(self, current_time: float) -> None:
        self.last_cast_time = current_time


class RotationStateMachine:
    """
    Manages transitions between Opener sequence and Looping rotation.
    Supports both:
    1. Sequential looping mode (repeating ordered steps indefinitely with auto-attack windows)
    2. Dynamic priority list mode.
    Protects channel completion with humanized ~15% eager cancellation slips.
    """

    def __init__(self, name: str, cancel_slip_probability: float = 0.15):
        self.name = name
        self.phase = RotationPhase.OPENER
        self.opener_index = 0
        self.opener_steps: List[RotationAction] = []
        
        # Sequential Looping rules (Re-runs indefinitely once done!)
        self.loop_steps: List[RotationAction] = []
        self.loop_index: int = 0
        self.loop_iteration: int = 1
        self.auto_attack_until: float = 0.0

        # Dynamic priority list rules (fallback)
        self.loop_skills: List[RotationAction] = []
        self.mech_skills: List[RotationAction] = []
        
        # State tracking
        self.active_kit: Optional[str] = None
        self.last_cast_action: Optional[RotationAction] = None
        self.combo_queue: List[RotationAction] = []

        # Channel & cast tracking
        self.channel_end_time: float = 0.0
        self.current_channel_action: Optional[RotationAction] = None
        self.cancel_slip_probability = cancel_slip_probability

    def reset_to_opener(self) -> None:
        """Resets combat state back to the Opener sequence (e.g. on fresh target)."""
        self.phase = RotationPhase.OPENER
        self.opener_index = 0
        self.loop_index = 0
        self.loop_iteration = 1
        self.auto_attack_until = 0.0
        self.active_kit = None
        self.combo_queue.clear()
        print(f"\n[Rotation] Resetting to OPENER sequence for '{self.name}'.")

    def set_opener_sequence(self, steps: List[RotationAction]) -> None:
        self.opener_steps = steps

    def set_loop_sequence(self, steps: List[RotationAction]) -> None:
        """Sets an ordered sequential loop that re-runs continuously until stopped."""
        self.loop_steps = steps
        self.loop_index = 0
        self.loop_iteration = 1

    def set_loop_skills(self, skills: List[RotationAction]) -> None:
        # Sort loop skills by priority descending
        self.loop_skills = sorted(skills, key=lambda s: s.priority, reverse=True)

    def set_mech_skills(self, skills: List[RotationAction]) -> None:
        # Sort mech skills by priority descending
        self.mech_skills = sorted(skills, key=lambda s: s.priority, reverse=True)

    def record_action_cast(self, action: RotationAction, current_time: float) -> None:
        """Records an action cast, advances opener/loop sequence, and initiates channel window."""
        action.record_cast(current_time)
        self.last_cast_action = action

        # 1. Opener advancement
        if self.phase == RotationPhase.OPENER:
            self.opener_index += 1
            if self.opener_index >= len(self.opener_steps):
                print(f"\n[Rotation] Opener complete! Transitioning into LOOPING rotation (Loop 1).")
                self.phase = RotationPhase.LOOP
                self.loop_index = 0

        # 2. Sequential Loop advancement (Re-runs indefinitely!)
        elif self.phase == RotationPhase.LOOP and self.loop_steps:
            # Advance if the executed action matches the current loop step
            if self.loop_index < len(self.loop_steps) and action == self.loop_steps[self.loop_index]:
                self.loop_index = (self.loop_index + 1) % len(self.loop_steps)
                if self.loop_index == 0:
                    self.loop_iteration += 1
                    print(f"\n[Rotation] === COMPLETED LOOP ITERATION {self.loop_iteration - 1}! RE-RUNNING LOOP ITERATION {self.loop_iteration} ===")

        if not action.is_instant and not action.is_auto_attack:
            self.current_channel_action = action
            self.channel_end_time = current_time + action.cast_delay

    def get_next_action(
        self,
        current_time: float,
        is_action_ready_fn: Optional[Callable[[RotationAction], bool]] = None
    ) -> Optional[RotationAction]:
        """
        Determines the next action according to Opener sequence or Looping rotation.
        Protects ongoing channels while allowing Off-GCD skills and simulating ~15% eager human cancels.
        Dynamically filters candidates by visual screen readiness when provided.
        """
        import random

        # 1. Any queued combo follow-up takes absolute priority
        if self.combo_queue:
            return self.combo_queue.pop(0)

        # 2. PHASE: OPENER (Strict ordered sequence)
        if self.phase == RotationPhase.OPENER:
            if self.opener_index < len(self.opener_steps):
                candidate = self.opener_steps[self.opener_index]
                if is_action_ready_fn and not is_action_ready_fn(candidate):
                    # Waiting for slot or weapon swap to be ready on screen
                    return None
                return candidate
            else:
                self.phase = RotationPhase.LOOP
                self.loop_index = 0

        # 3. Off-GCD / Mech Skills (Virtues, Pet Commands): Can weave during or between skills
        for mech_act in self.mech_skills:
            if mech_act.is_off_cooldown(current_time):
                if is_action_ready_fn and not is_action_ready_fn(mech_act):
                    continue  # Visually on cooldown on screen -> skip
                return mech_act

        # 4. Channel completion protection
        channeling = current_time < self.channel_end_time

        # 5. PHASE: LOOP (Sequential Re-running Loop Mode)
        if self.loop_steps:
            # Check passive auto-attack window: do not press buttons while naturally swinging!
            if current_time < self.auto_attack_until:
                return None

            if self.loop_index >= len(self.loop_steps):
                self.loop_index = 0
                self.loop_iteration += 1
                print(f"\n[Rotation] === RE-RUNNING LOOP ITERATION {self.loop_iteration} ===")

            step = self.loop_steps[self.loop_index]

            # Handle Passive Auto-Attack step
            if step.is_auto_attack:
                self.auto_attack_until = current_time + step.cast_delay
                print(f"  [AUTO-ATTACK] Yielding for natural game attack chain ({step.cast_delay:.1f}s)...")
                self.loop_index = (self.loop_index + 1) % len(self.loop_steps)
                if self.loop_index == 0:
                    self.loop_iteration += 1
                    print(f"\n[Rotation] === COMPLETED LOOP ITERATION {self.loop_iteration - 1}! RE-RUNNING LOOP ITERATION {self.loop_iteration} ===")
                return None

            if channeling:
                return None

            # Weapon skill step: Check screen visual readiness
            if is_action_ready_fn and not is_action_ready_fn(step):
                # Next skill in loop is on a brief cooldown -> yield to auto-attack until ready!
                return None
            return step

        # 6. Fallback: Dynamic Priority List Mode (Used when loop_steps is not configured)
        for skill in self.loop_skills:
            if skill.is_off_cooldown(current_time):
                # If caller provided visual readiness filter, check it!
                if is_action_ready_fn and not is_action_ready_fn(skill):
                    continue  # Visually on cooldown on screen -> skip to next candidate!

                if channeling:
                    # Human Imperfection: ~15% chance to eagerly cancel/clip a channel with higher-priority skill
                    if (
                        self.current_channel_action and
                        self.current_channel_action.cancellable and
                        skill.priority > self.current_channel_action.priority
                    ):
                        if random.random() < self.cancel_slip_probability:
                            print(f"  [HUMAN IMPERFECTION] ~15% Eager Clip: Prematurely cancelled '{self.current_channel_action.name}' to fire '{skill.name}'!")
                            self.channel_end_time = 0.0
                            self.current_channel_action = None
                            return skill

                    # 85% of the time, patient human lets channel complete before pressing next on-GCD skill
                    continue

                return skill

        return None


