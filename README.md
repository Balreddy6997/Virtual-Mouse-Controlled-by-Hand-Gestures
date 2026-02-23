# Virtual-Mouse-Controlled-by-Hand-Gestures

# 🖐️ Gesture Control

Control your mouse, scroll, and zoom using nothing but your webcam and hand gestures — powered by MediaPipe and PyAutoGUI.

---

## ✨ Features

| Mode | What it does |
|------|-------------|
| **MOUSE** | Move cursor, left/right/double click, screenshot |
| **SCROLL** | Scroll up or down continuously |
| **ZOOM** | Zoom in/out or reset zoom in any application |

---

## 📦 Requirements

- Python 3.8+
- A webcam

Install dependencies:

```bash
pip install opencv-python mediapipe pyautogui numpy
```

---

## 🚀 Usage

```bash
python gesture_control.py
```

Press **ESC** to quit.

---

## 🤚 Gesture Reference

### Mode Switching
Switch modes at any time using these gestures (middle + ring fingers always closed):

| Gesture | Switches to |
|---------|-------------|
| Thumb open only | **MOUSE** mode |
| Pinky open only | **SCROLL** mode |
| Thumb + Index open | **ZOOM** mode |

---

### 🖱️ MOUSE Mode

**Cursor Movement** — controlled by your index fingertip within the ROI box shown on screen.

| Gesture | Action |
|---------|--------|
| Thumb open | Cursor **moves** with index fingertip |
| Thumb closed | Cursor **stops** |
| Thumb closed + Index bent | **Left click** |
| Thumb closed + Middle bent | **Right click** |
| Thumb closed + Index + Middle bent | **Double click** |
| Full fist held for ~0.7s | **Screenshot** saved to current directory |

---

### 📜 SCROLL Mode

| Gesture | Action |
|---------|--------|
| Index up, rest closed | Scroll **up** ↑ |
| Full fist | Scroll **down** ↓ |
| All fingers open | **Stop** scrolling |

---

### 🔍 ZOOM Mode

Uses `Ctrl + Scroll` under the hood, so it works in browsers, image viewers, code editors, and more.

| Gesture | Action |
|---------|--------|
| Index up only | **Zoom in** (+) |
| Full fist | **Zoom out** (−) |
| All fingers open | **Reset zoom** (Ctrl+0) |

---

## ⚙️ Configuration

Tune these constants at the top of the script to your liking:

| Constant | Default | Description |
|----------|---------|-------------|
| `SMOOTH` | `4` | Cursor smoothing — lower = faster/jitterier |
| `ACT_COOLDOWN` | `0.50` | Seconds between clicks/mode switches |
| `SCROLL_SENS` | `600` | Scroll speed (legacy, not currently active) |
| `ZOOM_COOL` | `0.06` | Seconds between zoom steps |
| `SCREENSHOT_HOLD` | `0.7` | Seconds to hold fist for screenshot |
| `ROI_L/R/T/B` | `0.10 / 0.75 / 0.10 / 0.80` | Webcam region mapped to full screen |

---

## 🖥️ HUD Overview

The overlay window shows:
- **Top-right badge** — current active mode
- **ROI box** — the area your hand should stay within
- **Bottom legend** — all available modes at a glance
- **Flash banner** — briefly shown when switching modes
- **On-screen labels** — real-time action feedback (MOVING, LEFT CLICK, etc.)

---

## 📁 Screenshots

Screenshots taken via the fist-hold gesture are saved in the working directory as:
```
screenshot_<unix_timestamp>.png
```

---

## 🛠️ How It Works

1. **MediaPipe Hands** detects 21 hand landmarks from the webcam feed.
2. Finger states (extended / bent) are derived by comparing tip vs. pip/mcp joint Y-coordinates.
3. The thumb open/closed state is determined by the distance between the thumb tip and the middle-finger MCP joint — making it stable regardless of other finger positions.
4. The index fingertip is mapped from the ROI region of the webcam frame to full screen coordinates, with exponential smoothing applied to reduce jitter.
5. PyAutoGUI translates the detected gestures into OS-level mouse and keyboard events.

---

## ⚠️ Notes

- `pyautogui.FAILSAFE` is disabled — move your mouse to a screen corner will **not** abort the program. Use **ESC** instead.
- Works best with good, consistent lighting.
- Keep your hand within the colored ROI box drawn on the webcam preview.
- On some systems, `Ctrl+0` for zoom reset may not work in all apps — you can remap this in the ZOOM section of the code.
