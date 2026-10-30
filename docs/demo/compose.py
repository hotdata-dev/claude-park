#!/usr/bin/env python3
"""Add a narration band above the VHS recording and write docs/demo.gif.

Needs Pillow (caption images) and ffmpeg. Caption times are seconds into the
recording and follow the Sleeps in demo.tape; adjust both together. VHS
records at 20 fps (demo.tape) so its timeline matches wall time between renders.
"""
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

REPO = Path(__file__).resolve().parents[2]
RAW = Path("/tmp/claude-park-demo/raw.mp4")
OUT = REPO / "docs" / "demo.gif"

WIDTH = 1480
BAND = 92
BG = "#11111b"      # Catppuccin Mocha crust, a shade darker than the terminal
TEXT = "#cdd6f4"
ACCENT = "#f5c2e7"
FONT = "/System/Library/Fonts/SFNS.ttf"
FPS = 20

# (start, end, text). Text between `backticks` is drawn in the accent color.
CAPTIONS = [
    (0.0, 3.0, "A long Claude Code session, half done, and something more urgent comes up."),
    (3.0, 5.8, "Type `!park`. It is a shell command, so the model never runs."),
    (5.8, 9.6, "Haiku summarizes it in the background, the worktree is locked, build dirs are freed, the tab closes."),
    (9.6, 11.0, "Weeks later, in any terminal: `parked`."),
    (11.0, 21.9, "Every parked session with its title, phase, and git state. The preview says where it stands and what is next."),
    (21.9, 26.0, "`ctrl-o` shows the full card."),
    (26.0, 99.0, "`enter` resumes the session in its worktree, with its full history."),
]


def caption_image(text: str, path: Path) -> None:
    img = Image.new("RGB", (WIDTH, BAND), BG)
    draw = ImageDraw.Draw(img)
    size = 26
    font = ImageFont.truetype(FONT, size)
    parts = text.split("`")
    while sum(draw.textlength(p, font=font) for p in parts) > WIDTH - 80 and size > 16:
        size -= 1
        font = ImageFont.truetype(FONT, size)
    x = (WIDTH - sum(draw.textlength(p, font=font) for p in parts)) / 2
    y = (BAND - size) / 2 - 2
    for i, part in enumerate(parts):
        draw.text((x, y), part, font=font, fill=ACCENT if i % 2 else TEXT)
        x += draw.textlength(part, font=font)
    img.save(path)


def main() -> int:
    if not RAW.exists():
        sys.exit(f"{RAW} not found; run docs/demo/render.sh")
    with tempfile.TemporaryDirectory() as tmp:
        inputs, chain = [], f"[0:v]pad={WIDTH}:ih+{BAND}:0:{BAND}:color={BG}[v0]"
        for i, (start, end, text) in enumerate(CAPTIONS):
            png = Path(tmp) / f"cap{i}.png"
            caption_image(text, png)
            inputs += ["-i", str(png)]
            chain += (f";[v{i}][{i + 1}:v]overlay=0:0:"
                      f"enable='between(t,{start},{end})'[v{i + 1}]")
        last = f"v{len(CAPTIONS)}"
        chain += (f";[{last}]fps={FPS},split[a][b];[a]palettegen=max_colors=128[p];"
                  f"[b][p]paletteuse=dither=none")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(RAW), *inputs,
                        "-filter_complex", chain, str(OUT)], check=True)
    print(f"wrote {OUT} ({OUT.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
