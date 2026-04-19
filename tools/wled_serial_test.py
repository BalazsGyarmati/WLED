#!/usr/bin/env python3
"""Small helper to test the WLED serial interface from Linux.

Examples:
  python3 tools/wled_serial_test.py -p /dev/ttyACM0 version
  python3 tools/wled_serial_test.py -p /dev/ttyACM0 time
  python3 tools/wled_serial_test.py -p /dev/ttyACM0 json --verbose
  python3 tools/wled_serial_test.py -p /dev/ttyUSB0 led-json
  python3 tools/wled_serial_test.py -p /dev/ttyUSB0 led-bin --hex
  python3 tools/wled_serial_test.py -p /dev/ttyUSB0 listen --seconds 10
  python3 tools/wled_serial_test.py -p /dev/ttyACM0 baud 921600
  python3 tools/wled_serial_test.py -p /dev/ttyACM0 raw --text '{"on":true,"bri":64}'
"""

from __future__ import annotations

import argparse
import json
import os
import select
import sys
import termios
import time
from typing import Iterable


BAUD_MAP = {
    115200: 0xB0,
    230400: 0xB1,
    460800: 0xB2,
    500000: 0xB3,
    576000: 0xB4,
    921600: 0xB5,
    1000000: 0xB6,
    1500000: 0xB7,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-p", "--port", required=True, help="Serial device, e.g. /dev/ttyACM0")
    parser.add_argument(
        "-b", "--baud", type=int, default=115200, help="Current serial baud rate for the port"
    )
    parser.add_argument(
        "-t", "--timeout", type=float, default=1.0, help="Read timeout in seconds after sending"
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("version", help="Send 'v' and print the WLED version response")
    subparsers.add_parser("time", help="Send 'T' and print the WLED millisecond timestamp response")

    json_parser = subparsers.add_parser("json", help="Request JSON state/info via {'v':true}")
    json_parser.add_argument(
        "--verbose", action="store_true", help="Pretty-print returned JSON if possible"
    )

    subparsers.add_parser("led-json", help="Request current LED data as JSON array via 'l'")

    led_bin_parser = subparsers.add_parser("led-bin", help="Request current LED data as TPM2 via 'L'")
    led_bin_parser.add_argument("--hex", action="store_true", help="Print binary response as hex")

    listen_parser = subparsers.add_parser("listen", help="Listen for spontaneous serial events")
    listen_parser.add_argument(
        "--seconds", type=float, default=10.0, help="How long to listen before exiting"
    )
    listen_parser.add_argument(
        "--max-bytes", type=int, default=65536, help="Maximum number of bytes to read"
    )

    baud_parser = subparsers.add_parser("baud", help="Temporarily switch WLED to a supported baud rate")
    baud_parser.add_argument("new_baud", type=int, choices=sorted(BAUD_MAP.keys()))

    raw_parser = subparsers.add_parser("raw", help="Send raw text or bytes")
    raw_group = raw_parser.add_mutually_exclusive_group(required=True)
    raw_group.add_argument("--text", help="Literal text payload")
    raw_group.add_argument("--hex", dest="hex_bytes", help="Hex payload, e.g. '76' or '7b 22 76 22 3a 74 72 75 65 7d'")
    raw_parser.add_argument("--read-bytes", type=int, default=2048, help="Maximum bytes to read back")

    return parser.parse_args()


def baud_to_termios(baud: int) -> int:
    attr = f"B{baud}"
    if not hasattr(termios, attr):
        raise SystemExit(f"Unsupported baud for this system Python/termios build: {baud}")
    return getattr(termios, attr)


def set_termios_speed(attrs: list, speed: int) -> None:
    """Set input/output speed on platforms without cfsetispeed/cfsetospeed."""
    if hasattr(termios, "cfsetispeed") and hasattr(termios, "cfsetospeed"):
        termios.cfsetispeed(attrs, speed)
        termios.cfsetospeed(attrs, speed)
        return

    # POSIX termios attribute layout:
    # [iflag, oflag, cflag, lflag, ispeed, ospeed, cc]
    attrs[4] = speed
    attrs[5] = speed


class SerialPort:
    def __init__(self, path: str, baud: int):
        self.path = path
        self.baud = baud
        self.fd = None
        self._saved_attrs = None

    def __enter__(self) -> "SerialPort":
        fd = os.open(self.path, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
        attrs = termios.tcgetattr(fd)
        self._saved_attrs = attrs[:]

        attrs[0] = 0
        attrs[1] = 0
        attrs[2] = termios.CS8 | termios.CREAD | termios.CLOCAL
        attrs[3] = 0

        speed = baud_to_termios(self.baud)
        set_termios_speed(attrs, speed)
        termios.tcsetattr(fd, termios.TCSANOW, attrs)
        termios.tcflush(fd, termios.TCIOFLUSH)

        self.fd = fd
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self.fd is not None:
            if self._saved_attrs is not None:
                termios.tcsetattr(self.fd, termios.TCSANOW, self._saved_attrs)
            os.close(self.fd)
            self.fd = None

    def write(self, data: bytes) -> None:
        if self.fd is None:
            raise RuntimeError("Serial port is not open")
        view = memoryview(data)
        while view:
            written = os.write(self.fd, view)
            view = view[written:]

    def read_until_quiet(self, timeout: float, max_bytes: int = 8192, quiet_gap: float = 0.15) -> bytes:
        if self.fd is None:
            raise RuntimeError("Serial port is not open")

        chunks = []
        total = 0
        deadline = time.monotonic() + timeout
        last_data_time = None

        while time.monotonic() < deadline and total < max_bytes:
            remaining = max(0.0, min(deadline - time.monotonic(), quiet_gap))
            ready, _, _ = select.select([self.fd], [], [], remaining)
            if not ready:
                if last_data_time is not None and (time.monotonic() - last_data_time) >= quiet_gap:
                    break
                continue

            chunk = os.read(self.fd, min(1024, max_bytes - total))
            if not chunk:
                continue
            chunks.append(chunk)
            total += len(chunk)
            last_data_time = time.monotonic()

        return b"".join(chunks)


def print_text_response(data: bytes) -> None:
    if not data:
        print("No response received.", file=sys.stderr)
        return
    try:
        print(data.decode("utf-8", errors="replace").strip())
    except Exception:
        print(repr(data))


def hexdump(data: bytes, width: int = 16) -> str:
    lines = []
    for offset in range(0, len(data), width):
        chunk = data[offset : offset + width]
        hex_part = " ".join(f"{byte:02x}" for byte in chunk)
        ascii_part = "".join(chr(byte) if 32 <= byte <= 126 else "." for byte in chunk)
        lines.append(f"{offset:04x}: {hex_part:<{width * 3}} {ascii_part}")
    return "\n".join(lines)


def send_and_read(port: SerialPort, payload: bytes, timeout: float, max_bytes: int = 8192) -> bytes:
    port.write(payload)
    return port.read_until_quiet(timeout=timeout, max_bytes=max_bytes)


def parse_json_response(data: bytes, verbose: bool) -> None:
    text = data.decode("utf-8", errors="replace").strip()
    if not text:
        print("No response received.", file=sys.stderr)
        return
    if not verbose:
        print(text)
        return

    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        print(text)
        return

    print(json.dumps(obj, indent=2, sort_keys=True))


def raw_bytes_from_hex(values: str) -> bytes:
    cleaned = values.replace(" ", "").replace(":", "")
    return bytes.fromhex(cleaned)


def main() -> int:
    args = parse_args()

    with SerialPort(args.port, args.baud) as port:
        if args.command == "version":
            response = send_and_read(port, b"v", timeout=args.timeout, max_bytes=256)
            print_text_response(response)
            return 0

        if args.command == "time":
            response = send_and_read(port, b"T", timeout=args.timeout, max_bytes=256)
            print_text_response(response)
            return 0

        if args.command == "json":
            response = send_and_read(port, b'{"v":true}\n', timeout=args.timeout, max_bytes=16384)
            parse_json_response(response, args.verbose)
            return 0

        if args.command == "led-json":
            response = send_and_read(port, b"l", timeout=args.timeout, max_bytes=65536)
            print_text_response(response)
            return 0

        if args.command == "led-bin":
            response = send_and_read(port, b"L", timeout=args.timeout, max_bytes=65536)
            if args.hex:
                print(hexdump(response))
            else:
                sys.stdout.buffer.write(response)
            return 0

        if args.command == "listen":
            response = port.read_until_quiet(timeout=args.seconds, max_bytes=args.max_bytes, quiet_gap=args.seconds)
            if response:
                print_text_response(response)
            return 0

        if args.command == "baud":
            port.write(bytes([BAUD_MAP[args.new_baud]]))
            print(f"Sent temporary baud-switch command for {args.new_baud}.")
            print(f"Reconnect using --baud {args.new_baud} for further tests.")
            return 0

        if args.command == "raw":
            payload = args.text.encode("utf-8") if args.text is not None else raw_bytes_from_hex(args.hex_bytes)
            response = send_and_read(port, payload, timeout=args.timeout, max_bytes=args.read_bytes)
            if response:
                print_text_response(response)
            return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
