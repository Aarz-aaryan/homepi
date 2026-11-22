#!/usr/bin/env python3
"""
homepi TFT Clock — 2 windows, auto-cycle every 10s
Window 1: time + date + weather (with animated GIF/WebP background)
Window 2: r-server status (UP/DOWN)
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
    font      = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 55)
    font_date = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 22)
    font_weather = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
    font_status = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 28)
    font_list = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 13)
except Exception:
    font = font_date = font_weather = font_status = font_list = ImageFont.load_default()

def image_to_fb(img):
    arr = np.array(img.convert('RGB'), dtype=np.uint16)
    r, g, b = arr[:,:,0], arr[:,:,1], arr[:,:,2]
    rgb565 = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
    return rgb565.astype('<u2').tobytes()

# Cache weather and r-server status
weather_info = "Loading..."
rs_summary   = "Loading..."
rs_monitors  = []
rs_error     = False

# Provision the service user's SSH key and known_hosts before deployment.
RS_CMD = [
    "ssh", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes",
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
                
                # convert to RGBA
                current_frame = im.convert('RGBA')
                
                # Aspect-preserving scale to cover using NEAREST
                w, h = current_frame.size
                scale = max(target_w / w, target_h / h)
                new_w = int(round(w * scale))
                new_h = int(round(h * scale))
                img_resized = current_frame.resize((new_w, new_h), Image.NEAREST)
                
                # Crop to fit
                left = (new_w - target_w) // 2
                top = (new_h - target_h) // 2
                right = left + target_w
                bottom = top + target_h
                frame_covered = img_resized.crop((left, top, right, bottom))
                
                frames.append(frame_covered)
                durations.append(frame_dur)
                i += 1
    except EOFError:
        pass
    except Exception as e:
        print(f"Error loading {gif_path}: {e}")
    return frames, durations

# Find and validate GIFs at startup
all_gifs_raw = sorted(glob.glob("/home/visionai/gifs/*.gif") + glob.glob("/home/visionai/gifs/*.webp"))

def get_valid_gifs(gif_paths):
    # Runs the validation in a subprocess to protect startup from hangs
    code = f"""
import sys, json
from PIL import Image
paths = {repr(gif_paths)}
valid = []
for p in paths:
    try:
        with Image.open(p) as im:
            im.verify()
        valid.append(p)
    except Exception:
        pass
print(json.dumps(valid))
"""
    try:
        res = subprocess.run(["python3", "-c", code], timeout=5, capture_output=True, text=True)
        if res.returncode == 0:
            return json.loads(res.stdout)
    except Exception:
        pass
    
    # Fallback to individual check if combined validation failed/timed out
    valid = []
    for p in gif_paths:
        try:
            res = subprocess.run(
                ["python3", "-c", f"from PIL import Image; Image.open({repr(p)}).verify()"],
                timeout=1,
                capture_output=True
            )
            if res.returncode == 0:
                valid.append(p)
        except Exception:
            pass
    return valid

all_gifs = get_valid_gifs(all_gifs_raw)

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

# Active GIF cache
active_gif_path = None
active_frames = []
active_durations = []

# Preload state
preload_lock = threading.Lock()
preloaded_slot = None  # (day_index, slot_index)
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

window = 0

with open(FB, "wb") as fb:
    while True:
        if window == 0:
            window_start = time.time()
            frame_index = 0
            
            # Check current slot
            now = datetime.now()
            day_index, slot_index = get_slot_info(now)
            target_path = get_gif_path(day_index, slot_index, all_gifs)
            
            if target_path:
                if active_gif_path != target_path:
                    # Look at preload cache first
                    with preload_lock:
                        if preloaded_slot == (day_index, slot_index) and preloaded_path == target_path:
                            active_gif_path = preloaded_path
                            active_frames = preloaded_frames
                            active_durations = preloaded_durations
                        else:
                            active_gif_path = None
                    
                    if active_gif_path is None:
                        # Synchronous load fallback
                        active_gif_path = target_path
                        active_frames, active_durations = load_gif_frames(target_path, W, H)
                    
                    frame_index = 0
                    
                    # Preload next slot
                    next_dt = now + timedelta(hours=3)
                    n_day_index, n_slot_index = get_slot_info(next_dt)
                    n_path = get_gif_path(n_day_index, n_slot_index, all_gifs)
                    if n_path:
                        start_preload(n_day_index, n_slot_index, n_path)
            
            # Play GIF for 10 seconds
            while time.time() - window_start < 10.0:
                loop_start = time.time()
                now = datetime.now()
                
                # Check slot change mid-play
                day_index, slot_index = get_slot_info(now)
                target_path = get_gif_path(day_index, slot_index, all_gifs)
                if target_path and active_gif_path != target_path:
                    break
                
                if active_frames:
                    f_idx = frame_index % len(active_frames)
                    frame = active_frames[f_idx]
                    dur = active_durations[f_idx]
                    
                    # Draw on a copy of the frame
                    img = frame.copy()
                    draw = ImageDraw.Draw(img)
                    
                    # 1. Bounding box for time text
                    t_str = now.strftime("%I:%M:%S").lstrip("0")
                    bbox_t = draw.textbbox((0, 0), t_str, font=font)
                    text_w = bbox_t[2] - bbox_t[0]
                    x_t = (W - text_w) // 2
                    y_t = 40
                    
                    bbox_at_dest = draw.textbbox((x_t, y_t), t_str, font=font)
                    rect_x0 = bbox_at_dest[0] - 10
                    rect_y0 = bbox_at_dest[1] - 5
                    rect_x1 = bbox_at_dest[2] + 10
                    rect_y1 = bbox_at_dest[3] + 5
                    
                    draw.rectangle([rect_x0, rect_y0, rect_x1, rect_y1], fill=(0, 0, 0, 160))
                    draw.text((x_t, y_t), t_str, font=font, fill=(255, 255, 255, 255))
                    
                    # 2. Date text
                    d_str = now.strftime("%A, %B %d")
                    bbox_d = draw.textbbox((0, 0), d_str, font=font_date)
                    x_d = (W - (bbox_d[2] - bbox_d[0])) // 2
                    draw.text((x_d, 110), d_str, font=font_date, fill=(160, 160, 160, 255))
                    
                    # 3. Weather text
                    bbox_w = draw.textbbox((0, 0), weather_info, font=font_weather)
                    x_w = (W - (bbox_w[2] - bbox_w[0])) // 2
                    draw.text((x_w, 175), weather_info, font=font_weather, fill=(180, 220, 255, 255))
                    
                    fb.seek(0)
                    fb.write(image_to_fb(img))
                    frame_index += 1
                    
                    # Handle sleep to match native frame rate
                    sleep_sec = dur / 1000.0
                    elapsed = time.time() - loop_start
                    to_sleep = max(0.001, sleep_sec - elapsed)
                    time.sleep(to_sleep)
                else:
                    # Fallback (black background)
                    img = Image.new("RGB", (W, H), (0, 0, 0))
                    draw = ImageDraw.Draw(img)
                    t_str = now.strftime("%I:%M:%S").lstrip("0")
                    bbox_t = draw.textbbox((0, 0), t_str, font=font)
                    draw.text(((W - (bbox_t[2] - bbox_t[0])) // 2, 40), t_str, font=font, fill=(255, 255, 255))
                    
                    d_str = now.strftime("%A, %B %d")
                    bbox_d = draw.textbbox((0, 0), d_str, font=font_date)
                    draw.text(((W - (bbox_d[2] - bbox_d[0])) // 2, 110), d_str, font=font_date, fill=(160, 160, 160))
                    
                    bbox_w = draw.textbbox((0, 0), weather_info, font=font_weather)
                    draw.text(((W - (bbox_w[2] - bbox_w[0])) // 2, 175), weather_info, font=font_weather, fill=(180, 220, 255))
                    
                    fb.seek(0)
                    fb.write(image_to_fb(img))
                    time.sleep(0.5)
        else:
            # Window 1: r-server Status (unchanged)
            img = Image.new("RGB", (W, H), (0, 0, 0))
            draw = ImageDraw.Draw(img)
            
            draw.text((10, 10), "r-server Status", font=font_date, fill=(100, 100, 100))

            if rs_error:
                color = (255, 80, 80)
            else:
                color = (80, 255, 120)

            bbox = draw.textbbox((0, 0), rs_summary, font=font_status)
            draw.text(((W-(bbox[2]-bbox[0]))//2, 45), rs_summary, font=font_status, fill=color)

            y = 95
            for name, is_up in rs_monitors:
                dot = "●" if is_up else "○"
                col = (100, 255, 130) if is_up else (255, 90, 90)
                text = f"{dot} {name}"
                draw.text((20, y), text, font=font_list, fill=col)
                y += 17
                if y > 225:
                    break
            
            fb.seek(0)
            fb.write(image_to_fb(img))
            time.sleep(10)
            
        window = 1 - window
