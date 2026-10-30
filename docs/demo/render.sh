#!/bin/sh
# Rebuild the fictional demo fixture and render docs/demo.gif with VHS.
# The fixture lives in /tmp/claude-park-demo; your real ~/.claude, Claude
# sessions, and iTerm2 tabs are never touched.
set -eu
cd "$(dirname "$0")/../.."
python3 -I docs/demo/setup.py
# Start VHS from a minimal environment so no session variables leak in.
env -i HOME="$HOME" PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin" \
  TERM=xterm-256color LANG=en_US.UTF-8 vhs docs/demo/demo.tape
