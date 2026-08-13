#!/bin/bash

# Weather video updater for Raspberry Pi
# Downloads latest weather videos from server

LOG_FILE="/home/pi/simpsonstv/weather_update.log"
VIDEO_DIR="/home/pi/simpsonstv"

echo "$(date): Starting weather update" >> "$LOG_FILE"

# Function to download and replace video
download_video() {
    local url=$1
    local filename=$2
    local temp_file="${VIDEO_DIR}/${filename}.tmp"
    local final_file="${VIDEO_DIR}/${filename}"
    local max_attempts=3
    local attempt=1

    while [ $attempt -le $max_attempts ]; do
        if curl -f -s -o "$temp_file" "$url" --max-time 30; then
            if [ -s "$temp_file" ] && [ $(stat -f%z "$temp_file" 2>/dev/null || stat -c%s "$temp_file") -gt 20000 ]; then
                mv "$temp_file" "$final_file"
                echo "$(date): Successfully updated $filename (attempt $attempt)" >> "$LOG_FILE"
                return 0
            else
                echo "$(date): Attempt $attempt: downloaded $filename too small ($(stat -c%s "$temp_file" 2>/dev/null) bytes), retrying" >> "$LOG_FILE"
                rm -f "$temp_file"
            fi
        else
            echo "$(date): Attempt $attempt: curl failed for $filename" >> "$LOG_FILE"
            rm -f "$temp_file"
        fi
        attempt=$((attempt + 1))
        # Exponential backoff: 5s, 15s
        [ $attempt -le $max_attempts ] && sleep $((5 * (attempt - 1) * (attempt - 1)))
    done

    echo "$(date): GAVE UP on $filename after $max_attempts attempts; keeping old file" >> "$LOG_FILE"
    return 1
}

# Optional city filter -- pass "atx" / "ldn" / "bats" to download only that one.
# No arg = all of them.
TARGET="${1:-all}"

# "live" alias = atx + now (Pi 15-min cron uses this)
if [ "$TARGET" = "all" ] || [ "$TARGET" = "atx" ] || [ "$TARGET" = "live" ]; then
    download_video "https://weather.dwings.app/ATXweather.mp4" "ATXweather.mp4"
fi
if [ "$TARGET" = "all" ] || [ "$TARGET" = "bats" ]; then
    download_video "https://weather.dwings.app/BATSweather.mp4" "BATSweather.mp4"
fi
if [ "$TARGET" = "all" ] || [ "$TARGET" = "ldn" ]; then
    download_video "https://weather.dwings.app/LDNweather.mp4" "LDNweather.mp4"
fi
if [ "$TARGET" = "all" ] || [ "$TARGET" = "aqi" ]; then
    download_video "https://weather.dwings.app/AQIweather.mp4" "AQIweather.mp4"
fi
if [ "$TARGET" = "all" ] || [ "$TARGET" = "holiday" ]; then
    download_video "https://weather.dwings.app/HOLIDAYchannel.mp4" "HOLIDAYchannel.mp4"
fi
if [ "$TARGET" = "all" ] || [ "$TARGET" = "now" ] || [ "$TARGET" = "live" ]; then
    download_video "https://weather.dwings.app/NOWweather.mp4" "NOWweather.mp4"
fi
if [ "$TARGET" = "all" ] || [ "$TARGET" = "endcard" ]; then
    download_video "https://weather.dwings.app/BROADCAST_END.mp4" "BROADCAST_END.mp4"
fi

# If we're in STATIC mode, restart the current screen so it picks up the
# fresh video file (omxplayer holds the old inode otherwise).
# BUT skip if the user/system is in a "do not disturb" state:
#   - broadcast off (overnight)  -> respect the BROADCAST_END screen
#   - passive mode active        -> the passive-loop owns the screen
if ! systemctl is-active --quiet tvplayer.service \
   && [ -x /usr/local/bin/static ] \
   && [ ! -f /tmp/broadcast_off ] \
   && [ ! -f /tmp/passive_active ]; then
    cur=$(cat /tmp/static_screen_state 2>/dev/null || echo 0)
    case "$cur" in
        2) /usr/local/bin/static atx >> "$LOG_FILE" 2>&1 ;;
        3) /usr/local/bin/static ldn >> "$LOG_FILE" 2>&1 ;;
        4) /usr/local/bin/static bats >> "$LOG_FILE" 2>&1 ;;
        5) /usr/local/bin/static aqi >> "$LOG_FILE" 2>&1 ;;
        6) /usr/local/bin/static holiday >> "$LOG_FILE" 2>&1 ;;
        7) /usr/local/bin/static now >> "$LOG_FILE" 2>&1 ;;
    esac
fi

echo "$(date): Weather update complete" >> "$LOG_FILE"

