#!/usr/bin/env python3
"""A mock Claude Code session screen for the demo recording.

Draws a short fictional conversation and an input box. Typing `!` switches
the box to bash mode, as in Claude Code; on Enter the command runs for real
(against the demo fixture) and its output is shown inline. No model runs.
"""
import os
import shutil
import subprocess
import sys
import termios
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


def width() -> int:
    return shutil.get_terminal_size((100, 30)).columns


def out(text: str) -> None:
    sys.stdout.write(text)
    sys.stdout.flush()


def draw_conversation() -> None:
    out(f"{CLAUDE}✻{RESET} {BOLD}Claude Code{RESET} {DIM}· ~/code/web-app (csv-export){RESET}\n\n")
    out(f"{DIM}  … 58 earlier messages{RESET}\n\n")
    for who, text in CONVERSATION:
        if who == "user":
            out(f"{GREY}> {text}{RESET}\n\n")
        else:
            out(f"⏺ {text}\n\n")


def draw_box(buf: str) -> None:
    """Draw the input box at the cursor and leave the cursor after the input."""
    bash = buf.startswith("!")
    rule = (PINK if bash else DIM) + "─" * width() + RESET
    prompt = f"{PINK}! {RESET}{buf[1:]}" if bash else f"{GREY}❯{RESET} {buf}"
    hint = f"{PINK}! for bash mode{RESET}" if bash else f"{DIM}? for shortcuts{RESET}"
    # \r\n, not \n: this also runs while the terminal is in raw mode.
    out("\x1b[J" + rule + "\r\n" + prompt + "\r\n" + rule + "\r\n  " + hint)
    # Back up to the end of the prompt line.
    out(f"\x1b[2A\x1b[{len(prompt_text(buf)) + 1}G")


def prompt_text(buf: str) -> str:
    return ("! " + buf[1:]) if buf.startswith("!") else ("❯ " + buf)


def redraw(buf: str) -> None:
    out("\x1b[1A\r")  # to the top rule
    draw_box(buf)


def run_bash(cmd: str) -> None:
    out("\x1b[1A\r\x1b[J")
    out(f"{PINK}! {cmd}{RESET}\n")
    proc = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    lines = (proc.stdout + proc.stderr).rstrip("\n").splitlines() or ["(no output)"]
    for i, line in enumerate(lines):
        out(("  ⎿  " if i == 0 else "     ") + line + "\n")
    out("\n")


def main() -> int:
    out("\x1b[2J\x1b[H")
    draw_conversation()
    out("\n")
    draw_box("")
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
            redraw(buf)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, saved)
    if buf.startswith("!"):
        run_bash(buf[1:].strip())
        time.sleep(1.2)
        out(f"{DIM}  (claude-park ends the session and closes this tab){RESET}\n")
        time.sleep(1.5)
    return 0


if __name__ == "__main__":
    sys.exit(main())
