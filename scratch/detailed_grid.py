import cv2
import numpy as np

hud = cv2.imread("scratch/measured_hud.png")
H, W = hud.shape[:2]  # 136, 491

# Let's inspect the virtue icons in `hud`:
# Let's test different candidate boxes:
# Notice: Weapon 1 is around x=28..64, y=78..120
# Weapon 2 is around x=67..103, y=78..120
# Weapon 3 is around x=105..141, y=78..120
# Weapon 4 is around x=143..179, y=78..120
# Weapon 5 is around x=181..217, y=78..120

# Let's look at the virtues right above weapon 2, 3, 4:
# In `scratch/measured_virtues_strip.png`, the strip is hud[20:85, 90:185]
# Let's inspect the exact pixel rows and columns where the icons and key badges are:
strip = cv2.imread("scratch/measured_virtues_strip.png")
# Let's upscale strip 6x and draw a 1-pixel grid to visually inspect each coordinate:
scale = 6
scaled = cv2.resize(strip, (strip.shape[1] * scale, strip.shape[0] * scale), interpolation=cv2.INTER_NEAREST)

# Draw grid lines
for y in range(0, strip.shape[0]):
    color = (80, 80, 80) if y % 5 != 0 else (180, 180, 180)
    cv2.line(scaled, (0, y * scale), (scaled.shape[1], y * scale), color, 1)
    if y % 10 == 0:
        cv2.putText(scaled, f"y={20+y}", (2, y * scale - 2), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 255, 255), 1)

for x in range(0, strip.shape[1]):
    color = (80, 80, 80) if x % 5 != 0 else (180, 180, 180)
    cv2.line(scaled, (x * scale, 0), (x * scale, scaled.shape[0]), color, 1)
    if x % 10 == 0:
        cv2.putText(scaled, f"x={90+x}", (x * scale + 2, 12), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 255, 255), 1)

cv2.imwrite("scratch/virtues_grid_detailed.png", scaled)
print("Saved scratch/virtues_grid_detailed.png")
