import sys
import os
sys.path.insert(0, os.path.abspath("."))
import time
from profiles.profile_core_guardian import CoreGuardianRotationBehavior

beh = CoreGuardianRotationBehavior()
for m in beh.state_machine.mech_skills:
    m.cooldown = 20.0

actions_log = []
t0 = time.time()

# Run a real-time simulation for 15 seconds:
print("Starting real-time simulation of Core Guardian rotation...")
start_time = time.time()

while time.time() - start_time < 12.0:
    matched, act = beh.evaluate_condition(None, None)
    if matched and act:
        now = time.time()
        actions_log.append((now - t0, act.name, act.key, act.is_auto_attack))
        beh.execute_action(type("MockInput", (), {"press_key": lambda s, k: True})())
    time.sleep(0.05)

for elapsed, name, key, is_auto in actions_log:
    auto_tag = " [AUTO-ATTACK YIELD]" if is_auto else ""
    print(f"{elapsed:5.2f}s | Key: {key:2s} | {name}{auto_tag}")

print(f"\nTotal actions executed: {len(actions_log)}")
print(f"Current Phase: {beh.state_machine.phase.value}")
print(f"Current Loop Iteration: {beh.state_machine.loop_iteration}")
print(f"Current Loop Step Index: {beh.state_machine.loop_index}/{len(beh.state_machine.loop_steps)}")
