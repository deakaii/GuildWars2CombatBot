# 🚀 Antigrav Bot Machine Migration Guide

Follow this simple guide to pack up the **Antigrav Bot** into a clean, compact single folder, upload it to Google Drive, and set it up seamlessly on any new machine.

---

## 📦 Step 1: Clean & Zip the Folder (Before Uploading)

Before uploading to Google Drive, you should **exclude virtual environments and temporary build caches**. Python virtual environments (`.venv`) contain machine-specific file paths and binary links that won't work across different machines, and Android build caches (`.gradle`) add unnecessary gigabytes.

### Folders to EXCLUDE or DELETE before zipping:
- `screen_monitor_bot\.venv` (Will be regenerated automatically on the new machine)
- `.gradle` & `app\build` (If moving the Android app code)
- Any `__pycache__` folders

### How to Zip the Folder on Windows:
1. Open your Desktop in File Explorer.
2. Delete or skip the `screen_monitor_bot\.venv` folder (or leave it out).
3. Right-click the `Antigrav` folder.
4. Select **Compress to ZIP file** (or **Send to > Compressed (zipped) folder**).
5. Rename the file to `Antigrav_Bot_Backup.zip`.

*The zipped file will now be very small (~few MBs) and fast to upload!*

---

## ☁️ Step 2: Upload to Google Drive

1. Open [Google Drive](https://drive.google.com).
2. Drag and drop `Antigrav_Bot_Backup.zip` into your Google Drive.

---

## 💻 Step 3: Setup on the New Machine

1. Log into Google Drive on the new machine and download `Antigrav_Bot_Backup.zip`.
2. Extract/Unzip the folder onto your Desktop (e.g., `C:\Users\<YourName>\Desktop\Antigrav`).
3. Make sure **Python 3.10 or higher** is installed on the new machine (download from [python.org](https://www.python.org/downloads/)). *Check "Add Python to PATH" during installation.*
4. Double-click **`setup.bat`** in the `Antigrav` root folder.
   - *This script automatically creates a fresh `.venv` virtual environment and installs all dependencies (`mss`, `opencv-python`, `pydirectinput`, `pynput`, `pyyaml`, `Pillow`).*

---

## 🎮 Step 4: Run & Calibrate on the New Machine

1. Double-click **`start_gui.bat`** to launch the bot dashboard.
2. **Screen Calibration (Important for New Displays)**:
   - If your new machine has a different display resolution (e.g. 1080p vs 1440p) or scale factor:
   - Open a terminal in `screen_monitor_bot` and run:
     ```powershell
     .\.venv\Scripts\python.exe main.py --calibrate
     ```
   - Drag a box over your in-game skill bar / visual trigger region and press **Enter** to save the ROI for your new monitor!
3. Press **[F9]** to start the bot or **[F10]** to pause.

---

## 📄 File Overview
- `setup.bat` - One-click setup script to build virtual environment and install libraries.
- `start_gui.bat` - One-click launcher for the graphical bot dashboard.
- `MIGRATION_GUIDE.md` - This guide.
- `screen_monitor_bot/` - Core Python screen monitoring & automation logic.
