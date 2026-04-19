import cv2
import numpy as np
import mss
import time
import keyboard
import ctypes
import random

# ====== 鼠标控制===
user32 = ctypes.WinDLL('user32', use_last_error=True)


def mouse_move_relative(dx, dy):
    MAX_STEP = 100
    dx = max(-MAX_STEP, min(MAX_STEP, dx))
    dy = max(-MAX_STEP, min(MAX_STEP, dy))
    user32.mouse_event(0x0001, dx, dy, 0, 0)


def mouse_click():
    user32.mouse_event(0x0002, 0, 0, 0, 0)
    time.sleep(0.001)
    user32.mouse_event(0x0004, 0, 0, 0, 0)


# =========== 自定义需要识别的颜色（传入RGB =============
TARGET_RGB = [0,128, 255]
H_TOLERANCE = 15
S_TOLERANCE = 60
V_TOLERANCE = 60

# ==============所有参数=====================
MIN_AREA = 20
MAX_AREA = 5000 #这两个控制最小/最大识别区域面积，区间外的色块不被识别
W, H = 2560, 1600   #设置为屏幕真实的宽高
CX, CY = W // 2, H // 2
SCALE = 0.2    #鼠标移动灵敏度控制
AIM_THRESHOLD = 20  #准度判定静态设置（后续有动态调整）越小判定越严格

SEARCH_SPEED = 0    #可选在没有识别到指定颜色时随机移动视角搜索，此处已关闭
SEARCH_INTERVAL = 2
LOCK_DURATION = 5   #下面几个参数是防止当两个目标间距几乎相等时，容易左右横跳而设置的
MAX_TRACK_DIST = 50
DIST_TOLERANCE = 20

CROP_W = 1280//2
CROP_H = 800//2
crop_x1 = (W - CROP_W) // 2
crop_y1 = (H - CROP_H) // 2

DYNAMIC_FACTOR = 80

print("按 F1 开始调试 F2 终止调试")



def rgb_to_hsv_range(rgb, h_tol, s_tol, v_tol):
    """将传入的rgb转为opencv使用的hsv"""
    r, g, b = rgb
    rgb_arr = np.uint8([[[r, g, b]]])
    hsv = cv2.cvtColor(rgb_arr, cv2.COLOR_RGB2HSV)[0][0]

    h = int(hsv[0])
    s = int(hsv[1])
    v = int(hsv[2])

    lower_h = max(0, h - h_tol)
    upper_h = min(179, h + h_tol)
    lower_s = max(0, s - s_tol)
    upper_s = min(255, s + s_tol)
    lower_v = max(0, v - v_tol)
    upper_v = min(255, v + v_tol)

    return np.array([lower_h, lower_s, lower_v]), np.array([upper_h, upper_s, upper_v])


LOWER_COLOR, UPPER_COLOR = rgb_to_hsv_range(TARGET_RGB, H_TOLERANCE, S_TOLERANCE, V_TOLERANCE)


sct = mss.mss()
monitor = {"top": crop_y1, "left": crop_x1, "width": CROP_W, "height": CROP_H}
kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))

search_counter = 0
is_running = False

locked_x = None
locked_y = None
lock_timer = 0
smooth_x = 0.0
smooth_y = 0.0
EMA_ALPHA = 0.4



def split_blob_centers(roi_mask, offset_x, offset_y):
    """若小球存在粘连，将其拆分"""
    dist = cv2.distanceTransform(roi_mask, cv2.DIST_L2, 3)
    dist = cv2.normalize(dist, None, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_8U)
    _, peak = cv2.threshold(dist, 0.7 * dist.max(), 255, cv2.THRESH_BINARY)
    peak = np.uint8(peak)
    cnts, _ = cv2.findContours(peak, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    centers = []
    for c in cnts:
        M = cv2.moments(c)
        if M['m00'] != 0:
            cx = int(M["m10"] / M["m00"]) + offset_x
            cy = int(M["m10"] / M["m00"]) + offset_y
            centers.append((cx, cy))
    return centers


# ========= 主循环 ===========
while True:
    if keyboard.is_pressed('F1') and not is_running:
        is_running = True
        print("开始调试")
        locked_x = None
        locked_y = None
        lock_timer = 0
        smooth_x = 0.0
        smooth_y = 0.0
        search_counter = 0

    if keyboard.is_pressed('F2') and is_running:
        print("终止调试")
        is_running = False
        locked_x = None
        locked_y = None
        lock_timer = 0
        continue

    if not is_running:
        time.sleep(0.01)
        continue

    try:
        img = np.array(sct.grab(monitor))
    except:
        continue

    hsv = cv2.cvtColor(img[..., :3], cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, LOWER_COLOR, UPPER_COLOR)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=1)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    candidates = []
    best_area = 0
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if not (MIN_AREA < area < MAX_AREA):
            continue
        perimeter = cv2.arcLength(cnt, True)
        if perimeter == 0:
            continue
        circularity = 4 * np.pi * (area / (perimeter ** 2))
        x, y, w, h = cv2.boundingRect(cnt)

        if circularity < 0.6:
            roi = mask[y:y + h, x:x + w]
            sub_centers = split_blob_centers(roi, x + crop_x1, y + crop_y1)
            for (cx, cy) in sub_centers:
                dist = np.hypot(cx - CX, cy - CY)
                candidates.append((dist, cx, cy, area))
        else:
            M = cv2.moments(cnt)
            if M['m00'] == 0:
                continue
            cx = int(M["m10"] / M["m00"]) + crop_x1
            cy = int(M["m01"] / M["m00"]) + crop_y1
            dist = np.hypot(cx - CX, cy - CY)
            candidates.append((dist, cx, cy, area))

    candidates.sort(key=lambda p: p[0])
    t1 = candidates[0][:3] if len(candidates) > 0 else None
    t2 = candidates[1][:3] if len(candidates) > 1 else None
    best_area = candidates[0][3] if len(candidates) > 0 else 0

    best_x, best_y = None, None

    # 进行锁定
    if lock_timer > 0 and t1 is not None:
        lock_timer -= 1
        min_dist = float('inf')
        match_x, match_y = None, None
        for t in [t1, t2]:
            if t is None:
                continue
            d, x, y = t
            track_dist = ((x - locked_x) ** 2 + (y - locked_y) ** 2) ** 0.5
            if track_dist < min_dist and track_dist < MAX_TRACK_DIST:
                min_dist = track_dist
                match_x, match_y = x, y
        if match_x is not None:
            best_x, best_y = match_x, match_y
            locked_x, locked_y = match_x, match_y
        else:
            locked_x = None
            locked_y = None
            lock_timer = 0

    if best_x is None and t1 is not None:
        if t2 is not None and abs(t1[0] - t2[0]) < DIST_TOLERANCE:
            best_x, best_y = t1[1], t1[2]
            locked_x, locked_y = best_x, best_y
            lock_timer = LOCK_DURATION
        else:
            best_x, best_y = t1[1], t1[2]

    # 平滑
    if best_x is not None:
        if smooth_x == 0 and smooth_y == 0:
            smooth_x, smooth_y = best_x, best_y
        else:
            smooth_x = EMA_ALPHA * best_x + (1 - EMA_ALPHA) * smooth_x
            smooth_y = EMA_ALPHA * best_y + (1 - EMA_ALPHA) * smooth_y
        best_x, best_y = int(smooth_x), int(smooth_y)

    # 执行动作
    if best_x is not None:
        dx = int((best_x - CX) * SCALE)
        dy = int((best_y - CY) * SCALE)
        mouse_move_relative(dx, dy)

        dynamic_threshold = AIM_THRESHOLD + (best_area / DYNAMIC_FACTOR)
        current_dist_sq = (best_x - CX) ** 2 + (best_y - CY) ** 2
        if current_dist_sq < dynamic_threshold ** 2:
            mouse_click()
    else:
        search_counter += 1
        if search_counter >= SEARCH_INTERVAL:
            search_counter = 0
            r_dx = random.randint(-SEARCH_SPEED, SEARCH_SPEED)
            r_dy = random.randint(-SEARCH_SPEED // 2, SEARCH_SPEED // 2)
            mouse_move_relative(r_dx, r_dy)

    time.sleep(0.0001)
