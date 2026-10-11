"""
Passive HUD recorder: grabs the calibrated HUD region ~20x a second and records what the bot
reads (main + extra resources, every slot's ready state) with millisecond timestamps, plus
the frames. Sends no input and doesn't touch window focus. Line it up with logs/session_*.log
to see when presses actually took effect in game.

    python tools/record_hud.py --profession Thief --spec Deadeye --seconds 120

Writes scratch/recordings/<timestamp>/readings.csv and frames/<ms>.jpg.
"""

import argparse
import csv
import os
import sys
import time

import cv2
import yaml

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

from core.capture import ScreenMonitor
from core.cooldown_detector import UniversalCooldownDetector
from core.dpi_utils import enable_dpi_awareness
from core.resource_detector import UniversalResourceDetector


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    ap.add_argument("--profession", required=True)
    ap.add_argument("--spec", required=True)
    ap.add_argument("--seconds", type=float, default=120.0)
    ap.add_argument("--fps", type=float, default=20.0)
    args = ap.parse_args()

    enable_dpi_awareness()
    with open(os.path.join(BASE, "config", "settings.yaml"), "r") as f:
        region = (yaml.safe_load(f) or {}).get("region", {})
    monitor = ScreenMonitor(region)
    slots = UniversalCooldownDetector(profession=args.profession, spec=args.spec)
    resources = UniversalResourceDetector(profession=args.profession, spec=args.spec)
    res_names = ([resources.resource_name] if resources.resource_type != "none" else []) + list(resources.extras)
    slot_ids = list(slots.slots)

    out = os.path.join(BASE, "scratch", "recordings", time.strftime("%Y%m%d_%H%M%S"))
    os.makedirs(os.path.join(out, "frames"), exist_ok=True)
    print(f"Recording {args.seconds:.0f}s to {out}", flush=True)

    period = 1.0 / args.fps
    end = time.time() + args.seconds
    with open(os.path.join(out, "readings.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["time"] + res_names + slot_ids)
        while time.time() < end:
            t0 = time.time()
            frame = monitor.grab_frame()
            if frame is not None and frame.size:
                stamp = time.strftime("%H:%M:%S", time.localtime(t0)) + f".{int(t0 * 1000) % 1000:03d}"
                amounts = [resources.get_resource_state(frame, n).current_value for n in res_names]
                ready = ["R" if (st := slots.get_slot_status(frame, s)) and st.is_ready else "cd" for s in slot_ids]
                w.writerow([stamp] + [f"{a:g}" for a in amounts] + ready)
                cv2.imwrite(os.path.join(out, "frames", stamp.replace(":", "") + ".jpg"), frame,
                            [cv2.IMWRITE_JPEG_QUALITY, 90])
            time.sleep(max(0.0, period - (time.time() - t0)))
    monitor.close()
    print(f"Done: {out}", flush=True)


if __name__ == "__main__":
    main()
