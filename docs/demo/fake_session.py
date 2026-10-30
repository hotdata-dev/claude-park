#!/usr/bin/env python3
"""A mock Claude Code session screen for the demo recording.

Draws a short fictional conversation with the input box pinned to the bottom
of the window, as in Claude Code. Typing `!` switches the box to bash mode;
on Enter the command runs for real (against the demo fixture) and its output
is shown in the conversation. No model runs.
"""
import os
import shutil
import subprocess
import sys
import termios
import textwrap
import time
import tty

DIM, BOLD, RESET = "\x1b[2m", "\x1b[1m", "\x1b[0m"
PINK = "\x1b[38;5;205m"
GREY = "\x1b[38;5;245m"
CLAUDE = "\x1b[38;5;173m"

CONVERSATION = [
    ("user", "Add CSV export for dashboard reports."),
    ("claude", "Added a streaming `GET /reports/:id/export.csv` endpoint and tests."),
    ("user", "The 2M-row report times out after 60s."),
    ("claude", "The proxy cuts responses at 60s, so large exports need a background "
               "job that writes the file to storage and emails a link. Want me to "
               "start on that?"),
]

BOX_ROWS = 4  # rule, prompt, rule, hint


class Screen:
    def __init__(self):
        size = shutil.get_terminal_size((100, 30))
        self.cols, self.rows = size.columns, size.lines
        self.row = 1  # next free transcript row

    def out(self, text: str) -> None:
        sys.stdout.write(text)
        sys.stdout.flush()

    def line(self, text: str = "", indent: str = "", first: str = "") -> None:
        """Write wrapped transcript text, staying above the input box."""
        width = self.cols - len(indent) - 1
        chunks = textwrap.wrap(text, width) or [""]
        for i, chunk in enumerate(chunks):
            if self.row > self.rows - BOX_ROWS - 1:
                return
            prefix = first if i == 0 and first else indent
            self.out(f"\x1b[{self.row};1H\x1b[2K{prefix}{chunk}")
            self.row += 1

    def styled(self, style: str, text: str, first: str = "", indent: str = "") -> None:
        width = self.cols - len(indent) - 1
        for i, chunk in enumerate(textwrap.wrap(text, width) or [""]):
            prefix = first if i == 0 and first else indent
            self.out(f"\x1b[{self.row};1H\x1b[2K{prefix}{style}{chunk}{RESET}")
            self.row += 1

    def box(self, buf: str) -> None:
        bash = buf.startswith("!")
        top = self.rows - BOX_ROWS + 1
        rule = (PINK if bash else DIM) + "─" * self.cols + RESET
        prompt = f"{PINK}!{RESET} {buf[1:]}" if bash else f"{GREY}❯{RESET} {buf}"
        hint = f"  {PINK}! for bash mode{RESET}" if bash else f"  {DIM}? for shortcuts{RESET}"
        for offset, text in enumerate((rule, prompt, rule, hint)):
            self.out(f"\x1b[{top + offset};1H\x1b[2K{text}")
        visible = len(buf[1:]) + 2 if bash else len(buf) + 2
        self.out(f"\x1b[{top + 1};{visible + 1}H")


def main() -> int:
    s = Screen()
    s.out("\x1b[2J")
    s.line(f"{CLAUDE}✻{RESET} {BOLD}Claude Code{RESET} {DIM}· ~/code/web-app (csv-export){RESET}")
    s.line()
    s.line(f"{DIM}  … 58 earlier messages{RESET}")
    s.line()
    for who, text in CONVERSATION:
        if who == "user":
            s.styled(GREY, text, first=f"{GREY}> {RESET}", indent="  ")
        else:
            s.styled("", text, first="⏺ ", indent="  ")
        s.line()
    s.box("")

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
    s.styled(PINK, cmd, first=f"{PINK}! {RESET}")
    s.box("")
    proc = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    lines = (proc.stdout + proc.stderr).rstrip("\n").splitlines() or ["(no output)"]
    for i, text in enumerate(lines):
        if i == 0:
            s.line(text.strip(), first="  ⎿  ", indent="     ")
        else:
            s.line(text, indent="     ")
    s.line()
    s.box("")
    time.sleep(1.5)
    s.line(f"{DIM}  claude-park ends the session and closes this tab{RESET}")
    s.box("")
    time.sleep(2.4)
    return 0


if __name__ == "__main__":
    sys.exit(main())
