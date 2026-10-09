import cv2
import numpy as np

hud = cv2.imread("scratch/measured_hud.png")

# Let's test two sets of boxes:
# Set A: x=(98, 126, 154), y=41, w=27, h=30
# Set B: x=(100, 128, 156), y=41, w=27, h=30
# Set C: x=(99, 127, 155), y=42, w=26, h=29

for label, (v1, v2, v3) in [
    ("A", ((98, 41, 27, 30), (126, 41, 27, 30), (154, 41, 27, 30))),
    ("B", ((100, 41, 27, 30), (128, 41, 27, 30), (156, 41, 27, 30))),
    ("C", ((99, 42, 26, 29), (127, 42, 26, 29), (155, 42, 26, 29)))
]:
    vis = hud.copy()
    for b in [v1, v2, v3]:
        cv2.rectangle(vis, (b[0], b[1]), (b[0]+b[2], b[1]+b[3]), (0, 255, 0), 1)
    
    # Crop the virtue area
    crop = vis[35:75, 90:190]
    crop_4x = cv2.resize(crop, (crop.shape[1]*4, crop.shape[0]*4), interpolation=cv2.INTER_NEAREST)
    cv2.imwrite(f"scratch/virtues_set_{label}.png", crop_4x)

print("Saved sets A, B, C.")
