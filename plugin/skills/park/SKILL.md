---
name: park
description: Park this Claude Code session so it can be resumed weeks later. Writes a park card summarizing the session, locks the git worktree so cleanup tools leave it alone, optionally deletes rebuildable build dirs, and closes the terminal tab. Use when the user says "/park", "park this", or "park this session".
argument-hint: "[--clean] [--no-close]"
---

Park this session with the `claude-park` CLI, supplying your own summary.

1. Write a park card in Markdown with exactly these sections:

   **Goal** — one or two sentences on what this session is trying to achieve.
   **Done** — bullets of what is finished.
   **Next** — bullets of concrete next steps, most important first.
   **Gotchas** — bullets of open questions, blockers, or context that would be
   easy to forget. Write "None" if there are none.

   Be specific: name files, branches, PRs, commands, and decisions. The reader
   is you, weeks from now, with no memory of this session.

2. Pipe the card to the CLI in a single Bash call, passing through any
   arguments the user gave (`$ARGUMENTS`):

   ```bash
   claude-park park --summary-file - $ARGUMENTS <<'PARK_CARD'
   <the card>
   PARK_CARD
   ```

3. Reply with one line: the title it parked under. Do nothing after that;
   unless `--no-close` was given, the CLI ends this session and closes the
   tab a moment later.

If `claude-park` is not on PATH, tell the user to run `install.sh` from the
claude-park repo and stop.
