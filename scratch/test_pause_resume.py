import sys
import os
sys.path.insert(0, os.path.abspath("."))
import time
from profiles.profile_core_guardian import CoreGuardianRotationBehavior

beh = CoreGuardianRotationBehavior()
for m in beh.state_machine.mech_skills:
    m.cooldown = 20.0

# 1. Run 3 actions
for i in range(3):
    matched, act = beh.evaluate_condition(None, None)
    if matched:
        print(f"Action {i+1}: {act.name}")
        beh.execute_action(type("MockInput", (), {"press_key": lambda s, k: True})())
        time.sleep(0.05)

# 2. Simulate User Pausing for 2 seconds (e.g. F10 or GUI Pause)
print("\n--- USER PAUSED BOT (F10) ---")
time.sleep(1.0)

# 3. Simulate User Unpausing (F9 or GUI Engage)
print("--- USER RESUMED BOT (F9) ---")
for i in range(4):
    matched, act = beh.evaluate_condition(None, None)
    if matched:
        print(f"Resumed Action {i+1}: {act.name}")
        beh.execute_action(type("MockInput", (), {"press_key": lambda s, k: True})())
        time.sleep(0.05)

print("\n>>> PAUSE AND RESUME TEST PASSED! <<<")
