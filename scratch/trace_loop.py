import sys
import os
sys.path.insert(0, os.path.abspath("."))
import time
from profiles.profile_core_guardian import CoreGuardianRotationBehavior

beh = CoreGuardianRotationBehavior()
current_time = 1000.0

# Simulate: Opener completes, and virtues are on cooldown (realistic in-game)
# Let's see what loop_skills fire:
for step in range(25):
    # Virtues are on cooldown
    def is_ready_fn(act):
        if act.key in ["f1", "f2", "f3"]:
            return False
        return True

    act = beh.state_machine.get_next_action(current_time, is_action_ready_fn=is_ready_fn)
    if act:
        print(f"Step {step:2d} [T={current_time:.1f}]: Fired -> {act.name} (Key: {act.key}, CD={act.cooldown}s)")
        beh.state_machine.record_action_cast(act, current_time)
        current_time += act.cast_delay + 0.1
    else:
        print(f"Step {step:2d} [T={current_time:.1f}]: No action ready (ALL ON COOLDOWN / END OF ACTIONS)")
        current_time += 0.5
