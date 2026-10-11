"""
Hardware-level DirectInput dispatcher with humanized micro-delays and emergency kill-switch.
Designed for 3D DirectX applications without memory injection or suspicious synthetic API flags.
"""

import time
import random
import threading
from typing import Dict, Any, Optional
import pydirectinput
from pynput import keyboard

# Configure pydirectinput safety settings
pydirectinput.PAUSE = 0.01
pydirectinput.FAILSAFE = True

# Ensure tilde maps to grave accent scan code (0x29) for DirectX games
if "~" not in pydirectinput.KEYBOARD_MAPPING and "`" in pydirectinput.KEYBOARD_MAPPING:
    pydirectinput.KEYBOARD_MAPPING["~"] = pydirectinput.KEYBOARD_MAPPING["`"]


def is_target_game_focused(allowed_titles=("guild wars 2", "gw2"), allowed_exes=("gw2-64.exe", "gw2.exe")) -> bool:
    """
    Returns True ONLY if Guild Wars 2 is the active foreground window.
    Prevents synthetic keystrokes from leaking into IDE, chat, browser, or discord.
    """
    from core.window_utils import is_gw2_focused
    return is_gw2_focused(allowed_titles=allowed_titles, allowed_exes=allowed_exes)


class InputController:
    """
    Simulates physical keyboard inputs using hardware DirectInput scan codes.
    Includes background kill-switch listener and humanized timing jitter.
    """

    def __init__(self, stealth_config: Dict[str, Any], control_config: Dict[str, Any]):
        self.stealth_config = stealth_config
        self.control_config = control_config
        
        self.key_hold_range = stealth_config.get("key_hold_range", [0.052, 0.088])
        self.reaction_jitter_range = stealth_config.get("reaction_jitter_range", [0.030, 0.075])
        
        # Modifier (Shift + Mouse 5) randomized timing wiggle room
        self.mod_pre_range = stealth_config.get("modifier_pre_delay_range", [0.018, 0.048])
        self.mod_post_range = stealth_config.get("modifier_post_delay_range", [0.012, 0.036])

        # Rotation Effectiveness & Human Imperfection Model (85% effectiveness)
        self.rotation_effectiveness = float(stealth_config.get("rotation_effectiveness", 0.85))
        self.imperfection_cfg = stealth_config.get("imperfection_behaviors", {})
        self.last_pressed_action: Optional[str] = None

        # Game Window Focus Guard: Blocks inputs if user tabs away to IDE or browser
        self.require_game_focus = bool(control_config.get("require_game_focus", True))

        self._emergency_stop = threading.Event()
        self._is_active = threading.Event()
        
        # Start in active state by default (or can be paused initially)
        self._is_active.set()
        
        self._start_key_name = control_config.get("start_key", "f9").lower()
        self._stop_key_name = control_config.get("stop_key", "f10").lower()
        self._emergency_key_name = control_config.get("emergency_stop_key", "f12").lower()
        
        # Keybind translation layer
        from core.keybind_mapper import KeybindMapper
        self.mapper = KeybindMapper()

        # Start global hotkey listener
        self._listener: Optional[keyboard.Listener] = None
        self._start_hotkey_listener()

    def _start_hotkey_listener(self) -> None:
        """Starts a background low-level hook listening for start, stop, and emergency keys."""
        def on_press(key):
            try:
                k_name = ""
                if hasattr(key, "name") and key.name:
                    k_name = key.name.lower()
                elif hasattr(key, "char") and key.char:
                    k_name = key.char.lower()

                if k_name == self._emergency_key_name:
                    print(f"\n[EMERGENCY STOP] Triggered by [{k_name.upper()}]! Terminating immediately.")
                    self._emergency_stop.set()
                elif k_name == self._start_key_name:
                    if not self._is_active.is_set():
                        print(f"\n[MACRO] >>> ENGAGED (Started by [{k_name.upper()}]) <<<")
                        self._is_active.set()
                elif k_name == self._stop_key_name:
                    if self._is_active.is_set():
                        print(f"\n[MACRO] ||| DISENGAGED (Paused by [{k_name.upper()}]) |||")
                        self._is_active.clear()
            except Exception:
                pass

        self._listener = keyboard.Listener(on_press=on_press)
        self._listener.daemon = True
        self._listener.start()

    def is_active(self) -> bool:
        """Returns True if the action loop is engaged/running."""
        return self._is_active.is_set() and not self._emergency_stop.is_set()

    def disengage(self, reason: str = "") -> None:
        """Programmatically disengages/pauses the action loop."""
        if self._is_active.is_set():
            msg = f" ({reason})" if reason else ""
            print(f"\n[AUTO-DISENGAGE] Action loop paused{msg}.")
            self._is_active.clear()

    def engage(self) -> None:
        """Programmatically resumes the action loop."""
        self._is_active.set()

    def is_stopped(self) -> bool:
        """Returns True if emergency kill-switch was activated."""
        return self._emergency_stop.is_set()

    def trigger_emergency_stop(self) -> None:
        """Manually trigger emergency halt."""
        self._emergency_stop.set()

    def reset_emergency_stop(self) -> None:
        """Clears emergency stop flag so user can re-engage cleanly."""
        self._emergency_stop.clear()

    def _dispatch_mouse_button(self, button_name: str, hold_time: float) -> bool:
        """Dispatches mouse buttons (Middle, Mouse 4, Mouse 5) using hardware events."""
        import ctypes
        user32 = ctypes.windll.user32
        btn = button_name.lower().strip()

        MOUSEEVENTF_XDOWN = 0x0080
        MOUSEEVENTF_XUP = 0x0100
        XBUTTON1 = 0x0001  # Mouse 4
        XBUTTON2 = 0x0002  # Mouse 5

        try:
            if btn in ["mouse3", "m3", "middle"]:
                pydirectinput.mouseDown(button="middle")
                time.sleep(hold_time)
                pydirectinput.mouseUp(button="middle")
                return True
            elif btn in ["mouse4", "m4"]:
                user32.mouse_event(MOUSEEVENTF_XDOWN, 0, 0, XBUTTON1, 0)
                time.sleep(hold_time)
                user32.mouse_event(MOUSEEVENTF_XUP, 0, 0, XBUTTON1, 0)
                return True
            elif btn in ["mouse5", "m5"]:
                user32.mouse_event(MOUSEEVENTF_XDOWN, 0, 0, XBUTTON2, 0)
                time.sleep(hold_time)
                user32.mouse_event(MOUSEEVENTF_XUP, 0, 0, XBUTTON2, 0)
                return True
            elif btn == "left":
                pydirectinput.click(button="left")
                return True
            elif btn == "right":
                pydirectinput.click(button="right")
                return True
        except Exception as e:
            print(f"[InputController Error] Mouse dispatch failed for '{btn}': {e}")
            return False

        return False

    def _execute_low_level(self, action_str: str, hold_time: float) -> bool:
        """Executes a single key, mouse button, or modifier combo."""
        # Standardize tilde to backtick scan code
        if action_str == "~":
            action_str = "`"

        # Modifier combo (e.g. 'shift+mouse5', 'shift+1')
        if "+" in action_str:
            parts = action_str.split("+")
            modifier = parts[0].strip()
            sub_action = "+".join(parts[1:]).strip()
            if sub_action == "~":
                sub_action = "`"

            # Press modifier down
            pydirectinput.keyDown(modifier)
            # Randomized wiggle room before mouse/key event (18ms - 48ms)
            pre_delay = random.uniform(self.mod_pre_range[0], self.mod_pre_range[1])
            time.sleep(pre_delay)

            # Execute sub-action
            if sub_action.startswith("mouse") or sub_action.startswith("m") and sub_action != "m":
                self._dispatch_mouse_button(sub_action, hold_time)
            else:
                pydirectinput.keyDown(sub_action)
                time.sleep(hold_time)
                pydirectinput.keyUp(sub_action)

            # Randomized wiggle room after mouse/key event before releasing modifier (12ms - 36ms)
            post_delay = random.uniform(self.mod_post_range[0], self.mod_post_range[1])
            time.sleep(post_delay)
            pydirectinput.keyUp(modifier)
            return True

        # Standalone mouse button
        if action_str.startswith("mouse") or action_str.startswith("m") and action_str != "m":
            return self._dispatch_mouse_button(action_str, hold_time)

        # Standard keyboard key
        try:
            pydirectinput.keyDown(action_str)
            time.sleep(hold_time)
        finally:
            pydirectinput.keyUp(action_str)
        return True

    def is_game_focused(self) -> bool:
        """Returns True if Guild Wars 2 is the active window (or if guard is disabled)."""
        if not self.require_game_focus:
            return True
        return is_target_game_focused()

    def press_key(self, raw_input: str, double_tap: bool = False) -> bool:
        """
        Sends hardware input with humanized timing, modifier wiggle room,
        and an 85% rotation effectiveness model introducing natural human imperfections.
        If double_tap=True, executes a 100% reliable ground-target double-tap (Tap 1 to open/snap, Tap 2 to set).
        """
        if self.is_stopped():
            return False

        # Active Window Guard: Never press keys into Antigrav IDE, browser, or chat
        if not self.is_game_focused():
            return False

        # Translate action or default key into user's custom keybind
        target_action = self.mapper.translate(raw_input).lower().strip()

        # Human reaction jitter before physical action
        react_delay = random.uniform(self.reaction_jitter_range[0], self.reaction_jitter_range[1])
        time.sleep(react_delay)

        if self.is_stopped() or not self.is_game_focused():
            return False

        # Human key hold duration
        hold_time = random.uniform(self.key_hold_range[0], self.key_hold_range[1])

        try:
            # -------------------------------------------------------------
            # Ground-Target Double-Tap Mode (e.g. Sword of Justice, Symbol of Punishment)
            # 100% Reliable: Bypasses imperfection slips to guarantee ground attack lands!
            # Tap 1: Trigger reticle / snap to target
            # Tap 2: Confirm placement and cast attack (prevents stuck animation)
            # -------------------------------------------------------------
            if double_tap:
                print(f"  [GROUND-TARGET] Double-tapping '{target_action}' (100% reliable: Reticle -> Cast & Lock)...")
                tap1_hold = random.uniform(0.052, 0.068)
                self._execute_low_level(target_action, tap1_hold)
                
                # Discrete inter-tap delay for GW2 input buffer to acknowledge reticle (55ms - 75ms)
                time.sleep(random.uniform(0.055, 0.075))
                
                tap2_hold = random.uniform(0.050, 0.065)
                res = self._execute_low_level(target_action, tap2_hold)
                if res:
                    self.last_pressed_action = target_action
                return res

            # -------------------------------------------------------------
            # Human Imperfection Model (Simulates ~15% human error / slips)
            # -------------------------------------------------------------
            if self.imperfection_cfg.get("enabled", True) and random.random() > self.rotation_effectiveness:
                error_roll = random.random()

                # 1. Double-Tap / Rapid Re-press (Button Mash error) ~40% of slips
                if error_roll < 0.40:
                    print(f"  [HUMAN JITTER] Double-tapping '{target_action}' (button mash emulation)")
                    self._execute_low_level(target_action, hold_time)
                    # Quick realistic finger gap (32ms - 65ms)
                    time.sleep(random.uniform(0.032, 0.065))
                    self._execute_low_level(target_action, hold_time * 0.8)
                    self.last_pressed_action = target_action
                    return True

                # 2. Fat-Finger Slip (Presses auto-attack '1' or previous key) ~35% of slips
                elif error_roll < 0.75:
                    slip_key = self.last_pressed_action if self.last_pressed_action else "1"
                    print(f"  [HUMAN JITTER] Slip / Fat-finger: pressed '{slip_key}' instead of '{target_action}'")
                    self._execute_low_level(slip_key, hold_time)
                    return True

                # 3. Hesitation / Micro-Distraction ~25% of slips
                else:
                    hesitation = random.uniform(0.12, 0.22)
                    print(f"  [HUMAN JITTER] Reaction hesitation (+{hesitation * 1000:.0f}ms micro-pause before '{target_action}')")
                    time.sleep(hesitation)
                    # Falls through to normal execution

            # Standard 85% clean execution
            res = self._execute_low_level(target_action, hold_time)
            if res:
                self.last_pressed_action = target_action
            return res

        except Exception as e:
            print(f"[InputController Error] Failed to execute input for '{target_action}' (from '{raw_input}'): {e}")
            return False



    def close(self) -> None:
        """Stop background listener."""
        if self._listener and self._listener.is_alive():
            self._listener.stop()
