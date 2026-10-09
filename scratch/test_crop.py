import cv2
import yaml
import os

img_path = r"C:\Users\dakot\.gemini\antigravity-ide\brain\1995e392-98b9-4a69-be2f-e14be90b4d80\.user_uploaded\media_1791073788654.jpg"
img = cv2.imread(img_path)
H, W = img.shape[:2]

with open("config/settings.yaml", "r") as f:
    cfg = yaml.safe_load(f)

region = cfg["region"]
nx = region["norm_x"]
ny = region["norm_y"]
nw = region["norm_w"]
nh = region["norm_h"]

rx = int(nx * W)
ry = int(ny * H)
rw = int(nw * W)
rh = int(nh * H)

print(f"Full image: {W}x{H}")
print(f"Crop rect: x={rx}, y={ry}, w={rw}, h={rh}")

hud_crop = img[ry:ry+rh, rx:rx+rw].copy()
cv2.imwrite("scratch/current_hud_crop.png", hud_crop)
print(f"Saved scratch/current_hud_crop.png ({hud_crop.shape[1]}x{hud_crop.shape[0]})")
