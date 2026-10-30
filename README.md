# claude-park

Park idle Claude Code sessions and pick them up weeks later, without keeping
a terminal tab open for each one.

```
!park            # inside a Claude Code session: shelve it and close the tab
parked           # in any shell: browse parked sessions and resume one
```

## Why `!park` instead of a slash command

A slash command or skill runs a model turn, which re-sends the session's whole
context. For a stale session the prompt cache has expired, so a session
holding hundreds of thousands of tokens costs a full uncached request just to
be shelved. `!park` is a shell command: the parked session's model never runs.
Instead, a background job sends a trimmed transcript excerpt (opening request,
latest compaction summary, most recent turns, about 60K characters) to Haiku,
which writes the park card.

If the session is already warm, `/park` (the optional plugin) has the session
write its own card instead. That costs nothing extra while the cache is live.

## What parking does

1. Reads the session id from `$CLAUDE_CODE_SESSION_ID` and finds its
   transcript.
2. Records the title, directory, branch, ahead/dirty counts, last commit, PR
   (via `gh`), and last prompt in `~/.claude/parked/<session-id>.json`.
3. Runs `git worktree lock` on linked worktrees, with a reason that starts
   with `claude-park:`. `git worktree remove` and `prune` refuse locked
   worktrees, and `git worktree list` shows the reason, so other agents and
   cleanup scripts can see the worktree is parked rather than abandoned. A
   worktree that is already locked is left as it is.
4. With `--clean`, deletes gitignored, rebuildable directories (`target`,
   `node_modules`, `.venv`, `.next`, …) and records what was freed. It only
   touches paths git reports as ignored.
5. Starts the Haiku summary in the background, then stops the Claude process
   and closes the iTerm2 pane.

## Resuming

`parked` opens an fzf picker. The preview pane shows each session's card.

| key    | action |
| ------ | ------ |
| enter  | resume here (`cd <worktree> && claude --resume <id>`) |
| ctrl-t | resume in a new iTerm2 tab |
| ctrl-f | fresh session in the worktree, seeded with the park card instead of the full history |
| ctrl-x | drop: unpark without resuming |

Resuming unlocks the worktree and moves the card to `~/.claude/parked/archive/`.
The first turn after `--resume` re-sends the full history, which is
unavoidable. Use ctrl-f to skip that cost when the card is enough.

Every action also works directly:

```
parked list
parked show <id-prefix|title>
parked resume [--tab] [--fresh] <id-prefix|title>
parked drop <id-prefix|title>
parked summarize <id-prefix|title>     # regenerate the card
park --clean | --no-close | --no-summary | --no-pr
```

## Install

```
./install.sh            # links claude-park, park, parked into ~/.local/bin
```

Requires macOS with iTerm2 (for closing and opening tabs), Python 3.9+, and
git. fzf and gh are optional. Outside iTerm2, parking still works; it just
doesn't close the tab.

To install the optional `/park` skill:

```
claude plugin marketplace add <path-or-github-repo>
claude plugin install park@claude-park
```

Settings, via environment variables:

- `CLAUDE_PARK_MODEL`: summary model (default `haiku`)
- `CLAUDE_PARK_DIR`: where cards live (default `~/.claude/parked`)

## Tests

```
python3 -m unittest discover -s tests
```
