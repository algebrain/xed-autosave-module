#!/usr/bin/env bash
set -euo pipefail

export XED_AUTOSAVE_DEBUG=1
export XED_AUTOSAVE_DEBUG_LOG="${XED_AUTOSAVE_DEBUG_LOG:-$HOME/.xed/autosave/hadron-autosave.log}"

mkdir -p "$(dirname "$XED_AUTOSAVE_DEBUG_LOG")"
printf 'Xed autosave debug log: %s\n' "$XED_AUTOSAVE_DEBUG_LOG" >&2
exec xed --standalone "$@"
