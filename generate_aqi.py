#!/usr/bin/env python3
"""
Air Quality / Pollen channel video generator (Austin).

Sources:
- AQI: OpenWeather Air Pollution API (free, uses existing API key)
- Pollen: Pollen.com forecast endpoint (best-effort scrape; falls back if blocked)

Output: /var/www/weather/output/AQIweather.mp4
"""
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from dotenv import load_dotenv
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).parent))
from video_renderer import (
    COLORS,
    HEIGHT,
    WIDTH,
    draw_background,
    draw_gradient_bg,
    draw_header,
    get_font,
    hex_to_rgb,
)

load_dotenv()
API_KEY = os.getenv("OPENWEATHERMAP_API_KEY")
OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

AUSTIN_LAT, AUSTIN_LON = 30.2672, -97.7431
AUSTIN_ZIP = "78701"
DURATION = 20

# OpenWeather AQI scale 1..5 -> human label + color
AQI_LABELS = {
    1: ("GOOD", (76, 175, 80)),
    2: ("FAIR", (139, 195, 74)),
    3: ("MODERATE", (255, 193, 7)),
    4: ("POOR", (255, 152, 0)),
    5: ("VERY POOR", (244, 67, 54)),
}
POLLEN_LEVELS = [
    (2.5, "LOW", (76, 175, 80)),
    (4.9, "MODERATE", (255, 193, 7)),
    (7.3, "HIGH", (255, 152, 0)),
    (9.7, "VERY HIGH", (244, 67, 54)),
    (12.0, "EXTREME", (156, 39, 176)),
]


def fetch_aqi():
    try:
        r = requests.get(
            "http://api.openweathermap.org/data/2.5/air_pollution",
            params={"lat": AUSTIN_LAT, "lon": AUSTIN_LON, "appid": API_KEY},
            timeout=10,
        )
        r.raise_for_status()
        d = r.json()["list"][0]
        idx = d["main"]["aqi"]
        comp = d["components"]
        return {
            "aqi": idx,
            "label": AQI_LABELS[idx][0],
            "color": AQI_LABELS[idx][1],
            "pm25": round(comp.get("pm2_5", 0), 1),
            "pm10": round(comp.get("pm10", 0), 1),
            "o3": round(comp.get("o3", 0), 1),
            "no2": round(comp.get("no2", 0), 1),
        }
    except Exception as e:
        print(f"  ! AQI fetch failed: {e}")
        return None


def fetch_pollen():
    """Pollen.com expects a Referer header + User-Agent. Best effort."""
    try:
        r = requests.get(
            f"https://www.pollen.com/api/forecast/current/pollen/{AUSTIN_ZIP}",
            headers={
                "User-Agent": "Mozilla/5.0",
                "Referer": f"https://www.pollen.com/forecast/current/pollen/{AUSTIN_ZIP}",
            },
            timeout=10,
        )
        r.raise_for_status()
        d = r.json()
        period = d.get("Location", {}).get("periods", [{}])[0]
        idx = float(period.get("Index", 0))
        triggers = [t.get("Name", "") for t in period.get("Triggers", [])][:3]
        # Map index to level
        for ceil, label, color in POLLEN_LEVELS:
            if idx <= ceil:
                return {"index": round(idx, 1), "label": label, "color": color, "triggers": triggers}
        return {"index": round(idx, 1), "label": "EXTREME", "color": (156, 39, 176), "triggers": triggers}
    except Exception as e:
        print(f"  ! pollen fetch failed: {e}")
        return None


def render(aqi, pollen):
    """Broadcast-style gauge panel, big layout (approved Aug 10 pm).
    Drawn at 2x and downscaled so the gauge arcs stay smooth."""
    import math as _m
    S = 2
    W2, H2 = WIDTH * S, HEIGHT * S
    from video_renderer import BG_DIR
    bg_path = BG_DIR / "aqi.png"
    if bg_path.exists():
        img = Image.open(bg_path).convert("RGB").resize((W2, H2), Image.LANCZOS)
    else:
        img = Image.new("RGB", (W2, H2))
        draw_gradient_bg(ImageDraw.Draw(img), W2, H2)
    draw = ImageDraw.Draw(img)

    ORANGE = hex_to_rgb(COLORS["header_orange"])
    NAVY = (26, 35, 126)
    WHITE = (255, 255, 255)
    YELLOW = (255, 213, 79)
    GREEN = (76, 175, 80)
    SEGS = [GREEN, (139, 195, 74), YELLOW, (255, 140, 0), (229, 57, 53)]

    now = datetime.now(ZoneInfo("America/Chicago"))
    f = get_font
    def _t(x, y, txt, fnt, fill, anchor="mm"):
        draw.text((x, y), txt, font=fnt, fill=fill, anchor=anchor)

    draw.rectangle([0, 0, W2, 46 * S], fill=ORANGE)
    _t(W2 // 2, 15 * S, "AIR QUALITY", f(24 * S), WHITE)
    _t(W2 // 2, 36 * S, "Austin, TX", f(11 * S), YELLOW)
    _t(W2 - 10 * S, 13 * S, now.strftime("%I:%M %p").lstrip("0"), f(13 * S), WHITE, "rm")
    _t(W2 - 10 * S, 32 * S, now.strftime("%a %b %d").upper(), f(13 * S), WHITE, "rm")

    def gauge(cx, cy, r, frac, num, label, sub, num_col):
        draw.rounded_rectangle([cx - r - 20 * S, cy - r - 38 * S,
                                cx + r + 20 * S, cy + r + 64 * S],
                               radius=12 * S, fill=NAVY, outline=WHITE, width=3 * S)
        n = len(SEGS)
        for i, col in enumerate(SEGS):
            draw.arc([cx - r, cy - r, cx + r, cy + r],
                     180 + i * (180 / n), 180 + (i + 1) * (180 / n),
                     fill=col, width=22 * S)
        for i in range(n + 1):
            a = _m.radians(180 + i * (180 / n))
            draw.line([cx + int((r - 14 * S) * _m.cos(a)), cy + int((r - 14 * S) * _m.sin(a)),
                       cx + int((r + 10 * S) * _m.cos(a)), cy + int((r + 10 * S) * _m.sin(a))],
                      fill=WHITE, width=3 * S)
        a = _m.radians(180 + 180 * min(1.0, max(0.0, frac)))
        draw.line([cx, cy, cx + int((r - 22 * S) * _m.cos(a)),
                   cy + int((r - 22 * S) * _m.sin(a))], fill=WHITE, width=7 * S)
        draw.ellipse([cx - 9 * S, cy - 9 * S, cx + 9 * S, cy + 9 * S], fill=WHITE)
        _t(cx, cy + 30 * S, num, f(40 * S), num_col)
        _t(cx, cy - r - 22 * S, label, f(18 * S), YELLOW)
        _t(cx, cy + 58 * S, sub, f(16 * S), WHITE)

    if aqi:
        gauge(W2 // 4 + 2 * S, 208 * S, 112 * S, (aqi["aqi"] - 0.5) / 5.0,
              str(aqi["aqi"]), "AIR QUALITY", aqi["label"], aqi["color"])
    else:
        gauge(W2 // 4 + 2 * S, 208 * S, 112 * S, 0, "?", "AIR QUALITY", "NO DATA", WHITE)
    if pollen:
        sub = pollen["label"]
        if pollen.get("triggers"):
            sub += " \u00b7 " + pollen["triggers"][0].upper()
        gauge(3 * W2 // 4 - 2 * S, 208 * S, 112 * S, pollen["index"] / 12.0,
              str(pollen["index"]), "POLLEN", sub, pollen["color"])
    else:
        gauge(3 * W2 // 4 - 2 * S, 208 * S, 112 * S, 0, "?", "POLLEN", "NO DATA", WHITE)

    bar_y = 346 * S
    draw.rounded_rectangle([16 * S, bar_y, W2 - 16 * S, bar_y + 86 * S],
                           radius=10 * S, fill=NAVY, outline=WHITE, width=3 * S)
    _t(W2 // 2, bar_y + 15 * S, "POLLUTANTS  (\u00b5g/m\u00b3)", f(14 * S), YELLOW)
    data = [("PM2.5", aqi["pm25"] if aqi else 0, 50),
            ("PM10", aqi["pm10"] if aqi else 0, 100),
            ("O3", aqi["o3"] if aqi else 0, 120),
            ("NO2", aqi["no2"] if aqi else 0, 80)]
    bw = (W2 - 90 * S) // 4
    for i, (name, val, maxv) in enumerate(data):
        x = 36 * S + i * (bw + 6 * S)
        _t(x, bar_y + 36 * S, name, f(14 * S), WHITE, "lm")
        _t(x + bw - 22 * S, bar_y + 36 * S, str(val), f(14 * S), YELLOW, "rm")
        draw.rectangle([x, bar_y + 48 * S, x + bw - 24 * S, bar_y + 64 * S],
                       outline=WHITE, width=2 * S)
        fw = int((bw - 24 * S) * min(1.0, val / maxv))
        draw.rectangle([x, bar_y + 48 * S, x + max(3 * S, fw), bar_y + 64 * S], fill=GREEN)

    draw.rectangle([0, H2 - 34 * S, W2, H2], fill=NAVY)
    _t(W2 // 2, H2 - 17 * S, "AIR QUALITY: OPENWEATHER  |  POLLEN: POLLEN.COM",
       f(12 * S), WHITE)

    return img.resize((WIDTH, HEIGHT), Image.LANCZOS)

def main():
    start = time.time()
    print("\n" + "=" * 50)
    print("Air Quality / Pollen Generator")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50 + "\n")

    print("Fetching AQI...")
    aqi = fetch_aqi()
    if aqi:
        print(f"  AQI={aqi['aqi']} ({aqi['label']}); PM2.5={aqi['pm25']}")
    print("Fetching pollen...")
    pollen = fetch_pollen()
    if pollen:
        print(f"  Pollen={pollen['index']} ({pollen['label']}); triggers={pollen.get('triggers')}")

    img = render(aqi, pollen)
    out = OUTPUT_DIR / "AQIweather.mp4"
    tmp_dir = OUTPUT_DIR / "temp_aqi"
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
