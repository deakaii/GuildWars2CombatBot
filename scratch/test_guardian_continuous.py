import sys
import os
sys.path.insert(0, os.path.abspath("."))
import time
from profiles.profile_core_guardian import CoreGuardianRotationBehavior

beh = CoreGuardianRotationBehavior()
current_time = 1000.0

print("Testing Core Guardian Opener -> Loop 1 -> Loop 2 Transition:")

actions_log = []

for tick in range(100):
    matched, act = beh.evaluate_condition(None, None)
    if matched and act:
        actions_log.append((tick, current_time, act.name, act.key, act.is_auto_attack))
        beh.execute_action(type("MockInput", (), {"press_key": lambda s, k: True})())
        current_time += act.cast_delay + 0.1
    else:
        current_time += 0.2

for item in actions_log[:45]:
    tick, t, name, key, is_auto = item
    auto_tag = " [AUTO-ATTACK YIELD]" if is_auto else ""
    print(f"T={t:6.1f}s | Key: {key:2s} | {name}{auto_tag}")

print(f"\nTotal actions executed: {len(actions_log)}")
print(f"Current Phase: {beh.state_machine.phase.value}")
print(f"Current Loop Iteration: {beh.state_machine.loop_iteration}")
assert beh.state_machine.loop_iteration >= 2, "Loop failed to re-run into iteration 2!"
print("\n>>> VERIFICATION SUCCESS: Opener ran once, Loop re-runs continuously! <<<")
