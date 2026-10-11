"""
Simple Off-Cooldown Priority Rotation (no opener).

A rotation is one small YAML file per spec: config/rotations/{profession}_{spec}.yaml

    priority: [2, 3, 4, 5, 7, 0]   # skill-bar numbers; the first READY one is pressed
    double_tap:   {5: 0.25}        # ground-targeted skills: press twice, N seconds apart
    no_interrupt: {2: 0.75}        # cancelled if anything is cast over it: hold N seconds

Readiness comes only from the on-screen cooldown detector (no timers), so cooldown
reduction effects are handled automatically.

Pacing follows the game's skill queue: while one skill is casting, ONE more press may
queue behind it; further presses wait until the casting skill shows its cooldown (it
went off). Nothing is ever pressed while a no_interrupt skill is casting. A skill that
never goes on cooldown (out of range, no target) is skipped briefly instead of spammed.
"""

import os
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

import yaml

from behaviors.base import BaseBehavior
from core.cooldown_detector import UniversalCooldownDetector
from core.detector import VisualDetector
from core.input_controller import InputController
from profiles.base_profile import BaseCharacterProfile

ROTATIONS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "rotations")

# Skill-bar number -> cooldown detector slot
SKILL_SLOTS = {
    "1": "weapon_1", "2": "weapon_2", "3": "weapon_3", "4": "weapon_4", "5": "weapon_5",
    "6": "heal", "7": "utility_1", "8": "utility_2", "9": "utility_3", "0": "elite",
    "swap": "weapon_swap",
}

MAX_WAIT_FOR_COOLDOWN = 1.2   # seconds a press may stay "outstanding" without showing a cooldown
FAILED_SKILL_BACKOFF = 1.5    # seconds to skip a skill that was pressed but never went off
MAX_QUEUED = 2                # the casting skill + one queued behind it (the game's queue depth)


@dataclass
class SimpleRotation:
    name: str
    priority: List[str]
    double_tap: Dict[str, float] = field(default_factory=dict)
    no_interrupt: Dict[str, float] = field(default_factory=dict)


def rotation_path(profession: str, spec: str) -> str:
    p = profession.lower().strip().replace(" ", "_")
    s = spec.lower().strip().replace(" ", "_")
    return os.path.join(ROTATIONS_DIR, f"{p}_{s}.yaml")


def parse_simple_rotation(data: Dict[str, Any], default_name: str = "Rotation") -> SimpleRotation:
    """Validates a rotation dict. Raises ValueError with a readable message on mistakes."""
    def skill(v) -> str:
        k = str(v).strip().lower()
        if k not in SKILL_SLOTS:
            raise ValueError(f"'{v}' is not a skill-bar number (use 1-9, 0, or swap)")
        return k

    raw_priority = data.get("priority") or []
    if not isinstance(raw_priority, list) or not raw_priority:
        raise ValueError("'priority' must be a list of skill-bar numbers, e.g. [2, 3, 4, 5, 7, 0]")
    priority = [skill(v) for v in raw_priority]

    def seconds_map(key: str) -> Dict[str, float]:
        raw = data.get(key) or {}
        if not isinstance(raw, dict):
            raise ValueError(f"'{key}' must map skill numbers to seconds, e.g. {{5: 0.25}}")
        return {skill(k): float(v) for k, v in raw.items()}

    return SimpleRotation(
        name=str(data.get("name") or default_name),
        priority=priority,
        double_tap=seconds_map("double_tap"),
        no_interrupt=seconds_map("no_interrupt"),
    )


def load_simple_rotation(profession: str, spec: str) -> Optional[SimpleRotation]:
    """Loads config/rotations/{profession}_{spec}.yaml, or None if there isn't one."""
    path = rotation_path(profession, spec)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return parse_simple_rotation(data, default_name=f"{profession} {spec}".title())


@dataclass
class _Press:
    skill: str
    pressed_at: float
    hold: float          # no_interrupt: minimum seconds before anything else may be pressed
    went_off: bool = False


class SimpleRotationBehavior(BaseBehavior):
    """Presses the highest-priority ready skill, following the game's one-deep skill queue."""

    def __init__(
        self,
        rotation: SimpleRotation,
        cooldown_detector: UniversalCooldownDetector,
        clock: Callable[[], float] = time.time,
        log: Callable[[str], None] = print,
    ):
        super().__init__(name=f"{rotation.name}Rotation", priority=100, cooldown_seconds=0.0, cooldown_jitter_ratio=0.0)
        self.rotation = rotation
        self.cooldown_detector = cooldown_detector
        self.clock = clock
        self.log = log
        self.outstanding: List[_Press] = []    # pressed, not yet seen going on cooldown
        self.backoff_until: Dict[str, float] = {}
        self.next_skill: Optional[str] = None

    def is_on_cooldown(self, current_time: float) -> bool:
        return False   # pacing is handled by the skill-queue logic below, every engine tick

    # -- screen readings ---------------------------------------------------------------
    def _status(self, frame, skill: str):
        return self.cooldown_detector.get_slot_status(frame, SKILL_SLOTS[skill])

    def _is_ready(self, frame, skill: str) -> bool:
        st = self._status(frame, skill)
        return bool(st and st.is_ready)

    def _shows_cooldown(self, frame, skill: str) -> bool:
        st = self._status(frame, skill)
        return bool(st and not st.raw_is_ready)

    # -- decision ----------------------------------------------------------------------
    def _update_outstanding(self, frame, now: float) -> None:
        still = []
        for p in self.outstanding:
            if not p.went_off and self._shows_cooldown(frame, p.skill):
                p.went_off = True
            elapsed = now - p.pressed_at
            if p.went_off and elapsed >= p.hold:
                continue                                   # done
            if elapsed >= max(MAX_WAIT_FOR_COOLDOWN, p.hold + 1.0):
                if not p.went_off:
                    self.backoff_until[p.skill] = now + FAILED_SKILL_BACKOFF
                    self.log(f"[Rotation] Skill {p.skill} didn't go off (out of range / no target?); skipping it briefly.")
                continue
            still.append(p)
        self.outstanding = still

    def evaluate_condition(self, frame, detector: VisualDetector) -> Tuple[bool, Any]:
        self.next_skill = None
        if frame is None or getattr(frame, "size", 0) == 0:
            return False, None
        now = self.clock()
        self._update_outstanding(frame, now)

        # Never cast over a no_interrupt skill; otherwise allow one press queued behind a cast
        if any(p.skill in self.rotation.no_interrupt for p in self.outstanding):
            return False, None
        if len(self.outstanding) >= MAX_QUEUED:
            return False, None

        busy = {p.skill for p in self.outstanding}
        for skill in self.rotation.priority:
            if skill in busy or now < self.backoff_until.get(skill, 0.0):
                continue
            if self._is_ready(frame, skill):
                self.next_skill = skill
                return True, skill
        return False, None

    def execute_action(self, input_controller: InputController) -> bool:
        skill = self.next_skill
        self.next_skill = None
        if not skill:
            return False
        gap = self.rotation.double_tap.get(skill)
        if gap is not None:
            ok = input_controller.press_key(skill, double_tap=True, double_tap_gap=gap)
        else:
            ok = input_controller.press_key(skill)
        if not ok:
            return False
        hold = self.rotation.no_interrupt.get(skill, 0.0)
        self.outstanding.append(_Press(skill, self.clock(), hold))
        extra = f" (double-tap, {gap:.2f}s)" if gap is not None else ""
        extra += f" (no-interrupt {hold:.2f}s)" if hold else ""
        extra += " (queued)" if len(self.outstanding) > 1 else ""
        self.log(f"[{self.rotation.name}] Skill {skill}{extra}")
        return True


class SimpleRotationProfile(BaseCharacterProfile):
    """Profile wrapper so the engine/GUI can run a simple rotation file."""

    def __init__(self, rotation: SimpleRotation, profession: str = "", spec: str = ""):
        super().__init__(name=rotation.name, signature_template=None)
        self.rotation_behavior = SimpleRotationBehavior(
            rotation, UniversalCooldownDetector(profession=profession, spec=spec)
        )

    def setup_behaviors(self, detector: VisualDetector) -> None:
        self.register_behavior(self.rotation_behavior)

    def reset_rotation(self) -> None:
        self.rotation_behavior.outstanding.clear()
        self.rotation_behavior.backoff_until.clear()
