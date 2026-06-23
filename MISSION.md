# homepi-tft-clock

**Mission:** TFT clock display for homepi (Raspberry Pi) — 2.8" Adafruit ILI9341 display showing time/date/weather + r-server status, auto-cycling every 10 seconds.

---

## Status: ✅ Running

---

## Hardware

| Component | Detail |
|-----------|--------|
| Device | Raspberry Pi (homepi) on Tailscale VPN |
| Display | Adafruit 2.8" TFT (ILI9341 controller) |
| Resolution | 320×240 RGB565 |
| Framebuffer | `/dev/fb1` |
| Interface | SPI0 |
| Overlay | `pitft28-resistive` (display works; touch hardware is non-functional — see Touch section) |
| Touch | Non-functional (both resistive STMPE610 and capacitive EP0110M09 fail) |

**Tailscale IP:** `homepi` (local hostname)

---

## Display Layout

**Window 1 — Clock (5s)**
```
   12:34:56        ← large white time
 Monday, June 22   ← grey date
 ☁ 22C 5km/h       ← blue weather
```

**Window 2 — r-server Status (5s)**
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

Auto-cycles every 10 seconds (5s per window).

---

## Architecture

### Stack
- **Rendering:** Pillow → raw RGB565 bytes → `/dev/fb1` (no X11, no pygame, no SDL)
- **Weather:** Open-Meteo API (free, no auth) — `api.open-meteo.com/v1/forecast`
- **r-server status:** SSH to r-server@100.84.224.18 → `docker exec uptime-kuma sqlite3` query
- **Service:** systemd `clock.service`, runs as **root**, `ExecStart=/usr/bin/python3 /home/visionai/clock.py`
- **Fonts:** DejaVuSans (bundled with Pi OS)

### Threads
- `weather_loop()` — fetches every 10 minutes, caches in `weather_info`
- `rserver_loop()` — fetches every 60s, caches in `rs_summary` + `rs_monitors`
- Main loop — draws current window, sleeps 10s, flips window

### Key Files

| File | Location | Purpose |
|------|----------|---------|
| `clock.py` | `/home/visionai/clock.py` on homepi | Main display script (166 lines) |
| `clock.service` | `/etc/systemd/system/clock.service` on homepi | systemd unit |
| `config.txt` | `/boot/firmware/config.txt` on homepi | Device tree overlays |

---

## Configuration

### `/boot/firmware/config.txt` (relevant lines)
```
dtparam=spi=on
dtoverlay=pitft28-resistive,rotate=90,speed=64000000,fps=30
# dtparam=i2c_arm=on   ← disabled (touch is non-functional)
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

**Resistive (STMPE610 on SPI)**
- Overlay: `pitft28-resistive`
- `dmesg: unknown chip id: 0x0` — SPI communication failure, probe fails
- No `/dev/input/event*` device created

**Capacitive (EP0110M09 on I2C, FT6xxx family)**
- Overlay: `pitft28-capacitive` + `dtparam=i2c_arm=on`
- Device creates at `/dev/input/event0` ("1-0038 EP0110M09")
- `evtest` shows correct capabilities (EV_ABS X 0-239, Y 0-319, BTN_TOUCH)
- **Zero touch events ever fire** — known Linux kernel/FT driver issue with this chip variant
- Reverted to resistive overlay (display still works perfectly)

**Decision:** Display-only operation. No swipe/click. Auto-cycle is the fallback.

---

## Service Management

```bash
# Restart (requires sudo — use PTY fork method from remote)
python3 restart_clock.py

# Check status
ssh homepi@homepi 'systemctl status clock'

# View logs
ssh homepi@homepi 'journalctl -u clock -f'
```

**Restart script:** `restart_clock.py` (uses PTY fork to feed sudo password over SSH)

---

## API Reference

### Open-Meteo Weather
```
GET https://api.open-meteo.com/v1/forecast
  ?latitude=39.9526&longitude=-75.1652
  &current_weather=true
```
No API key required.

### r-server Uptime Kuma (via SSH + docker exec)
```bash
ssh r-server@100.84.224.18 \
  "sudo docker exec uptime-kuma sqlite3 /app/data/kuma.db \
    'SELECT name,active FROM monitor;'"
```
Returns pipe-delimited rows: `Immich|1`, `Vaultwarden|1`, etc.

---

## Passwords & Access

| Target | Password |
|--------|----------|
| homepi SSH | `000000` |
| r-server SSH | `aarz1947` |
| homepi sudo | `000000` |

**Passwordless SSH:**
- `homepi → r-server`: SSH key added to `r-server@100.84.224.18:~/.ssh/authorized_keys`
  (also copied to `/root/.ssh/` so root service can use it)

---

## Issues & Blockers

| Issue | Status |
|-------|--------|
| Touch non-functional (hardware) | **Won't fix** — confirmed both resistive and capacitive are broken |
| No TTY for sudo from SSH | **Won't fix** — works around with PTY fork script |
| r-server Uptime Kuma API requires auth | **Resolved** — using SSH+docker exec instead |

---

## What's Done

- [x] TFT display working with Pillow framebuffer rendering
- [x] 2-window auto-cycling (clock + r-server status)
- [x] Open-Meteo weather API integration
- [x] r-server status via SSH + docker exec (no Uptime Kuma API auth needed)
- [x] systemd service with auto-restart
- [x] Passwordless SSH homepi → r-server
- [x] Device tree overlays configured
- [x] Touch hardware diagnosed as non-functional (no software fix)
- [x] Full documentation in MISSION.md

## What's Left

- [ ] Home directory cleanup (`/home/visionai` stays as-is per user preference)
- [ ] (Anything else future sessions discover)

---

## Session History

| Date | Session Summary |
|------|----------------|
| 2026-06-22 | Initial build: Pillow framebuffer, weather, r-server status. Touch attempted (both resistive + capacitive overlays tried, both failed). 2-window auto-cycle deployed and running. |

---

## Quick Recovery (if you need to re-deploy from scratch)

```bash
# 1. Copy clock.py to homepi
scp clock.py homepi@homepi:/home/visionai/clock.py

# 2. Enable SPI in config.txt if needed
# dtoverlay=pitft28-resistive,rotate=90,speed=64000000,fps=30

# 3. Start service
sudo systemctl enable clock
sudo systemctl start clock

# 4. Verify
systemctl status clock
```
