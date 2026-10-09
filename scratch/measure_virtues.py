import cv2
import numpy as np

img = cv2.imread(r"C:\Users\dakot\.gemini\antigravity-ide\brain\1995e392-98b9-4a69-be2f-e14be90b4d80\.user_uploaded\media_1791073788654.jpg")
H, W = img.shape[:2]

# Crop the HUD exactly as ScreenMonitor does:
nx = 0.2461
ny = 0.7875
nw = 0.4795
nh = 0.2125

rx = int(nx * W)  # 252
ry = int(ny * H)  # 504
rw = int(nw * W)  # 491
rh = int(nh * H)  # 136

hud = img[ry:ry+rh, rx:rx+rw].copy()
cv2.imwrite("scratch/measured_hud.png", hud)

# Let's inspect the 3 Virtues in `hud`:
# Virtue 1 (Justice): M5
# Virtue 2 (Resolve): M4
# Virtue 3 (Courage): Shift+M5

# Let's print pixel coordinates by finding the bright icons and key circles in hud:
# We know weapon 1 starts around x=28 in hud, weapon 2 at x=67, weapon 3 at x=105, weapon 4 at x=143, weapon 5 at x=181
# The virtues sit above weapon 2, 3, 4!
# Let's crop from y=20 to y=85, x=90 to x=185 in hud:
virtue_strip = hud[20:85, 90:185].copy()
cv2.imwrite("scratch/measured_virtues_strip.png", virtue_strip)

print("HUD shape:", hud.shape)
print("Virtue strip shape:", virtue_strip.shape)
