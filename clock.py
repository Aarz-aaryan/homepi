#!/usr/bin/env python3
"""
homepi TFT Clock — 2 windows, auto-cycle every 10s
Window 0: time + date + weather (with animated GIF background + scrolling ribbon)
Window 1: r-server status (UP/DOWN)
"""
import time
from datetime import datetime, timedelta
import threading
import subprocess
import requests
import random
import glob
import os
import json
from PIL import Image, ImageDraw, ImageFont
import numpy as np

FB = "/dev/fb0"
W, H = 320, 240

try:
    font      = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 48)
    font_date = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
    font_weather = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
    font_status = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 28)
    font_list = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 13)
    font_ribbon = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 13)
except Exception:
    font = font_date = font_weather = font_status = font_list = font_ribbon = ImageFont.load_default()

def image_to_fb(img):
    arr = np.array(img.convert('RGB'), dtype=np.uint16)
    r, g, b = arr[:,:,0], arr[:,:,1], arr[:,:,2]
    rgb565 = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
    return rgb565.astype('<u2').tobytes()

weather_info = "Loading..."
rs_summary   = "Loading..."
rs_monitors  = []
rs_error     = False

RS_CMD = [
    "sshpass", "-p", "aarz1947",
    "ssh", "-o", "StrictHostKeyChecking=no",
    "-o", "ConnectTimeout=8",
    "r-server@100.84.224.18",
    "sudo docker exec uptime-kuma sqlite3 /app/data/kuma.db \"SELECT name,active FROM monitor;\""
]

WEATHER_ICONS = {
    0: "sun", 1: "partly_cloudy", 2: "cloudy", 3: "fog",
    45: "fog", 48: "fog",
    51: "drizzle", 53: "drizzle", 55: "drizzle",
    61: "rain", 63: "rain", 65: "rain",
    80: "showers", 95: "thunder"
}

def update_weather():
    global weather_info
    url = "https://api.open-meteo.com/v1/forecast?latitude=39.9526&longitude=-75.1652&current_weather=true"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            d = r.json().get("current_weather", {})
            code = d.get('weathercode', 0)
            icon = WEATHER_ICONS.get(code, "?")
            weather_info = f"{icon} {d.get('temperature', '??')}C {d.get('windspeed', '??')}km/h"
    except Exception:
        if weather_info == "Loading...":
            weather_info = "Error"

def update_rserver():
    global rs_summary, rs_monitors, rs_error
    try:
        out = subprocess.run(RS_CMD, timeout=15, capture_output=True).stdout.decode().strip()
        if not out:
            rs_summary = "No monitors"
            rs_monitors = []
            return
        up = down = 0
        monitors = []
        for line in out.splitlines():
            if "|" not in line:
                continue
            parts = line.strip().split("|")
            name = parts[0].strip()
            active = parts[-1].strip()
            if active == "1":
                up += 1
                monitors.append((name, True))
            else:
                down += 1
                monitors.append((name, False))
        rs_summary = f"{up} UP  {down} DOWN"
        rs_monitors = monitors
        rs_error = False
    except subprocess.TimeoutExpired:
        rs_summary = "r-server timeout"
        rs_error = True
    except Exception as e:
        rs_summary = f"Error: {type(e).__name__}"
        rs_error = True

def weather_loop():
    update_weather()
    while True:
        time.sleep(600)
        update_weather()

def rserver_loop():
    update_rserver()
    while True:
        time.sleep(60)
        update_rserver()

t_weather = threading.Thread(target=weather_loop, daemon=True)
t_rserver  = threading.Thread(target=rserver_loop,  daemon=True)
t_weather.start()
t_rserver.start()

def load_gif_frames(gif_path, target_w, target_h):
    frames = []
    durations = []
    try:
        with Image.open(gif_path) as im:
            duration = im.info.get('duration', 100)
            if duration is None or duration <= 10:
                duration = 100
            i = 0
            while True:
                im.seek(i)
                frame_dur = im.info.get('duration', duration)
                if frame_dur is None or frame_dur <= 10:
                    frame_dur = duration
                current_frame = im.convert('RGBA')
                w, h = current_frame.size
                scale = max(target_w / w, target_h / h)
                new_w = int(round(w * scale))
                new_h = int(round(h * scale))
                img_resized = current_frame.resize((new_w, new_h), Image.NEAREST)
                left = (new_w - target_w) // 2
                top = (new_h - target_h) // 2
                right = left + target_w
                bottom = top + target_h
                frame_covered = img_resized.crop((left, top, right, bottom))
                frames.append(frame_covered.convert('RGB'))
                durations.append(frame_dur)
                i += 1
    except EOFError:
        pass
    except Exception as e:
        print(f"Error loading {gif_path}: {e}")
    return frames, durations

all_gifs_raw = sorted(glob.glob("/home/visionai/gifs/*.gif") + glob.glob("/home/visionai/gifs/*.webp"))

all_gifs = all_gifs_raw
print(f"[GIF] {len(all_gifs)} valid GIFs")

def get_slot_info(dt):
    year = dt.year
    day_of_year = dt.timetuple().tm_yday
    day_index = year * 365 + day_of_year
    slot_index = (dt.hour // 3) % 8
    return day_index, slot_index

def get_gif_path(day_index, slot_index, gif_list):
    if not gif_list:
        return None
    r = random.Random(day_index)
    shuffled = list(gif_list)
    r.shuffle(shuffled)
    return shuffled[slot_index % len(shuffled)]

active_gif_path = None
active_frames = []
active_durations = []

preload_lock = threading.Lock()
preloaded_slot = None
preloaded_path = None
preloaded_frames = []
preloaded_durations = []
preload_thread = None

def preload_worker(day_index, slot_index, gif_path):
    global preloaded_slot, preloaded_path, preloaded_frames, preloaded_durations
    f, d = load_gif_frames(gif_path, W, H)
    with preload_lock:
        preloaded_slot = (day_index, slot_index)
        preloaded_path = gif_path
        preloaded_frames = f
        preloaded_durations = d

def start_preload(day_index, slot_index, gif_path):
    global preload_thread
    with preload_lock:
        if preloaded_slot == (day_index, slot_index) and preloaded_path == gif_path:
            return
    preload_thread = threading.Thread(
        target=preload_worker,
        args=(day_index, slot_index, gif_path),
        daemon=True
    )
    preload_thread.start()

# ─── RIBBON SYSTEM ───────────────────────────────────────────────────────────
RIBBON_H     = 24
RIBBON_SPEED = 0.7
REPEAT_GAP   = 80      # px of black between copies (clean news-ticker feel)
TILE_W       = W * 4   # 1280px wide — generous buffer for wraparound

# Cached ribbon state
_ribbon_tile   = None
_ribbon_stride = 1     # unit + REPEAT_GAP
_ribbon_key    = ""
_ribbon_scroll = 0.0

def _build_ribbon_tile(tag_text, day_str, weather_str, all_up):
    """Build a wide RGB tile with multiple content copies separated by gaps."""
    tile = Image.new("RGB", (TILE_W, RIBBON_H), (0, 0, 0))
    d = ImageDraw.Draw(tile)

    # Measure each piece
    def w(text):
        return d.textbbox((0, 0), text, font=font_ribbon)[2]
    tag_w     = w(tag_text)
    day_w     = w(day_str)
    weather_w = w(weather_str)
    sep       = "    •    "
    sep_w     = w(sep)
    bullet    = "  •  "
    bullet_w  = w(bullet)

    dot_r     = 5        # dot radius
    gap_text  = 10       # px between text and dot
    gap_in    = 6        # px between elements

    # One content block: [tag | dot | day | sep | weather | bullet]
    unit = tag_w + gap_in + (dot_r * 2) + gap_text + day_w + sep_w + weather_w + bullet_w
    stride = unit + REPEAT_GAP

    # Layout positions inside unit
    tag_x   = 0
    dot_x0  = tag_w + gap_in
    dot_cx  = dot_x0 + dot_r
    day_x0  = dot_x0 + (dot_r * 2) + gap_text
    sep_x0  = day_x0 + day_w
    wx0     = sep_x0 + sep_w
    bul_x0  = wx0 + weather_w

    # Colors
    if all_up:
        tag_col, txt_col, dot_col = (180, 180, 180), (255, 255, 255), (0, 220, 80)
    else:
        tag_col, txt_col, dot_col = (180, 180, 180), (255, 255, 255), (255, 60, 60)

    y_txt = (RIBBON_H - 13) // 2
    dot_cy = RIBBON_H // 2

    # Lay down enough copies to cover TILE_W plus one extra for wrap safety
    copies = (TILE_W // stride) + 2
    for i in range(copies):
        x = i * stride
        d.text((x + tag_x, y_txt), tag_text, font=font_ribbon, fill=tag_col)
        d.ellipse([x + dot_x0, dot_cy - dot_r, x + dot_x0 + dot_r * 2, dot_cy + dot_r], fill=dot_col)
        d.text((x + day_x0, y_txt), day_str, font=font_ribbon, fill=txt_col)
        d.text((x + sep_x0, y_txt), sep, font=font_ribbon, fill=(100, 100, 100))
        d.text((x + wx0, y_txt), weather_str, font=font_ribbon, fill=(160, 220, 255))
        d.text((x + bul_x0, y_txt), bullet, font=font_ribbon, fill=(80, 80, 80))

    return tile, stride

def _ribbon_cache_key():
    any_down = any(not is_up for _, is_up in rs_monitors)
    all_up = rs_monitors and not rs_error and not any_down
    return f"{all_up}|{weather_info}|{datetime.now().strftime('%a %b %d')}"

def draw_ribbon(img):
    global _ribbon_tile, _ribbon_key, _ribbon_scroll, _ribbon_stride
    key = _ribbon_cache_key()
    if key != _ribbon_key:
        any_down = any(not is_up for _, is_up in rs_monitors)
        all_up = rs_monitors and not rs_error and not any_down
        day_str = datetime.now().strftime("%a %b %d").upper()
        weather_str = weather_info if weather_info else "NO DATA"
        _ribbon_tile, _ribbon_stride = _build_ribbon_tile("r-svr", day_str, weather_str, all_up)
        _ribbon_key = key
        _ribbon_scroll = 0.0
        print(f"[RIBBON] rebuilt cache, stride={_ribbon_stride}px")
    _ribbon_scroll = (_ribbon_scroll + RIBBON_SPEED) % _ribbon_stride
    sx = int(_ribbon_scroll)
    img.paste(_ribbon_tile.crop((sx, 0, sx + W, RIBBON_H)), (0, 0))

# ─── MAIN LOOP ────────────────────────────────────────────────────────────────
window = 0

with open(FB, "wb") as fb:
    while True:
        if window == 0:
            window_start = time.time()
            frame_index = 0
            now = datetime.now()
            day_index, slot_index = get_slot_info(now)
            target_path = get_gif_path(day_index, slot_index, all_gifs)
            if target_path:
                if active_gif_path != target_path:
                    with preload_lock:
                        if preloaded_slot == (day_index, slot_index) and preloaded_path == target_path:
                            active_gif_path = preloaded_path
                            active_frames = preloaded_frames
                            active_durations = preloaded_durations
                        else:
                            active_gif_path = None
                    if active_gif_path is None:
                        active_gif_path = target_path
                        active_frames, active_durations = load_gif_frames(target_path, W, H)
                        print(f"[GIF] Load: {target_path.split('/')[-1]}")
                    frame_index = 0
                    next_dt = now + timedelta(hours=3)
                    n_day_index, n_slot_index = get_slot_info(next_dt)
                    n_path = get_gif_path(n_day_index, n_slot_index, all_gifs)
                    if n_path:
                        start_preload(n_day_index, n_slot_index, n_path)

            while time.time() - window_start < 20.0:
                loop_start = time.time()
                now = datetime.now()
                day_index, slot_index = get_slot_info(now)
                target_path = get_gif_path(day_index, slot_index, all_gifs)
                if target_path and active_gif_path != target_path:
                    break

                if active_frames:
                    f_idx = frame_index % len(active_frames)
                    frame = active_frames[f_idx]
                    dur = active_durations[f_idx]
                    img = frame.copy()
                    draw = ImageDraw.Draw(img)
                    draw_ribbon(img)

                    t_str = now.strftime("%-I:%M %p")
                    tb = draw.textbbox((0, 0), t_str, font=font)
                    tw = tb[2] - tb[0]
                    th_px = tb[3] - tb[1]
                    x_t = (W - tw) // 2
                    y_t = RIBBON_H + 20
                    overlay = Image.new('RGBA', (W, H), (0, 0, 0, 0))
                    od = ImageDraw.Draw(overlay)
                    od.rectangle([x_t - 6, y_t - 4, x_t + tw + 6, y_t + th_px + 4], fill=(0, 0, 0, 155))
                    img.paste(overlay, (0, 0), overlay)
                    draw = ImageDraw.Draw(img)
                    draw.text((x_t, y_t), t_str, font=font, fill=(255, 255, 255))

                    d_str = now.strftime("%a, %b %d").upper()
                    db = draw.textbbox((0, 0), d_str, font=font_date)
                    dw = db[2] - db[0]
                    draw.text(((W - dw) // 2, y_t + th_px + 12), d_str, font=font_date, fill=(180, 200, 230))

                    w_str = weather_info if weather_info else "No data"
                    wb = draw.textbbox((0, 0), w_str, font=font_weather)
                    ww = wb[2] - wb[0]
                    draw.text(((W - ww) // 2, y_t + th_px + 32), w_str, font=font_weather, fill=(160, 220, 255))

                    fb.seek(0)
                    fb.write(image_to_fb(img))
                    frame_index += 1

                    sleep_sec = dur / 1000.0
                    elapsed = time.time() - loop_start
                    time.sleep(max(0.001, sleep_sec - elapsed))
                else:
                    img = Image.new("RGB", (W, H), (0, 0, 0))
                    draw = ImageDraw.Draw(img)
                    draw_ribbon(img)
                    t_str = now.strftime("%-I:%M %p")
                    tb = draw.textbbox((0, 0), t_str, font=font)
                    tw = tb[2] - tb[0]
                    draw.text(((W - tw) // 2, RIBBON_H + 20), t_str, font=font, fill=(255, 255, 255))
                    d_str = now.strftime("%a, %b %d").upper()
                    db = draw.textbbox((0, 0), d_str, font=font_date)
                    dw = db[2] - db[0]
                    draw.text(((W - dw) // 2, RIBBON_H + 80), d_str, font=font_date, fill=(180, 200, 230))
                    fb.seek(0)
                    fb.write(image_to_fb(img))
                    time.sleep(0.5)
        else:
            img = Image.new("RGB", (W, H), (0, 0, 0))
            draw = ImageDraw.Draw(img)
            draw.text((10, 10), "r-server Status", font=font_date, fill=(100, 100, 100))
            color = (255, 80, 80) if rs_error else (80, 255, 120)
            bbox = draw.textbbox((0, 0), rs_summary, font=font_status)
            sw = bbox[2] - bbox[0]
            draw.text(((W - sw) // 2, 45), rs_summary, font=font_status, fill=color)
            y = 95
            for name, is_up in rs_monitors:
                dot = "●" if is_up else "○"
                col = (100, 255, 130) if is_up else (255, 90, 90)
                draw.text((20, y), f"{dot} {name}", font=font_list, fill=col)
                y += 17
                if y > 225:
                    break
            fb.seek(0)
            fb.write(image_to_fb(img))
            time.sleep(8)
        window = 1 - window
