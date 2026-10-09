import cv2
import os

img_path = r"C:\Users\dakot\.gemini\antigravity-ide\brain\1995e392-98b9-4a69-be2f-e14be90b4d80\.user_uploaded\media_1791073788654.jpg"
img = cv2.imread(img_path)
print("Image shape:", img.shape)

# Let's inspect where the HUD is in this screenshot
# If screen resolution is W x H:
h, w = img.shape[:2]
print(f"Resolution: {w} x {h}")
