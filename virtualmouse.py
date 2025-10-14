import cv2
import mediapipe as mp
import pyautogui
import time
import math

# =========================
# Helper Functions
# =========================
def finger_bent(lm, tip, pip):
    """Return True if finger is bent (tip below pip)."""
    if tip == 4:  # Thumb tip
        return lm[tip].y > lm[2].y + 0.05
    return lm[tip].y > lm[pip].y

def distance(p1, p2):
    """Return Euclidean distance between two Mediapipe landmarks."""
    return math.sqrt((p1.x - p2.x) ** 2 + (p1.y - p2.y) ** 2)

# =========================
# Mediapipe Initialization
# =========================
mp_hands = mp.solutions.hands
mp_draw = mp.solutions.drawing_utils
hands = mp_hands.Hands(max_num_hands=2, min_detection_confidence=0.7)

# Webcam & Screen
cap = cv2.VideoCapture(0)
screen_w, screen_h = pyautogui.size()

# Settings
smoothing = 7
speed = 2.5
prev_x, prev_y = 0, 0
last_action_time = 0
cooldown = 0.5

# ROI (Region of Interest)
roi_left_margin = 0.15
roi_right_margin = 0.70
roi_top_margin = 0.20 
roi_bottom_margin = 0.50

# Two-hand zoom tracking
previous_hand_distance = None

# =========================
# Main Loop
# =========================
while True:
    ret, frame = cap.read()
    if not ret:
        break

    frame = cv2.flip(frame, 1)
    h, w, _ = frame.shape
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    # Draw ROI box
    roi_x_min = int(w * roi_left_margin)
    roi_x_max = int(w * roi_right_margin)
    roi_y_min = int(h * roi_top_margin)
    roi_y_max = int(h * roi_bottom_margin)
    cv2.rectangle(frame, (roi_x_min, roi_y_min), (roi_x_max, roi_y_max), (255, 0, 0), 2)

    # Process frame for hand landmarks
    result = hands.process(rgb_frame)

    hand_list = []
    if result.multi_hand_landmarks:
        for hand_landmarks in result.multi_hand_landmarks:
            mp_draw.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)
            hand_list.append(hand_landmarks.landmark)

    # -----------------------
    # TWO-HAND ZOOM DETECTION
    # -----------------------
    if len(hand_list) == 2:
        # Get index fingertip from both hands
        left_index = hand_list[0][8]
        right_index = hand_list[1][8]

        # Compute distance between hands (normalized)
        current_distance = distance(left_index, right_index)

        if previous_hand_distance is not None and time.time() - last_action_time > cooldown:
            if current_distance > previous_hand_distance + 0.03:
                pyautogui.hotkey('ctrl', '+')
                cv2.putText(frame, "Zoom In (Two Hands)", (10, 230),
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                last_action_time = time.time()

            elif current_distance < previous_hand_distance - 0.03:
                pyautogui.hotkey('ctrl', '-')
                cv2.putText(frame, "Zoom Out (Two Hands)", (10, 230),
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
                last_action_time = time.time()

        previous_hand_distance = current_distance
    else:
        previous_hand_distance = None  # Reset if only one hand visible

    # -----------------------
    # SINGLE-HAND MOUSE CONTROL (Only if 1 hand is detected)
    # -----------------------
    if len(hand_list) == 1:
        lm = hand_list[0]

        # Cursor Movement
        thumb_open_for_cursor_stop = lm[4].x > lm[3].x
        if not thumb_open_for_cursor_stop:
            x = int(lm[8].x * w)
            y = int(lm[8].y * h)

            x = max(roi_x_min, min(x, roi_x_max))
            y = max(roi_y_min, min(y, roi_y_max))

            norm_x = (x - roi_x_min) / (roi_x_max - roi_x_min)
            norm_y = (y - roi_y_min) / (roi_y_max - roi_y_min)

            target_x = int(norm_x * screen_w)
            target_y = int(norm_y * screen_h)

            curr_x = prev_x + (target_x - prev_x) / smoothing
            curr_y = prev_y + (target_y - prev_y) / smoothing

            move_x = prev_x + (curr_x - prev_x) * speed
            move_y = prev_y + (curr_y - prev_y) * speed

            move_x = max(0, min(move_x, screen_w - 1))
            move_y = max(0, min(move_y, screen_h - 1))

            pyautogui.moveTo(move_x, move_y)
            prev_x, prev_y = move_x, move_y

            cv2.putText(frame, "Moving Cursor", (10, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        else:
            cv2.putText(frame, "Thumb Open - Cursor Stopped", (10, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

        # Finger Bend Detection
        index_bent = finger_bent(lm, 8, 6)
        middle_bent = finger_bent(lm, 12, 10)
        ring_bent = finger_bent(lm, 16, 14)
        pinky_bent = finger_bent(lm, 20, 18)
        thumb_bent = finger_bent(lm, 4, 2)

        if time.time() - last_action_time > cooldown:
            # Left Click
            if index_bent and not middle_bent and not ring_bent and not pinky_bent and not thumb_bent:
                pyautogui.click()
                cv2.putText(frame, "Left Click", (10, 80),
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 0), 2)
                last_action_time = time.time()

            # Right Click
            elif middle_bent and not index_bent and not ring_bent and not pinky_bent and not thumb_bent:
                pyautogui.click(button='right')
                cv2.putText(frame, "Right Click", (10, 110),
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
                last_action_time = time.time()

            # Double Click
            elif index_bent and middle_bent and not ring_bent and not pinky_bent and not thumb_bent:
                pyautogui.doubleClick()
                cv2.putText(frame, "Double Click", (10, 140),
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
                last_action_time = time.time()

            # Screenshot
            elif index_bent and middle_bent and ring_bent and pinky_bent:
                save_path = f"screenshot_{int(time.time())}.png"
                pyautogui.screenshot(save_path)
                print("Screenshot saved as:", save_path)
                cv2.putText(frame, "Screenshot Taken", (10, 170),
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
                last_action_time = time.time()

    cv2.imshow("Virtual Mouse with Two-Hand Zoom", frame)

    if cv2.waitKey(1) & 0xFF == 27:  # ESC to exit
        break

cap.release()
cv2.destroyAllWindows()