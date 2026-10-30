#!/usr/bin/env python3
"""A mock Claude Code session screen for the demo recording.

Draws a busy, fictional mid-task session (tool calls, a diff, a long reply)
with the input box pinned to the bottom of the window, as in Claude Code.
Typing `!` switches the box to bash mode; on Enter the command runs for real
(against the demo fixture) and its output scrolls into the conversation. No
model runs.
"""
import os
import shutil
import subprocess
import sys
import termios
import textwrap
import time
import tty

RESET, BOLD, DIM, ITALIC = "\x1b[0m", "\x1b[1m", "\x1b[2m", "\x1b[3m"
PINK = "\x1b[38;5;205m"
GREEN = "\x1b[38;5;114m"
GREY = "\x1b[38;5;245m"
YELLOW = "\x1b[38;5;221m"
DEL_BG = "\x1b[48;5;52m"
ADD_BG = "\x1b[48;5;22m"

BOX_ROWS = 4  # rule, prompt, rule, status


def wrap(text: str, width: int, first: str, rest: str):
    lines = textwrap.wrap(text, width) or [""]
    return [first + lines[0]] + [rest + line for line in lines[1:]]


def transcript(cols: int):
    """The fictional session so far, as styled lines."""
    w = cols - 6
    out = []
    add = out.append

    def tool(name, arg, result, more=None):
        add(f"{GREEN}●{RESET} {BOLD}{name}{RESET}({arg})")
        for i, line in enumerate(result):
            add(("  ⎿  " if i == 0 else "     ") + line)
        if more:
            add(f"     {DIM}… +{more} line{'s' if more != 1 else ''}{RESET}")

    out.extend(wrap("I'll check where the 60s limit comes from before changing the endpoint.",
                    w, "● ", "  "))
    add("")
    tool("Grep", 'pattern: "setTimeout|timeout:", path: "src/"',
         [f"Found {BOLD}3{RESET} files", "src/reports/export.ts", "src/server/http.ts"], more=1)
    tool("Read", "src/server/http.ts", [f"Read {BOLD}64{RESET} lines"])
    tool("Read", "src/reports/export.ts", [f"Read {BOLD}118{RESET} lines"])
    tool("Bash", "cd ~/code/web-app && npm test -- reports/export",
         [f"{GREEN}PASS{RESET} src/reports/export.test.ts (4.2 s)",
          f"  {GREEN}✓{RESET} streams rows as CSV (312 ms)",
          f"  {GREEN}✓{RESET} escapes quotes, commas and newlines (18 ms)"], more=14)
    add(f"{GREEN}●{RESET} {BOLD}Update{RESET}(src/reports/export.ts)")
    add(f"  ⎿  Updated {BOLD}src/reports/export.ts{RESET} with 2 additions and 1 removal")
    for num, mark, code in [
        ("41", " ", "  const rows = db.reports.cursor(reportId, { batchSize: 5000 });"),
        ("42", "-", "  res.setTimeout(60_000);"),
        ("42", "+", "  res.setTimeout(0);"),
        ("43", "+", "  res.flushHeaders();"),
        ("44", " ", "  for await (const batch of rows) {"),
        ("45", " ", "    res.write(toCsv(batch));"),
    ]:
        line = f"{num} {mark}{code}"
        if mark == "-":
            add(f"     {DEL_BG}{line.ljust(w - 2)}{RESET}")
        elif mark == "+":
            add(f"     {ADD_BG}{line.ljust(w - 2)}{RESET}")
        else:
            add(f"     {DIM}{num}{RESET} {mark}{code}")
    tool("Bash", "curl -s -o /dev/null -w '%{http_code} %{time_total}\\n' "
                 "localhost:3000/reports/r_2m/export.csv",
         [f"{YELLOW}504{RESET} 60.01"])
    add("")
    out.extend(wrap("The 2M-row report still fails at 60s. The endpoint streams fine; the proxy "
                    "in front of it cuts any response longer than 60s, so removing our own "
                    "timeout doesn't help.", w, "● ", "  "))
    add("")
    add(f"  - {BOLD}Small reports:{RESET} stream directly, as now.")
    add(f"  - {BOLD}Large reports:{RESET} a background job writes the CSV to storage and emails a link.")
    add(f"  - {BOLD}Proxy timeout:{RESET} raising it to 10 minutes also works, but affects every route.")
    add("")
    add("  Want me to start on the background job?")
    add("")
    add(f"{DIM}✻ Churned for 6m 12s · done 4:02 PM{RESET}")
    add("")
    recap = wrap("Adding CSV export to dashboard reports. Small exports stream fine; large ones "
                 "time out at the proxy. Next: move large exports to a background job.",
                 w - 10, "", "")
    add(f"{DIM}※ recap: {ITALIC}{recap[0]}{RESET}")
    for line in recap[1:]:
        add(f"  {DIM}{ITALIC}{line}{RESET}")
    add("")
    return out


class Screen:
    def __init__(self):
        size = shutil.get_terminal_size((100, 30))
        self.cols, self.rows = size.columns, size.lines
        self.lines = transcript(self.cols)

    def out(self, text: str) -> None:
        sys.stdout.write(text)
        sys.stdout.flush()

    def render(self, buf: str) -> None:
        """Draw the newest lines that fit above the input box, like a scrolled terminal."""
        height = self.rows - BOX_ROWS
        visible = self.lines[-height:]
        visible = [""] * (height - len(visible)) + visible
        for row, line in enumerate(visible, 1):
            self.out(f"\x1b[{row};1H\x1b[2K{line}")
        self.box(buf)

    def box(self, buf: str) -> None:
        bash = buf.startswith("!")
        top = self.rows - BOX_ROWS + 1
        rule = (PINK if bash else DIM) + "─" * self.cols + RESET
        prompt = f"{PINK}!{RESET} {buf[1:]}" if bash else f"{GREY}❯{RESET} {buf}"
        status = (f"  {PINK}! for bash mode{RESET}" if bash
                  else f"  {YELLOW}⏵⏵ auto mode on{RESET} {DIM}(shift+tab to cycle){RESET}")
        for offset, text in enumerate((rule, prompt, rule, status)):
            self.out(f"\x1b[{top + offset};1H\x1b[2K{text}")
        visible = len(buf[1:]) + 2 if bash else len(buf) + 2
        self.out(f"\x1b[{top + 1};{visible + 1}H")


def main() -> int:
    s = Screen()
    s.out("\x1b[2J")
    s.render("")

    fd = sys.stdin.fileno()
    saved = termios.tcgetattr(fd)
    buf = ""
    try:
        tty.setraw(fd)
        while True:
            ch = os.read(fd, 1).decode(errors="ignore")
            if ch in ("\r", "\n"):
                break
            if ch in ("\x03", "\x04"):
                return 1
            if ch == "\x7f":
                buf = buf[:-1]
            elif ch.isprintable():
                buf += ch
            s.box(buf)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, saved)

    if not buf.startswith("!"):
        return 0
    cmd = buf[1:].strip()
    s.lines.append(f"{PINK}! {cmd}{RESET}")
    s.render("")
    proc = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    output = (proc.stdout + proc.stderr).rstrip("\n").splitlines() or ["(no output)"]
    for i, text in enumerate(output):
        s.lines.append(("  ⎿  " + text.strip()) if i == 0 else ("     " + text))
    s.lines.append("")
    s.render("")
    time.sleep(1.5)
    s.lines.append(f"{DIM}  claude-park ends the session and closes this tab{RESET}")
    s.render("")
    time.sleep(2.4)
    return 0


if __name__ == "__main__":
    sys.exit(main())
