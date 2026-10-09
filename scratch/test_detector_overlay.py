import sys
import os
sys.path.insert(0, os.path.abspath("."))
import cv2
import numpy as np
from core.cooldown_detector import UniversalCooldownDetector

img = cv2.imread("scratch/current_hud_crop.png")
detector = UniversalCooldownDetector()
detector.set_composite("Guardian", "Core")

statuses = detector.get_all_slot_statuses(img)
vis = detector.render_overlay(img, statuses)
cv2.imwrite("scratch/current_hud_overlay.png", vis)
print("Saved scratch/current_hud_overlay.png")

for slot_id, status in statuses.items():
    print(f"Slot: {slot_id:12s} Ready: {str(status.is_ready):5s} Box: {status.bounding_box}")
