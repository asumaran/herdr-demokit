# shellcheck shell=bash
# record.sh — record the populated demo session with asciinema and render the
# GIF with agg. Sourced by bin/herdr-demo after session.sh.

demo_record() {
  local cast
  cast="$(mktemp -t herdr-demo).cast"

  # --headless: don't touch the invoking terminal. --window-size matches the
  # driver's pty. asciicast-v2 because agg doesn't read the newer v3 format.
  "${CLEAN_ENV[@]}" DEMO_COLS="$DEMO_COLS" DEMO_ROWS="$DEMO_ROWS" \
    DEMO_PREFIX="$DEMO_PREFIX" DEMO_LINGER="$DEMO_LINGER" \
    asciinema rec --headless --overwrite -f asciicast-v2 \
    --window-size "${DEMO_COLS}x${DEMO_ROWS}" \
    -c "python3 '$DEMO_DRIVER' play '$DEMO_KEYS' herdr session attach '$DEMO_SESSION'" \
    "$cast"

  python3 "$KIT_ROOT/lib/trim.py" "$cast"

  mkdir -p "$(dirname "$DEMO_OUT")"
  agg --theme "$DEMO_THEME" --font-dir "$DEMO_FONT_DIR" \
    --font-family "$DEMO_FONT_FAMILY" --font-size "$DEMO_FONT_SIZE" \
    --last-frame-duration "$DEMO_LAST_FRAME" "$cast" "$DEMO_OUT"
  log "wrote $DEMO_OUT"

  # Debug aid: keep the trimmed cast around for inspection.
  if [[ -n "${DEMO_KEEP_CAST:-}" ]]; then
    cp "$cast" "$DEMO_KEEP_CAST"
    log "kept cast at $DEMO_KEEP_CAST"
  fi
  rm -f "$cast"
}
