# WLED v0.15.4.x Local Changes

This document describes the local changes prepared for the `v0.15.4.x` branch and explains why they were added.

## Summary

The current change set contains six repository-level changes:

1. `platformio_override.ini`
2. `tools/wled_serial_test.py`
3. `wled00/data/settings_sync.htm`
4. `usermods/serial_events/`
5. `wled00/button.cpp` and related minimal button-event plumbing
6. `.gitignore`

## Why These Changes Were Added

### `platformio_override.ini`

This override adds a dedicated PlatformIO environment for a Waveshare ESP32-S3-Zero style setup where WLED must communicate over the board's hardware TX/RX pins.

The override disables the USB CDC console configuration and switches the build to normal UART mode:

- `ARDUINO_USB_CDC_ON_BOOT=0`
- `ARDUINO_USB_MODE=0`

This is required so serial communication can use the TX/RX pins on the board instead of the USB CDC serial path.

### `tools/wled_serial_test.py`

This helper script was added for serial interface testing from Linux. It makes it easier to verify that the board responds correctly over UART after the override is applied.

The script can:

- request the firmware version
- request the current WLED millisecond timestamp
- request a compact device info JSON snapshot
- request JSON info/state
- request LED data in JSON or binary form
- send raw commands
- send a temporary baud-rate switch command

The script uses only Python standard library modules, so no extra Python package install is required.

### `wled00/data/settings_sync.htm`

The serial baud-rate selector now includes `9600`.

This was added so low-speed control commands can be sent more safely over longer cables, where lower baud rates can be more reliable than high-speed serial communication.

The MQTT section also includes a new checkbox:

- `Publish timestamped button events`

When enabled, WLED publishes an additional MQTT message for each button event on a new topic that does not overlap with the stock WLED MQTT button topic layout:

- `<mqttDeviceTopic>/button_ts/<id>`
- `<mqttDeviceTopic>/motion_ts/<id>` for PIR-style motion inputs

Payload format:

```txt
<unix_timestamp_ms>|<action>
```

Examples:

```txt
1713545145123|S
1713545148456|L
1713545152789|D
1713545158123|ON
1713545162456|OFF
```

Action codes:

- `S` = short press
- `L` = long press
- `D` = double press
- `ON` = switch on
- `OFF` = switch off

If WLED does not yet have valid network time, the timestamp is `0`.

### `usermods/serial_events/`

This branch adds a dedicated `Serial Events` usermod for compact serial event reporting.

The usermod emits one event per line:

```txt
EV|<timestamp>|<code>|<value1>[|<value2>]
```

Examples:

```txt
EV|1713545123123|ONL|1
EV|1713545128456|PWR|1
EV|1713545130789|BRI|128
EV|1713545135123|FX|23
EV|1713545136345|PAL|5
EV|1713545137456|SPD|200
EV|1713545138567|INT|90
EV|1713545140123|PST|12
EV|1713545145456|BTN|1|S
```

Field meanings:

- `EV`: fixed event prefix
- `<timestamp>`: Unix timestamp in milliseconds
- `<code>`: event type code
- `<value1>`: primary event value
- `<value2>`: optional secondary value, currently used only by button events

Event code reference:

- `ONL|<0|1>`: network online/offline state
- `PWR|<0|1>`: logical power state
- `BRI|<0..255>`: global brightness
- `FX|<effectId>`: current effect ID
- `PAL|<paletteId>`: current palette ID
- `SPD|<0..255>`: current effect speed
- `INT|<0..255>`: current effect intensity
- `PST|<presetId>`: current preset ID
- `BTN|<buttonId>|<action>`: button event

Button ID reference:

- `0` = first configured WLED button
- `1` = second configured WLED button
- `2` = third configured WLED button
- `3` = fourth configured WLED button

Button action codes:

- `S` = short press
- `L` = long press
- `D` = double press
- `ON` = switch on
- `OFF` = switch off

ID resolution:

- Effect names: `GET /json/effects`, then use the event's `FX` value as the zero-based array index
- Palette names/data: `GET /json/palx`, then use the event's `PAL` value as the zero-based array index
- Preset IDs: standard WLED preset slot IDs from the presets system

The usermod is enabled in `platformio_override.ini` for the local UART-focused environment:

```ini
-D USERMOD_SERIAL_EVENTS
```

The usermod uses the Usermods settings/config section for:

- `enabled`
- `timestamp`

The config section name is `SerialEvents`.
For backward compatibility, the usermod also reads the legacy `Serial Events` section name from existing config.

### `wled00/button.cpp` and related minimal plumbing

The core changes were kept intentionally small:

- a new optional MQTT publish path for timestamped button events
- a new usermod callback so usermods can receive `buttonId + action` directly

This makes the serial usermod possible without rewriting the button handling logic.

### `.gitignore`

`platformio_override.ini` was removed from `.gitignore` so this board-specific override can be tracked in git together with the related changes.

## How To Test The Serial Changes

Build the web UI first if needed, then build the firmware with the override environment:

```sh
npm ci
npm run build
pio run -e esp32s3dev_8MB_opi_uart
```

After flashing the firmware and connecting the board through its UART interface, use the helper script from Linux.

### 1. Read version

```sh
python3 tools/wled_serial_test.py -p /dev/ttyUSB0 version
```

or for a CDC-style device path:

```sh
python3 tools/wled_serial_test.py -p /dev/ttyACM0 version
```

### 2. Read JSON state/info

```sh
python3 tools/wled_serial_test.py -p /dev/ttyUSB0 json --verbose
```

### 2a. Read the dedicated millisecond timestamp response

```sh
python3 tools/wled_serial_test.py -p /dev/ttyUSB0 time
```

Expected response:

```txt
T|1713545145456
```

### 2b. Read the compact device info JSON

```sh
python3 tools/wled_serial_test.py -p /dev/ttyUSB0 info --verbose
```

This uses the dedicated serial command `i`.

The uppercase `I` command is already used by the stock Improv serial protocol, so the compact info JSON uses lowercase `i` to avoid breaking that existing interface.

Example response:

```json
{
  "ip": "192.168.1.42",
  "hostname": "wled-kitchen",
  "mac": "AB:CD:EF:01:02:03",
  "mqtt_device_topic": "wled/kitchen",
  "mqtt_group_topic": "wled/all",
  "wifi_ssid": "MyWiFi",
  "wifi_rssi": -58,
  "wifi_connected": true,
  "mqtt_connected": true,
  "uptime_s": 12345
}
```

Field meanings:

- `ip`: current local IP address
- `hostname`: current mDNS/hostname value
- `mac`: uppercase MAC address with `:` separators
- `mqtt_device_topic`: configured MQTT device topic
- `mqtt_group_topic`: configured MQTT group topic
- `wifi_ssid`: current connected Wi-Fi SSID
- `wifi_rssi`: current Wi-Fi RSSI in dBm
- `wifi_connected`: whether Wi-Fi is currently connected
- `mqtt_connected`: whether MQTT is currently connected
- `uptime_s`: uptime in seconds

### 3. Read LED data as JSON

```sh
python3 tools/wled_serial_test.py -p /dev/ttyUSB0 led-json
```

### 4. Read LED data as binary TPM2 and print it as hex

```sh
python3 tools/wled_serial_test.py -p /dev/ttyUSB0 led-bin --hex
```

### 5. Send a raw JSON control command

```sh
python3 tools/wled_serial_test.py -p /dev/ttyUSB0 raw --text '{"on":true,"bri":64}'
```

### 6. Send a temporary baud-switch command

```sh
python3 tools/wled_serial_test.py -p /dev/ttyUSB0 baud 921600
```

Then reconnect using the new baud rate:

```sh
python3 tools/wled_serial_test.py -p /dev/ttyUSB0 --baud 921600 version
```

### 7. Test low-speed communication at 9600

If WLED is configured to use `9600`, connect with:

```sh
python3 tools/wled_serial_test.py -p /dev/ttyUSB0 --baud 9600 version
python3 tools/wled_serial_test.py -p /dev/ttyUSB0 --baud 9600 raw --text '{"on":true}'
```

This is the recommended way to verify long-cable control-command communication after selecting `9600` in the Sync settings page.

### 8. Listen for compact serial event lines

After enabling the `Serial Events` usermod and flashing the firmware, you can listen for spontaneous events:

```sh
python3 tools/wled_serial_test.py -p /dev/ttyUSB0 --baud 9600 listen --seconds 10
```

Trigger a few actions in WLED while the script is listening, for example:

- toggle power
- change brightness
- change effect or palette
- press configured buttons

Expected output format:

```txt
EV|1713545123123|ONL|1
EV|1713545128456|PWR|1
EV|1713545145456|BTN|1|S
```

### 9. Verify timestamped MQTT button topics

Enable:

- `Publish on button press`
- `Publish timestamped button events`

Then subscribe to:

```txt
<mqttDeviceTopic>/button_ts/#
<mqttDeviceTopic>/motion_ts/#
```

Press a button or trigger a switch/PIR input and confirm that both the legacy button topic and the new timestamped topic are published.

## Recommended Git Flow From Detached HEAD

If you are currently on a detached HEAD, create the branch from the current checkout before committing:

```sh
git switch -c v0.15.4.x
```

That keeps the current uncommitted changes attached to the new branch, and you can then stage and commit normally.
