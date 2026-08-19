# kiosk-pc — Ubuntu HDMI Kiosk Display

**Mission:** Fullscreen Chromium kiosk on an old Ubuntu PC connected to a TV, showing a frosted-glass dashboard with time, weather, r-server monitors, Hermes health, and animated pixel-art GIF backgrounds with lofi music.

---

## Status: ✅ Running

**Last updated:** 2026-08-19 (merged into unified homepi repo)

---

## Identity

| Component | Detail |
|-----------|--------|
| Device | Old PC with HDMI out |
| Tailscale IP | `100.110.212.126` |
| OS | Ubuntu 24.04.4 LTS |
| User | `kiosk` / `aarz1947` |
| Kiosk UID | `kiosk` (useradd -r, no password, `/home/kiosk/`) |
| Display output | HDMI-A-1, 1024×768 (overscan-safe mode) |
| Chrome | `/opt/google/chrome/chrome --kiosk` |
| Disk | 234GB total, ≈8.8GB used post-debloat |

---

## Architecture

### Stack

- **Ubuntu 24.04** — GNOME desktop install, aggressively de-bloated (~1500 → ~1268 packages)
- **LightDM autologin** — kiosk user auto-logs into X session at boot
- **`start-kiosk.sh`** — X session script launched by LightDM; runs xrandr, unclutter, then execs chrome
- **Google Chrome** — `--kiosk` mode, `--password-store=basic` (bypasses GNOME keyring prompt)
- **`kiosk_server.py`** — Python `http.server` on `localhost:8088`, serves dashboard + JSON endpoints
- **`kiosk-web.service`** — systemd unit for `kiosk_server.py`
- **`kiosk-lofi.service`** — systemd unit for `start-lofi.sh` (SomaFM Groove Salad stream via mpv)
- **GIF backgrounds** — served by `kiosk_server.py` at `/backgrounds/<name>`, magic-byte validated

### LightDM Autologin Path (critical)

```
boot → lightdm → kiosk user session → start-kiosk.sh → xrandr → unclutter → google-chrome --kiosk
                                                                      → kiosk_server.py ← served by kiosk-web.service
```

Chrome runs as a child of the X session (NOT from a separate systemd unit). This avoids the X display race condition.

### Key Files

| File | Location | Purpose |
|------|----------|---------|
| `index.html` | `/opt/kiosk/index.html` | Dashboard UI (frosted-glass 2×2 tile grid) |
| `kiosk_server.py` | `/opt/kiosk/kiosk_server.py` | Python web server (port 8088) |
| `start-kiosk.sh` | `/opt/kiosk/start-kiosk.sh` | X session launcher (lightdm exec) |
| `start-lofi.sh` | `/opt/kiosk/start-lofi.sh` | mpv SomaFM Groove Salad stream |
| `rs-stats.sh` | `/opt/kiosk/rs-stats.sh` | r-server health stats script |
| `kiosk-web.service` | `/etc/systemd/system/` | systemd unit for kiosk_server.py |
| `kiosk-lofi.service` | `/etc/systemd/system/` | systemd unit for mpv stream |

---

## Dashboard Layout

Four frosted-glass tiles in a 2×2 CSS grid (1024×768):

```
┌─────────────────┬─────────────────┐
│  TIME           │  WEATHER        │
│  56px clock     │  temp + cond    │
│  date           │  feels/humid    │
├─────────────────┼─────────────────┤
│  R-SERVER       │  HERMES HEALTH  │
│  6 UP · 0 DOWN  │  ● online      │
│  CPU/MEM/disk   │  Tailscale 3/7 │
└─────────────────┴─────────────────┘
        [pixel-art GIF background]
```

### Server Endpoints

| Endpoint | Returns |
|----------|---------|
| `GET /` | `index.html` |
| `GET /monitors.json` | Uptime Kuma monitors via SSH → sqlite3 |
| `GET /identity.json` | homescreen hostname/kernel/uptime/tailscale |
| `GET /hermes-health.json` | Tailscale peer count, r-server reachability |
| `GET /rserver-stats.json` | CPU/MEM/disk/containers/uptime via SSH |
| `GET /backgrounds/list.json` | List of validated GIF filenames |
| `GET /backgrounds/<name>` | Raw GIF bytes (1h cache) |
| `GET /audio.json` | Lofi playing status + track name |

---

## xrandr Display Mode

**Critical:** `start-kiosk.sh` MUST set `xrandr --output HDMI-1 --mode 1024x768` before chrome starts. The TV has overscan at its native 1360×768 — 1024×768 is the largest mode that fills the visible area without clipping.

```bash
# In /opt/kiosk/start-kiosk.sh, FIRST line after set +e:
xrandr --output HDMI-1 --mode 1024x768 2>/dev/null
```

Iterate modes (800×450 → 960×540 → 1024×768 → 1280×720 → 1360×768), scrot each, verify visually. EDID panel dimensions are NOT reliable — trust physical measurement.

---

## GIF Background Rotation

- **Content source:** [JoshuaThadi/Wall-E-Desk](https://github.com/JoshuaThadi/Wall-E-Desk) (WebP files renamed to .gif filtered out via magic-byte check)
- **Valid count:** 47 GIFs (46MB), validated by `is_valid_gif()` checking `GIF87a`/`GIF89a` magic bytes
- **Rotation:** client-side `setInterval(rotateBackground, 5*60*1000)` picks random GIF with cache-bust `?t=<timestamp>`
- **CSS:** `object-fit: cover; image-rendering: pixelated; filter: brightness(0.85) contrast(1.05) saturate(1.2)`

---

## Deployment

```bash
# From your machine (after NOPASSWD sudo is set up on the target):
scp index.html kiosk_server.py start-kiosk.sh rs-stats.sh homescreen@100.110.212.126:/tmp/
scp start-lofi.sh kiosk-lofi.service homescreen@100.110.212.126:/tmp/
ssh homescreen@100.110.212.126 'sudo mv /tmp/*.py /tmp/*.sh /opt/kiosk/ && sudo chmod +x /opt/kiosk/*.sh'

# Deploy GIFs (large — run once)
scp -r gifs/ homescreen@100.110.212.126:/opt/kiosk/gifs/

# Enable services
ssh homescreen@100.110.212.126 'sudo systemctl enable --now kiosk-web kiosk-lofi'
```

---

## SSH Access

```bash
ssh -i ~/.ssh/id_ed25519_homescreen homescreen@100.110.212.126
# NOPASSWD sudo for homescreen user (no password needed for sudo)
```

---

## Service Management

```bash
# Restart web server
ssh homescreen@100.110.212.126 'sudo systemctl restart kiosk-web'

# Check kiosk-web status
ssh homescreen@100.110.212.126 'systemctl status kiosk-web -n 5'

# Check chrome process
ssh homescreen@100.110.212.126 'ps aux | grep chrome | grep -v grep'

# Check lofi
ssh homescreen@100.110.212.126 'curl -s http://127.0.0.1:8088/audio.json'

# Check monitors endpoint
ssh homescreen@100.110.212.126 'curl -s http://127.0.0.1:8088/monitors.json'
```

---

## Auto-Update (GIFs / wallpaper)

The `download_gifs.py` script in this directory re-validates all GIFs and updates the served list. Run locally and re-scp the gifs directory.

---

## Known Issues & Resolutions

| Issue | Fix |
|-------|-----|
| Chrome GNOME keyring prompt on first run | `--password-store=basic` flag in chrome launch |
| TV overscan — content clipped at edges | `xrandr --output HDMI-1 --mode 1024x768` in `start-kiosk.sh` |
| `.gif` files that are actually WebP → black frames | `is_valid_gif()` checks magic bytes at startup |
| Chrome started by systemd before X is ready | Chrome runs from `start-kiosk.sh` inside X session, NOT from systemd |
| lofi music never deployed | `kiosk-lofi.service` + `start-lofi.sh` existed in repo but were not on box (2026-08-16 fix) |
| apt `chromium-browser` reinstalls snapd on Ubuntu 24.04 | Use Google Chrome from Google's apt repo, NOT Ubuntu's `chromium-browser` package |

---

## Session History

| Date | Event |
|------|-------|
| 2026-07-23 | Initial deployment — de-bloat, chrome, kiosk-server |
| 2026-07-24 | LightDM autologin fix, xrandr 1024×768 fix (TV overscan) |
| 2026-08-16 | GIF magic-byte validation fix, lofi music deployed |
| 2026-08-19 | Merged into unified `homepi` repo as `kiosk-pc/` |
