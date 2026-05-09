#!/usr/bin/env bash
set -euo pipefail

# Install writers-room into Claude Code, Codex CLI, and Gemini CLI
# by symlinking this directory into each tool's user-scope skills folder.
# Safe to re-run: existing entries are skipped, not overwritten.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_NAME="writers-room"

TARGETS=(
  "$HOME/.claude/skills/$SKILL_NAME"
  "$HOME/.agents/skills/$SKILL_NAME"
  "$HOME/.gemini/skills/$SKILL_NAME"
)

LABELS=(
  "Claude Code"
  "Codex CLI"
  "Gemini CLI"
)

echo "Linking $SCRIPT_DIR into:"
for i in "${!TARGETS[@]}"; do
  target="${TARGETS[$i]}"
  label="${LABELS[$i]}"
  parent="$(dirname "$target")"
  mkdir -p "$parent"
  if [ -L "$target" ] || [ -e "$target" ]; then
    echo "  [skip]   $label  ->  $target  (already exists)"
    continue
  fi
  ln -s "$SCRIPT_DIR" "$target"
  echo "  [ok]     $label  ->  $target"
done

echo
echo "Done. Restart your CLI so it discovers the skill."
