"""
Fight recorder: saves the HUD frames the engine already grabs, from F9 (engage) to F10
(disengage), one folder per fight. Frames are named by wall-clock time (HHMMSS.mmm.jpg) so
they line up with logs/session_*.log. Writing happens on a background thread so the rotation
never waits on disk. Only the newest `keep` fights are kept (~50 MB per minute of fight).

settings.yaml:
    recording:
      enabled: true
      keep: 5
"""

import os
import queue
import shutil
import threading
import time
from typing import Any, Dict, Optional

import cv2
import numpy as np

DEFAULT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scratch", "recordings")


class FightRecorder:
    def __init__(self, root: str = DEFAULT_DIR, keep: int = 5, jpeg_quality: int = 90):
        self.root = root
        self.keep = max(1, int(keep))
        self.jpeg_quality = int(jpeg_quality)
        self.folder: Optional[str] = None
        self._queue: "queue.Queue[Optional[tuple]]" = queue.Queue(maxsize=200)
        self._writer: Optional[threading.Thread] = None

    @classmethod
    def from_config(cls, config: Dict[str, Any]) -> Optional["FightRecorder"]:
        cfg = config.get("recording") or {}
        if not cfg.get("enabled"):
            return None
        return cls(root=cfg.get("dir") or DEFAULT_DIR, keep=cfg.get("keep", 5))

    @property
    def recording(self) -> bool:
        return self.folder is not None

    def start(self) -> str:
        if self.recording:
            return self.folder
        os.makedirs(self.root, exist_ok=True)
        self.folder = os.path.join(self.root, time.strftime("fight_%Y%m%d_%H%M%S"))
        os.makedirs(self.folder, exist_ok=True)
        self._prune()
        self._writer = threading.Thread(target=self._write_loop, args=(self.folder,), daemon=True)
        self._writer.start()
        return self.folder

    def add(self, frame: np.ndarray, t: Optional[float] = None) -> None:
        if not self.recording or frame is None or getattr(frame, "size", 0) == 0:
            return
        t = time.time() if t is None else t
        try:
            self._queue.put_nowait((t, frame.copy()))
        except queue.Full:
            pass                                   # disk can't keep up: drop a frame, never stall the bot

    def stop(self) -> Optional[str]:
        folder = self.folder
        if folder is None:
            return None
        self.folder = None
        self._queue.put(None)
        if self._writer:
            self._writer.join(timeout=10)
        self._writer = None
        return folder

    def _write_loop(self, folder: str) -> None:
        last_stem, repeat = None, 0
        while True:
            item = self._queue.get()
            if item is None:
                return
            t, frame = item
            stem = time.strftime("%H%M%S", time.localtime(t)) + f".{int(t * 1000) % 1000:03d}"
            repeat = repeat + 1 if stem == last_stem else 0
            last_stem = stem
            name = f"{stem}_{repeat}.jpg" if repeat else f"{stem}.jpg"   # same millisecond: keep both
            cv2.imwrite(os.path.join(folder, name), frame, [cv2.IMWRITE_JPEG_QUALITY, self.jpeg_quality])

    def _prune(self) -> None:
        fights = sorted(d for d in os.listdir(self.root)
                        if d.startswith("fight_") and os.path.isdir(os.path.join(self.root, d)))
        for old in fights[:-self.keep]:
            shutil.rmtree(os.path.join(self.root, old), ignore_errors=True)
