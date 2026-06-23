#!/usr/bin/env python3
"""
homepi TFT Clock — 2 windows, auto-cycle every 10s
Window 1: time + date + weather
Window 2: r-server status (UP/DOWN)
"""
import time
from datetime import datetime
import threading
import subprocess
import requests
from PIL import Image, ImageDraw, ImageFont

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
    pixels = img.convert("RGB").load()
    buf = bytearray(W * H * 2)
    for y in range(H):
        for x in range(W):
            r, g, b = pixels[x, y]
            val = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
            idx = (y * W + x) * 2
            buf[idx]   = val & 0xFF
            buf[idx+1] = (val >> 8) & 0xFF
    return buf

# Cache weather and r-server status
weather_info = "Loading..."
rs_summary   = "Loading..."
rs_monitors  = []
rs_error     = False

RS_CMD = [
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
            active = parts[-1].strip()  # -1 to handle names with pipes
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
    global weather_info
    update_weather()
    while True:
        time.sleep(600)

def rserver_loop():
    update_rserver()
    while True:
        time.sleep(60)

t_weather = threading.Thread(target=weather_loop, daemon=True)
t_rserver  = threading.Thread(target=rserver_loop,  daemon=True)
t_weather.start()
t_rserver.start()

window = 0

with open(FB, "wb") as fb:
    while True:
        img = Image.new("RGB", (W, H), (0, 0, 0))
        draw = ImageDraw.Draw(img)

        if window == 0:
            now = datetime.now()
            t = now.strftime("%I:%M:%S").lstrip("0")
            bbox = draw.textbbox((0, 0), t, font=font)
            draw.text(((W-(bbox[2]-bbox[0]))//2, 40), t, font=font, fill=(255, 255, 255))

            d = now.strftime("%A, %B %d")
            bbox = draw.textbbox((0, 0), d, font=font_date)
            draw.text(((W-(bbox[2]-bbox[0]))//2, 110), d, font=font_date, fill=(160, 160, 160))

            bbox = draw.textbbox((0, 0), weather_info, font=font_weather)
            draw.text(((W-(bbox[2]-bbox[0]))//2, 175), weather_info, font=font_weather, fill=(180, 220, 255))

        else:
            # Window 2: r-server status
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
