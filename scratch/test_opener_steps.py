import sys
import os
sys.path.insert(0, os.path.abspath("."))
import time
from profiles.profile_core_guardian import ProfileCoreGuardian
from core.detector import VisualDetector
from core.input_controller import InputController

prof = ProfileCoreGuardian()
det = VisualDetector()
prof.setup_behaviors(det)
rot = prof.rotation_behavior
mock_ctrl = InputController({}, {"require_game_focus": False})

for i in range(7):
    matched, act = rot.evaluate_condition(None, det)
    print(f"Index {rot.state_machine.opener_index}: matched={matched}, act={act.name if act else None}, key={act.key if act else None}")
    if matched:
        rot.execute_action(mock_ctrl)
