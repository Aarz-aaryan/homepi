# Home devices: display, kiosk and Echo relay

Documentation baseline: **2026-11-15**. This repository contains the historical Raspberry Pi display and the merged `kiosk-pc/` implementation. Not every home-device service was remotely verified in this update.

## Keep the roles separate

| Component | Responsibility | Evidence / confidence |
|---|---|---|
| homepi Raspberry Pi | TFT clock/status display (`clock.py`, `clock.service`) | Existing repository implementation; present operation not rechecked |
| homescreen / kiosk PC | Home display/kiosk and the Echo relay host | Kiosk files in `kiosk-pc/`; relay described by current voice deployment docs, not yet synchronized here |
| Echo Dot | Custom Wyoming microphone/speaker endpoint with local Alexa wake word | Current agent-server Echo implementation and deployment notes; home Wi-Fi acceptance still pending |
| agent-server | Pi reasoning interfaces and GPU STT/TTS | Source/service inspection, active on 2026-11-15 |
| r-server | Storage/application services and monitoring | Read-only SSH inventory on 2026-11-15 |

Do not assume that every “Pi” reference means the Raspberry Pi: **Pi Coding Agent is software on agent-server**, distinct from the homepi hardware.

## Echo audio path

```text
Echo → home Wi-Fi → homescreen echo-relay.service
     → restricted SSH forward over Tailscale → agent-server :18700 loopback
     → dedicated Pi conversation + shared Whisper/Kokoro GPU workers
```

The relay's owner-local files live at `~/echo-pi-relay` on homescreen. It discovers the Echo and reconnects the restricted tunnel. No speech models run on the kiosk. The dedicated SSH credential must remain private and must not grant a general remote shell.

Echo conversation behavior, session expiry, feedback suppression and verification limits are documented in the [current voice/Echo guide](https://github.com/Aarz-aaryan/control-dashboard/blob/main/docs/current-system/voice-and-whatsapp.md). Browser `/voice on` is a different interface and is not required for Echo.

## Climate/fan telemetry is a separate device endpoint

The dashboard's fixed climate upstream is `http://100.110.11.122:5000/api`. Its telemetry is ambient DHT11 temperature/humidity and scheduled fan duty, not CPU temperature or measured fan RPM. This address differs from the historical TFT homepi address in `MISSION.md`; device identity/hardware ownership has **not** been reconciled. Do not deploy clock or cooling configuration based on the name alone.

## Repository navigation and limits

- [MISSION.md](MISSION.md): historical TFT hardware, rendering and operational notes. Its “Running” status is dated, not a fresh health check.
- `kiosk-pc/`: merged kiosk implementation; `homescreen-kiosk` was already marked superseded by this directory.
- [Cross-system overview](https://github.com/Aarz-aaryan/control-dashboard/blob/main/docs/current-system/README.md).

Outstanding: verify the actual home hosts/services and physical Echo conversation with the owner; publish a sanitized, reviewed relay deployment package; reconcile display/climate device inventory. No kiosk deployment, firmware update, microphone capture or service restart was performed here.
