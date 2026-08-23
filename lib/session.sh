# shellcheck shell=bash
# session.sh — lifecycle of the isolated demo herdr session plus the helpers a
# scenario.sh uses to populate it. Sourced by bin/herdr-demo after common.sh.
#
# The demo session has its own socket and state dir, so the user's default
# herdr session is never touched. Starting a client is what boots a session
# server (there is no `herdr session start`), so a client is held in a hidden
# pty while the workspaces are created and dropped afterwards; the server
# keeps running until demo_session_down.

DEMO_HOLD_PID=""

demo_session_up() {
  # Fresh session every run so the recording is deterministic.
  herdr session stop "$DEMO_SESSION" >/dev/null 2>&1 || true
  sleep 1
  herdr session delete "$DEMO_SESSION" >/dev/null 2>&1 || true

  # The holding client is launched from DEMO_START_CWD so the initial
  # workspace is the one the demo starts on. DEMO_SESSION_ENV rides on the
  # server's env, which plugin commands inherit (popup size overrides, etc.).
  (cd "$DEMO_START_CWD" &&
    "${CLEAN_ENV[@]}" ${DEMO_SESSION_ENV[@]+"${DEMO_SESSION_ENV[@]}"} \
      python3 "$DEMO_DRIVER" hold herdr --session "$DEMO_SESSION") >/dev/null &
  DEMO_HOLD_PID=$!
  local _i
  for _i in $(seq 1 40); do [[ -S "$DEMO_SOCKET" ]] && break; sleep 0.5; done
  [[ -S "$DEMO_SOCKET" ]] || die "demo session socket never appeared at $DEMO_SOCKET"
  sleep 2
}

# Drop the setup client; the session server keeps running.
demo_session_release_hold() {
  [[ -n "$DEMO_HOLD_PID" ]] || return 0
  kill "$DEMO_HOLD_PID" 2>/dev/null || true
  wait "$DEMO_HOLD_PID" 2>/dev/null || true
  DEMO_HOLD_PID=""
  sleep 1
}

demo_session_down() {
  demo_session_release_hold
  herdr session stop "$DEMO_SESSION" >/dev/null 2>&1 || true
  sleep 1
  herdr session delete "$DEMO_SESSION" >/dev/null 2>&1 || true
}

# ---- helpers for scenario.sh's demo_setup ----

# Workspace id of the launch workspace (cwd = DEMO_START_CWD).
demo_first_workspace() {
  demo herdr workspace list | json 'd["result"]["workspaces"][0]["workspace_id"]'
}

# demo_adopt_repo <workspace-id> <repo-path>: attach worktree metadata to an
# existing workspace so herdr (and the plugins) see it as that repo's main
# checkout.
demo_adopt_repo() {
  demo herdr worktree open --workspace "$1" --path "$2" --no-focus >/dev/null
}

# demo_open_repo <repo-path>: new workspace for a main checkout; prints its id.
demo_open_repo() {
  local wid
  wid="$(demo herdr workspace create --cwd "$1" --no-focus |
    json 'd["result"]["workspace"]["workspace_id"]')"
  demo_adopt_repo "$wid" "$1"
  echo "$wid"
}

# demo_open_worktree <repo-path> <worktree-path>: open a linked worktree with
# the owning repo as --cwd context (herdr groups it under that repo).
demo_open_worktree() {
  demo herdr worktree open --cwd "$1" --path "$2" --no-focus >/dev/null
}

# demo_pane_by_cwd <dir>: id of the first pane whose cwd is <dir>, or empty.
demo_pane_by_cwd() {
  demo herdr pane list | python3 -c '
import json, sys
target = sys.argv[1]
for p in json.load(sys.stdin)["result"]["panes"]:
    if p.get("cwd") == target:
        print(p["pane_id"]); break
' "$1"
}

# demo_split_below <dir> [ratio] [focus]: split the pane whose cwd is <dir>
# downwards (default ratio 0.72) so herdr's pane dividers are visible, like a
# real working layout. Focus stays on the original pane unless the third
# argument is "focus" (herdr has no "focus pane by id"; --focus on the split
# is the way to land the user on the new pane). Prints the new pane id.
demo_split_below() {
  local pane focus="--no-focus"
  [[ "${3:-}" == "focus" ]] && focus="--focus"
  pane="$(demo_pane_by_cwd "$1")"
  [[ -n "$pane" ]] || die "no pane with cwd $1 to split"
  demo herdr pane split --pane "$pane" --direction down --ratio "${2:-0.72}" "$focus" |
    json 'd["result"]["pane"]["pane_id"]'
}

# demo_run_in_pane <pane-id> <command>: type a command into a pane and press
# Enter (before the recording starts, e.g. to put a pane in a busy state).
demo_run_in_pane() { demo herdr pane run "$1" "$2" >/dev/null; }

demo_focus_workspace() { demo herdr workspace focus "$1" >/dev/null; }
