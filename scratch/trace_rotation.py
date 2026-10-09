import sys
import os
sys.path.insert(0, os.path.abspath("."))
import time
from profiles.profile_core_guardian import CoreGuardianRotationBehavior

beh = CoreGuardianRotationBehavior()
print(f"Initial Phase: {beh.state_machine.phase}")

current_time = 1000.0

# Simulate execution of actions
for step in range(30):
    matched, act = beh.evaluate_condition(None, None)
    if matched:
        print(f"Step {step:2d} [T={current_time:.1f}]: Fired -> {act.name} (Key: {act.key})")
        beh.state_machine.record_action_cast(act, current_time)
        current_time += act.cast_delay + 0.1
    else:
        print(f"Step {step:2d} [T={current_time:.1f}]: No action ready (matched={matched})")
        current_time += 0.5
