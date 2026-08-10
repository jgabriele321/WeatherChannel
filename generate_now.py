#!/usr/bin/env python3
"""
NOW Austin — a dedicated current-conditions video.
Big temp, big icon, big stats. Updates every 15 min.

Output: /var/www/weather/output/NOWweather.mp4
"""
import shutil, subprocess, sys, time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw

sys.path.insert(0, "/var/www/weather")
from video_renderer import (
    COLORS, HEIGHT, WIDTH,
    draw_background, draw_gradient_bg, draw_weather_icon, get_font,
    hex_to_rgb,
)
from weather_api import fetch_current
from replicate_image import fetch_styled
from openai_image import fetch_edited

import math


def draw_big_icon(draw, cx, cy, icon_type, scale=3.0):
    """Big version of weather icon — scales the same shapes by `scale`."""
    from video_renderer import _icon_asset
    img = getattr(draw, "_image", None)
    asset = _icon_asset(icon_type)
    if img is not None and asset is not None:
        size = int(85 * scale)
        icon = asset.resize((size, size), Image.LANCZOS)
        img.paste(icon, (cx - size // 2, cy - size // 2), icon)
        return
    s = scale
    if icon_type == "sun":
        draw.ellipse([cx - 25*s, cy - 25*s, cx + 25*s, cy + 25*s], fill="#ffd54f")
        for angle in range(0, 360, 30):
            rad = math.radians(angle)
            x1 = cx + int(30*s * math.cos(rad)); y1 = cy + int(30*s * math.sin(rad))
            x2 = cx + int(40*s * math.cos(rad)); y2 = cy + int(40*s * math.sin(rad))
            draw.line([x1, y1, x2, y2], fill="#ffd54f", width=int(3*s))
    elif icon_type == "clouds":
        draw.ellipse([cx - 35*s, cy - 10*s, cx - 5*s, cy + 20*s], fill="#9e9e9e")
        draw.ellipse([cx - 20*s, cy - 20*s, cx + 20*s, cy + 15*s], fill="#bdbdbd")
        draw.ellipse([cx,        cy - 10*s, cx + 35*s, cy + 20*s], fill="#9e9e9e")
    elif icon_type == "rain":
        draw.ellipse([cx - 30*s, cy - 25*s, cx,        cy], fill="#9e9e9e")
        draw.ellipse([cx - 15*s, cy - 30*s, cx + 20*s, cy - 5*s], fill="#bdbdbd")
        draw.ellipse([cx + 5*s,  cy - 25*s, cx + 35*s, cy], fill="#9e9e9e")
        for i in range(int(-20*s), int(25*s), int(15*s)):
            draw.line([cx + i, cy + 10*s, cx + i - 5*s, cy + 30*s], fill="#64b5f6", width=int(2*s))
    elif icon_type == "thunderstorm":
        draw.ellipse([cx - 30*s, cy - 25*s, cx,        cy], fill="#616161")
        draw.ellipse([cx - 15*s, cy - 30*s, cx + 20*s, cy - 5*s], fill="#757575")
        draw.ellipse([cx + 5*s,  cy - 25*s, cx + 35*s, cy], fill="#616161")
        pts = [(cx, cy + 5*s), (cx - 8*s, cy + 20*s), (cx, cy + 18*s), (cx - 5*s, cy + 35*s)]
        draw.line(pts[:2], fill="#ffeb3b", width=int(3*s))
        draw.line(pts[1:3], fill="#ffeb3b", width=int(3*s))
        draw.line(pts[2:], fill="#ffeb3b", width=int(3*s))
    elif icon_type == "snow":
        draw.ellipse([cx - 30*s, cy - 25*s, cx,        cy], fill="#bdbdbd")
        draw.ellipse([cx - 15*s, cy - 30*s, cx + 20*s, cy - 5*s], fill="#e0e0e0")
        draw.ellipse([cx + 5*s,  cy - 25*s, cx + 35*s, cy], fill="#bdbdbd")
        for i in range(int(-20*s), int(25*s), int(15*s)):
            draw.ellipse([cx + i - 3*s, cy + 15*s, cx + i + 3*s, cy + 21*s], fill="#ffffff")



OUT = Path("/var/www/weather/output")
OUT.mkdir(exist_ok=True)
DURATION = 20


def render(c):
    img = Image.new("RGB", (WIDTH, HEIGHT))
    draw = ImageDraw.Draw(img)
    draw_background(img, (c or {}).get("condition"))

    # Header bar
    draw.rectangle([0, 0, WIDTH, 50], fill=hex_to_rgb(COLORS["header_orange"]))
    f_title = get_font(24)
    title = "RIGHT NOW"
    tw = draw.textlength(title, font=f_title)
    draw.text(((WIDTH - tw) // 2, 8), title,
              fill=hex_to_rgb(COLORS["text_white"]), font=f_title)
    sub = "Austin, TX"
    f_sub = get_font(12)
    sw = draw.textlength(sub, font=f_sub)
    draw.text(((WIDTH - sw) // 2, 34), sub,
              fill=hex_to_rgb(COLORS["text_yellow"]), font=f_sub)

    # Local time + date in top right
    tz = ZoneInfo("America/Chicago")
    now = datetime.now(tz)
    f_clk = get_font(14)
    draw.text((456, 10), now.strftime("%I:%M %p").lstrip("0"),
              fill=hex_to_rgb(COLORS["text_white"]), font=f_clk)
    draw.text((456, 28), now.strftime("%a %b %d").upper(),
              fill=hex_to_rgb(COLORS["text_white"]), font=f_clk)

    if not c:
        f = get_font(28)
        msg = "Data unavailable"
        mw = draw.textlength(msg, font=f)
        draw.text(((WIDTH - mw) // 2, 200), msg,
                  fill=hex_to_rgb(COLORS["text_white"]), font=f)
    else:
        # Big temperature on the left
        f_temp = get_font(160)
        temp = f"{c['temp']}°"
        # Dark blue + white border so it reads on the light sky backgrounds
        draw.text((40, 80), temp,
                  fill=(16, 38, 110), font=f_temp,
                  stroke_width=6, stroke_fill=(255, 255, 255))

        # Big icon on the right (3x scale)
        draw_big_icon(draw, 510, 170, c["icon"], scale=3.0)

        # Description below temp
        f_desc = get_font(36)
        desc = c["description"].upper()
        dw = draw.textlength(desc, font=f_desc)
        draw.text((40 + 20, 250), desc,
                  fill=hex_to_rgb(COLORS["text_yellow"]), font=f_desc)

        # Stats grid below
        f_stat_label = get_font(13)
        f_stat_val = get_font(28)
        stats = [
            ("FEELS LIKE", f"{c['feels_like']}°"),
            ("HUMIDITY", f"{c['humidity']}%"),
            ("WIND", f"{c['wind_speed']} {c['wind_unit']}"),
        ]
        chip_y = 320
        chip_w = 200
        for i, (label, val) in enumerate(stats):
            x = 30 + i * 195
            draw.rectangle([x, chip_y, x + chip_w - 5, chip_y + 70],
                           fill=hex_to_rgb(COLORS["card_fill"]),
                           outline=hex_to_rgb(COLORS["card_border"]), width=2)
            draw.text((x + 10, chip_y + 6), label,
                      fill=hex_to_rgb(COLORS["text_yellow"]), font=f_stat_label)
            vw = draw.textlength(val, font=f_stat_val)
            draw.text((x + (chip_w - vw) // 2 - 3, chip_y + 28), val,
                      fill=hex_to_rgb(COLORS["text_white"]), font=f_stat_val)

    # Bottom bar
    draw.rectangle([0, HEIGHT - 64, WIDTH, HEIGHT],
                   fill=hex_to_rgb(COLORS["bar_blue"]))
    bot = f"UPDATED {now.strftime('%I:%M %p').lstrip('0')}"
    f_bot = get_font(14)
    bw = draw.textlength(bot, font=f_bot)
    draw.text(((WIDTH - bw) // 2, HEIGHT - 50), bot,
              fill=hex_to_rgb(COLORS["text_white"]), font=f_bot)
    return img



def render_styled(c):
    """AI styling disabled — always fall back to PIL renderer.
    Re-enable by removing this short-circuit.
    """
    return None
    if not c:
        return None
    base = render(c)  # our existing PIL renderer with crisp data
    prompt = (
        "Restyle this image as a polished 1995 Weather Channel broadcast graphic. "
        "Use a navy blue gradient background with restrained orange accent bars. "
        "Keep the EXACT composition and layout. ALL text and numbers must remain "
        "identical to the input \u2014 do NOT add any new text, captions, logos, "
        "labels, icons, weather symbols, clipart, decorative elements, taglines, "
        "footers, channel bugs, scan lines, or graphic flourishes. Only apply "
        "color and typography treatment to existing elements. Clean, professional, "
        "minimal, broadcast-quality. No TV set bezel, no border around the screen."
    )
    img = fetch_edited(base, prompt, quality="medium", size="1536x1024", use_cache=True)
    if not img:
        return None
    # Fit-to-inside safe zone: 10% padding on each side, leave bottom strip for date.
    PAD_X = int(WIDTH * 0.05)   # 32 (was 64; 5% = 25% more visible area)
    PAD_Y = int(HEIGHT * 0.05)  # 24
    inner_w = WIDTH - PAD_X * 2  # 512
    inner_h = HEIGHT - PAD_Y * 2  # 384
    canvas = Image.new("RGB", (WIDTH, HEIGHT), (0, 0, 0))
    sw, sh = img.size
    scale = min(inner_w / sw, inner_h / sh)
    nw, nh = int(sw * scale), int(sh * scale)
    img = img.resize((nw, nh), Image.LANCZOS)
    ox = PAD_X + (inner_w - nw) // 2
    oy = PAD_Y + (inner_h - nh) // 2
    canvas.paste(img, (ox, oy))
    return canvas


def main():
    start = time.time()
    print("\n=== NOW Austin generator ===")
    c = fetch_current("austin")
    if c:
        print(f"  {c['temp']}° {c['description']}, feels {c['feels_like']}°, wind {c['wind_speed']} {c['wind_unit']}")
    img = render_styled(c)
    if not img:
        print("  (falling back to PIL render)")
        img = render(c)
    out = OUT / "NOWweather.mp4"
    tmp = OUT / "temp_now"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    f = tmp / "frame.png"
    img.save(f)
    cmd = [
        "ffmpeg", "-y", "-loop", "1", "-i", str(f),
        "-t", str(DURATION), "-vf", "fps=30,format=yuv420p",
        "-c:v", "libx264", "-preset", "medium", "-crf", "23", "-g", "30", "-keyint_min", "30",
        "-an", str(out) + ".tmp.mp4",
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr[-1500:])
        shutil.rmtree(tmp, ignore_errors=True)
        return 1
    import os as _os
    _os.replace(str(out) + ".tmp.mp4", out)  # atomic: Pi can pull any time
    shutil.rmtree(tmp)
    elapsed = time.time() - start
    print(f"\n  -> {out} ({out.stat().st_size//1024} KB) in {elapsed:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
