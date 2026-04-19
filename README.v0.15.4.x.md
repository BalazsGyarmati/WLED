# WLED v0.15.4.x Local Changes

This document describes the local changes prepared for the `v0.15.4.x` branch and explains why they were added.

## Summary

The current change set contains four repository-level changes:

1. `platformio_override.ini`
2. `tools/wled_serial_test.py`
3. `wled00/data/settings_sync.htm`
4. `.gitignore`

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
- request JSON info/state
- request LED data in JSON or binary form
- send raw commands
- send a temporary baud-rate switch command

The script uses only Python standard library modules, so no extra Python package install is required.

### `wled00/data/settings_sync.htm`

The serial baud-rate selector now includes `9600`.

This was added so low-speed control commands can be sent more safely over longer cables, where lower baud rates can be more reliable than high-speed serial communication.

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

## Recommended Git Flow From Detached HEAD

If you are currently on a detached HEAD, create the branch from the current checkout before committing:

```sh
git switch -c v0.15.4.x
```

That keeps the current uncommitted changes attached to the new branch, and you can then stage and commit normally.
