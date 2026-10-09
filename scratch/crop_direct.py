import cv2
import numpy as np

img = cv2.imread(r"C:\Users\dakot\.gemini\antigravity-ide\brain\1995e392-98b9-4a69-be2f-e14be90b4d80\.user_uploaded\media_1791073788654.jpg")

# In img (1024x640), let's crop around virtues:
# Let's crop x: 340 to 450, y: 520 to 600
virtues_area = img[520:600, 340:450]
cv2.imwrite("scratch/virtues_screen_area.png", virtues_area)

# Let's crop weapon bar:
# x: 270 to 500, y: 570 to 635
weapon_area = img[570:635, 270:500]
cv2.imwrite("scratch/weapon_screen_area.png", weapon_area)

# Let's crop the S+E icon:
# x: 430 to 480, y: 480 to 540
se_area = img[480:540, 430:480]
cv2.imwrite("scratch/se_screen_area.png", se_area)

print("Saved virtue, weapon, and se crops.")
