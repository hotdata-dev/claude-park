# Renders docs/demo.gif. Run docs/demo/render.sh rather than vhs directly:
# it builds the fictional fixture this tape expects first.

Output docs/demo.gif

Require fzf

Set Shell "bash"
Set FontFamily "Menlo"
Set FontSize 16
Set Width 1480
Set Height 840
Set Padding 20
Set Theme "Catppuccin Mocha"
Set WindowBar Colorful
Set TypingSpeed 45ms

# Isolate: scrub the recording machine's Claude/iTerm2 vars, point every
# claude-park path at the throwaway fixture, and use stand-in claude and gh.
Hide
Type "source /tmp/claude-park-demo/env.sh && clear"
Enter
Sleep 500ms
Show

Sleep 800ms
Type "# in Claude Code, !park runs this shell command (no model turn)"
Enter
Sleep 400ms
Type "park"
Sleep 300ms
Enter
Sleep 2.5s

Type "git worktree list; ls"
Sleep 300ms
Enter
Sleep 3s

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
