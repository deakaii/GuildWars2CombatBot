import cv2
import numpy as np

c1 = cv2.imread("scratch/crop_v1.png")
c2 = cv2.imread("scratch/crop_v2.png")
c3 = cv2.imread("scratch/crop_v3.png")

# Let's inspect the edge profiles:
# For V1:
print("V1 horizontal profile (mean along columns):", np.mean(c1, axis=(0, 2)))
print("V1 vertical profile (mean along rows):", np.mean(c1, axis=(1, 2)))

# The top 2-3 rows and bottom rows:
# The icon border in GW2 has a bright inner graphic and a dark frame.
# Let's find the exact dark frame:
# In c1 (30x27):
# rows: 0 to 29, cols: 0 to 26
# Let's check where the key circle is:
# In GW2, the circle with "M5" is in the bottom left, typically around y=20..28, x=0..12.
# Let's verify:
print("Bottom-left 10x10 patch of V1 mean:", np.mean(c1[20:30, 0:10], axis=(0,1)))
