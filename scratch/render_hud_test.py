import sys
import os
sys.path.insert(0, os.path.abspath("."))
import cv2
import numpy as np
from core.cooldown_detector import UniversalCooldownDetector

# Load user's HUD crop
frame = cv2.imread("scratch/measured_hud.png")
h, w = frame.shape[:2]

# Test rendering Guardian Core
cd_guard = UniversalCooldownDetector(profession="Guardian", spec="Core")
disp_guard = frame.copy()
statuses_guard = cd_guard.get_all_slot_statuses(frame)

for s_id, st in statuses_guard.items():
    sx, sy, sw, sh = st.bounding_box
    box_color = (60, 220, 80) if st.is_ready else (40, 50, 230)
    cv2.rectangle(disp_guard, (sx, sy), (sx + sw, sy + sh), box_color, 2)
    if s_id.startswith("mech_"):
        m_num = s_id.replace("mech_f", "")
        v_names = {"1": "V1(M5)", "2": "V2(M4)", "3": "V3(Shift+M5)"}
        short_name = v_names.get(m_num, f"V{m_num}")
    else:
        short_name = s_id.replace("weapon_", "W").replace("utility_", "U").replace("heal", "Heal").replace("elite", "Elite")
    tag = f"{short_name}" if st.is_ready else f"{short_name}:CD"
    cv2.putText(disp_guard, tag, (sx + 2, sy + 13), cv2.FONT_HERSHEY_SIMPLEX, 0.32, box_color, 1)

# Add duo banner
cv2.rectangle(disp_guard, (0, 0), (w, 18), (20, 20, 20), -1)
cv2.putText(disp_guard, "ACTIVE DUO: [ GUARDIAN | CORE ] - 3 VIRTUES", (6, 13), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (100, 220, 255), 1)

cv2.imwrite("scratch/simulated_live_hud_guardian.png", disp_guard)
print("Saved scratch/simulated_live_hud_guardian.png")

# Now let's crop just the virtue area at 3x zoom to verify the bounding boxes
virtue_zoom = disp_guard[20:80, 85:195].copy()
virtue_zoom_3x = cv2.resize(virtue_zoom, (virtue_zoom.shape[1]*3, virtue_zoom.shape[0]*3), interpolation=cv2.INTER_NEAREST)
cv2.imwrite("scratch/virtues_perfect_fit_verified.png", virtue_zoom_3x)
print("Saved scratch/virtues_perfect_fit_verified.png")
