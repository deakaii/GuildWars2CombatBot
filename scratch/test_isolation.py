import sys
import os
sys.path.insert(0, os.path.abspath("."))
import cv2
import numpy as np

# Test the clean isolation of mechanic slots
from core.cooldown_detector import UniversalCooldownDetector

frame = cv2.imread("scratch/measured_hud.png")

# Case 1: Guardian Core
det_guard = UniversalCooldownDetector(profession="Guardian", spec="Core")
slots_guard = det_guard.slots
print(f"Guardian Core slots count: {len(slots_guard)}")
print("Guardian mech slots:", [k for k in slots_guard if k.startswith("mech_")])
for k, v in slots_guard.items():
    if k.startswith("mech_"):
        print(f"  {k}: {v}")

# Case 2: Engineer Mechanist
det_mech = UniversalCooldownDetector(profession="Engineer", spec="Mechanist")
slots_mech = det_mech.slots
print(f"Engineer Mechanist slots count: {len(slots_mech)}")
print("Mechanist mech slots:", [k for k in slots_mech if k.startswith("mech_")])
for k, v in slots_mech.items():
    if k.startswith("mech_"):
        print(f"  {k}: {v}")

# Case 3: Other profession (e.g. Warrior)
det_war = UniversalCooldownDetector(profession="Warrior", spec="Spellbreaker")
slots_war = det_war.slots
print(f"Warrior Spellbreaker slots count: {len(slots_war)}")
print("Warrior mech slots (should be empty, no carry-over):", [k for k in slots_war if k.startswith("mech_")])
