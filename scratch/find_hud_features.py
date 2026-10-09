import cv2
import numpy as np

img = cv2.imread(r"C:\Users\dakot\.gemini\antigravity-ide\brain\1995e392-98b9-4a69-be2f-e14be90b4d80\.user_uploaded\media_1791073788654.jpg")
H, W = img.shape[:2]

# The health globe is a big red circle at the bottom center.
# Let's inspect the region around x=450 to 580, y=500 to 640
hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

# Red color mask for health globe
lower_red1 = np.array([0, 100, 100])
upper_red1 = np.array([10, 255, 255])
lower_red2 = np.array([170, 100, 100])
upper_red2 = np.array([180, 255, 255])
mask_red = cv2.bitwise_or(cv2.inRange(hsv, lower_red1, upper_red1), cv2.inRange(hsv, lower_red2, upper_red2))

# Find health globe center
contours, _ = cv2.findContours(mask_red[450:640, 400:600], cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
if contours:
    largest = max(contours, key=cv2.contourArea)
    (gx, gy), radius = cv2.minEnclosingCircle(largest)
    gx += 400
    gy += 450
    print(f"Health globe center ~ ({gx:.1f}, {gy:.1f}), radius ~ {radius:.1f}")

# Let's find the exact horizontal baseline of weapon skills 1-5 and utilities 6-0
# Let's slice the region y=550 to 640, x=250 to 780
# And look at vertical and horizontal edges or template positions.
