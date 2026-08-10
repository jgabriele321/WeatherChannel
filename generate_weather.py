#!/usr/bin/env python3
"""
90s Weather Channel Video Generator

Usage:
    python generate_weather.py            # all cities
    python generate_weather.py austin     # only austin (with NOW strip)
    python generate_weather.py london     # only london
"""
import sys
import time
from datetime import datetime
from pathlib import Path

from weather_api import fetch_current, fetch_forecast
from replicate_image import fetch_styled
from openai_image import fetch_edited
from video_renderer import generate_video, generate_forecast_frame

OUTPUT_DIR = Path(__file__).parent / "output"



def _render_styled_3day(forecast):
    """AI styling disabled — always fall back to PIL renderer."""
    return None
    from PIL import Image as _Image
    if not forecast or not forecast.get("forecasts"):
        return None
    base = generate_forecast_frame(forecast)  # crisp PIL with accurate cards
    prompt = (
        "Restyle this 3-day forecast image as a polished 1995 Weather Channel "
        "broadcast graphic. Use a navy blue gradient background with restrained "
        "orange accent bars. Keep the EXACT composition and layout. ALL text, "
        "day names, and numbers must remain identical to the input \u2014 do NOT "
        "add any new text, captions, logos, labels, icons, weather symbols, "
        "clipart, decorative elements, taglines, footers, channel bugs, scan "
        "lines, or graphic flourishes. Only apply color and typography treatment "
        "to existing elements. Clean, professional, minimal, broadcast-quality. "
        "No TV set bezel, no border around the screen."
    )
    img = fetch_edited(base, prompt, quality="medium", size="1536x1024", use_cache=True)
    if not img:
        return None

    # Fit-to-inside 10% safe zone (matches generate_now.py / holiday channel)
    WIDTH, HEIGHT = 640, 480
    PAD_X = int(WIDTH * 0.05)
    PAD_Y = int(HEIGHT * 0.05)
    inner_w = WIDTH - PAD_X * 2
    inner_h = HEIGHT - PAD_Y * 2
    canvas = _Image.new("RGB", (WIDTH, HEIGHT), (0, 0, 0))
    sw, sh = img.size
    scale = min(inner_w / sw, inner_h / sh)
    nw, nh = int(sw * scale), int(sh * scale)
    img = img.resize((nw, nh), _Image.LANCZOS)
    ox = PAD_X + (inner_w - nw) // 2
    oy = PAD_Y + (inner_h - nh) // 2
    canvas.paste(img, (ox, oy))
    return canvas


def _styled_to_mp4(canvas, output_path, duration=20, fps=30):
    """Encode a single PIL frame to a 20s looped MP4 (matches PIL pipeline)."""
    import shutil, subprocess, tempfile
    from pathlib import Path as _Path
    tmp_dir = _Path(tempfile.mkdtemp(prefix="styled_mp4_"))
    frame = tmp_dir / "frame.png"
    canvas.save(frame)
    cmd = [
        "ffmpeg", "-y", "-loop", "1", "-i", str(frame),
        "-t", str(duration), "-vf", f"fps={fps},format=yuv420p",
        "-c:v", "libx264", "-preset", "medium", "-crf", "23", "-g", "30", "-keyint_min", "30",
        "-an", str(output_path),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    shutil.rmtree(tmp_dir, ignore_errors=True)
    return r.returncode == 0


def generate_for(city_key):
    print(f"\n--- Processing {city_key.upper()} ---")
    forecast = fetch_forecast(city_key)
    current = None  # NOW now lives on its own dedicated screen

    # Austin: try AI-stylized 3-day; fall back to PIL renderer on any failure.
    if city_key == "austin":
        styled = _render_styled_3day(forecast)
        if styled:
            from pathlib import Path as _Path
            out = _Path(__file__).parent / "output" / "ATXweather.mp4"
            if _styled_to_mp4(styled, out):
                print(f"  styled ATXweather.mp4 ({out.stat().st_size//1024} KB)")
                return out
            print("  (encode failed, falling back to PIL)")
        else:
            print("  (no styled image, falling back to PIL)")

    return generate_video(city_key, forecast, current=current)


def main():
    args = sys.argv[1:]
    cities = args if args else ["austin", "london"]
    valid = {"austin", "london"}
    cities = [c for c in cities if c in valid]
    if not cities:
        print(f"no valid cities; choose from {sorted(valid)}")
        return 1

    start = time.time()
    print(f"\n{'=' * 50}")
    print("90s Weather Channel Video Generator")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Cities: {', '.join(cities)}")
    print(f"{'=' * 50}\n")

    generated = []
    for c in cities:
        try:
            generated.append(generate_for(c))
        except Exception as e:
            print(f"X Failed to generate {c}: {e}")
            import traceback
            traceback.print_exc()

    elapsed = time.time() - start
    print(f"\nDone. {len(generated)} videos in {elapsed:.1f}s")
    for path in generated:
        print(f"  - {path}")
    return 0 if len(generated) == len(cities) else 1


if __name__ == "__main__":
    sys.exit(main())
