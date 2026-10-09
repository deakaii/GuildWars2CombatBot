import cv2
import numpy as np

# Let's inspect crop_v1, crop_v2, crop_v3:
c1 = cv2.imread("scratch/crop_v1.png")
c2 = cv2.imread("scratch/crop_v2.png")
c3 = cv2.imread("scratch/crop_v3.png")

print(f"Crop 1: {c1.shape}, mean BGR: {c1.mean(axis=(0,1))}")
print(f"Crop 2: {c2.shape}, mean BGR: {c2.mean(axis=(0,1))}")
print(f"Crop 3: {c3.shape}, mean BGR: {c3.mean(axis=(0,1))}")

# Let's see if the key circle (M5, M4) is inside or below:
# In Guild Wars 2, the keybind text (like "M5", "M4") is in a small round circle at the bottom-left of the skill icon!
# In our candidate: v1_box = (98, 41, 27, 30)
# Let's inspect where the circle is:
# Let's slice the candidate into icon top and keybind circle:
# Let's upscale and save each crop with border:
for name, c in [("v1", c1), ("v2", c2), ("v3", c3)]:
    big = cv2.resize(c, (c.shape[1]*8, c.shape[0]*8), interpolation=cv2.INTER_NEAREST)
    cv2.imwrite(f"scratch/inspect_{name}_big.png", big)

print("Saved inspect_v1_big, v2_big, v3_big")
