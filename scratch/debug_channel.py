import sys
import os
sys.path.insert(0, os.path.abspath("."))
import time
from profiles.profile_core_guardian import CoreGuardianRotationBehavior

beh = CoreGuardianRotationBehavior()
for m in beh.state_machine.mech_skills:
    m.cooldown = 20.0

current_time = 1000.0

for tick in range(15):
    matched, act = beh.evaluate_condition(None, None)
    print(f"Tick {tick:2d} [T={current_time:.2f}]: channel_end={beh.state_machine.channel_end_time:.2f}, channeling={current_time < beh.state_machine.channel_end_time}")
    if matched and act:
        print(f"  -> Action: {act.name}")
        beh.execute_action(type("MockInput", (), {"press_key": lambda s, k: True})())
        current_time += act.cast_delay + 0.1
    else:
        current_time += 0.5
