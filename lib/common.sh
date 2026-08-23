# shellcheck shell=bash
# common.sh — shared definitions for herdr-demo. Sourced by bin/herdr-demo.

log() { printf 'herdr-demo: %s\n' "$*" >&2; }
die() { log "$*"; exit 1; }

# The recording may itself run from inside a herdr pane; strip the inherited
# plugin/pane env so the demo client doesn't refuse to nest and the CLI talks
# to the demo session instead of the enclosing one.
CLEAN_ENV=(env -u HERDR_ENV -u HERDR_SOCKET_PATH -u HERDR_PANE_ID
  -u HERDR_TAB_ID -u HERDR_WORKSPACE_ID -u HERDR_STARTUP_CWD
  TERM=xterm-256color COLORTERM=truecolor)

# demo <cmd...>: run a command against the demo session (e.g. `demo herdr
# pane list`). Available to scenario.sh.
demo() { "${CLEAN_ENV[@]}" HERDR_SOCKET_PATH="$DEMO_SOCKET" "$@"; }

# json <python-expr>: read the JSON on stdin into `d` and print the expression.
json() { python3 -c "import json, sys; d = json.load(sys.stdin); print($1)"; }

require_cmd() {
  local c
  for c in "$@"; do
    command -v "$c" >/dev/null 2>&1 || die "missing required command: $c"
  done
}
