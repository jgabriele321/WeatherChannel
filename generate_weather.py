#!/usr/bin/env python3
"""
90s Weather Channel Video Generator

Generates authentic 90s Weather Channel-style forecast videos
for Austin, TX and London, UK.

Usage:
    python generate_weather.py

Output:
    output/ATXweather.mp4 - Austin forecast video
    output/LDNweather.mp4 - London forecast video
"""

import sys
import time
from datetime import datetime
from pathlib import Path

from weather_api import fetch_forecast, fetch_nearby_weather
from video_renderer import generate_video

OUTPUT_DIR = Path(__file__).parent / "output"


def generate_all_videos():
    """Generate weather videos for all cities."""
    start_time = time.time()
    print(f"\n{'='*50}")
    print(f"90s Weather Channel Video Generator")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*50}\n")
    
    cities = ["austin", "london"]
    generated = []
    
    for city_key in cities:
        try:
            print(f"\n--- Processing {city_key.upper()} ---")
            
            # Fetch forecast data
            forecast = fetch_forecast(city_key)
            nearby = fetch_nearby_weather(city_key)
            
            # Generate video
            output_path = generate_video(city_key, forecast, nearby)
            generated.append(output_path)
            
        except Exception as e:
            print(f"✗ Failed to generate {city_key}: {e}")
            import traceback
            traceback.print_exc()
    
    elapsed = time.time() - start_time
    
    print(f"\n{'='*50}")
    print(f"Generation complete!")
    print(f"Time elapsed: {elapsed:.1f} seconds")
    print(f"Videos generated: {len(generated)}")
    for path in generated:
        print(f"  - {path}")
    print(f"{'='*50}\n")
    
    return len(generated) == len(cities)


if __name__ == "__main__":
    success = generate_all_videos()
    sys.exit(0 if success else 1)

