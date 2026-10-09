import sys
import os
sys.path.insert(0, os.path.abspath("."))
import time
from profiles.profile_core_guardian import CoreGuardianRotationBehavior

beh = CoreGuardianRotationBehavior()
# Set in-game realistic cooldowns for virtues
for m in beh.state_machine.mech_skills:
    m.cooldown = 20.0

current_time = 1000.0

for tick in range(12):
    matched, act = beh.evaluate_condition(None, None)
    step_info = f"loop_index={beh.state_machine.loop_index}, channeling={current_time < beh.state_machine.channel_end_time}, auto_until={beh.state_machine.auto_attack_until}"
    if matched and act:
        print(f"Tick {tick:2d} [T={current_time:.1f}]: Fired -> {act.name} ({step_info})")
        beh.execute_action(type("MockInput", (), {"press_key": lambda s, k: True})())
        current_time += act.cast_delay + 0.1
    else:
        print(f"Tick {tick:2d} [T={current_time:.1f}]: None ({step_info})")
        current_time += 0.2
