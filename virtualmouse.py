import cv2
import mediapipe as mp
import pyautogui
import time
import numpy as np

pyautogui.FAILSAFE = False

# ─────────────────────────────────────────────────────────────
#  MediaPipe
# ─────────────────────────────────────────────────────────────
mp_hands = mp.solutions.hands
mp_draw  = mp.solutions.drawing_utils
hands    = mp_hands.Hands(max_num_hands=1,
                          min_detection_confidence=0.8,
                          min_tracking_confidence=0.7)

# ─────────────────────────────────────────────────────────────
#  Screen & Camera
# ─────────────────────────────────────────────────────────────
cap = cv2.VideoCapture(0)
screen_w, screen_h = pyautogui.size()

# ─────────────────────────────────────────────────────────────
#  ROI — region of webcam mapped to full screen
# ─────────────────────────────────────────────────────────────
ROI_L, ROI_R = 0.10, 0.75
ROI_T, ROI_B = 0.10, 0.80

# ─────────────────────────────────────────────────────────────
#  Modes  (DRAW removed)
# ─────────────────────────────────────────────────────────────
MODES = ["MOUSE", "SCROLL", "ZOOM"]
mode_idx = 0

MODE_COLOR = {
    "MOUSE":  (0,   210, 110),   # green
    "SCROLL": (0,   170, 255),   # blue
    "ZOOM":   (0,   220, 200),   # cyan
}
MODE_LABEL = {
    "MOUSE":  "MOUSE  - thumb open=move, close=stop+click",
    "SCROLL": "SCROLL - fist=down  index up=up  open=stop",
    "ZOOM":   "ZOOM   - index up=in  fist=out  all open=reset",
}

# ─────────────────────────────────────────────────────────────
#  Tuning
# ─────────────────────────────────────────────────────────────
SMOOTH       = 4      # cursor smoothing (lower = faster)
ACT_COOLDOWN = 0.50   # min seconds between clicks/actions
SCROLL_SENS  = 600    # scroll speed
ZOOM_SENS    = 8.0    # pinch pixels per zoom step
ZOOM_COOL    = 0.06   # min seconds between zoom steps

# ─────────────────────────────────────────────────────────────
#  State
# ─────────────────────────────────────────────────────────────
prev_x = prev_y  = 0
last_act         = 0.0
last_zoom_t      = 0.0
scroll_ref_y     = None
pinch_ref_dist   = None
mode_flash_t     = -99.0
fist_hold_start  = None   # for screenshot hold gesture
SCREENSHOT_HOLD  = 0.7   # seconds to hold fist for screenshot

# ─────────────────────────────────────────────────────────────
#  Gesture helpers
# ─────────────────────────────────────────────────────────────

def is_extended(lm, tip, pip, mcp):
    """Finger extended = tip is above both pip and mcp joint."""
    return lm[tip].y < lm[pip].y and lm[tip].y < lm[mcp].y


def thumb_open(lm):
    """
    Thumb OPEN = tip (lm4) far from middle-finger MCP (lm9).
    This landmark pair is stable regardless of other finger positions.
    """
    dx = lm[4].x - lm[9].x
    dy = lm[4].y - lm[9].y
    return (dx*dx + dy*dy) ** 0.5 > 0.15


def get_fingers(lm):
    return {
        "thumb":  thumb_open(lm),
        "index":  is_extended(lm, 8,  6,  5),
        "middle": is_extended(lm, 12, 10, 9),
        "ring":   is_extended(lm, 16, 14, 13),
        "pinky":  is_extended(lm, 20, 18, 17),
    }


def pinch_dist_px(lm, w, h):
    x1, y1 = lm[4].x * w, lm[4].y * h
    x2, y2 = lm[8].x * w, lm[8].y * h
    return ((x2-x1)**2 + (y2-y1)**2) ** 0.5


def move_cursor(lm, w, h, rx1, rx2, ry1, ry2):
    """Map index fingertip inside ROI → screen position, apply smoothing."""
    global prev_x, prev_y
    ix = int(lm[8].x * w)
    iy = int(lm[8].y * h)
    ix = max(rx1, min(ix, rx2))
    iy = max(ry1, min(iy, ry2))
    nx = (ix - rx1) / (rx2 - rx1)
    ny = (iy - ry1) / (ry2 - ry1)
    tx = int(nx * screen_w)
    ty = int(ny * screen_h)
    prev_x = int(prev_x + (tx - prev_x) / SMOOTH)
    prev_y = int(prev_y + (ty - prev_y) / SMOOTH)
    pyautogui.moveTo(prev_x, prev_y)

# ─────────────────────────────────────────────────────────────
#  HUD helpers
# ─────────────────────────────────────────────────────────────

def rounded_rect(img, x1, y1, x2, y2, r, color, alpha=0.82):
    ov = img.copy()
    cv2.rectangle(ov, (x1+r, y1), (x2-r, y2), color, -1)
    cv2.rectangle(ov, (x1, y1+r), (x2, y2-r), color, -1)
    for cx, cy in [(x1+r,y1+r),(x2-r,y1+r),(x1+r,y2-r),(x2-r,y2-r)]:
        cv2.circle(ov, (cx,cy), r, color, -1)
    cv2.addWeighted(ov, alpha, img, 1-alpha, 0, img)


def draw_hud(frame, mode, w, h, flash_t):
    col = MODE_COLOR[mode]
    now = time.time()

    # ── Top-right mode badge ──────────────────────────────────
    bw, bh = 340, 56
    bx, by = w - bw - 14, 12
    rounded_rect(frame, bx, by, bx+bw, by+bh, 12, (12,12,22), alpha=0.85)
    cv2.rectangle(frame, (bx, by+8), (bx+5, by+bh-8), col, -1)
    cv2.putText(frame, mode, (bx+16, by+24),
                cv2.FONT_HERSHEY_DUPLEX, 0.78, col, 1, cv2.LINE_AA)
    sub = MODE_LABEL[mode].split("-",1)[-1].strip()
    cv2.putText(frame, sub, (bx+16, by+46),
                cv2.FONT_HERSHEY_SIMPLEX, 0.40, (160,160,175), 1, cv2.LINE_AA)


    # ── Flash banner on mode switch ───────────────────────────
    elapsed = now - flash_t
    if elapsed < 1.0:
        fade = max(0.0, 1.0 - elapsed)
        ov   = frame.copy()
        cv2.rectangle(ov, (0, h//2-36), (w, h//2+36), col, -1)
        cv2.addWeighted(ov, fade*0.55, frame, 1-fade*0.55, 0, frame)
        txt = f"  {mode} MODE  "
        tsz = cv2.getTextSize(txt, cv2.FONT_HERSHEY_DUPLEX, 1.3, 2)[0]
        cv2.putText(frame, txt, (w//2 - tsz[0]//2, h//2+16),
                    cv2.FONT_HERSHEY_DUPLEX, 1.3, (255,255,255), 2, cv2.LINE_AA)

    # ── Bottom legend ─────────────────────────────────────────
    lx, ly = 14, h - 110
    for m in MODES:
        active = (m == mode)
        bg = MODE_COLOR[m] if active else (32,32,42)
        rounded_rect(frame, lx, ly, lx+220, ly+28, 5, bg, alpha=0.78)
        tc = (255,255,255) if active else (120,120,135)
        cv2.putText(frame, MODE_LABEL[m].split("-")[0].strip() +
                    " - " + MODE_LABEL[m].split("-",1)[-1].strip()[:28],
                    (lx+8, ly+18), cv2.FONT_HERSHEY_SIMPLEX,
                    0.38, tc, 1, cv2.LINE_AA)
        ly += 32

    # ── Thumb hint (always visible) ───────────────────────────
    hint = "Thumb OPEN=move  CLOSED=stop  |  Switch: Pinky=SCROLL  Thumb=MOUSE  Thumb+Index=ZOOM"
    cv2.putText(frame, hint, (14, h-8),
                cv2.FONT_HERSHEY_SIMPLEX, 0.33, (100,100,118), 1, cv2.LINE_AA)


# ─────────────────────────────────────────────────────────────
#  Main loop
# ─────────────────────────────────────────────────────────────
while True:
    ret, frame = cap.read()
    if not ret:
        break

    frame = cv2.flip(frame, 1)
    h, w, _ = frame.shape
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    # ROI box
    rx1, rx2 = int(w*ROI_L), int(w*ROI_R)
    ry1, ry2 = int(h*ROI_T), int(h*ROI_B)
    mode = MODES[mode_idx]
    mc   = MODE_COLOR[mode]
    cv2.rectangle(frame, (rx1,ry1), (rx2,ry2), mc, 2)

    result = hands.process(rgb)
    now    = time.time()

    if result.multi_hand_landmarks:
        hl = result.multi_hand_landmarks[0]
        lm = hl.landmark

        # Draw skeleton in mode colour
        spec = mp_draw.DrawingSpec(color=mc, thickness=2, circle_radius=3)
        mp_draw.draw_landmarks(frame, hl, mp_hands.HAND_CONNECTIONS, spec, spec)

        f       = get_fingers(lm)
        thm_up  = f["thumb"]    # True = open, False = closed/bent
        idx_up  = f["index"]
        mid_up  = f["middle"]
        rng_up  = f["ring"]
        pnk_up  = f["pinky"]

        # ══════════════════════════════════════════════════════
        #  STEP 1 — CURSOR  (runs in ALL modes)
        #  Thumb OPEN  → cursor follows index fingertip
        #  Thumb CLOSED → cursor freezes
        # ══════════════════════════════════════════════════════
        if thm_up:
            move_cursor(lm, w, h, rx1, rx2, ry1, ry2)
            # Visual: glowing dot on index tip
            tip_x = int(lm[8].x * w)
            tip_y = int(lm[8].y * h)
            cv2.circle(frame, (tip_x, tip_y), 14, mc, -1)
            cv2.circle(frame, (tip_x, tip_y), 17, (255,255,255), 1)
            cv2.putText(frame, "MOVING", (10, 42),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.75, mc, 2)
        else:
            cv2.putText(frame, "STOPPED", (10, 42),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.75, (80,80,95), 1)

        # ══════════════════════════════════════════════════════
        #  STEP 2 — MODE SWITCH  (instant, works from any mode)
        #  All closed + only PINKY open  → MOUSE mode
        #  All closed + only THUMB open  → SCROLL mode
        #  All closed + THUMB + INDEX open → ZOOM mode
        # ══════════════════════════════════════════════════════

        # Base: index, middle, ring all closed
        base_closed = not idx_up and not mid_up and not rng_up

        to_mouse  = base_closed and pnk_up  and not thm_up  # pinky only
        to_scroll = base_closed and thm_up  and not pnk_up  # thumb only
        to_zoom   = base_closed and thm_up  and idx_up and not pnk_up  # thumb+index

        # Re-check idx for zoom (it was used in base_closed above so override)
        to_zoom   = not mid_up and not rng_up and not pnk_up and thm_up and idx_up
        to_scroll = not idx_up and not mid_up and not rng_up and pnk_up and not thm_up  # pinky open → SCROLL
        to_mouse  = not idx_up and not mid_up and not rng_up and not pnk_up and thm_up  # thumb open → MOUSE

        switch_gesture = to_mouse or to_scroll or to_zoom

        if switch_gesture and now - last_act > ACT_COOLDOWN:
            new_mode = None
            if to_zoom:
                new_mode = "ZOOM"
            elif to_mouse:
                new_mode = "MOUSE"
            elif to_scroll:
                new_mode = "SCROLL"

            if new_mode and new_mode != MODES[mode_idx]:
                mode_idx       = MODES.index(new_mode)
                mode_flash_t   = now
                scroll_ref_y   = None
                pinch_ref_dist = None
                last_act       = now

        # Visual feedback for switch gestures
        if to_scroll:
            cv2.putText(frame, "-> SCROLL MODE", (10, 78),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.65, MODE_COLOR["SCROLL"], 2)
        elif to_mouse:
            cv2.putText(frame, "-> MOUSE MODE", (10, 78),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.65, MODE_COLOR["MOUSE"], 2)
        elif to_zoom:
            cv2.putText(frame, "-> ZOOM MODE", (10, 78),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.65, MODE_COLOR["ZOOM"], 2)

        pinky_only = to_scroll or to_mouse or to_zoom  # guard clicks during mode switch

        # ══════════════════════════════════════════════════════
        #  STEP 3 — CLICKS  (all modes, only when thumb CLOSED)
        #  Index bend        → Left Click
        #  Middle bend       → Right Click
        #  Index+Middle bend → Double Click
        # ══════════════════════════════════════════════════════
        if mode == "MOUSE" and not thm_up and not pinky_only:

            # ── Screenshot: full fist held for 0.7s ──────────
            full_fist = not idx_up and not mid_up and not rng_up and not pnk_up

            if full_fist:
                if fist_hold_start is None:
                    fist_hold_start = now
                held = now - fist_hold_start
                progress = min(held / SCREENSHOT_HOLD, 1.0)

                # Draw hold progress arc on wrist area
                wx = int(lm[0].x * w)
                wy = int(lm[0].y * h)
                cv2.ellipse(frame, (wx, wy), (28, 28), -90, 0,
                            int(360 * progress), (0, 0, 220), 3)
                cv2.putText(frame, f"Hold for screenshot...",
                            (10, 78), cv2.FONT_HERSHEY_SIMPLEX,
                            0.65, (0, 0, 220), 2)

                if held >= SCREENSHOT_HOLD and now - last_act > ACT_COOLDOWN:
                    save_path = f"screenshot_{int(now)}.png"
                    pyautogui.screenshot(save_path)
                    print("Screenshot saved:", save_path)
                    cv2.putText(frame, "SCREENSHOT SAVED!", (10, 78),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 220), 2)
                    last_act       = now
                    fist_hold_start = None
            else:
                fist_hold_start = None

            # ── Clicks (only when NOT full fist) ─────────────
            if not full_fist and now - last_act > ACT_COOLDOWN:

                # Double click — index AND middle both bent
                if not idx_up and not mid_up:
                    pyautogui.doubleClick()
                    cv2.putText(frame, "DOUBLE CLICK", (10, 78),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,220,220), 2)
                    last_act = now

                # Left click — only index bent, middle extended
                elif not idx_up and mid_up:
                    pyautogui.click()
                    cv2.putText(frame, "LEFT CLICK", (10, 78),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (50,220,50), 2)
                    last_act = now

                # Right click — only middle bent, index extended
                elif idx_up and not mid_up:
                    pyautogui.click(button='right')
                    cv2.putText(frame, "RIGHT CLICK", (10, 78),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (220,220,50), 2)
                    last_act = now
        else:
            fist_hold_start = None

        # ══════════════════════════════════════════════════════
        #  STEP 4 — MODE-SPECIFIC ACTIONS
        # ══════════════════════════════════════════════════════
        mode = MODES[mode_idx]   # re-read in case it just changed

        # ── SCROLL MODE ───────────────────────────────────────
        #  All fingers OPEN          → stop scrolling
        #  All fingers CLOSED (fist) → scroll DOWN continuously
        #  All closed + index OPEN   → scroll UP continuously
        if mode == "SCROLL":
            all_open   = idx_up and mid_up and rng_up and pnk_up
            all_closed = not idx_up and not mid_up and not rng_up and not pnk_up
            scroll_up_gesture = idx_up and not mid_up and not rng_up and not pnk_up  # fist + index open

            if all_open:
                # All fingers open → stop
                cv2.putText(frame, "SCROLL STOPPED  (open palm)", (10, 112),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.65, (80,80,95), 1)

            elif scroll_up_gesture:
                # Index open, rest closed → scroll UP
                pyautogui.scroll(15)
                tip_x = int(lm[8].x * w)
                tip_y = int(lm[8].y * h)
                cv2.circle(frame, (tip_x, tip_y), 12, mc, -1)
                cv2.putText(frame, "SCROLL UP  ↑", (10, 112),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.75, mc, 2)

            elif all_closed:
                # Full fist → scroll DOWN
                pyautogui.scroll(-15)
                cv2.putText(frame, "SCROLL DOWN  ↓", (10, 112),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0,170,255), 2)

            else:
                cv2.putText(frame, "Fist=scroll down  Index up=scroll up  Open=stop",
                            (10, 112), cv2.FONT_HERSHEY_SIMPLEX,
                            0.48, (80,80,95), 1)

        # ── ZOOM MODE ─────────────────────────────────────────
        #  Index finger UP   → Zoom IN  (Ctrl + scroll up)
        #  Index finger DOWN → Zoom OUT (Ctrl + scroll down)
        #  All fingers open  → Reset zoom (Ctrl+0)
        elif mode == "ZOOM":
            all_open_zoom = idx_up and mid_up and rng_up and pnk_up

            if all_open_zoom:
                # All open → reset zoom
                if now - last_act > ACT_COOLDOWN:
                    pyautogui.hotkey('ctrl', '0')
                    last_act = now
                    cv2.putText(frame, "ZOOM RESET (Ctrl+0)", (10, 112),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.75, (255,200,0), 2)
                else:
                    cv2.putText(frame, "ZOOM RESET (Ctrl+0)", (10, 112),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.75, (255,200,0), 2)

            elif idx_up and not mid_up and not rng_up and not pnk_up:
                # Only index UP → Zoom IN
                if now - last_zoom_t > ZOOM_COOL:
                    pyautogui.keyDown('ctrl')
                    pyautogui.scroll(3)
                    pyautogui.keyUp('ctrl')
                    last_zoom_t = now
                tip_x = int(lm[8].x * w)
                tip_y = int(lm[8].y * h)
                cv2.circle(frame, (tip_x, tip_y), 12, mc, -1)
                cv2.putText(frame, "ZOOM IN  +", (10, 112),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, mc, 2)

            elif not idx_up and not mid_up and not rng_up and not pnk_up:
                # Full fist → Zoom OUT
                if now - last_zoom_t > ZOOM_COOL:
                    pyautogui.keyDown('ctrl')
                    pyautogui.scroll(-3)
                    pyautogui.keyUp('ctrl')
                    last_zoom_t = now
                cv2.putText(frame, "ZOOM OUT  -", (10, 112),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,170,255), 2)

            else:
                cv2.putText(frame, "Index UP=zoom in  Fist=zoom out  All open=reset",
                            (10, 112), cv2.FONT_HERSHEY_SIMPLEX,
                            0.50, (80,80,95), 1)

    else:
        # No hand detected — reset all stateful tracking
        scroll_ref_y     = None
        pinch_ref_dist   = None
        fist_hold_start  = None
        cv2.putText(frame, "No hand detected", (10, 42),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.65, (60,60,75), 1)

    draw_hud(frame, MODES[mode_idx], w, h, mode_flash_t)
    cv2.imshow("Gesture Control", frame)
    if cv2.waitKey(1) & 0xFF == 27:
        break

cap.release()
cv2.destroyAllWindows()
