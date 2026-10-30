#!/bin/sh
# Link claude-park, park, and parked into a directory on PATH.
set -eu

dest="${1:-$HOME/.local/bin}"
src="$(cd "$(dirname "$0")/bin" && pwd)"

command -v python3 >/dev/null || { echo "python3 is required" >&2; exit 1; }
command -v git >/dev/null || { echo "git is required" >&2; exit 1; }

mkdir -p "$dest"
for name in claude-park park parked; do
  ln -sfn "$src/claude-park" "$dest/$name"
  echo "linked $dest/$name"
done

case ":$PATH:" in
  *":$dest:"*) ;;
  *) echo "note: $dest is not on PATH" ;;
esac
command -v fzf >/dev/null || echo "note: install fzf for the interactive picker (brew install fzf)"
command -v gh >/dev/null || echo "note: install gh to record PR links on park cards"
