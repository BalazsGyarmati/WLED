# Serial Events Usermod

This usermod emits compact one-line event records over the WLED serial interface.

## Features

- Reports Wi-Fi online/offline transitions
- Reports power, brightness, effect, palette, speed, intensity, and preset changes
- Reports button events with button ID and action
- Uses compact event lines designed for easy parsing in Node-RED
- Optionally includes Unix timestamps from the WLED time source

## Serial Format

Each event is emitted as a single line:

```txt
EV|<timestamp>|<code>|<value1>[|<value2>]
```

Examples:

```txt
EV|1713545123|ONL|1
EV|1713545128|PWR|1
EV|1713545130|BRI|128
EV|1713545135|FX|23
EV|1713545136|PAL|5
EV|1713545137|SPD|200
EV|1713545138|INT|90
EV|1713545140|PST|12
EV|1713545145|BTN|1|S
```

Button action codes:

- `S` = short press
- `L` = long press
- `D` = double press
- `ON` = switch on
- `OFF` = switch off

If WLED does not yet have a valid time source, the timestamp is `0`.

## Configuration

The usermod adds a `Serial Events` section to the Usermods settings/config:

- `enabled`: turns the usermod on or off
- `timestamp`: includes Unix timestamps when enabled

## Required Core Changes

This usermod depends on the button-event callback added in this branch so it can receive button ID and action directly from `button.cpp`.
