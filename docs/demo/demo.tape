# Records the terminal part of docs/demo.gif. Run docs/demo/render.sh rather
# than vhs directly: it builds the fictional fixture first and adds captions
# (docs/demo/compose.py) afterwards. Caption timings there follow the Sleeps here.

Output "/tmp/claude-park-demo/raw.mp4"

Require fzf

Set Shell "bash"
Set FontFamily "Menlo"
Set FontSize 16
Set Width 1480
Set Height 900
Set Padding 20
Set Theme "Catppuccin Mocha"
Set WindowBar Colorful
Set TypingSpeed 45ms
Set Framerate 20

# Isolate: scrub the recording machine's Claude/iTerm2 vars, point every
# claude-park path at the throwaway fixture, and use stand-in claude and gh.
Hide
Type "source /tmp/claude-park-demo/env.sh && clear && python3 $DEMO_SESSION_UI; clear"
Enter
Sleep 800ms
Show

# A long-running Claude Code session that has to wait. !park runs as a
# shell command, so the session's model never runs.
Sleep 3s
Type "!"
Sleep 1.2s
Type "park"
Sleep 1.2s
Enter
Sleep 4.4s

# The tab is gone. Later, a fresh terminal:
Hide
Type "newtab"
Enter
Sleep 300ms
Show
Sleep 600ms
Type "parked"
Sleep 300ms
Enter
Sleep 3s

Down
Sleep 2s
Down
Sleep 2s
Down
Sleep 2s
Up
Sleep 400ms
Up
Sleep 1.5s

Ctrl+O
Sleep 4s
Ctrl+O
Sleep 1.5s

Enter
Sleep 3.5s
