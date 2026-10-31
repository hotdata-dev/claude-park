<p align="center">
  <img src="docs/banner.png" alt="claude-park: Park your sessions. Pick up where you left off.">
</p>

You have a dozen Claude Code sessions running across different git worktrees. Some are half-finished, others you won't touch for weeks. Keeping them open wastes resources; closing them makes it harder to pick up where you left off.

**claude-park lets you shelve a Claude Code session and resume it whenever you're ready.** It preserves your conversation, protects your worktree, and generates a concise summary of where you left off.

Two commands:

```bash
!park     # inside Claude Code: park this session and close its tab
parked    # in any shell: find a parked session and resume it
```

![Parking a session, browsing parked sessions, and resuming one](docs/demo.gif)

## Install

```bash
./install.sh
```

This links `claude-park`, `park`, and `parked` into `~/.local/bin`.

**Requirements:** macOS, Python 3.9+, and git. iTerm2 is needed to automatically close and reopen tabs; without it, parking still stops Claude but leaves the tab open.

Optional dependencies:
- `fzf` for the interactive session picker
- `gh` for GitHub pull request information

### Optional: `/park` skill

If your Claude session is still warm, the optional `/park` skill can write its own summary using the context already available to the model, avoiding a separate Haiku summarization call.

```bash
claude plugin marketplace add hotdata-dev/claude-park
claude plugin install park@claude-park
```

## Why park a session?

**Free up your workspace.** Stop idle Claude processes, close unused terminal tabs, and reclaim disk space from rebuildable dependencies.

**Protect unfinished work.** Lock your git worktree against accidental removal and leave a `PARKED.md` notice explaining that the work is parked, not abandoned.

**Never lose your place.** Preserve the full conversation and generate a concise park card capturing the goal, progress, next steps, and gotchas.

**Resume without starting over.** Return to the original conversation, or start a fresh session using the park card instead of re-sending the entire history.

## How parking works

### Park without re-sending your context

`!park` is a shell command, not a Claude slash command. Parking doesn't invoke your active Claude model or re-send its entire conversation.

Instead, a background job passes a trimmed transcript excerpt (opening request, latest compaction summary, and recent turns, up to roughly 60K characters) to Haiku, which generates a **park card** containing:

- The task's goal and current progress
- What has already been completed
- Next steps
- Important context and gotchas

The result is saved alongside the session's metadata, ready whenever you return.

### Protect your work

Parking does more than save the conversation:

1. **Records session state.** Saves the title, directory, branch, ahead/dirty counts, last commit, associated PR (via `gh`), and last prompt in `~/.claude/parked/<session-id>.json`.
2. **Locks the worktree.** Uses `git worktree lock` with a `claude-park:` reason. Git refuses to remove or prune locked worktrees. Existing locks are preserved.
3. **Leaves a notice.** Writes `PARKED.md` at the worktree root with the resume command and park card. The file is hidden from `git status` via `.git/info/exclude`. An existing `PARKED.md` not created by claude-park is never overwritten.
4. **Reclaims disk space.** Removes gitignored, rebuildable directories such as `target`, `node_modules`, `.venv`, and `.next`. Only paths reported as ignored by git are touched. Use `--no-clean` to skip cleanup.
5. **Preserves the transcript.** Hard-links the conversation into `~/.claude/parked/transcripts/`, protecting it from Claude Code's automatic transcript cleanup without duplicating its disk usage. The original is relinked on resume if necessary.
6. **Closes the session.** Stops the Claude process and closes its iTerm2 pane.

## Resuming a session

Run `parked` from any shell to browse your parked sessions.

The interactive fzf picker shows each session's age, repository, title, progress, and git state:

```text
  3d  api-server  Rate limiter for the public search API     ▰▰▰▰▱ review  PR #482 open
  9d  web-app     Migrate settings page to new form library  ▰▰▱▱▱ design  2 uncommitted
```

A lightweight Haiku pass over the park card generates a short preview with:

- A descriptive title
- Current phase (research → design → build → review → wrap-up)
- One-line status
- Top three next steps

### Resume the full conversation, or start fresh

You have two ways to pick up your work.

**Resume the original session** to restore the full conversation exactly where you left it:

```bash
parked resume <id>
```

**Start fresh with the park card** to give a new Claude session the essential context without re-sending the entire conversation:

```bash
parked resume --fresh <id>
```

The fresh option is especially useful for long-running tasks where the original conversation has accumulated hundreds of thousands of tokens.

### Picker shortcuts

| Key | Action |
| --- | --- |
| `enter` | Resume the original session in the current terminal |
| `ctrl-t` | Resume in a new iTerm2 tab |
| `ctrl-f` | Start a fresh session seeded with the park card |
| `ctrl-x` | Drop the parked session without resuming |
| `ctrl-o` | Toggle between the short preview and full park card |

Resuming or dropping a session unlocks its worktree, removes the generated `PARKED.md`, and archives the park card.

### Park and resume repeatedly

You can park the same session more than once without losing context.

When you park it again, claude-park starts from the archived card:

- **No new conversation turns?** The existing card is reused without another model call.
- **New conversation turns?** Haiku updates the card using only the new turns, preserving older context captured in previous summaries.
- **Summary update fails?** The previous card is retained and marked stale, and the next park retries.

This allows context to survive repeated parking and resuming, even as older conversation history moves outside the summarization window.

## Token usage

claude-park is designed to minimize unnecessary model calls and context reprocessing.

| Action | Token usage |
| --- | --- |
| Park with `!park` | A Haiku call summarizes a trimmed transcript excerpt; the full conversation is not re-sent to your active Claude model |
| Park using `/park` | Uses the active session's existing context to generate the card, avoiding a separate summarization call; a small Haiku call still turns the card into the picker preview |
| Resume original session | Claude may need to re-send the full conversation history on the next turn |
| Resume fresh session | Starts with the much smaller park card instead of the full conversation |
| Park again with no new turns | Reuses the existing card without a model call |

The full conversation remains available when you need it. The fresh-session option gives you a way to continue without paying to reconstruct all of that context.

## Command reference

Everything available in the interactive picker also works directly from the command line.

```bash
# Browse and inspect parked sessions
parked list
parked show [--brief] [--color] <id-prefix|title>

# Resume a session
parked resume [--tab] [--fresh] <id-prefix|title>

# Remove a session from parking without resuming
parked drop <id-prefix|title>

# Refresh generated summaries and previews
parked refresh [--all] [<id>]
parked summarize <id-prefix|title>

# Check transcript compatibility
parked doctor [--session <id>]

# Customize parking behavior
park --no-clean | --no-close | --no-summary | --no-pr
```

### Configuration

Configure claude-park using environment variables:

| Variable | Description | Default |
| --- | --- | --- |
| `CLAUDE_PARK_MODEL` | Model used for generating park cards | `haiku` |
| `CLAUDE_PARK_DIR` | Directory where parked sessions are stored | `~/.claude/parked` |

## Claude Code compatibility

claude-park reads Claude Code's local transcripts (`~/.claude/projects/*/<session-id>.jsonl`) and the `CLAUDE_CODE_SESSION_ID` environment variable.

**These are not documented, stable interfaces.** A future Claude Code update could change their format.

Rather than silently producing empty or incorrect summaries, claude-park fails loudly when it encounters an unrecognized transcript format:

- If a transcript contains entries but no readable turns, parking skips summarization and reports the incompatibility.
- Each park card records the Claude Code version that produced the transcript.
- `parked doctor` inspects your latest transcript (or a specified session) and reports which fields it recognizes.

After upgrading Claude Code, you can check compatibility with:

```bash
parked doctor
```

The command exits non-zero if the transcript format is not recognized.

## Development and tests

Run the test suite with:

```bash
python3 -m unittest discover -s tests
```

The demo shown above uses fictional data in `/tmp/claude-park-demo`, with stand-ins for `claude` and `gh`.

To regenerate it:

```bash
docs/demo/render.sh
```

Requires [VHS](https://github.com/charmbracelet/vhs), fzf, ffmpeg, and Pillow.

## License

MIT. See [LICENSE](LICENSE).

claude-park is an independent project by Hotdata, Inc. for Claude Code. It is not affiliated with or endorsed by Anthropic.
