#!/usr/bin/env python3
"""
Holiday / National Day channel generator.
Scrapes today's holidays from checkiday.com (meta heuristic), picks the
most "fun" one, applies known-holiday theming for big calendar days,
renders a video matching the weather aesthetic.

Output: /var/www/weather/output/HOLIDAYchannel.mp4
"""
import random
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")
import requests
from PIL import Image, ImageDraw

import os
from io import BytesIO

CACHE_IMG_DIR = Path(__file__).parent / "cache" / "holiday_images"
CACHE_IMG_DIR.mkdir(parents=True, exist_ok=True)

OPENAI_KEY = os.getenv("OPENAI_API_KEY")


def _overlay_title(img, name):
    """Draw the holiday name onto the illustration, retro-card style.
    PIL text can never misspell — this is why the rig generates art only."""
    from video_renderer import get_font as _get_font
    draw = ImageDraw.Draw(img)
    w, h = img.size
    title = name.upper()
    size = int(h * 0.14)
    font = _get_font(size)
    while draw.textlength(title, font=font) > w * 0.92 and size > 20:
        size -= 4
        font = _get_font(size)
    tw = draw.textlength(title, font=font)
    x, y = (w - tw) // 2, int(h * 0.035)
    sh = max(2, size // 18)  # shadow/outline scale with font size
    draw.text((x + 2 * sh, y + 2 * sh), title, font=font, fill=(40, 20, 60))
    for dx in (-sh, sh):
        for dy in (-sh, sh):
            draw.text((x + dx, y + dy), title, font=font, fill=(120, 30, 90))
    draw.text((x, y), title, font=font, fill=(255, 230, 60))
    return img


def fetch_holiday_image_rig(name):
    """Generate the card art locally on the AI rig (ComfyUI / Chroma1-HD),
    then overlay the title with PIL. Free; falls back to None if the rig
    is busy (gpu-gate: 3 tries then give up) or unreachable."""
    from rig_image import fetch_rig_image
    # Subject-first wording: any mention of "television" or "channel card"
    # makes Chroma draw a literal TV set instead of the holiday subject.
    prompt = (
        f"A vibrant flat 1990s cartoon illustration celebrating {name}. "
        f"The main subject of {name} depicted front and center, filling the "
        f"frame, on a bold retro geometric background with sunbursts and "
        f"confetti shapes. Bright saturated colors, simple bold shapes, "
        f"kitschy fun, 1990s commercial aesthetic. The image contains no "
        f"text, no letters, no words, no captions."
    )
    print("  trying rig (ComfyUI/Chroma) ...")
    img = fetch_rig_image(prompt, label="holiday-card")
    if img is None:
        return None
    return _overlay_title(img, name)


def fetch_holiday_image(name):
    """Holiday card image, cached per-day.
    Primary: free local generation on the AI rig (+ PIL title overlay).
    Fallback: gpt-image-1 with baked-in text (~$0.04/image)."""
    today = datetime.now(ZoneInfo("America/Chicago")).strftime("%Y-%m-%d")
    cache_path = CACHE_IMG_DIR / f"{today}.png"
    if cache_path.exists():
        try:
            return Image.open(cache_path).convert("RGB")
        except Exception:
            pass
    img = fetch_holiday_image_rig(name)
    if img:
        img.save(cache_path)
        return img
    print("  rig unavailable -> gpt-image-1 fallback")
    if not OPENAI_KEY:
        print("  (no OPENAI_API_KEY set)")
        return None
    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_KEY)
        prompt = (
            f"Vintage 90s television channel ID card for \"{name}\". "
            f"The holiday name appears as a bold, prominent display title "
            f"in a retro typeface. Below or beside the title, a vibrant flat "
            f"illustration related to {name}. 90s commercial aesthetic, "
            f"bright saturated colors, simple bold shapes, kitschy fun. "
            f"Composition fills the frame; suitable as a full-screen "
            f"TV channel background."
        )
        print(f"  generating gpt-image-1: {prompt[:80]}...")
        import base64
        resp = client.images.generate(
            model="gpt-image-1",
            prompt=prompt,
            size="1536x1024",
            quality="medium",
            n=1,
        )
        # gpt-image-1 returns base64
        b64 = resp.data[0].b64_json
        img_bytes = base64.b64decode(b64)
        img = Image.open(BytesIO(img_bytes)).convert("RGB")
        img.save(cache_path)
        return img
    except Exception as e:
        print(f"  ! image fetch failed: {e}")
        return None



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
DURATION = 20

# Known calendar holidays — (month, day) -> (name, theme_id)
KNOWN_HOLIDAYS = {
    (1, 1): ("New Year's Day", "newyear"),
    (2, 14): ("Valentine's Day", "valentine"),
    (3, 17): ("St. Patrick's Day", "stpatrick"),
    (7, 4): ("Independence Day", "july4"),
    (10, 31): ("Halloween", "halloween"),
    (11, 25): ("Thanksgiving", "thanksgiving"),
    (12, 24): ("Christmas Eve", "christmas"),
    (12, 25): ("Christmas Day", "christmas"),
    (12, 31): ("New Year's Eve", "newyear"),
}

# Theme palettes: (bg_top, bg_bot, accent, text)
THEMES = {
    "default": ((26, 35, 126), (57, 73, 171), (255, 213, 79), (255, 255, 255)),
    "halloween": ((20, 0, 30), (60, 20, 0), (255, 140, 0), (255, 255, 255)),
    "christmas": ((10, 50, 30), (40, 100, 50), (220, 30, 30), (255, 255, 255)),
    "july4": ((10, 20, 90), (180, 30, 30), (255, 255, 255), (255, 255, 255)),
    "valentine": ((90, 0, 30), (200, 50, 100), (255, 200, 220), (255, 255, 255)),
    "stpatrick": ((10, 50, 20), (30, 130, 50), (255, 215, 0), (255, 255, 255)),
    "newyear": ((20, 0, 50), (60, 30, 120), (255, 215, 0), (255, 255, 255)),
    "thanksgiving": ((60, 30, 0), (140, 70, 20), (255, 180, 50), (255, 255, 255)),
}

# Tone filter: skip these (somber / awareness)
SKIP_KEYWORDS = [
    "memorial", "remembrance", "awareness", "victims",
    "mourning", "grief", "abuse", "violence", "cancer",
    "suicide", "tragedy", "tragedies", "workers", "armed forces",
    "veterans", "holocaust", "ptsd",
]
# Bias toward food / fun
BOOST_KEYWORDS = [
    "national", "pie", "donut", "doughnut", "cookie", "pizza",
    "ice cream", "kiss", "hug", "love", "friend", "best friend",
    "superhero", "superheroes", "movie", "music", "joke", "fun",
    "puppy", "kitten", "cat", "dog", "blueberry", "chocolate",
    "coffee", "tea", "cake", "pancake", "cheese", "bacon",
    "comedy", "poetry", "pay it forward", "story",
]


def fetch_holidays():
    try:
        r = requests.get(
            "https://www.checkiday.com/",
            headers={"User-Agent": "Mozilla/5.0 RetroTV-channel/1.0"},
            timeout=15,
        )
        r.raise_for_status()
    except Exception as e:
        print(f"  ! checkiday fetch failed: {e}")
        return []

    # Heuristic: any node ending in "Day" within angle brackets
    names = []
    seen = set()
    for m in re.finditer(r">([A-Z][^<>]{4,80} Day)<", r.text):
        n = m.group(1).strip()
        if n.lower().startswith("also known as"):
            continue
        if "daily" in n.lower():
            continue
        if n in seen:
            continue
        seen.add(n)
        names.append(n)
    return names


def score(name):
    lc = name.lower()
    if any(k in lc for k in SKIP_KEYWORDS):
        return -1000
    s = 0
    for k in BOOST_KEYWORDS:
        if k in lc:
            s += 5
    # Shorter names tend to be punchier
    s -= len(name) * 0.1
    # Random tiebreak
    s += random.random()
    return s


def pick_holiday():
    today = datetime.now(ZoneInfo("America/Chicago"))
    key = (today.month, today.day)
    if key in KNOWN_HOLIDAYS:
        name, theme = KNOWN_HOLIDAYS[key]
        return name, theme

    candidates = fetch_holidays()
    if not candidates:
        return f"{today.strftime('%A').upper()}", "default"

    scored = [(score(n), n) for n in candidates]
    scored = [t for t in scored if t[0] > -1000]
    if not scored:
        return f"{today.strftime('%A').upper()}", "default"
    scored.sort(reverse=True)
    return scored[0][1], "default"


def themed_gradient(draw, theme):
    top, bot, _, _ = THEMES.get(theme, THEMES["default"])
    for y in range(HEIGHT):
        ratio = y / HEIGHT
        r = int(top[0] + (bot[0] - top[0]) * ratio)
        g = int(top[1] + (bot[1] - top[1]) * ratio)
        b = int(top[2] + (bot[2] - top[2]) * ratio)
        draw.line([(0, y), (WIDTH, y)], fill=(r, g, b))


def render(name, theme):
    img = Image.new("RGB", (WIDTH, HEIGHT))
    draw = ImageDraw.Draw(img)
    # Full-bleed (approved Aug 10 pm): 3% margin, art FILLS the space
    # (slight center-crop), date bar overlaid on the art instead of
    # reserving its own strip.
    PAD_X = int(WIDTH * 0.03)
    PAD_Y = int(HEIGHT * 0.03)
    inner_w = WIDTH - PAD_X * 2
    inner_h = HEIGHT - PAD_Y * 2
    img.paste((0, 0, 0), (0, 0, WIDTH, HEIGHT))  # thin black frame

    bg_img = fetch_holiday_image(name)
    if bg_img:
        sw, sh = bg_img.size
        scale = max(inner_w / sw, inner_h / sh)
        nw, nh = int(sw * scale), int(sh * scale)
        bg_img = bg_img.resize((nw, nh), Image.LANCZOS)
        cx = (nw - inner_w) // 2
        cy = (nh - inner_h) // 2
        bg_img = bg_img.crop((cx, cy, cx + inner_w, cy + inner_h))
        img.paste(bg_img, (PAD_X, PAD_Y))
    else:
        # Fallback: themed gradient inside the safe zone
        inner = Image.new("RGB", (inner_w, inner_h))
        inner_draw = ImageDraw.Draw(inner)
        top, bot, _, _ = THEMES.get(theme, THEMES["default"])
        for y in range(inner_h):
            ratio = y / inner_h
            r = int(top[0] + (bot[0] - top[0]) * ratio)
            g = int(top[1] + (bot[1] - top[1]) * ratio)
            b = int(top[2] + (bot[2] - top[2]) * ratio)
            inner_draw.line([(0, y), (inner_w, y)], fill=(r, g, b))
        img.paste(inner, (PAD_X, PAD_Y))
    draw = ImageDraw.Draw(img)  # reattach after paste
    palette = THEMES.get(theme, THEMES["default"])
    accent = palette[2]
    text_col = palette[3]

    # Date bar overlaid semi-transparent on the art (full-bleed layout).
    today = datetime.now(ZoneInfo("America/Chicago"))
    date_str = today.strftime("%A, %B %d, %Y").upper()
    bar_h = 30
    bar_top = HEIGHT - PAD_Y - bar_h
    overlay_draw = ImageDraw.Draw(img, "RGBA")
    overlay_draw.rectangle([PAD_X, bar_top, WIDTH - PAD_X, HEIGHT - PAD_Y],
                           fill=(0, 0, 0, 190))
    f_date = get_font(15)
    dw = overlay_draw.textlength(date_str, font=f_date)
    overlay_draw.text(((WIDTH - dw) // 2, bar_top + 7),
                      date_str, fill=accent, font=f_date)
    return img


def main():
    start = time.time()
    print("\n" + "=" * 50)
    print("Holiday Channel Generator")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50 + "\n")

    name, theme = pick_holiday()
    print(f"Today's holiday: {name}  (theme={theme})")

    img = render(name, theme)
    out = OUTPUT_DIR / "HOLIDAYchannel.mp4"
    tmp_dir = OUTPUT_DIR / "temp_holiday"
    if tmp_dir.exists():
        shutil.rmtree(tmp_dir)
    tmp_dir.mkdir(parents=True)
    frame = tmp_dir / "frame.png"
    img.save(frame)

    cmd = [
        "ffmpeg", "-y", "-loop", "1", "-i", str(frame),
        "-t", str(DURATION), "-vf", "fps=30,format=yuv420p",
        "-c:v", "libx264", "-preset", "medium", "-crf", "23",
        "-an", str(out) + ".tmp.mp4",
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr[-1500:])
        shutil.rmtree(tmp_dir, ignore_errors=True)
        return 1
    import os as _os
    _os.replace(str(out) + ".tmp.mp4", out)  # atomic: Pi can pull any time
    shutil.rmtree(tmp_dir)
    elapsed = time.time() - start
    size_kb = out.stat().st_size / 1024
    print(f"\nDone. {out} ({size_kb:.1f} KB) in {elapsed:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
