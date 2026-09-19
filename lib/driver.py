#!/usr/bin/env python3
"""Pty driver for herdr-demo recordings.

Runs a command inside a fixed-size pty, relays its output to stdout (which
asciinema records) and answers the terminal queries TUIs send at startup
(colors, cursor position, device attributes). Nothing answers them inside a
bare pty or asciinema's headless mode, which leaves termenv-style detection
blocked and makes scripted keystrokes get swallowed as query replies, so the
driver acts as a minimal terminal and answers them.

Modes:
  hold                 keep the program alive until killed (session setup,
                       not recorded)
  play <keys.json>     replay the keystroke script, detach with prefix+q,
                       then exit

Usage: driver.py hold <command> [args...]
       driver.py play <keys.json> <command> [args...]

Environment:
  DEMO_COLS / DEMO_ROWS   pty size (default 170x44)
  DEMO_PREFIX             herdr prefix key, e.g. "ctrl+b" (default)
  DEMO_LINGER             seconds to hold the final frame before detaching
                          (default 2.4)

keys.json is a JSON array of steps, executed in order. Waits are relative to
the previous step:
  ["wait", 1.5]             pause 1.5 s
  ["key", "enter"]          press one key (see KEY_NAMES, "ctrl+<x>", or a
                            single literal character)
  ["type", "price"]         type text, one character every 0.17 s
  ["type", "price", 0.25]   same with an explicit interval
  ["prefix", "f"]           herdr chord: prefix, 0.35 s, then the key
"""

import fcntl
import json
import os
import pty
import re
import select
import signal
import struct
import sys
import termios
import time

COLS = int(os.environ.get("DEMO_COLS", "170"))
ROWS = int(os.environ.get("DEMO_ROWS", "44"))
LINGER = float(os.environ.get("DEMO_LINGER", "2.4"))
TYPE_INTERVAL = 0.17
CHORD_GAP = 0.35

KEY_NAMES = {
    "enter": b"\r",
    "esc": b"\x1b",
    "tab": b"\t",
    "backspace": b"\x7f",
    "space": b" ",
    "up": b"\x1b[A",
    "down": b"\x1b[B",
    "right": b"\x1b[C",
    "left": b"\x1b[D",
}


def key_bytes(name: str) -> bytes:
    if name == "prefix":
        return key_bytes(os.environ.get("DEMO_PREFIX", "ctrl+b"))
    if name in KEY_NAMES:
        return KEY_NAMES[name]
    if name.startswith("ctrl+alt+") and len(name) == 10 and name[9].isalpha():
        # legacy encoding: alt is an ESC prefix on the control byte
        return b"\x1b" + bytes([ord(name[9].lower()) - 96])
    if name.startswith("ctrl+") and len(name) == 6 and name[5].isalpha():
        return bytes([ord(name[5].lower()) - 96])
    if name in ("shift+down", "shift+up"):
        return b"\x1b[1;2B" if name == "shift+down" else b"\x1b[1;2A"
    if len(name) == 1:
        return name.encode()
    raise ValueError(f"unknown key name: {name!r}")


def compile_steps(steps) -> list:
    """Turns keys.json steps into (delay, bytes) pairs."""
    out = []
    for step in steps:
        if not isinstance(step, list) or not step:
            raise ValueError(f"bad step: {step!r}")
        op, args = step[0], step[1:]
        if op == "wait":
            out.append((float(args[0]), b""))
        elif op == "key":
            out.append((0.0, key_bytes(args[0])))
        elif op == "type":
            interval = float(args[1]) if len(args) > 1 else TYPE_INTERVAL
            for i, ch in enumerate(args[0]):
                out.append((0.0 if i == 0 else interval, ch.encode()))
        elif op == "prefix":
            out.append((0.0, key_bytes("prefix")))
            out.append((CHORD_GAP, key_bytes(args[0])))
        else:
            raise ValueError(f"unknown step {op!r}")
    return out


def detach_steps() -> list:
    # linger on the final frame, then detach cleanly (prefix+q); record.sh
    # trims the detach tail from the cast so the GIF ends on the UI.
    return [(LINGER, key_bytes("prefix")), (CHORD_GAP, b"q"), (0.8, b"")]


QUERY_REPLIES = [
    (re.compile(rb"\x1b\]11;\?(\x07|\x1b\\)"),
     lambda m: b"\x1b]11;rgb:1e1e/1e1e/2e2e" + m.group(1)),
    (re.compile(rb"\x1b\]10;\?(\x07|\x1b\\)"),
     lambda m: b"\x1b]10;rgb:f8f8/f8f8/f2f2" + m.group(1)),
    (re.compile(rb"\x1b\[6n"), lambda m: b"\x1b[1;1R"),
    (re.compile(rb"\x1b\[0?c"), lambda m: b"\x1b[?62;22c"),
    (re.compile(rb"\x1b\[>0?q"), lambda m: b"\x1bP>|herdr-demo\x1b\\"),
    (re.compile(rb"\x1b\[\?u"), lambda m: b"\x1b[?0u"),
    (re.compile(rb"\x1b\[\?(\d+)\$p"), lambda m: b"\x1b[?" + m.group(1) + b";0$y"),
]


def answer_queries(fd: int, buf: bytes) -> bytes:
    """Replies to terminal queries found in buf; returns the unmatched tail
    kept for queries split across reads."""
    for rx, reply in QUERY_REPLIES:
        while True:
            m = rx.search(buf)
            if not m:
                break
            os.write(fd, reply(m))
            buf = buf[: m.start()] + buf[m.end():]
    return buf[-32:]


def main() -> int:
    mode = sys.argv[1]
    if mode == "hold":
        script, cmd = [], sys.argv[2:]
    elif mode == "play":
        with open(sys.argv[2]) as f:
            script = compile_steps(json.load(f)) + detach_steps()
        cmd = sys.argv[3:]
    else:
        print(__doc__, file=sys.stderr)
        return 2

    pid, fd = pty.fork()
    if pid == 0:
        os.execvp(cmd[0], cmd)

    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", ROWS, COLS, 0, 0))

    out = sys.stdout.buffer
    steps = iter(script)
    step = next(steps, None)
    deadline = time.monotonic() + step[0] if step else None
    tail = b""

    while True:
        timeout = max(0.0, deadline - time.monotonic()) if deadline else 0.5
        ready, _, _ = select.select([fd], [], [], timeout)
        if ready:
            try:
                data = os.read(fd, 65536)
            except OSError:
                break
            if not data:
                break
            out.write(data)
            out.flush()
            tail = answer_queries(fd, tail + data)
        if deadline is not None and time.monotonic() >= deadline:
            os.write(fd, step[1])
            step = next(steps, None)
            deadline = time.monotonic() + step[0] if step else None
        if mode == "play" and step is None and deadline is None:
            break

    if mode == "play":
        # the client is still attached after prefix+q lands: finish it
        os.kill(pid, signal.SIGTERM)
    os.waitpid(pid, 0)
    return 0


if __name__ == "__main__":
    sys.exit(main())
