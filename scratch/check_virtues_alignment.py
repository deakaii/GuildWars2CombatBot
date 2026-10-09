import cv2
import numpy as np

# Let's inspect the entire left area above weapon skills in hud_crop:
# y from 0 to 90, x from 50 to 250
frame = cv2.imread("scratch/current_hud_crop.png")
area = frame[0:90, 50:250].copy()

# Draw the current rects on area:
# Note: area is offset by x=50, y=0
# mech_f1 is at x=104, y=47 -> in area: x=54, y=47
# mech_f2 is at x=133, y=47 -> in area: x=83, y=47
# mech_f3 is at x=162, y=47 -> in area: x=112, y=47

marked = area.copy()
cv2.rectangle(marked, (104-50, 47), (104-50+28, 47+36), (0, 255, 0), 1)
cv2.rectangle(marked, (133-50, 47), (133-50+28, 47+36), (0, 255, 0), 1)
cv2.rectangle(marked, (162-50, 47), (162-50+28, 47+36), (0, 255, 0), 1)

# Scale up 4x for crystal clear visualization
marked_big = cv2.resize(marked, (marked.shape[1]*4, marked.shape[0]*4), interpolation=cv2.INTER_NEAREST)
cv2.imwrite("scratch/virtues_current_alignment_4x.png", marked_big)
print("Saved virtues_current_alignment_4x.png")
