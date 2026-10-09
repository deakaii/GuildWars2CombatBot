import sys
import os
sys.path.insert(0, os.path.abspath("."))
import cv2
import numpy as np
from core.cooldown_detector import UniversalCooldownDetector

frame = cv2.imread("scratch/current_hud_crop.png")
cd_det = UniversalCooldownDetector(profession="Guardian", spec="Core")

display = frame.copy()
slot_statuses = cd_det.get_all_slot_statuses(frame)

for s_id, st in slot_statuses.items():
    sx, sy, sw, sh = st.bounding_box
    box_color = (60, 220, 80) if st.is_ready else (40, 50, 230)
    cv2.rectangle(display, (sx, sy), (sx + sw, sy + sh), box_color, 2)
    cv2.putText(display, s_id, (sx, sy - 2), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 255, 255), 1)

cv2.imwrite("scratch/simulated_live_hud.png", display)
print("Saved scratch/simulated_live_hud.png")
