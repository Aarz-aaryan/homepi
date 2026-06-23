# homepi

**Mission:** TFT clock display for homepi (Raspberry Pi) — 2.8" Adafruit ILI9341 display showing time/date/weather + r-server status, auto-cycling every 10 seconds.

---

## Status: ✅ Running

**Last rebuilt:** 2026-06-23 (fresh Raspbian 13 image after SD card failure)

---

## Hardware

| Component | Detail |
|-----------|--------|
| Device | Raspberry Pi (homepi) |
| Tailscale IP | `100.106.151.81` |
| Display | Adafruit 2.8" TFT (ILI9341 controller) |
| Resolution | 320×240 RGB565 |
| Framebuffer | `/dev/fb0` |
| Interface | SPI0 |
| Overlay | `pitft28-capacitive,rotate=90` |
| Touch | Non-functional (hardware issue — see Touch section) |

---

## Display Layout

**Window 1 — Clock (~5s)**
```
   12:34:56        ← large white time
 Monday, June 22   ← grey date
 ☁ 22C 5km/h       ← blue weather
```

**Window 2 — r-server Status (~5s)**
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
- **Raspberry Pi OS:** Raspbian 13 (Trixie), Linux 6.18.34, Python 3.13.5
- **Rendering:** Pillow → raw RGB565 bytes → `/dev/fb0` (no X11, no pygame, no SDL)
- **Weather:** Open-Meteo API (free, no auth)
- **r-server status:** SSH to r-server@100.84.224.18 → `docker exec uptime-kuma sqlite3`
- **Service:** systemd `clock.service`, runs as **root**
- **Fonts:** DejaVuSans (pre-installed on Raspbian)

### Key Files

| File | Location | Purpose |
|------|----------|---------|
| `clock.py` | `/home/visionai/clock.py` on homepi | Main display script (166 lines) |
| `clock.service` | `/etc/systemd/system/clock.service` | systemd unit |
| `config.txt` | `/boot/firmware/config.txt` | Device tree overlays |

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

# 2. Install sshpass (sudo without TTY workaround)
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

# 7. Set up passwordless SSH to r-server
# Generate key on homepi:
ssh homepi@100.106.151.81 ssh-keygen -f ~/.ssh/id_ed25519 -t ed25519 -N "" -C "homepi@100.106.151.81"
# Add the pubkey to r-server:
ssh r-server@100.84.224.18 "echo '<pubkey>' >> ~/.ssh/authorized_keys"
ssh r-server@100.84.224.18 "sudo bash -c \"echo '<pubkey>' >> /root/.ssh/authorized_keys\""
```

---

## Service Management

```bash
# Restart
sshpass -p 'aarz1947' ssh -o StrictHostKeyChecking=no homepi@100.106.151.81 'sudo systemctl restart clock'

# Check status
sshpass -p 'aarz1947' ssh -o StrictHostKeyChecking=no homepi@100.106.151.81 'systemctl status clock --no-pager -n 5'

# View logs
sshpass -p 'aarz1947' ssh -o StrictHostKeyChecking=no homepi@100.106.151.81 'journalctl -u clock --no-pager -n 20'
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
ssh r-server@100.84.224.18 \
  "sudo docker exec uptime-kuma sqlite3 /app/data/kuma.db \
    'SELECT name,active FROM monitor;'"
```
Returns pipe-delimited rows: `Immich|1`, `Vaultwarden|1`, etc.

---

## Passwords & Access

| Target | Password |
|--------|----------|
| homepi SSH | `aarz1947` |
| homepi sudo | `aarz1947` |
| r-server SSH | `aarz1947` |

**Passwordless SSH:**
- `homepi → r-server`: SSH key in `~/.ssh/id_ed25519.pub` added to `r-server@100.84.224.18:~/.ssh/authorized_keys` and `/root/.ssh/authorized_keys`

---

## Issues & Blockers

| Issue | Status |
|-------|--------|
| Touch non-functional | **Won't fix** — confirmed both capacitive (FT driver) and resistive (chip ID 0x0) are broken |
| sudo requires TTY from SSH | **Resolved** — `sshpass` installed on new homepi for all sudo operations |

---

## What's Done

- [x] Fresh Raspbian 13 installed, Tailscale configured
- [x] SPI enabled + `pitft28-capacitive` overlay loaded (display works)
- [x] All dependencies pre-installed (Pillow 11.1, requests, DejaVu fonts, Python 3.13)
- [x] 2-window display (clock + r-server status, 10s auto-cycle)
- [x] systemd service running (PID 2160, clean journal)
- [x] Passwordless SSH homepi → r-server
- [x] Open-Meteo weather API verified (21.5°C, 6.2km/h)
- [x] r-server status verified (6 UP / 0 DOWN)
- [x] MISSION.md updated with new IP and fresh rebuild steps

## What's Left

- [ ] (Nothing critical — display is fully operational)

---

## Session History

| Date | Session Summary |
|------|----------------|
| 2026-06-22 | Initial build on previous SD card. Touch attempted (both resistive + capacitive overlays tried, both failed). 2-window auto-cycle running. |
| 2026-06-23 | SD card failed. Fresh Raspbian 13 image. Full rebuild from scratch on new homepi IP (100.106.151.81). Everything working again. |

---

## Quick Recovery Checklist

After any future reimage/rebuild, check this list:

- [ ] `sshpass` installed
- [ ] `dtparam=spi=on` + `dtoverlay=pitft28-capacitive,rotate=90` in `/boot/firmware/config.txt`
- [ ] Reboot
- [ ] `/dev/fb0` exists (TFT framebuffer)
- [ ] `/home/visionai/` exists and owned by `homepi:homepi`
- [ ] `clock.py` deployed to `/home/visionai/`
- [ ] `clock.service` installed and enabled
- [ ] SSH key generated on homepi, added to r-server
- [ ] `systemctl start clock` → check `journalctl -u clock` for errors
- [ ] Display shows Window 1 (time/weather) then flips to Window 2 (r-server) after ~10s
