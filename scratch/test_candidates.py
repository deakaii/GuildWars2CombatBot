import cv2
import numpy as np

img = cv2.imread(r"C:\Users\dakot\.gemini\antigravity-ide\brain\1995e392-98b9-4a69-be2f-e14be90b4d80\.user_uploaded\media_1791073788654.jpg")

# In the screenshot img (1024x640):
# Let's locate the 3 virtue icons:
# F1 (Virtue of Justice - M5)
# F2 (Virtue of Resolve - M4)
# F3 (Virtue of Courage)

# Let's look at the black borders and the keybind circles (M5, M4):
# In the screenshot:
# Notice where the circle "M5" is, and where "M4" is.
# Let's search for "M5" and "M4" text or circles, and the square icons!
sub = img[530:585, 345:435]

# Let's find contours in that sub-region:
gray = cv2.cvtColor(sub, cv2.COLOR_BGR2GRAY)
# Edges:
edges = cv2.Canny(gray, 50, 150)

# Also let's print the exact crop bounds for each:
# Let's test a few candidate bounding boxes:
# For Virtue 1:
# x in 348 to 376? (width ~28)
# y in 543 to 571? (height ~28)
# Let's test:
for i, x_cand in enumerate([349, 377, 405]):
    crop = img[540:575, x_cand:x_cand+28]
    cv2.imwrite(f"scratch/candidate_v{i+1}.png", crop)

# Also what about the weapon skills 1..5?
# Let's test candidate boxes for weapon skills:
# Weapon 1: x in [275, 315]?
for i, x_cand in enumerate([278, 316, 354, 392, 430]):
    crop = img[580:625, x_cand:x_cand+38]
    cv2.imwrite(f"scratch/candidate_w{i+1}.png", crop)

print("Saved candidates.")
