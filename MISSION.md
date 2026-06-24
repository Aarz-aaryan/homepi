# homepi

**Mission:** TFT clock display for homepi (Raspberry Pi) — 2.8" Adafruit ILI9341 display with animated GIF background, scrolling status ribbon (day/date/weather/r-server dot), and r-server status window.

---

## Status: ✅ Running

**Last updated:** 2026-06-23 (ribbon + GIF background)

---

## Hardware

| Component | Detail |
|-----------|--------|
| Device | Raspberry Pi 3B+ (homepi) |
| Tailscale IP | `100.106.151.81` |
| Display | Adafruit 2.8" TFT (ILI9341 controller) |
| Resolution | 320×240 RGB565 |
| Framebuffer | `/dev/fb0` |
| Interface | SPI0 |
| Overlay | `pitft28-capacitive,rotate=90` |
| Touch | Non-functional (hardware issue — see Touch section) |

---

## Display Layout

**Window 0 — Clock with GIF Background (~10s)**
```
[scrolling ribbon: r-svr ● MON JUN 23  |  sunny 22C 5km/h  • ]
                    7:45 PM              ← large white time, semi-transparent box
                 MON, JUN 23            ← grey date
               sunny 22C 5km/h          ← blue weather
```
- GIF animated background (cycles every 3h, deterministic per time slot)
- Ribbon scrolls right-to-left at 0.7px/frame, continuous seamless loop
- `r-svr` label in grey, green dot if all r-server monitors up, red if any down

**Window 1 — r-server Status (~10s)**
```
 r-server Status
  6 UP  0 DOWN     ← green
 ● Immich
 ● Vaultwarden
 ● Nextcloud
 ● Collabora Office
 ● Homepage
 ● Glances
```
Auto-cycles every 10 seconds.

---

## Architecture

### Stack
- **Raspberry Pi OS:** Raspbian 13 (Trixie), Linux 6.18.34, Python 3.13.5
- **Rendering:** Pillow → raw RGB565 bytes → `/dev/fb0` (no X11, no pygame, no SDL)
- **Background GIFs:** Pre-loaded from `/home/visionai/gifs/`, pre-resized to 320×240 RGBA, cycling every 3h via deterministic slot shuffle
- **Ribbon:** Pre-built 1280px RGB tile (multiple content copies with 50px gaps), paste-crop onto frame each frame
- **Weather:** Open-Meteo API (free, no auth)
- **r-server status:** SSH to r-server@100.84.224.18 → `docker exec uptime-kuma sqlite3`
- **Service:** systemd `clock.service`, runs as **root**
- **Fonts:** DejaVuSans (pre-installed on Raspbian)

### Key Files

| File | Location | Purpose |
|------|----------|---------|
| `clock.py` | `/home/visionai/clock.py` on homepi | Main display script (443 lines) |
| `clock.service` | `/etc/systemd/system/clock.service` | systemd unit |
| `gifs/` | `/home/visionai/gifs/` | 13 valid GIFs (downloaded from Wall-E-Desk repo) |
| `config.txt` | `/boot/firmware/config.txt` | Device tree overlays |

---

## GIF Background

GIFs sourced from [JoshuaThadi/Wall-E-Desk](https://github.com/JoshuaThadi/Wall-E-Desk/tree/main/Pixel-Art) (58 files, 13 valid GIFs under 500KB).

**Slot system:** 8 slots × 3h = 24h coverage. Deterministic shuffle per day (`year*365 + day_of_year` as seed), so the same GIF plays at the same slot every day.

**Preloading:** Next slot's GIF preloaded in background thread while current plays. Zero gap on transitions.

---

## Scrolling Ribbon

- **Height:** 24px strip at top of display
- **Content per unit:** `[r-svr] [●] [MON JUN 23] [ | ] [sunny 22C 5km/h] [ • ]`
- **Spacing:** 50px black gap between content units (clean news-ticker feel)
- **Speed:** 0.7 px/frame (~1.2s per character at 12px font)
- **Cache:** Ribbon tile rebuilt only when content changes (weather refresh, day rollover, r-server status change)
- **Dot color:** Green (0,220,80) if all r-server monitors up; Red (255,60,60) if any down

---

## Configuration

### `/boot/firmware/config.txt` (relevant additions)
```
dtparam=spi=on
dtoverlay=pitft28-capacitive,rotate=90,speed=64000000,fps=30
```

### `/etc/systemd/system/clock.service`
```ini
[Unit]
Description=TFT Clock Display
After=network.target

[Service]
ExecStart=/usr/bin/python3 /home/visionai/clock.py
Restart=always
User=root
WorkingDirectory=/home/visionai

[Install]
WantedBy=multi-user.target
```

---

## Touch — Non-Functional (Hardware Issue)

Both touch variants were tested and **neither works**:

**Capacitive (EP0110M09 on I2C, FT6xxx family) — CURRENT OVERLAY**
- Device creates at `/dev/input/event0` ("1-0038 EP0110M09")
- `evtest` shows correct capabilities (EV_ABS X 0-239, Y 0-319, BTN_TOUCH)
- **Zero touch events fire** — known Linux kernel/FT driver issue with this chip variant
- No software fix available

**Resistive (STMPE610 on SPI) — WAS TRIED FIRST**
- `dmesg: unknown chip id: 0x0` — SPI probe fails
- No `/dev/input/event*` device created

**Decision:** Display-only. Auto-cycle is the only navigation.

---

## Setup Steps (Full Rebuild)

```bash
# 1. SSH in
ssh homepi@100.106.151.81

# 2. Install sshpass
sudo apt-get install -y sshpass

# 3. Enable SPI + TFT overlay
# Add to /boot/firmware/config.txt:
#   dtparam=spi=on
#   dtoverlay=pitft28-capacitive,rotate=90,speed=64000000,fps=30
sudo nano /boot/firmware/config.txt
sudo reboot

# 4. Create /home/visionai
sudo mkdir /home/visionai
sudo chown homepi:homepi /home/visionai

# 5. Deploy clock.py
# From your machine:
scp clock.py homepi@100.106.151.81:/home/visionai/clock.py

# 6. Set up systemd service
scp clock.service homepi@100.106.151.81:/tmp/clock.service
ssh homepi@100.106.151.81 sudo mv /tmp/clock.service /etc/systemd/system/
ssh homepi@100.106.151.81 sudo systemctl daemon-reload
ssh homepi@100.106.151.81 sudo systemctl enable clock
ssh homepi@100.106.151.81 sudo systemctl start clock

# 7. Set up GIFs directory
ssh homepi@100.106.151.81 'mkdir -p /home/visionai/gifs'
# Download GIFs via agy or manually from:
# https://github.com/JoshuaThadi/Wall-E-Desk/tree/main/Pixel-Art

# 8. Set up passwordless SSH to r-server
ssh homepi@100.106.151.81 ssh-keygen -f ~/.ssh/id_ed25519 -t ed25519 -N "" -C "homepi@100.106.151.81"
ssh homepi@100.106.151.81 'cat ~/.ssh/id_ed25519.pub'  # add to r-server
```

---

## Service Management

```bash
# Restart
sshpass -p 'aarz1947' ssh -o StrictHostKeyChecking=no homepi@100.106.151.81 \
  'sshpass -p "aarz1947" sudo systemctl restart clock'

# Check status
sshpass -p 'aarz1947' ssh -o StrictHostKeyChecking=no homepi@100.106.151.81 \
  'systemctl status clock --no-pager -n 5'

# View logs
sshpass -p 'aarz1947' ssh -o StrictHostKeyChecking=no homepi@100.106.151.81 \
  'journalctl -u clock --no-pager -n 20'
```

---

## API Reference

### Open-Meteo Weather
```
GET https://api.open-meteo.com/v1/forecast
  ?latitude=39.9526&longitude=-75.1652
  &current_weather=true
```
No API key required.

### r-server Uptime Kuma (via SSH)
```bash
sshpass -p 'aarz1947' ssh -o StrictHostKeyChecking=no r-server@100.84.224.18 \
  "sudo docker exec uptime-kuma sqlite3 /app/data/kuma.db 'SELECT name,active FROM monitor;'"
```
Returns pipe-delimited rows: `Immich|1`, `Vaultwarden|1`, etc.

---

## Passwords & Access

| Target | Password |
|--------|----------|
| homepi SSH | `aarz1947` |
| homepi sudo | `aarz1947` |
| r-server SSH | `aarz1947` |

---

## Issues & Blockers

| Issue | Status |
|-------|--------|
| Touch non-functional | **Won't fix** — confirmed both capacitive (FT driver) and resistive (chip ID 0x0) are broken |
| sudo requires TTY from SSH | **Resolved** — `sshpass` installed on homepi for all sudo operations |
| Some .gif files are actually WebP | **Resolved** — validation filters to real GIFs, 13 valid files used |

---

## What's Done

- [x] Fresh Raspbian 13 installed, Tailscale configured
- [x] SPI enabled + `pitft28-capacitive` overlay loaded (display works)
- [x] 2-window display (clock + r-server status, 10s auto-cycle)
- [x] systemd service running (PID 7265, stable ~35% CPU)
- [x] Passwordless SSH homepi → r-server
- [x] Open-Meteo weather API verified (21.5°C, 6.2km/h)
- [x] r-server status verified (6 UP / 0 DOWN)
- [x] **NEW:** Animated GIF background (window 0 only, 13 valid GIFs, 3h slot cycling)
- [x] **NEW:** Scrolling ribbon with r-server status dot (green/red), day/date/weather
- [x] **NEW:** Seamless ribbon loop with tile caching (no per-frame rebuild)
- [x] **NEW:** GIF preloading (next slot pre-loaded while current plays)
- [x] MISSION.md updated

## What's Left

- [ ] Tune ribbon scroll speed (currently 0.7px/frame)
- [ ] GIF quality: some GIFs have visible artefacts (WebP source files)

---

## Session History

| Date | Session Summary |
|------|----------------|
| 2026-06-22 | Initial build on previous SD card. Touch attempted (both resistive + capacitive overlays tried, both failed). 2-window auto-cycle running. |
| 2026-06-23 AM | SD card failed. Fresh Raspbian 13 image. Full rebuild from scratch on new homepi IP (100.106.151.81). Everything working again. |
| 2026-06-23 PM | Added animated GIF background to window 0. Downloaded 58 files from Wall-E-Desk repo, filtered to 13 valid GIFs. Implemented 3h deterministic GIF slot cycling with background preloading. Added scrolling ribbon at top (day/date/weather/r-server dot) with tile caching. |

---

## Quick Recovery Checklist

After any future reimage/rebuild, check this list:

- [ ] `sshpass` installed
- [ ] `dtparam=spi=on` + `dtoverlay=pitft28-capacitive,rotate=90` in `/boot/firmware/config.txt`
- [ ] Reboot
- [ ] `/dev/fb0` exists (TFT framebuffer)
- [ ] `/home/visionai/` exists and owned by `homepi:homepi`
- [ ] `clock.py` + `gifs/` deployed to `/home/visionai/`
- [ ] `clock.service` installed and enabled
- [ ] SSH key generated on homepi, added to r-server
- [ ] `systemctl start clock` → check `journalctl -u clock` for errors
- [ ] Display shows Window 0 (time/weather/GIF) then flips to Window 1 (r-server) after ~10s
