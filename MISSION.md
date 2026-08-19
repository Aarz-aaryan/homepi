# homepi — Unified Homescreen Project

**Mission:** Time, weather, and r-server status displayed on two different screens in two different rooms, built with different stacks but sharing the same data sources and GIF library.

---

## Status: Both Targets Running

| Target | Device | Status | Last Updated |
|--------|--------|--------|-------------|
| `homepi/` | Raspberry Pi 3B+ + 2.8" TFT | ✅ Running | 2026-08-19 |
| `kiosk-pc/` | Ubuntu PC + HDMI TV | ✅ Running | 2026-08-19 |

**Unified repo:** `Aarz-aaryan/homepi` (merged 2026-08-19)

---

## Two Targets

### [`homepi/`](/homepi/) — Raspberry Pi TFT

**2.8" Adafruit ILI9341 320×240** driven via Pillow → `/dev/fb0` (no X11).

```
ssh homepi@100.106.151.81
```

- 2-window auto-cycle: clock/GIF → r-server status
- Animated GIF background (58 GIFs, 3h deterministic slot cycling)
- Open-Meteo weather, r-server Uptime Kuma via SSH
- systemd `clock.service` running as root

**Files:** `homepi/clock.py`, `homepi/clock.service`

---

### [`kiosk-pc/`](/kiosk-pc/) — Ubuntu PC Chromium Kiosk

**Fullscreen Chromium on HDMI TV 1024×768** via lightdm → X session → chrome.

```
ssh -i ~/.ssh/id_ed25519_homescreen homescreen@100.110.212.126
```

- 4 frosted-glass tiles: Time · Weather · r-Server · Hermes Health
- Animated GIF backgrounds (47 GIFs, 5min rotation)
- SomaFM Groove Salad lofi via mpv
- `kiosk_server.py` on port 8088, `kiosk-web.service`
- xrandr 1024×768 for TV overscan-safe mode

**Files:** `kiosk-pc/index.html`, `kiosk-pc/kiosk_server.py`, `kiosk-pc/start-kiosk.sh`

---

## Shared Infrastructure

### r-server Uptime Kuma

Both targets SSH to r-server and query Uptime Kuma directly:

```bash
ssh r-server@100.84.224.18 \
  "sudo docker exec uptime-kuma sqlite3 /app/data/kuma.db 'SELECT name,active FROM monitor;'"
```

### Open-Meteo Weather (free, no API key)

Both use the same endpoint:
```
GET https://api.open-meteo.com/v1/forecast?latitude=39.9526&longitude=-75.1652&current_weather=true
```

### GIF Backgrounds — `/gifs/`

Animated pixel-art GIFs sourced from [JoshuaThadi/Wall-E-Desk](https://github.com/JoshuaThadi/Wall-E-Desk). Both targets use the same library.

- **homepi:** 58 GIFs, pre-resized to 320×240, deterministic time-slot cycling
- **kiosk-pc:** 47 GIFs, served raw by `kiosk_server.py`, client-side rotation

GIF validation (`download_gifs.py`): checks `GIF87a`/`GIF89a` magic bytes to filter out WebP files renamed to `.gif`.

---

## Passwords & Access

| Target | SSH | sudo |
|--------|-----|------|
| homepi | `aarz1947` | `aarz1947` |
| kiosk-pc | `aarz1947` | NOPASSWD |
| r-server | `aarz1947` | `aarz1947` |

---

## GitHub History

| Date | Change |
|------|--------|
| 2026-06-22 | homepi repo created (Pi TFT project) |
| 2026-07-23 | homescreen-kiosk repo created (PC kiosk project) |
| 2026-08-19 | Both merged into `homepi/` repo — homepi = unified project |

---

## What's Left

- [ ] homepi: Tune ribbon scroll speed (currently 0.7px/frame)
- [ ] kiosk-pc: Add weather API integration (currently "no data" placeholder)
