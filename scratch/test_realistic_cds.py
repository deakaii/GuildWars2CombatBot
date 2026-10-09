import sys
import os
sys.path.insert(0, os.path.abspath("."))
import time
from profiles.profile_core_guardian import CoreGuardianRotationBehavior

beh = CoreGuardianRotationBehavior()
# Set in-game realistic cooldowns for virtues
for m in beh.state_machine.mech_skills:
    if "justice" in m.name.lower():
        m.cooldown = 20.0
    elif "resolve" in m.name.lower():
        m.cooldown = 30.0
    elif "courage" in m.name.lower():
        m.cooldown = 40.0
    elif "advance" in m.name.lower():
        m.cooldown = 20.0

current_time = 1000.0
actions_log = []

for tick in range(120):
    matched, act = beh.evaluate_condition(None, None)
    if matched and act:
        actions_log.append((tick, current_time, act.name, act.key, act.is_auto_attack))
        beh.execute_action(type("MockInput", (), {"press_key": lambda s, k: True})())
        current_time += act.cast_delay + 0.1
    else:
        current_time += 0.2

for item in actions_log:
    tick, t, name, key, is_auto = item
    auto_tag = " [AUTO-ATTACK YIELD]" if is_auto else ""
    print(f"T={t:6.1f}s | Key: {key:2s} | {name}{auto_tag}")

print(f"\nTotal actions executed: {len(actions_log)}")
print(f"Current Loop Iteration: {beh.state_machine.loop_iteration}")
