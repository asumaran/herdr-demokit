# CLAUDE.md

Guidance for working in this repository.

## What this is

`asdemokit` is the tool that records the README demo GIFs of the
asumaran herdr plugins (`asgoto`, `asgotopr`, `asconfirmclose`). It
lives on the development machine only (cloned under `~/Developer`, `bin/` on
PATH); it never ships with the plugins and is never run in CI, since a take
needs the user's herdr config/keybinds, personal repos, fonts and `gh` auth.
Each plugin keeps its own scenario under `scripts/demo/` (`scenario.sh` +
`keys.json`) and runs `asdemo record` from its repo root.

## Layout

- `bin/asdemo` — the CLI (`record`, `up`, `down`, `doctor`): option
  parsing, scenario loading (defaults < scenario.sh < environment), the
  record flow and the EXIT trap that tears the session down.
- `lib/common.sh` — `CLEAN_ENV` (strips inherited `HERDR_*` so the demo
  client can nest inside a herdr pane), `demo` (run a command against the
  demo session), `json`, `log`/`die`.
- `lib/session.sh` — session lifecycle (boot via a held client in a pty,
  release, stop+delete) and the `demo_*` helpers scenarios use.
- `lib/driver.py` — pty driver: answers terminal queries, `hold` and `play`
  modes, `keys.json` compiler (`wait`/`key`/`type`/`prefix` steps), appends
  the detach (`DEMO_LINGER`, prefix+q).
- `lib/trim.py` — asciicast head/tail trim (first alt-screen enter, 1.5 s
  before the detach).
- `lib/record.sh` — asciinema headless recording + agg render.

Bash >= 4 (`#!/usr/bin/env bash`, Homebrew bash on macOS), python3 stdlib
only, asciinema >= 3 (`--headless`), agg.

## Decisions

- asciinema + agg + the pty driver, not VHS: evaluated and rejected (Chrome's
  text rasterisation is visibly heavier than agg's, and VHS's GIF encoder
  upscales frames; see README). Don't revisit without a rendering fix.
- The keystroke script is data (`keys.json`), the session layout is code
  (`scenario.sh`): plugins differ mostly in what the session holds, so the
  layout gets the full shell + helpers, while keystrokes stay declarative.
- Environment overrides beat `scenario.sh` for every `DEMO_*` setting, so a
  one-off `DEMO_COLS=200 asdemo record` needs no edit.
- The tool always recreates the session (stop + delete + boot) per take and
  tears it down on exit, even on failure. `--keep-session` is a debugging
  aid only.
- Never touch the user's default herdr session; everything goes through
  `demo` (explicit `HERDR_SOCKET_PATH` of the demo session).

## Conventions

- Conventional Commits (`type(scope): description`).
- Never mention AI tooling in commits or repo-visible text.
- Don't commit, tag or push unless explicitly asked.
