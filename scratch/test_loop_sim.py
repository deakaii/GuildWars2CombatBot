import sys
import os
sys.path.insert(0, os.path.abspath("."))
import time

# Let's test a sequential looping state machine prototype
class Action:
    def __init__(self, name, key, cast_delay=0.5, is_auto_attack=False, is_instant=False):
        self.name = name
        self.key = key
        self.cast_delay = cast_delay
        self.is_auto_attack = is_auto_attack
        self.is_instant = is_instant

opener = [
    Action("Shield of Wrath (Focus 5)", "5", 0.5),
    Action("Sword of Justice (Utility R)", "r", 0.3),
    Action("Ray of Judgment (Focus 4)", "4", 0.5),
    Action("Symbol of Blades (Sword 2)", "2", 0.4),
    Action("Zealot's Defense (Sword 3)", "3", 1.8),
    Action("Weapon Swap to Greatsword", "`", 0.1, is_instant=True),
]

loop = [
    Action("Symbol of Resolution (GS 4)", "4", 0.6),
    Action("Whirling Wrath (GS 2)", "2", 1.5),
    Action("Sword of Justice (Utility R)", "r", 0.3),
    Action("Binding Blade (GS 5)", "5", 0.5),
    Action("Leap of Faith (GS 3)", "3", 0.8),
    Action("GS Auto-Attacks (Strike x2)", "1", 2.0, is_auto_attack=True),
    Action("Whirling Wrath (GS 2)", "2", 1.5),
    Action("Symbol of Resolution (GS 4)", "4", 0.6),
    Action("GS Auto-Attack (Strike x1)", "1", 1.0, is_auto_attack=True),
    Action("Sword of Justice (Utility R)", "r", 0.3),
    Action("Weapon Swap to Sword/Focus", "`", 0.1, is_instant=True),
    Action("Zealot's Defense (Sword 3)", "3", 1.8),
    Action("Ray of Judgment (Focus 4)", "4", 0.5),
    Action("Symbol of Blades (Sword 2)", "2", 0.4),
    Action("Sword Auto-Attacks (Chains x5)", "1", 4.5, is_auto_attack=True),
    Action("Symbol of Blades (Sword 2)", "2", 0.4),
    Action("Zealot's Defense (Sword 3)", "3", 1.8),
    Action("Shield of Wrath (Focus 5)", "5", 0.5),
    Action("Weapon Swap to Greatsword", "`", 0.1, is_instant=True),
]

# Simulate running opener then 2 full loops
phase = "OPENER"
opener_idx = 0
loop_idx = 0
loop_counter = 1

history = []

for step in range(50):
    if phase == "OPENER":
        act = opener[opener_idx]
        opener_idx += 1
        history.append(f"OPENER: {act.name}")
        if opener_idx >= len(opener):
            phase = "LOOP"
            history.append("--- TRANSITION TO LOOP ---")
    else:
        act = loop[loop_idx]
        history.append(f"LOOP {loop_counter} [Step {loop_idx+1}/{len(loop)}]: {act.name}")
        loop_idx += 1
        if loop_idx >= len(loop):
            loop_idx = 0
            loop_counter += 1
            history.append(f"=== LOOP FINISHED -> RE-RUNNING LOOP {loop_counter} ===")

for h in history[:30]:
    print(h)
print(f"... Total steps simulated: {len(history)}, Reached Loop {loop_counter}")
