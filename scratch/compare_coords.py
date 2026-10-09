import cv2
import numpy as np

img = cv2.imread(r"C:\Users\dakot\.gemini\antigravity-ide\brain\1995e392-98b9-4a69-be2f-e14be90b4d80\.user_uploaded\media_1791073788654.jpg")

# Let's inspect the exact pixel bounds of the 3 virtues:
# Let's find the circle or borders:
# Let's write an image with multiple colored boxes testing Y offsets from 535 to 555 and X offsets
test_img = img[530:585, 340:445].copy()

# Virtue 1 icon is approx: x: 350 to 376 (width 26), y: 544 to 572 (height 28)
# Virtue 2 icon is approx: x: 377 to 403 (width 26), y: 544 to 572 (height 28)
# Virtue 3 icon is approx: x: 404 to 430 (width 26), y: 544 to 572 (height 28)

print("Virtue 1 actual box in 1024x640: x=350..376, y=544..572")

# Now let's check weapon skills 1..5:
# Weapon 1: x: 279..315 (width 36), y: 582..624 (height 42)
# Weapon 2: x: 317..353 (width 36), y: 582..624 (height 42)
# Weapon 3: x: 355..391 (width 36), y: 582..624 (height 42)
# Weapon 4: x: 393..429 (width 36), y: 582..624 (height 42)
# Weapon 5: x: 431..467 (width 36), y: 582..624 (height 42)

# Health globe: center = (512, 593), radius = 34
# Health globe bounds: x: 478..546, y: 559..627

# Utility skills 6..0:
# Heal (Q): x: 557..593 (width 36), y: 582..624 (height 42)
# Utility 1 (E): x: 595..631 (width 36), y: 582..624 (height 42)
# Utility 2 (R): x: 633..669 (width 36), y: 582..624 (height 42)
# Utility 3 (T): x: 671..707 (width 36), y: 582..624 (height 42)
# Elite (M3): x: 709..745 (width 36), y: 582..624 (height 42)

# Now let's calculate:
# If our screen ROI is currently:
# rx = int(0.2461 * 1024) = 252
# ry = int(0.7875 * 640) = 504
# rw = int(0.4795 * 1024) = 491
# rh = int(0.2125 * 640) = 136

# In this ROI of 491 x 136:
# Where do the virtues land if we convert their exact screen coordinates relative to ROI?
# In screen coords:
# V1: x = 350, y = 544
# Relative to ROI (rx=252, ry=504):
# V1_rel_x = 350 - 252 = 98
# V1_rel_y = 544 - 504 = 40!
# Wait! In our current UniversalCooldownDetector:
# "mech_f1": (0.212, 0.346, 0.059, 0.265)
# In 491 x 136:
# sx = int(0.212 * 491) = 104!
# sy = int(0.346 * 136) = 47!
# Wait! Look at that:
# Real V1_rel_y = 40! Our detector was using 47 (which is 7 pixels lower than 40)!
# Wait, why did the user say:
# "THE ICONS ARE TOO HIGH."
# "THIS IS THE ENTIRE SCREENSHOT TO HELP ALIGN"
