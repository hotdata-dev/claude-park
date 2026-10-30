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
4. Writes `PARKED.md` at the worktree root: a "parked, not abandoned" notice,
   the resume command, and the card. It is hidden from `git status` through
   the repo's `.git/info/exclude`, so it never shows up as a change. Agents
   and scripts that ignore git locks still see it when they look in the
   directory. A `PARKED.md` that claude-park didn't write is never
   overwritten or deleted. Resuming or dropping the session removes the file.
5. Deletes gitignored, rebuildable directories (`target`, `node_modules`,
   `.venv`, `.next`, …) and records what was freed. It only touches paths git
   reports as ignored. Pass `--no-clean` to keep them.
6. Starts the Haiku summary in the background, then stops the Claude process
   and closes the iTerm2 pane.

## Resuming

`parked` opens an fzf picker with one line per session: age, repo, title,
phase, and git state.

```
  3d  api-server    Rate limiter for the public search API        ▰▰▰▰▱ review    PR #482 open
  9d  web-app       Migrate settings page to new form library     ▰▰▱▱▱ design    2 uncommitted
```

After the card is written, Haiku makes a second, small pass over the card to
produce the title, phase (research → design → build → review → wrap-up), a
one-line status, and the top three next steps. The preview shows that short
view, and ctrl-o switches to the full card. Names set with `/rename` are
never used as titles, but you can still search by them. `parked refresh`
regenerates these fields from existing cards without needing transcripts.

| key    | action |
| ------ | ------ |
| enter  | resume here (`cd <worktree> && claude --resume <id>`) |
| ctrl-t | resume in a new iTerm2 tab |
| ctrl-f | fresh session in the worktree, seeded with the park card instead of the full history |
| ctrl-x | drop: unpark without resuming |
| ctrl-o | switch the preview between the short view and the full card |

Resuming unlocks the worktree, removes `PARKED.md`, and moves the card to `~/.claude/parked/archive/`.
Parking the same session again starts from that card. With no new
conversation turns, it reuses the card as is, without a model call. With new
turns, Haiku updates the old card from only the new turns. That way, context
that has scrolled out of the excerpt window survives repeated park/resume
cycles. If the update fails, the old card stays, marked stale, and the next
park retries the update.
The first turn after `--resume` re-sends the full history, which is
unavoidable. Use ctrl-f to skip that cost when the card is enough.

Every action also works directly:

```
parked list
parked show [--brief] [--color] <id-prefix|title>
parked refresh [--all] [<id>]          # regenerate titles and short views from cards
parked resume [--tab] [--fresh] <id-prefix|title>
parked drop <id-prefix|title>
parked summarize <id-prefix|title>     # regenerate the card
parked doctor [--session <id>]         # check transcripts are still readable
park --no-clean | --no-close | --no-summary | --no-pr
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

## Claude Code compatibility

claude-park reads Claude Code's session transcripts
(`~/.claude/projects/*/<session-id>.jsonl`) and the `CLAUDE_CODE_SESSION_ID`
environment variable. Neither is a documented, stable interface. To keep a
format change from quietly producing empty cards:

- If a transcript has entries but no readable conversation turns, parking
  skips the summary, marks the card as failed with "transcript format not
  recognized (Claude Code <version>)", and prints a warning.
- Each card records the Claude Code version that wrote the transcript.
- `parked doctor` parses your most recent transcript (or `--session <id>`)
  and reports which fields it found. Run it after upgrading Claude Code. It
  exits non-zero when the format is not recognized.

## Tests

```
python3 -m unittest discover -s tests
```
