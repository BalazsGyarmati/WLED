# Serial Events Usermod

This usermod emits compact one-line event records over the WLED serial interface.

## Features

- Reports Wi-Fi online/offline transitions
- Reports power, brightness, effect, palette, speed, intensity, and preset changes
- Reports button events with button ID and action
- Uses compact event lines designed for easy parsing in Node-RED
- Optionally includes Unix timestamps in milliseconds from the WLED time source

## Serial Format

Each event is emitted as a single line:

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

## Event Reference

The event format is:

```txt
EV|<timestamp>|<code>|<value1>[|<value2>]
```

Field meanings:

- `EV`: fixed event prefix
- `<timestamp>`: Unix timestamp in milliseconds
- `<code>`: event type code
- `<value1>`: primary event value
- `<value2>`: optional secondary value, currently used only for button actions

### Event Codes

- `ONL|<0|1>`
  - `1` = WLED is connected to the network
  - `0` = WLED is not connected to the network

- `PWR|<0|1>`
  - `1` = logical power on
  - `0` = logical power off
  - This is derived from the global brightness state used by WLED

- `BRI|<0..255>`
  - Global brightness value

- `FX|<effectId>`
  - Current effect ID

- `PAL|<paletteId>`
  - Current palette ID

- `SPD|<0..255>`
  - Current effect speed

- `INT|<0..255>`
  - Current effect intensity

- `PST|<presetId>`
  - Current preset ID
  - Only emitted for non-zero preset IDs

- `BTN|<buttonId>|<action>`
  - `<buttonId>` is the WLED button index
  - `<action>` is one of the button action codes listed below

### Button ID Meaning

`buttonId` is the zero-based WLED button index:

- `0` = first configured button
- `1` = second configured button
- `2` = third configured button
- `3` = fourth configured button

The actual GPIO assigned to each button depends on the hardware configuration in WLED.

### Button Action Codes

- `S` = short press
- `L` = long press
- `D` = double press
- `ON` = switch on
- `OFF` = switch off

`ON` and `OFF` are used for switch-style inputs and PIR-style motion inputs.

## Resolving IDs To Human-Readable Names

Some event values are numeric IDs by design to keep the serial payload compact.

### Effect IDs (`FX`)

Resolve effect IDs through the WLED JSON API:

- `GET /json/effects`

This returns the effect-name array in ID order, so:

- `FX|23` means item `23` from `/json/effects`

### Palette IDs (`PAL`)

Resolve palette IDs through the WLED JSON API:

- `GET /json/palx`

This returns palette data in ID order, so:

- `PAL|5` means item `5` from `/json/palx`

Depending on your setup, palette names are also available from:

- `GET /json`

under the `palettes` field.

### Preset IDs (`PST`)

Preset IDs are the normal WLED preset slot IDs from the presets system.

- `PST|12` means preset slot `12`

The human-readable preset name is whatever you saved into that preset slot in WLED.
You can inspect presets through the presets UI or by reading the preset storage used by WLED.

If WLED does not yet have a valid time source, the timestamp is `0`.

## Configuration

The usermod adds a `SerialEvents` section to the Usermods settings/config:

- `enabled`: turns the usermod on or off
- `timestamp`: includes Unix timestamps when enabled

For backward compatibility, the usermod still accepts the legacy `Serial Events` section name when reading existing config.

## Required Core Changes

This usermod depends on the button-event callback added in this branch so it can receive button ID and action directly from `button.cpp`.
