#!/usr/bin/env bash







set -uo pipefail
if [ -t 0 ]; then payload=""; else payload=$(cat 2>/dev/null || true); fi
root="${OBSERVATORY_ROOT:-}"
if [ -z "$root" ] && [ -n "${CLAUDE_PLUGIN_ROOT:-}" ]; then
  c="${CLAUDE_PLUGIN_ROOT}"
  for _ in 1 2 3 4 5 6; do
    [ -f "$c/observatory.py" ] && { root="$c"; break; }
    n="$(cd "$c/.." 2>/dev/null && pwd)" || break
    [ "$n" = "$c" ] && break
    c="$n"
  done
fi
[ -n "$root" ] || exit 0
[ -f "$root/tools/session_start.py" ] || exit 0
py="${OBSERVATORY_PYTHON:-$root/.venv/bin/python}"   # set by `full agent install`
[ -x "$py" ] || py="$(command -v python3 2>/dev/null)"
[ -n "$py" ] || exit 0
printf '%s' "$payload" | "$py" "$root/tools/session_start.py" 2>/dev/null || true
exit 0
