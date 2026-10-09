import sys
import os
sys.path.insert(0, os.path.abspath("."))
import cv2
import numpy as np
from core.cooldown_detector import UniversalCooldownDetector

frame = cv2.imread("scratch/current_hud_crop.png")
H, W = frame.shape[:2]
print(f"HUD Frame size: {W}x{H}")

cd_det = UniversalCooldownDetector(profession="Guardian", spec="Core")
slot_statuses = cd_det.get_all_slot_statuses(frame)

os.makedirs("scratch/slots_debug", exist_ok=True)
for s_id, st in slot_statuses.items():
    sx, sy, sw, sh = st.bounding_box
    crop = frame[sy:sy+sh, sx:sx+sw]
    cv2.imwrite(f"scratch/slots_debug/{s_id}.png", crop)
    print(f"Slot {s_id:12s}: rect=({sx}, {sy}, {sw}, {sh}) ready={st.is_ready} black_ratio={st.black_sweep_ratio:.2f}")
