import cv2
import numpy as np

hud = cv2.imread("scratch/measured_hud.png")
H, W = hud.shape[:2] # 136, 491

# Let's inspect the exact pixel bounds of the 3 virtues:
# Strip was: hud[20:85, 90:185]
# Let's find the 3 virtue icons by checking brightness/contrast:
# In strip (y from 20 to 85, x from 90 to 185 in hud):
# Let's test candidate bounding boxes:
# Let's calculate the bounding boxes:
# V1 (Virtue of Justice - M5):
# Top of icon in hud: y is around 40 to 42
# Bottom of icon in hud: y is around 70 to 72
# Left of V1 in hud: x is around 97 to 100
# Right of V1 in hud: x is around 125 to 128
# Width ~ 27, Height ~ 30
# V2 (Virtue of Resolve - M4):
# Left of V2 in hud: x is around 126 to 129
# Right of V2 in hud: x is around 154 to 157
# V3 (Virtue of Courage - Shift+M5):
# Left of V3 in hud: x is around 155 to 158
# Right of V3 in hud: x is around 183 to 186

# Let's test these candidate boxes:
v1_box = (98, 41, 27, 30)
v2_box = (126, 41, 27, 30)
v3_box = (154, 41, 27, 30)

# Also let's check what normalized coordinates these give in W=491, H=136:
nx1, ny1, nw1, nh1 = v1_box[0] / W, v1_box[1] / H, v1_box[2] / W, v1_box[3] / H
nx2, ny2, nw2, nh2 = v2_box[0] / W, v2_box[1] / H, v2_box[2] / W, v2_box[3] / H
nx3, ny3, nw3, nh3 = v3_box[0] / W, v3_box[1] / H, v3_box[2] / W, v3_box[3] / H

print(f"Candidate V1: [{nx1:.3f}, {ny1:.3f}, {nw1:.3f}, {nh1:.3f}] -> box {v1_box}")
print(f"Candidate V2: [{nx2:.3f}, {ny2:.3f}, {nw2:.3f}, {nh2:.3f}] -> box {v2_box}")
print(f"Candidate V3: [{nx3:.3f}, {ny3:.3f}, {nw3:.3f}, {nh3:.3f}] -> box {v3_box}")

# Let's draw these boxes on `hud` and also crop each one individually to verify:
test_hud = hud.copy()
cv2.rectangle(test_hud, (v1_box[0], v1_box[1]), (v1_box[0]+v1_box[2], v1_box[1]+v1_box[3]), (0, 255, 0), 1)
cv2.rectangle(test_hud, (v2_box[0], v2_box[1]), (v2_box[0]+v2_box[2], v2_box[1]+v2_box[3]), (0, 255, 0), 1)
cv2.rectangle(test_hud, (v3_box[0], v3_box[1]), (v3_box[0]+v3_box[2], v3_box[1]+v3_box[3]), (0, 255, 0), 1)

cv2.imwrite("scratch/test_hud_virtues.png", test_hud)

crop1 = hud[v1_box[1]:v1_box[1]+v1_box[3], v1_box[0]:v1_box[0]+v1_box[2]]
crop2 = hud[v2_box[1]:v2_box[1]+v2_box[3], v2_box[0]:v2_box[0]+v2_box[2]]
crop3 = hud[v3_box[1]:v3_box[1]+v3_box[3], v3_box[0]:v3_box[0]+v3_box[2]]

cv2.imwrite("scratch/crop_v1.png", crop1)
cv2.imwrite("scratch/crop_v2.png", crop2)
cv2.imwrite("scratch/crop_v3.png", crop3)

print("Saved test_hud_virtues.png and crop_v1..v3.png")
