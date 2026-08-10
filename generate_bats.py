#!/usr/bin/env python3
"""
Bat Channel video generator.

Scrapes austinbatrefuge.org/congress-avenue-bridge/ for tonight's
predicted bat-emergence flight time, then renders a 90s-Weather-Channel
style animated video of bat silhouettes flying over the Congress Avenue
Bridge silhouette with the prediction text overlaid.

Output: /var/www/weather/output/BATSweather.mp4
"""

import math
import random
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from PIL import Image, ImageDraw

# Reuse style helpers from the existing weather renderer
sys.path.insert(0, str(Path(__file__).parent))
from video_renderer import (
    COLORS,
    HEIGHT,
    WIDTH,
    draw_gradient_bg,
    get_font,
    hex_to_rgb,
)

OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

FPS = 30
DURATION = 20  # seconds
TOTAL_FRAMES = FPS * DURATION

BAT_PAGE_URL = "https://austinbatrefuge.org/congress-avenue-bridge/"
TIMEOUT = 15


# ---------------------------------------------------------------------------
# Scraping
# ---------------------------------------------------------------------------

PREDICTION_RE = re.compile(
    r"Flight Time prediction.{0,500}?is between.{0,800}?"
    r"<h2[^>]*>\s*(\d{1,2}:\d{2}\s*[apAP]\.?[mM]\.?)"
    r"\s*(?:&#8211;|&#x2013;|[-–—])\s*"
    r"(\d{1,2}:\d{2}\s*[apAP]\.?[mM]\.?)\s*</h2>",
    re.IGNORECASE | re.DOTALL,
)


def fetch_prediction():
    """Return (start_str, end_str) like (7:40pm, 8:15pm), or (None, None)."""
    try:
        r = requests.get(BAT_PAGE_URL, timeout=TIMEOUT,
                         headers={"User-Agent": "RetroTV-bat-channel/1.0"})
        r.raise_for_status()
    except Exception as e:
        print(f"  ! fetch failed: {e}")
        return None, None

    m = PREDICTION_RE.search(r.text)
    if not m:
        print("  ! prediction regex did not match page content")
        return None, None

    def normalize(t):
        return re.sub(r"\s+", "", t).lower().replace(".", "")

    return normalize(m.group(1)), normalize(m.group(2))


# ---------------------------------------------------------------------------
# Visual elements
# ---------------------------------------------------------------------------

def draw_dusk_sky(draw, w, h):
    """Replace the standard blue gradient with a sunset/dusk gradient."""
    top = (32, 28, 70)        # deep indigo
    mid = (180, 70, 70)       # warm dusk red
    bottom = (250, 170, 90)   # horizon orange
    horizon_y = int(h * 0.62)
    for y in range(h):
        if y < horizon_y:
            ratio = y / horizon_y
            r = int(top[0] + (mid[0] - top[0]) * ratio)
            g = int(top[1] + (mid[1] - top[1]) * ratio)
            b = int(top[2] + (mid[2] - top[2]) * ratio)
        else:
            ratio = (y - horizon_y) / max(1, h - horizon_y)
            r = int(mid[0] + (bottom[0] - mid[0]) * ratio)
            g = int(mid[1] + (bottom[1] - mid[1]) * ratio)
            b = int(mid[2] + (bottom[2] - mid[2]) * ratio)
        draw.line([(0, y), (w, y)], fill=(r, g, b))


def draw_bridge(draw, w, h):
    """Simple silhouette of an arched bridge across the lower portion."""
    deck_y = int(h * 0.78)
    water_y = int(h * 0.88)
    # Water (darker band)
    draw.rectangle([0, water_y, w, h], fill=(15, 20, 45))
    # Bridge deck
    draw.rectangle([0, deck_y, w, water_y], fill=(20, 18, 30))
    # Six arches
    arches = 6
    span = w / arches
    for i in range(arches):
        x0 = int(i * span)
        x1 = int((i + 1) * span)
        draw.pieslice([x0, deck_y - 18, x1, water_y + 18],
                      start=180, end=360, fill=(20, 18, 30))
    # Reflection band on water
    for i in range(arches):
        x0 = int(i * span + 6)
        x1 = int((i + 1) * span - 6)
        draw.line([(x0, water_y + 4), (x1, water_y + 4)],
                  fill=(50, 40, 70))


BAT_PNG = Path(__file__).parent / "assets" / "bat.png"


def make_bat_sprite(size=20):
    """Return a bat sprite at the requested HEIGHT in px.

    Loads assets/bat.png if present; falls back to a tiny procedural shape.
    """
    if BAT_PNG.exists():
        sprite = Image.open(BAT_PNG).convert("RGBA")
        # Resize so HEIGHT == size, preserving aspect ratio
        w, h = sprite.size
        new_h = size
        new_w = max(1, int(w * (new_h / h)))
        return sprite.resize((new_w, new_h), Image.LANCZOS)
    # Fallback: tiny black silhouette
    s = size
    sprite = Image.new("RGBA", (s * 2, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(sprite)
    d.ellipse([s - 2, s // 3, s + 2, s - 2], fill=(0, 0, 0, 255))
    return sprite


BAT_FRAMES_DIR = Path(__file__).parent / "assets" / "bat_frames"
FLAP_FPS = 12  # flap-cycle playback speed


def load_bat_frames(size=30):
    """Rig-generated animated flap-cycle frames (RGBA); falls back to the
    single static sprite if assets/bat_frames/ is missing."""
    frames = []
    if BAT_FRAMES_DIR.exists():
        for p in sorted(BAT_FRAMES_DIR.glob("*.png")):
            try:
                s = Image.open(p).convert("RGBA")
                w, h = s.size
                frames.append(s.resize((max(1, int(w * size / h)), size),
                                       Image.LANCZOS))
            except Exception:
                pass
    return frames or [make_bat_sprite(size=size)]


# ---------------------------------------------------------------------------
# Composition
# ---------------------------------------------------------------------------

def build_background():
    """The static background that every frame is composited onto."""
    bg = Image.new("RGB", (WIDTH, HEIGHT))
    draw = ImageDraw.Draw(bg)
    draw_dusk_sky(draw, WIDTH, HEIGHT)
    draw_bridge(draw, WIDTH, HEIGHT)
    return bg


def draw_overlay(img, start_str, end_str):
    """Header bar + center text + bottom bar (matches weather aesthetic)."""
    draw = ImageDraw.Draw(img)

    # Header bar
    draw.rectangle([0, 0, WIDTH, 50], fill=hex_to_rgb(COLORS["header_orange"]))
    title = "BAT WATCH"
    f_title = get_font(26)
    tw = draw.textlength(title, font=f_title)
    draw.text(((WIDTH - tw) // 2, 8), title,
              fill=hex_to_rgb(COLORS["text_white"]), font=f_title)

    sub = "Congress Avenue Bridge - Austin, TX"
    f_sub = get_font(12)
    sw = draw.textlength(sub, font=f_sub)
    draw.text(((WIDTH - sw) // 2, 34), sub,
              fill=hex_to_rgb(COLORS["text_yellow"]), font=f_sub)

    # Center prediction text
    f_label = get_font(33)
    label = "Tonight's Flight"
    lw = draw.textlength(label, font=f_label)
    draw.text(((WIDTH - lw) // 2, 95), label,
              fill=hex_to_rgb(COLORS["text_yellow"]), font=f_label)

    if start_str and end_str:
        time_text = f"{start_str} - {end_str}"
    else:
        time_text = "Check austinbatrefuge.org"
    f_time = get_font(60)
    tw = draw.textlength(time_text, font=f_time)
    draw.text(((WIDTH - tw) // 2, 145), time_text,
              fill=hex_to_rgb(COLORS["text_white"]), font=f_time)

    # Date line
    local_tz = ZoneInfo("America/Chicago")
    date_str = datetime.now(local_tz).strftime("%A, %B %d").upper()
    f_date = get_font(21)
    dw = draw.textlength(date_str, font=f_date)
    draw.text(((WIDTH - dw) // 2, 225), date_str,
              fill=hex_to_rgb(COLORS["text_gray"]), font=f_date)

    # Bottom info bar (reuse weather's helper)
    draw.rectangle([0, HEIGHT - 64, WIDTH, HEIGHT],
                   fill=hex_to_rgb(COLORS["bar_blue"]))
    bottom = "EMERGENCE PREDICTION FROM AUSTIN BAT REFUGE"
    f_bot = get_font(12)
    bw = draw.textlength(bottom, font=f_bot)
    draw.text(((WIDTH - bw) // 2, HEIGHT - 64 + 14), bottom,
              fill=hex_to_rgb(COLORS["text_white"]), font=f_bot)


def render_frames(start_str, end_str, frames_dir):
    """Generate all PNG frames for the video."""
    bg = build_background()
    flap_frames = load_bat_frames(size=30)
    n_flap = len(flap_frames)

    # Bat trajectories: each bat has a starting offset, speed, vertical sine path
    rng = random.Random(42)
    bats = []
    for _ in range(18):
        bats.append({
            "x_offset": rng.uniform(-WIDTH, 0),
            "speed": rng.uniform(70, 130),       # px per second
            "y_base": rng.randint(60, int(HEIGHT * 0.7)),
            "amp": rng.uniform(8, 22),
            "freq": rng.uniform(0.6, 1.6),       # Hz
            "phase": rng.uniform(0, math.tau),
            "scale": rng.uniform(0.7, 1.3),
            "flap_offset": rng.randrange(max(1, n_flap)),
        })

    # Pre-scale every flap frame per bat so the render loop only pastes
    for bat in bats:
        bat["frames"] = [
            f.resize((max(1, int(f.width * bat["scale"])),
                      max(1, int(f.height * bat["scale"]))), Image.LANCZOS)
            for f in flap_frames
        ]

    sprite_w = max(f.width for f in flap_frames)

    for i in range(TOTAL_FRAMES):
        t = i / FPS
        frame = bg.copy()
        for bat in bats:
            x = int(bat["x_offset"] + bat["speed"] * t)
            x = x % (WIDTH + sprite_w * 2) - sprite_w
            y = int(bat["y_base"]
                    + bat["amp"] * math.sin(bat["freq"] * t * math.tau
                                            + bat["phase"]))
            scaled = bat["frames"][(int(t * FLAP_FPS) + bat["flap_offset"]) % n_flap]
            frame.paste(scaled, (x, y), scaled)
        draw_overlay(frame, start_str, end_str)
        frame.save(frames_dir / f"frame_{i:04d}.png")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    start = time.time()
    print(f"\n{'=' * 50}")
    print("Bat Channel Video Generator")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'=' * 50}\n")

    print("Fetching tonight's prediction...")
    start_str, end_str = fetch_prediction()
    if start_str and end_str:
        print(f"  Tonight: {start_str} - {end_str}")
    else:
        print("  Falling back to generic on-screen text")

    output_path = OUTPUT_DIR / "BATSweather.mp4"
    temp_dir = OUTPUT_DIR / "temp_bats"
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir(parents=True)

    print(f"Rendering {TOTAL_FRAMES} frames...")
    render_frames(start_str, end_str, temp_dir)

    print(f"Encoding to {output_path}...")
    cmd = [
        "ffmpeg", "-y",
        "-framerate", str(FPS),
        "-i", str(temp_dir / "frame_%04d.png"),
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "23",
        "-pix_fmt", "yuv420p",
        "-r", str(FPS),
        str(output_path) + ".tmp.mp4",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print("ffmpeg stderr:", result.stderr[-2000:])
        shutil.rmtree(temp_dir, ignore_errors=True)
        return 1

    shutil.rmtree(temp_dir)
    elapsed = time.time() - start
    import os as _os
    _os.replace(str(output_path) + ".tmp.mp4", output_path)  # atomic: Pi can pull any time
    size_kb = output_path.stat().st_size / 1024
    print(f"\nDone. {output_path} ({size_kb:.1f} KB) in {elapsed:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
