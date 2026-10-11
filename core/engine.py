"""
Prioritization Engine & Decision Loop.
Orchestrates screen capture, prioritized behavior evaluation, and stealth input dispatching.
"""

import time
import random
from typing import List, Dict, Any, Optional

from core.capture import ScreenMonitor
from core.detector import VisualDetector
from core.input_controller import InputController
from core.fight_recorder import FightRecorder
from behaviors.base import BaseBehavior


class PrioritizationEngine:
    """
    Main loop prioritizing and dispatching actions based on screen perception.
    """

    def __init__(
        self,
        config: Dict[str, Any],
        monitor: ScreenMonitor,
        detector: VisualDetector,
        input_controller: InputController
    ):
        self.config = config
        self.monitor = monitor
        self.detector = detector
        self.input_controller = input_controller
        
        self.behaviors: List[BaseBehavior] = []
        
        timing_cfg = config.get("timing", {})
        self.base_tick_interval = float(timing_cfg.get("tick_interval", 0.50))
        self.tick_jitter = timing_cfg.get("tick_jitter_range", [0.02, 0.08])
        
        self.running = False
        self.ticks_processed = 0

        # Target Guard configuration (auto-disengage when enemy is dead/gone)
        self.target_guard_cfg = config.get("target_guard", {})
        self.target_guard_enabled = bool(self.target_guard_cfg.get("enabled", False))
        self.missing_target_tolerance = int(self.target_guard_cfg.get("missing_target_tolerance_ticks", 2))
        self.consecutive_missing_target_ticks = 0

        # Fight recording (settings.yaml recording.enabled): F9 starts it, F10 stops it
        self.recorder = FightRecorder.from_config(config)

    def stop_recording(self) -> None:
        """Ends the current fight recording, if any (called on disengage and shutdown)."""
        if self.recorder and self.recorder.recording:
            print(f"[Recorder] Saved fight to {self.recorder.stop()}")

    def register_behavior(self, behavior: BaseBehavior) -> None:
        """
        Registers a behavior and keeps the list sorted by priority descending (highest first).
        """
        self.behaviors.append(behavior)
        self.behaviors.sort(key=lambda b: b.priority, reverse=True)
        print(f"[Engine] Registered '{behavior.name}' (Priority: {behavior.priority}, Cooldown: {behavior.base_cooldown}s)")

    def _check_target_guard(self, frame) -> bool:
        """
        Verifies if the enemy/target is still available.
        Returns True if target is present, False if target is lost.
        """
        if not self.target_guard_enabled:
            return True

        template_name = self.target_guard_cfg.get("template_filename", "target_indicator.png")
        threshold = float(self.target_guard_cfg.get("confidence_threshold", 0.78))
        
        # Check if template file exists
        if not self.detector.load_template(template_name):
            # If target template hasn't been captured yet, don't block
            return True

        res = self.detector.match_template(frame, template_name, threshold=threshold, multi_scale=True)
        return res.matched

    def run_tick(self) -> Optional[str]:
        """
        Executes a single evaluation cycle:
        1. Captures frame from configured ROI.
        2. Validates engagement state and target guard.
        3. Evaluates behaviors from highest priority to lowest.
        4. Executes the first eligible behavior whose condition matches.
        """
        # 1. Active Window Guard: Verify Guild Wars 2 is the active foreground window FIRST
        if hasattr(self.input_controller, "is_game_focused") and not self.input_controller.is_game_focused():
            self.ticks_processed += 1
            return None

        # 2. If loop is disengaged (via F10 macro or target guard), skip actions
        if not self.input_controller.is_active():
            self.stop_recording()
            self.ticks_processed += 1
            return None

        # 3. Only grab frame when Guild Wars 2 is actually in focus and loop is active
        now = time.time()
        frame = self.monitor.grab_frame()
        if self.recorder:
            if not self.recorder.recording:
                print(f"[Recorder] Recording fight to {self.recorder.start()}")
            self.recorder.add(frame, now)

        # Verify target is still available
        if self.target_guard_enabled:
            target_present = self._check_target_guard(frame)
            if not target_present:
                self.consecutive_missing_target_ticks += 1
                if self.consecutive_missing_target_ticks >= self.missing_target_tolerance:
                    self.input_controller.disengage("Enemy/Target no longer present")
                    self.ticks_processed += 1
                    return None
            else:
                self.consecutive_missing_target_ticks = 0

        triggered_name = None

        for behavior in self.behaviors:
            # Check cooldown first before doing visual evaluation
            if behavior.is_on_cooldown(now):
                continue

            matched, result = behavior.evaluate_condition(frame, self.detector)

            if matched:
                behavior.trigger(self.input_controller)
                triggered_name = behavior.name
                # Highest priority rule satisfied; preempt lower priority rules for this tick
                break

        self.ticks_processed += 1
        return triggered_name

    def run_loop(self) -> None:
        """
        Runs the continuous prioritization loop until emergency stop or user interrupt.
        """
        self.running = True
        ctrl_cfg = self.config.get("control", self.config.get("safety", {}))
        start_key = ctrl_cfg.get("start_key", "F9").upper()
        stop_key = ctrl_cfg.get("stop_key", "F10").upper()
        emergency_key = ctrl_cfg.get("emergency_stop_key", "F12").upper()
        
        print("\n" + "=" * 65)
        print("  PRIORITIZATION LOGIC ENGINE STARTED")
        print(f"  - Cadence: ~{int(self.base_tick_interval * 1000)}ms per tick")
        print(f"  - Registered behaviors: {len(self.behaviors)}")
        print(f"  - [ {start_key} ]  : ENGAGE Action Loop (Start Macro)")
        print(f"  - [ {stop_key} ] : DISENGAGE Action Loop (Pause Macro)")
        print(f"  - [ {emergency_key} ] : EMERGENCY KILL SWITCH (Halt Script)")
        print("=" * 65 + "\n")

        try:
            while self.running and not self.input_controller.is_stopped():
                t_start = time.perf_counter()

                triggered = self.run_tick()

                # Telemetry output
                latency = self.monitor.last_latency_ms
                is_active = self.input_controller.is_active()

                is_focused = getattr(self.input_controller, "is_game_focused", lambda: True)()
                if triggered:
                    print(f"[{time.strftime('%H:%M:%S')}] Tick #{self.ticks_processed:04d} | Grab: {latency:.1f}ms | ACTION: {triggered}")
                else:
                    if self.ticks_processed % 8 == 0:
                        if not is_focused:
                            status_str = "STANDBY (GW2 TABBED OUT)"
                        elif not is_active:
                            status_str = "STANDBY (F9 ARMED)"
                        else:
                            status_str = "ACTIVE"
                        print(f"[{time.strftime('%H:%M:%S')}] [{status_str}] Tick #{self.ticks_processed:04d} | Latency: {latency:.1f}ms")

                # If tabbed out of GW2, sleep 150ms to conserve CPU
                if not is_focused:
                    time.sleep(0.15)
                    continue

                # Compute sleep time with humanized micro-jitter
                jitter = random.uniform(self.tick_jitter[0], self.tick_jitter[1])
                elapsed = time.perf_counter() - t_start
                sleep_time = max(0.01, (self.base_tick_interval + jitter) - elapsed)
                
                # Check for stop during sleep in small chunks
                sleep_end = time.time() + sleep_time
                while time.time() < sleep_end and not self.input_controller.is_stopped():
                    time.sleep(0.015)

        except KeyboardInterrupt:
            print("\n[Engine] Interrupted by user (Ctrl+C).")
        finally:
            self.stop()


    def stop(self) -> None:
        """Stops the loop and releases resources."""
        self.running = False
        self.stop_recording()
        self.monitor.close()
        self.input_controller.close()
        print(f"[Engine] Stopped. Processed {self.ticks_processed} ticks safely.")
