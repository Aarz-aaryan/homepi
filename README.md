# homepi

**Unified homescreen project** — two different displays running on two different devices in the same home lab, both showing time, weather, and r-server status.

| Target | Device | Display | Stack |
|--------|--------|---------|-------|
| `homepi` | Raspberry Pi 3B+ (100.106.151.81) | 2.8" Adafruit TFT ILI9341 320×240 | Pillow → `/dev/fb0`, Python 3 |
| `kiosk-pc` | Ubuntu PC (100.110.212.126) | HDMI TV 1024×768 | Chromium kiosk, Python http.server |

Both targets share the same GIF library and the same r-server Uptime Kuma integration.

---

## Targets

### [`homepi/`](homepi/) — Raspberry Pi TFT Display

Raspberry Pi 3B+ with a 2.8" Adafruit capacitive TFT (ILI9341, 320×240) driven via Pillow writing raw RGB565 to `/dev/fb0`. No X11, no pygame — pure framebuffer.

```
ssh homepi@100.106.151.81
```

**Stack:** Raspbian 13 · Python 3 · Pillow · systemd · Open-Meteo API · SSH to r-server for Uptime Kuma data

**Key files:** `homepi/clock.py` (main script), `homepi/clock.service` (systemd unit)

---

### [`kiosk-pc/`](kiosk-pc/) — Ubuntu PC Chromium Kiosk

Old PC with Ubuntu 24.04 running Chromium in `--kiosk` mode, pointed at a local Python web server that aggregates r-server stats.

```
ssh -i ~/.ssh/id_ed25519_homescreen homescreen@100.110.212.126
```

**Stack:** Ubuntu 24.04 · Google Chrome · lightdm autologin · Python http.server · Open-Meteo API · SSH to r-server for Uptime Kuma data

**Key files:** `kiosk-pc/index.html` (dashboard UI), `kiosk-pc/kiosk_server.py` (backend), `kiosk-pc/start-kiosk.sh` (X session launcher), `kiosk-pc/kiosk-web.service` (systemd unit)

---

## Shared Resources

### GIF Backgrounds — `/gifs/`

Animated pixel-art GIFs used as backgrounds on **both** targets. Source: [JoshuaThadi/Wall-E-Desk](https://github.com/JoshuaThadi/Wall-E-Desk/tree/main/Pixel-Art).

- **homepi:** All 58 validated GIFs, pre-resized to 320×240 RGB565, cycling via deterministic time-slot shuffle
- **kiosk-pc:** 47 validated GIFs (WebP renamed to .gif filtered out via magic-byte check), served raw by `kiosk_server.py` at `/backgrounds/<name>`

GIF validation script: `download_gifs.py` (checks `GIF87a`/`GIF89a` magic bytes, filters renamed WebP files).

```
# Re-run GIF validation
python3 download_gifs.py
```

### r-server Uptime Kuma

Both targets SSH to r-server and query the Uptime Kuma SQLite DB directly:

```bash
ssh r-server@100.84.224.18 \
  "sudo docker exec uptime-kuma sqlite3 /app/data/kuma.db 'SELECT name,active FROM monitor;'"
```

Returns pipe-delimited rows: `Immich|1`, `Vaultwarden|1`, etc.

### Open-Meteo Weather (free, no API key)

Both targets use the same Open-Meteo endpoint:
```
GET https://api.open-meteo.com/v1/forecast?latitude=39.9526&longitude=-75.1652&current_weather=true
```

---

## Quick-Reference Commands

```bash
# homepi — restart display service
ssh homepi@100.106.151.81 'sudo systemctl restart clock'
ssh homepi@100.106.151.81 'journalctl -u clock --no-pager -n 20'

# kiosk-pc — restart web server
ssh homescreen@100.110.212.126 'sudo systemctl restart kiosk-web'
# kiosk-pc — check chrome process
ssh homescreen@100.110.212.126 'ps aux | grep chrome | grep -v grep'

# Both — check r-server monitors
ssh r-server@100.84.224.18 "sudo docker exec uptime-kuma sqlite3 /app/data/kuma.db 'SELECT name,active FROM monitor;'"
```

---

## Passwords & Access

| Target | SSH | sudo |
|--------|-----|------|
| homepi | `aarz1947` | `aarz1947` |
| kiosk-pc | `aarz1947` (key preferred) | NOPASSWD via sudoers |
| r-server | `aarz1947` | `aarz1947` |

---

## Repos & Branches

| Repo | Status | Purpose |
|------|--------|---------|
| `Aarz-aaryan/homepi` | **Active** | Master repo — unified doc + all targets |
| `Aarz-aaryan/homescreen-kiosk` | **Archived** | Merged into `homepi/kiosk-pc/` (2026-08-19) |

---

## Upstream Dependencies

| Dependency | License | Used by |
|-----------|---------|---------|
| [JoshuaThadi/Wall-E-Desk](https://github.com/JoshuaThadi/Wall-E-Desk) | MIT | GIF backgrounds |
| [Open-Meteo](https://open-meteo.com/) | CC BY 4.0 | Weather data |
| Google Chrome | proprietary | kiosk-pc browser |
| Pillow | HPND | homepi framebuffer |
