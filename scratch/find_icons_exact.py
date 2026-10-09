import cv2
import numpy as np

img = cv2.imread(r"C:\Users\dakot\.gemini\antigravity-ide\brain\1995e392-98b9-4a69-be2f-e14be90b4d80\.user_uploaded\media_1791073788654.jpg")
H, W = img.shape[:2]

# Let's inspect:
# 1. Where does the weapon skill bar sit in absolute Y in img?
# 2. Where do the virtues sit in absolute Y in img?
# 3. Where is the bottom edge of the screen / HUD?
# 4. Where does our current ROI (ry=504, rh=136 -> y from 504 to 640) place them?

# Let's find the exact bounding box of the weapon 1 icon in img:
# In img (1024x640), weapon 1 has a sword/spear icon with blue flames around it and number '1' below it.
# Let's print the brightness or find edges around x=260 to 320, y=550 to 640:

# Let's crop a detailed strip around the bottom center
strip = img[500:640, 250:780].copy()
print("Bottom strip shape:", strip.shape)

# Let's find where the virtue icons are:
# Virtue 1 (F1 / M5) has icon with fists/blue flames
# Virtue 2 (F2 / M4) has icon with blue cross/wings
# Virtue 3 (F3 / Shift+M5) has icon with blue shield
# Above Virtue 1/2 is an icon with S+E (Shift+E)
# Let's locate the virtue icons precisely!
