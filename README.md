# Screen Monitoring & Prioritization Logic Loop 🎯

An extensible, undetectable automation engine designed for 3D Windows and DirectX applications. It monitors a designated region of your screen, evaluates prioritized behaviors at a configurable cadence (~500ms), and executes humanized hardware-level inputs safely.

---

## ⚡ Quick Start

### 1. Launch the Modern Graphical Dashboard (Recommended)
```powershell
cd screen_monitor_bot
.\.venv\Scripts\python.exe main.py --gui
```
- Features a **Profession / Elite Spec / Build** dropdown tree (covering all 9 Professions and 36 Elite Specs).
- Loads rotation priorities, keybinds, and cooldowns dynamically (default test build: **Engineer -> Mechanist -> Power Mechanist**).
- Direct buttons for **Start Bot (F9)**, **Pause (F10)**, **Open Live HUD**, and **Calibrate Region**.
- Live activity console showing real-time telemetry and character state.

### 2. Step 1: Calibrate Screen Region & Grab Trigger Template
Run the visual calibrator:
```powershell
python main.py --calibrate
```
- A fullscreen overlay freezes your screen.
- **Drag a box** over the region of the screen you want to monitor (e.g., skill bar, buff slot, status indicator).
- Press **`[Enter]`** to save the ROI coordinates to `config/settings.yaml`.
- Press **`[T]`** to save your selected box directly as the reference template image (`config/templates/trigger_icon.png`)!
- Press **`[ESC]`** to cancel.

### 3. Step 2: Verify with Live Diagnostic HUD (Read-Only)
Before sending any inputs, launch the read-only live preview HUD:
```powershell
python main.py --hud
```
- Shows live FPS, latency (typically **~3–5ms**), and the cropped ROI in real time.
- Visually draws an emerald box around detected trigger icons with real-time confidence % and scale factor.
- Press **`[S]`** to save a fresh template snapshot.
- Press **`[Q]`** to exit.

### 4. Step 3: Run the Full Prioritization Loop
```powershell
python main.py
```
- Monitors the calibrated ROI every ~250ms (with micro-jitter to prevent periodic pattern detection).
- When your visual cue is detected and its cooldown has elapsed, it dispatches the configured DirectInput key press (`'1'`).

#### 🎮 Macro Controls & State Management:
- **`[F9]` (Start Macro)**: Engages the action loop. All prioritized rules will evaluate and execute actions.
- **`[F10]` (Stop / Pause Macro)**: Disengages the action loop. The bot enters `STANDBY / PAUSED` mode (passively monitoring, but **zero** inputs will be sent).
- **`[F12]` (Emergency Stop)**: Instantly halts and terminates the script.

#### 🛡️ Automatic Enemy / Target Guard:
- When enabled in `settings.yaml`, the bot continuously verifies if the target/enemy indicator is present.
- If the target is lost or dies, the bot **automatically disengages** within 2 ticks (~500ms) to ensure no unwanted abilities or inputs are triggered when there's nothing to fight!

---

## 🖥️ Multi-Device & Resolution Independence

To ensure this works consistently across different monitors, resolutions (1080p, 1440p, 4K), and Windows DPI scaling (100%, 125%, 150%):
1. **Per-Monitor DPI Awareness**: The engine calls Windows `SetProcessDpiAwareness(2)` to interact with physical device pixels rather than blurry virtualized pixels.
2. **Normalized Relative Coordinates**: When you calibrate with `calibrate_roi.py`, it calculates normalized ratios (`0.0` to `1.0` of screen width and height). If you move the configuration to a 1440p or 4K monitor, the ROI automatically scales to the corresponding physical coordinates on that display!
3. **Multi-Scale Template Matching**: Reference templates are matched across dynamic scale pyramids (`0.8x` to `1.25x`), detecting the target icon even if the game's UI is scaled slightly differently across resolutions.

---

## 🛡️ Anti-Detection & Stealth Design

1. **Zero Memory Injection**: Operates 100% externally using passive Windows desktop duplication / `mss`. It never accesses game memory, attaches debuggers, or hooks game DLLs.
2. **Hardware DirectInput Scan Codes**: Uses Windows `SendInput` with `KEYEVENTF_SCANCODE` via `pydirectinput`, generating identical low-level scan codes to physical keyboards.
3. **Humanized Micro-Jitter**:
   - Random key hold duration: 52ms – 88ms (simulating physical switch travel).
   - Reaction time latency: 30ms – 75ms randomized delay before dispatching.
   - Fuzzy cooldown margins (+/- 5%) so actions never trigger on exact millisecond intervals.

---

## ➕ How to Add New Behaviors (Behavior 2, 3, etc.)

Adding new behaviors is modular and clean.

### 1. Create `behaviors/behavior_two.py`:
```python
from behaviors.base import BaseBehavior

class BehaviorTwo(BaseBehavior):
    def __init__(self, config):
        # Name, Priority (e.g. 50 is evaluated after 100), Cooldown in seconds
        super().__init__(name="SecondaryAction", priority=50, cooldown_seconds=5.0)
        self.key_to_press = "2"

    def evaluate_condition(self, frame, detector):
        # Match a template, check a color threshold, or check pixel intensity
        res = detector.match_template(frame, "secondary_icon.png", threshold=0.80)
        return res.matched, res

    def execute_action(self, input_controller):
        print(f"[{self.name}] Triggered -> Pressing key '{self.key_to_press}'")
        return input_controller.press_key(self.key_to_press)
```

### 2. Register it in `main.py`:
```python
from behaviors.behavior_two import BehaviorTwo

b2 = BehaviorTwo(config.get("behavior_two", {}))
engine.register_behavior(b2)
```

The engine automatically sorts all behaviors by priority and ensures high-priority conditions are always satisfied first!

---

## 🧪 Running Automated Tests
```powershell
python tests/test_pipeline.py
```
Validates DPI awareness, screen capture latency, multi-scale template matching, priority hierarchy evaluation, and the emergency kill switch.
