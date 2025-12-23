# 📺 WeatherChannel - 90s Weather Video Generator

Generates authentic 90s Weather Channel-style forecast videos for Austin, TX and London, UK.

## Features

- **Retro 90s aesthetic**: Blue gradients, chunky fonts, thick borders
- **Two 20-second videos**: ATXweather.mp4 and LDNweather.mp4
- **3-day forecast cards** (0-10 seconds)
- **Animated weather map** (10-20 seconds)
- **Daily cron updates** at 6am

## Setup

```bash
# Clone the repo
git clone https://github.com/jgabriele321/WeatherChannel.git
cd WeatherChannel

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy and configure environment
cp .env.example .env
# Edit .env with your OpenWeatherMap API key

# Run
python generate_weather.py
```

## Output

- `output/ATXweather.mp4` - Austin, TX forecast (°F)
- `output/LDNweather.mp4` - London, UK forecast (°C)

## Video Specs

- Resolution: 640x480 (4:3)
- Duration: 20 seconds
- Format: H.264, 30fps
- Color space: yuv420p

## Cron Setup

Add to crontab for daily updates at 6am:

```bash
0 6 * * * cd /var/www/weather && /var/www/weather/venv/bin/python generate_weather.py
```

## License

MIT

