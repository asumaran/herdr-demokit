#!/usr/bin/env python3
"""Trim an asciicast v2 file in place so the rendered GIF starts and ends on
the demo's UI.

Head: everything before the first alt-screen enter (CSI ?1049h, i.e. herdr
taking over the terminal) is dropped and timestamps are rebased, so frame 0
is the attached client rather than an empty terminal waiting for it.

Tail: the detach (the PREFIX indicator from pressing prefix+q, the alt-screen
exit and the "detached from server" message) is cut so the GIF ends — and
loops — on the final UI frame. The cut lands 1.5 s before the detach marker
to also drop the prefix-indicator redraw.
"""

import json
import sys

HEAD_MARGIN = 0.0
TAIL_MARGIN = 1.5


def main(path: str) -> None:
    with open(path) as f:
        lines = f.read().splitlines(True)
    header, body = lines[0], lines[1:]
    events = [json.loads(line) for line in body]

    start = 0.0
    for t, kind, data in events:
        if kind == "o" and "\x1b[?1049h" in data:
            start = max(0.0, t - HEAD_MARGIN)
            break

    cut = None
    for t, kind, data in events:
        if t <= start:
            continue
        if kind == "o" and ("\x1b[?1049l" in data or "detached from server" in data):
            cut = t - TAIL_MARGIN
            break

    out = [header]
    for t, kind, data in events:
        if t < start:
            continue
        if cut is not None and t >= cut:
            break
        out.append(json.dumps([round(t - start, 6), kind, data]) + "\n")

    with open(path, "w") as f:
        f.writelines(out)


if __name__ == "__main__":
    main(sys.argv[1])
