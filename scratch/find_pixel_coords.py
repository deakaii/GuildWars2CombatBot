import cv2
import numpy as np

img = cv2.imread(r"C:\Users\dakot\.gemini\antigravity-ide\brain\1995e392-98b9-4a69-be2f-e14be90b4d80\.user_uploaded\media_1791073788654.jpg")

# Let's inspect where the virtue icons are by searching for their dark circular/square borders or icons:
# Virtues are located around x in [350, 440], y in [530, 580] in img (1024x640)
# Let's write an annotated image of that region with grid lines every 5 pixels:
sub = img[530:590, 340:445].copy()
grid = sub.copy()
for yy in range(0, sub.shape[0], 5):
    cv2.line(grid, (0, yy), (sub.shape[1], yy), (50, 50, 50), 1)
    if yy % 10 == 0:
        cv2.putText(grid, str(530+yy), (2, yy-2), cv2.FONT_HERSHEY_SIMPLEX, 0.25, (0, 255, 255), 1)
for xx in range(0, sub.shape[1], 5):
    cv2.line(grid, (xx, 0), (xx, sub.shape[0]), (50, 50, 50), 1)
    if xx % 20 == 0:
        cv2.putText(grid, str(340+xx), (xx+2, 10), cv2.FONT_HERSHEY_SIMPLEX, 0.25, (0, 255, 255), 1)

grid_big = cv2.resize(grid, (grid.shape[1]*4, grid.shape[0]*4), interpolation=cv2.INTER_NEAREST)
cv2.imwrite("scratch/virtues_grid_annotated.png", grid_big)
print("Saved scratch/virtues_grid_annotated.png")
