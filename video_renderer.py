"""
Video Renderer - Generates 90s Weather Channel style images and videos
"""

import os
import subprocess
from pathlib import Path
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

# Paths
ASSETS_DIR = Path(__file__).parent / "assets"
OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

# Video specs
WIDTH = 640
HEIGHT = 480
FPS = 30
DURATION = 20

# Colors (90s Weather Channel palette)
COLORS = {
    "bg_dark": "#1a237e",       # Deep blue
    "bg_light": "#3949ab",      # Lighter blue
    "card_fill": "#5c6bc0",     # Card background
    "card_border": "#1a237e",   # Card border
    "header_orange": "#ff6f00", # Orange header bar
    "text_yellow": "#ffd54f",   # Yellow headers
    "text_white": "#ffffff",    # White text
    "text_gray": "#b0bec5",     # Gray subtext
    "bar_blue": "#283593",      # Bottom bar
}


def hex_to_rgb(hex_color: str) -> tuple:
    """Convert hex color to RGB tuple."""
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def get_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """Get a font - uses system fonts with fallback."""
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/Library/Fonts/Arial Bold.ttf",
    ]
    
    for path in font_paths:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except:
                continue
    
    # Fallback to default
    return ImageFont.load_default()


def draw_gradient_bg(draw: ImageDraw.Draw, width: int, height: int):
    """Draw blue gradient background."""
    top = hex_to_rgb(COLORS["bg_dark"])
    bottom = hex_to_rgb(COLORS["bg_light"])
    
    for y in range(height):
        ratio = y / height
        r = int(top[0] + (bottom[0] - top[0]) * ratio)
        g = int(top[1] + (bottom[1] - top[1]) * ratio)
        b = int(top[2] + (bottom[2] - top[2]) * ratio)
        draw.line([(0, y), (width, y)], fill=(r, g, b))


def draw_header(draw: ImageDraw.Draw, city: str, region: str):
    """Draw header with logo and city name."""
    # Orange header bar
    draw.rectangle([0, 0, WIDTH, 50], fill=hex_to_rgb(COLORS["header_orange"]))
    
    # "THE WEATHER CHANNEL" logo box
    draw.rectangle([10, 8, 120, 42], fill=hex_to_rgb(COLORS["bg_dark"]), 
                   outline=hex_to_rgb(COLORS["text_white"]), width=2)
    
    font_small = get_font(8)
    font_medium = get_font(12)
    
    draw.text((18, 10), "THE", fill=hex_to_rgb(COLORS["text_white"]), font=font_small)
    draw.text((18, 18), "WEATHER", fill=hex_to_rgb(COLORS["text_white"]), font=font_small)
    draw.text((18, 28), "CHANNEL", fill=hex_to_rgb(COLORS["text_white"]), font=font_small)
    
    # City name and region
    font_title = get_font(24)
    draw.text((140, 8), f"{city} {region}", fill=hex_to_rgb(COLORS["text_white"]), font=font_title)
    draw.text((140, 32), "Extended Forecast", fill=hex_to_rgb(COLORS["text_yellow"]), font=font_medium)
    
    # Time and date
    now = datetime.now()
    time_str = now.strftime("%I:%M:%S %p")
    date_str = now.strftime("%a %b %d").upper()
    
    font_time = get_font(14)
    draw.text((520, 10), time_str, fill=hex_to_rgb(COLORS["text_white"]), font=font_time)
    draw.text((520, 28), date_str, fill=hex_to_rgb(COLORS["text_white"]), font=font_time)


def draw_forecast_card(draw: ImageDraw.Draw, x: int, y: int, 
                       day_name: str, icon: str, description: str,
                       high: int, low: int, unit: str):
    """Draw a single forecast card."""
    card_width = 180
    card_height = 280
    
    # Card background with border
    draw.rectangle([x, y, x + card_width, y + card_height], 
                   fill=hex_to_rgb(COLORS["card_fill"]),
                   outline=hex_to_rgb(COLORS["card_border"]), width=3)
    
    # Day name header
    font_day = get_font(28)
    day_width = draw.textlength(day_name, font=font_day)
    draw.text((x + (card_width - day_width) // 2, y + 10), 
              day_name, fill=hex_to_rgb(COLORS["text_yellow"]), font=font_day)
    
    # Weather icon (placeholder - draw simple shapes)
    icon_y = y + 50
    draw_weather_icon(draw, x + card_width // 2, icon_y + 40, icon)
    
    # Description
    font_desc = get_font(16)
    desc_width = draw.textlength(description, font=font_desc)
    draw.text((x + (card_width - desc_width) // 2, y + 150),
              description, fill=hex_to_rgb(COLORS["text_white"]), font=font_desc)
    
    # Hi/Lo labels
    font_label = get_font(14)
    draw.text((x + 30, y + 190), "Lo", fill=hex_to_rgb(COLORS["text_gray"]), font=font_label)
    draw.text((x + 110, y + 190), "Hi", fill=hex_to_rgb(COLORS["text_gray"]), font=font_label)
    
    # Temperatures
    font_temp = get_font(36)
    draw.text((x + 20, y + 210), str(low), fill=hex_to_rgb(COLORS["text_white"]), font=font_temp)
    draw.text((x + 100, y + 210), str(high), fill=hex_to_rgb(COLORS["text_white"]), font=font_temp)


def draw_weather_icon(draw: ImageDraw.Draw, cx: int, cy: int, icon_type: str):
    """Draw a simple weather icon centered at (cx, cy)."""
    if icon_type == "sun":
        # Yellow sun
        draw.ellipse([cx-25, cy-25, cx+25, cy+25], fill="#ffd54f")
        # Sun rays
        for angle in range(0, 360, 45):
            import math
            rad = math.radians(angle)
            x1 = cx + int(30 * math.cos(rad))
            y1 = cy + int(30 * math.sin(rad))
            x2 = cx + int(40 * math.cos(rad))
            y2 = cy + int(40 * math.sin(rad))
            draw.line([x1, y1, x2, y2], fill="#ffd54f", width=3)
    
    elif icon_type == "clouds":
        # Gray clouds
        draw.ellipse([cx-35, cy-10, cx-5, cy+20], fill="#9e9e9e")
        draw.ellipse([cx-20, cy-20, cx+20, cy+15], fill="#bdbdbd")
        draw.ellipse([cx, cy-10, cx+35, cy+20], fill="#9e9e9e")
    
    elif icon_type == "rain":
        # Cloud with rain
        draw.ellipse([cx-30, cy-25, cx, cy], fill="#9e9e9e")
        draw.ellipse([cx-15, cy-30, cx+20, cy-5], fill="#bdbdbd")
        draw.ellipse([cx+5, cy-25, cx+35, cy], fill="#9e9e9e")
        # Rain drops
        for i in range(-20, 25, 15):
            draw.line([cx+i, cy+10, cx+i-5, cy+30], fill="#64b5f6", width=2)
    
    elif icon_type == "thunderstorm":
        # Cloud
        draw.ellipse([cx-30, cy-25, cx, cy], fill="#616161")
        draw.ellipse([cx-15, cy-30, cx+20, cy-5], fill="#757575")
        draw.ellipse([cx+5, cy-25, cx+35, cy], fill="#616161")
        # Lightning bolt
        points = [(cx, cy+5), (cx-8, cy+20), (cx, cy+18), (cx-5, cy+35)]
        draw.line(points[:2], fill="#ffeb3b", width=3)
        draw.line(points[1:3], fill="#ffeb3b", width=3)
        draw.line(points[2:], fill="#ffeb3b", width=3)
        # Rain
        for i in [-15, 15]:
            draw.line([cx+i, cy+10, cx+i-3, cy+25], fill="#64b5f6", width=2)
    
    elif icon_type == "snow":
        # Cloud
        draw.ellipse([cx-30, cy-25, cx, cy], fill="#bdbdbd")
        draw.ellipse([cx-15, cy-30, cx+20, cy-5], fill="#e0e0e0")
        draw.ellipse([cx+5, cy-25, cx+35, cy], fill="#bdbdbd")
        # Snowflakes
        for i in range(-20, 25, 15):
            draw.ellipse([cx+i-3, cy+15, cx+i+3, cy+21], fill="#ffffff")
            draw.ellipse([cx+i-3, cy+28, cx+i+3, cy+34], fill="#ffffff")


def draw_bottom_bar(draw: ImageDraw.Draw, text: str):
    """Draw bottom info bar."""
    draw.rectangle([0, HEIGHT-35, WIDTH, HEIGHT], fill=hex_to_rgb(COLORS["bar_blue"]))
    
    font = get_font(16)
    text_width = draw.textlength(text, font=font)
    draw.text(((WIDTH - text_width) // 2, HEIGHT - 28), 
              text, fill=hex_to_rgb(COLORS["text_white"]), font=font)


def generate_forecast_frame(forecast: dict) -> Image.Image:
    """Generate the forecast cards frame."""
    img = Image.new("RGB", (WIDTH, HEIGHT))
    draw = ImageDraw.Draw(img)
    
    # Background
    draw_gradient_bg(draw, WIDTH, HEIGHT)
    
    # Header
    draw_header(draw, forecast["city"], forecast["region"])
    
    # Three forecast cards
    card_start_x = 30
    card_y = 70
    card_spacing = 200
    
    for i, day in enumerate(forecast["forecasts"][:3]):
        draw_forecast_card(
            draw, 
            card_start_x + i * card_spacing, 
            card_y,
            day["day_name"],
            day["icon"],
            day["description"],
            day["high"],
            day["low"],
            forecast["unit_symbol"]
        )
    
    # Bottom bar
    draw_bottom_bar(draw, f"BAROMETRIC PRESSURE: 30.03 IN.")
    
    return img


def generate_map_frame(city_key: str, nearby: list, frame_num: int) -> Image.Image:
    """Generate a map animation frame."""
    img = Image.new("RGB", (WIDTH, HEIGHT))
    draw = ImageDraw.Draw(img)
    
    # Background
    draw_gradient_bg(draw, WIDTH, HEIGHT)
    
    # Simple map placeholder - draw outline
    if city_key == "austin":
        # US outline (simplified)
        draw.rectangle([50, 100, 590, 380], outline=hex_to_rgb(COLORS["text_gray"]), width=2)
        draw.text((300, 90), "UNITED STATES", fill=hex_to_rgb(COLORS["text_yellow"]), 
                  font=get_font(20))
        
        # City positions (approximate screen coords)
        positions = {
            "Austin": (280, 300),
            "Houston": (320, 320),
            "Dallas": (290, 250),
            "San Antonio": (260, 320),
            "El Paso": (150, 290),
        }
    else:
        # Europe outline (simplified)
        draw.rectangle([50, 100, 590, 380], outline=hex_to_rgb(COLORS["text_gray"]), width=2)
        draw.text((280, 90), "WESTERN EUROPE", fill=hex_to_rgb(COLORS["text_yellow"]),
                  font=get_font(20))
        
        positions = {
            "London": (200, 180),
            "Paris": (220, 240),
            "Berlin": (350, 200),
            "Amsterdam": (250, 170),
            "Brussels": (240, 210),
        }
    
    # Draw cities with weather
    font_city = get_font(12)
    font_temp = get_font(16)
    
    # Animate: highlight different cities based on frame
    highlight_idx = frame_num % (len(nearby) + 1)
    
    for i, city_data in enumerate(nearby):
        name = city_data["name"]
        if name in positions:
            x, y = positions[name]
            
            # Draw weather icon
            draw_weather_icon(draw, x, y, city_data["icon"])
            
            # City name and temp
            is_highlighted = (i == highlight_idx - 1)
            color = COLORS["text_yellow"] if is_highlighted else COLORS["text_white"]
            
            draw.text((x - 20, y + 45), name, fill=hex_to_rgb(color), font=font_city)
            draw.text((x - 10, y + 60), f"{city_data['temp']}°", 
                     fill=hex_to_rgb(color), font=font_temp)
    
    # Bottom bar
    draw_bottom_bar(draw, "REGIONAL CONDITIONS")
    
    return img


def generate_video(city_key: str, forecast: dict, nearby: list):
    """Generate the complete weather video."""
    output_name = "ATXweather.mp4" if city_key == "austin" else "LDNweather.mp4"
    output_path = OUTPUT_DIR / output_name
    temp_dir = OUTPUT_DIR / f"temp_{city_key}"
    temp_dir.mkdir(exist_ok=True)
    
    print(f"Generating {output_name}...")
    
    # Generate forecast frame (held for 10 seconds = 300 frames)
    forecast_img = generate_forecast_frame(forecast)
    forecast_path = temp_dir / "forecast.png"
    forecast_img.save(forecast_path)
    
    # Generate map frames (10 seconds = 300 frames, but we use 10 unique frames)
    map_frames = []
    for i in range(10):
        map_img = generate_map_frame(city_key, nearby, i)
        frame_path = temp_dir / f"map_{i:03d}.png"
        map_img.save(frame_path)
        map_frames.append(frame_path)
    
    # Create video with ffmpeg
    # Part 1: Forecast held for 10 seconds
    # Part 2: Map animation for 10 seconds (cycle through 10 frames)
    
    # Create concat file
    concat_file = temp_dir / "concat.txt"
    with open(concat_file, "w") as f:
        # Forecast: 10 seconds
        f.write(f"file '{forecast_path.absolute()}'\n")
        f.write("duration 10\n")
        # Map frames: 1 second each
        for frame in map_frames:
            f.write(f"file '{frame.absolute()}'\n")
            f.write("duration 1\n")
        # Last frame needs to be listed again without duration
        f.write(f"file '{map_frames[-1].absolute()}'\n")
    
    # Run ffmpeg
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_file),
        "-vf", f"fps={FPS},format=yuv420p",
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "23",
        str(output_path)
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print(f"✓ Generated {output_path}")
    except subprocess.CalledProcessError as e:
        print(f"✗ ffmpeg error: {e.stderr}")
        raise
    
    # Cleanup temp files
    import shutil
    shutil.rmtree(temp_dir)
    
    return output_path


if __name__ == "__main__":
    # Test rendering
    test_forecast = {
        "city": "Austin",
        "region": "Metro",
        "unit_symbol": "°F",
        "forecasts": [
            {"day_name": "THU", "high": 84, "low": 61, "icon": "thunderstorm", "description": "T'storms"},
            {"day_name": "FRI", "high": 80, "low": 64, "icon": "thunderstorm", "description": "T'storms"},
            {"day_name": "SAT", "high": 78, "low": 64, "icon": "thunderstorm", "description": "T'storms"},
        ]
    }
    
    img = generate_forecast_frame(test_forecast)
    img.save(OUTPUT_DIR / "test_forecast.png")
    print(f"Test image saved to {OUTPUT_DIR / 'test_forecast.png'}")

