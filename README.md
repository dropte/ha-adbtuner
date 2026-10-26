# ADBTuner for Home Assistant

A [HACS](https://hacs.xyz) custom integration for [ADBTuner](https://adbtuner.github.io/), the app that turns Android TV / Fire TV devices plus an HDMI encoder into tuners for Channels DVR and other IPTV clients.

See at a glance whether a tuner is busy and what it's playing, get alerted if a device or encoder drops off, free a stuck tuner from a dashboard, and (with a guide) browse or automate on what's airing across your ADBTuner channels.

## Features

For each ADBTuner **tuner** (streaming device):

| Entity | What it shows |
|---|---|
| `sensor.<tuner>_status` | `idle`, `tuning`, `tuned` or `maintenance`, with channel, provider and since-when attributes |
| `sensor.<tuner>_channel` | The channel being streamed, e.g. `2306 Peacock (Web) 06` |
| `sensor.<tuner>_now_playing` | *(with a guide)* The programme on that channel right now, e.g. `Premier League: Chelsea vs. Tottenham` |
| `binary_sensor.<tuner>_in_use` | On while ADBTuner holds the tuner |
| `binary_sensor.<tuner>_device_connected` | ADBTuner can reach the device over ADB |
| `binary_sensor.<tuner>_stream_connected` | ADBTuner can reach the streaming endpoint (HDMI encoder) |
| `sensor.<tuner>_last_tune` | Result of the last tune (`complete`, `error`, …) with channel, client, time-to-stream and error |
| `image.<tuner>_last_tune_screenshot` | ADBTuner's screenshot from the last tune |
| `button.<tuner>_unlock_tuner` / `_retry_tuner` | Free a tuner stuck "in use" / retry one that failed its connectivity check |

For the **server**: a version sensor and, with a guide, `calendar.adbtuner_guide`: every non-idle programme on your ADBTuner channels, usable in the calendar dashboard and in automations ("notify me 10 minutes before any match with *Arsenal* in the title").

## Guide support (optional)

Give the integration an **XMLTV guide URL** whose channel ids match your ADBTuner channels' **M3U ids**. Setups built with [FruitDeepLinks](https://github.com/kineticman/FruitDeepLinks) ADB lanes work out of the box: use `http://<fdl-host>:6655/out/adb_lanes.xml` and set each ADBTuner channel's M3U id to the lane's `tvg-id` (e.g. `sportscenter01`). Any other XMLTV source works the same way. Placeholder entries such as `Idle` / `Stand By` are ignored.

## Installation

### HACS
1. HACS → ⋮ → **Custom repositories** → add `https://github.com/dropte/ha-adbtuner` as an **Integration**.
2. Install **ADBTuner**, then restart Home Assistant.

### Manual
Copy `custom_components/adbtuner` into your Home Assistant `config/custom_components/` folder and restart.

## Setup

**Settings → Devices & services → Add integration → ADBTuner**

- **ADBTuner URL**: the address of ADBTuner's web UI, e.g. `http://192.168.1.10:5592`. Home Assistant must be able to reach it, so if ADBTuner runs in Docker, publish port 5592.
- **Guide (XMLTV) URL**: optional; can be added or changed later under *Configure*.

## Notes

- Polls ADBTuner every 15 seconds, the channel list every 10 minutes, and the guide every 30 minutes.
- Tested with ADBTuner `20260918-1` (API `/api/v1`). ADBTuner isn't open source and its API has changed between releases; please open an issue if a new release breaks something.
- Not affiliated with ADBTuner or FruitDeepLinks.

## Development

`tests/` holds Home Assistant–independent unit tests (`pytest -q tests`). CI runs `hassfest`, the HACS validator and the tests.
