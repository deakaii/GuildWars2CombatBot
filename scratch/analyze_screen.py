import cv2
import numpy as np

img = cv2.imread(r"C:\Users\dakot\.gemini\antigravity-ide\brain\1995e392-98b9-4a69-be2f-e14be90b4d80\.user_uploaded\media_1791073788654.jpg")
H, W = img.shape[:2]

# Let's draw the current ROI on the full screenshot
# norm_x: 0.2461, norm_y: 0.7875, norm_w: 0.4795, norm_h: 0.2125
nx = 0.2461
ny = 0.7875
nw = 0.4795
nh = 0.2125

rx = int(nx * W)
ry = int(ny * H)
rw = int(nw * W)
rh = int(nh * H)

full_with_roi = img.copy()
cv2.rectangle(full_with_roi, (rx, ry), (rx + rw, ry + rh), (0, 0, 255), 2)
cv2.putText(full_with_roi, f"ROI: {rx},{ry} {rw}x{rh}", (rx, ry - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)

cv2.imwrite("scratch/full_with_roi.png", full_with_roi)
print(f"Full with ROI saved: ROI={rx},{ry},{rw},{rh} on image {W}x{H}")

# Now let's inspect the bottom area of the full image:
# Where are the actual skill icons?
# Let's crop from y=450 to 640 and x=200 to 800
bottom_area = img[450:640, 200:800].copy()
cv2.imwrite("scratch/bottom_area.png", bottom_area)
print("Bottom area saved.")
