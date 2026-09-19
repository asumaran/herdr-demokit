# herdr-demokit

Records README demo GIFs of [herdr](https://github.com/herdrdev/herdr)
plugins. One tool, one scenario per plugin: the tool boots an isolated herdr
session, populates it the way the plugin's scenario describes, replays a
keystroke script against an attached client, records it headless with
asciinema and renders the GIF with agg. The user's default herdr session is
never touched.

Used by [herdr-goto](https://github.com/asumaran/herdr-goto),
[gotopr](https://github.com/asumaran/gotopr) and
[herdr-confirm-close](https://github.com/asumaran/herdr-confirm-close); each
keeps its own `scripts/demo/` scenario.

## Install

```sh
git clone https://github.com/asumaran/herdr-demokit ~/Developer/herdr-demokit
export PATH="$HOME/Developer/herdr-demokit/bin:$PATH"   # or symlink bin/herdr-demo
```

Requirements:

- herdr >= 0.7.5 with the plugin being demoed registered (`herdr plugin
  link`/`install`) and its keybinds in the user's herdr config.
- `asciinema` >= 3 and `agg` (`brew install asciinema agg`).
- bash >= 4 (`brew install bash`; macOS's `/bin/bash` is 3.2) and `python3`.
- The GIF font in `~/Library/Fonts` (default: Berkeley Mono).

`herdr-demo doctor` checks all of that.

## Usage

From the plugin's repo root:

```sh
herdr-demo record                 # -> docs/demo.gif (scenario's DEMO_OUT)
herdr-demo record -o /tmp/try.gif --keep-cast /tmp/try.cast
herdr-demo up                     # boot + populate the session, leave it running
herdr-demo down                   # stop + delete it
herdr-demo doctor
```

Options: `-s/--scenario DIR` (default `scripts/demo`), `-o/--out FILE`,
`--keep-session` (record without tearing the session down), `--keep-cast
FILE` (keep the trimmed asciicast for inspection).

A full take runs in about 30 seconds: ~8 s to boot and populate the session,
the length of the keystroke script, and a couple of seconds to render.

## Scenario contract

A scenario directory holds `scenario.sh` and `keys.json`.

### scenario.sh

Sourced by the tool with bash `set -euo pipefail`. Settings (all optional)
and hooks:

| setting | default | meaning |
|---|---|---|
| `DEMO_SESSION` | `demo` | name of the isolated herdr session |
| `DEMO_OUT` | `docs/demo.gif` | output GIF, relative to the repo root |
| `DEMO_START_CWD` | repo root | cwd of the initial workspace (the demo starts there) |
| `DEMO_SESSION_ENV` | `()` | `KEY=VALUE` array injected into the session server's env; plugin commands inherit it (popup-size overrides, scan roots, ...) |
| `DEMO_COLS` / `DEMO_ROWS` | `170` / `44` | recording terminal size |
| `DEMO_PREFIX` | `ctrl+b` | herdr prefix key |
| `DEMO_LINGER` | `2.4` | seconds to hold the last frame before detaching |
| `DEMO_THEME` / `DEMO_FONT_FAMILY` / `DEMO_FONT_SIZE` / `DEMO_FONT_DIR` | `dracula` / `Berkeley Mono` / `14` / `~/Library/Fonts` | agg rendering |
| `DEMO_LAST_FRAME` | `2` | agg `--last-frame-duration` |
| `DEMO_KEYS` | `<scenario>/keys.json` | keystroke script |

Any of these can also be overridden from the environment
(`DEMO_COLS=200 herdr-demo record`).

- `demo_setup()` (required): populate the session. Runs with the server up
  and a holding client attached; the initial workspace already exists with
  `DEMO_START_CWD` as cwd. Helpers:
  - `demo herdr ...` runs any herdr CLI command against the demo session.
  - `demo_first_workspace` prints the initial workspace id.
  - `demo_adopt_repo <workspace-id> <repo>` attaches worktree metadata to a
    workspace (so herdr shows it as that repo's main checkout).
  - `demo_open_repo <repo>` creates a workspace for a main checkout and
    adopts it; prints the id.
  - `demo_open_worktree <repo> <worktree-path>` opens a linked worktree under
    its repo.
  - `demo_pane_by_cwd <dir>` prints the first pane id with that cwd.
  - `demo_split_below <dir> [ratio] [focus]` splits that pane downwards
    (default ratio 0.72); pass `focus` to land on the new pane. Prints the
    new pane id.
  - `demo_run_in_pane <pane-id> <command>` types a command + Enter into a
    pane before recording (e.g. to make it busy).
  - `demo_focus_workspace <id>`. The tool focuses the initial workspace
    after `demo_setup` returns.
- `demo_build()` (optional): runs before the session boots, e.g. build the
  plugin binary stamped with the manifest version so the UI shows the
  release look.
- `demo_teardown()` (optional): runs after the session is torn down, even
  on failure, e.g. restore the dev build or state you parked.

### keys.json

A JSON array of steps replayed once the client is attached; waits are
relative to the previous step:

```json
[
  ["wait", 3.0],
  ["prefix", "f"],
  ["wait", 2.4],
  ["type", "price"],
  ["wait", 1.3],
  ["key", "enter"]
]
```

- `["wait", seconds]`
- `["key", name]`: `enter`, `esc`, `tab`, `backspace`, `space`, arrows,
  `shift+up`/`shift+down`, `ctrl+<letter>`, `ctrl+alt+<letter>` (for plugins
  bound to a chord with no prefix variant), `prefix`, or a single literal
  character.
- `["type", text]` / `["type", text, interval]`: one character every
  `interval` seconds (default 0.17).
- `["prefix", name]`: herdr chord, i.e. prefix, 0.35 s, then the key.

The tool appends the detach (`DEMO_LINGER`, then prefix+q). The cast is
trimmed so the GIF opens on the attached client (everything before herdr's
alt-screen enter is dropped) and ends on the last UI frame (the detach tail
is cut 1.5 s before the alt-screen exit), then rendered by agg.

## How it works

- `lib/driver.py` runs the herdr client in a fixed-size pty, relays its
  output to asciinema and answers the terminal queries TUIs send at startup
  (OSC 10/11, CSI 6n, DA, XTVERSION, kitty keyboard, DECRQM). Nothing
  answers them inside a bare pty or asciinema's headless mode, which stalls
  termenv-style detection and makes scripted keystrokes get swallowed as
  query replies. In `hold` mode it just keeps a client alive: starting a
  client is what boots a session server (there is no `herdr session start`).
- `lib/session.sh` boots/destroys the session and provides the `demo_*`
  helpers. The recording may itself run from inside a herdr pane, so the
  inherited `HERDR_*` env is stripped for every demo command, otherwise the
  client refuses to nest and the CLI talks to the enclosing session.
- `lib/record.sh` + `lib/trim.py`: asciinema -> trim -> agg.

Recording engines were compared before settling on this one: VHS
(ttyd/xterm.js + Chrome) reproduces the flow but rasterises text through
Skia, which draws visibly heavier strokes than agg's swash, and its GIF
encoder upscales every frame (charmbracelet/vhs#625). Bypassing the encoder
left the stroke weight, so asciinema + agg stayed.
