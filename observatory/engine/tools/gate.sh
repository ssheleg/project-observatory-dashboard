#!/usr/bin/env bash














set -uo pipefail
cd "$(dirname "$0")/.." || exit 2
umask 077
PY="./.venv/bin/python"
[ -x "$PY" ] || PY="$(command -v python3)" || exit 2
group="${1:-check}"
[ "$#" -eq 0 ] || shift
log="$("$PY" -c 'from tools.install_launchd import prepare_logs, LOG_DIR; prepare_logs(("gate.log",)); print(LOG_DIR / "gate.log")')" || exit 2
rotate() {
  local f="$1" limit=$((2 * 1024 * 1024))
  [ -f "$f" ] || return 0
  local size; size=$(stat -f %z "$f" 2>/dev/null || stat -c %s "$f" 2>/dev/null || echo 0)
  [ "$size" -gt "$limit" ] || return 0
  [ -f "$f.2" ] && mv -f "$f.2" "$f.3"
  [ -f "$f.1" ] && mv -f "$f.1" "$f.2"
  mv -f "$f" "$f.1"
}
rotate "$log"
printf '=== %s gate %s ===\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$group" >> "$log"
"$PY" observatory.py "$group" "$@" >> "$log" 2>&1
code=$?
printf '=== gate %s exit %s ===\n' "$group" "$code" >> "$log"
tail -n 4 "$log"
exit "$code"
