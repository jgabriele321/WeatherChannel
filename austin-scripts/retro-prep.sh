#!/bin/bash
# Prepare retro-TV episodes for the Pi Zero W.
#
# The Zero W can ONLY hardware-decode h264 (omxplayer). Most Sonarr grabs are
# HEVC/x265, which the Pi cannot play at all. This normalizes everything to
# h264 mp4 at the panel's native 640x480.
#
#   HEVC / anything else  -> transcode to h264 (libx264 veryfast, ~10x realtime)
#   already h264          -> remux to mp4 (stream copy, seconds)
#
# Idempotent: skips anything already present in OUT. Safe to re-run as more
# episodes finish downloading.
#
# Usage: retro-prep.sh [parallel_jobs]   (default 3)

set -u
IN=/mnt/hdd/retrotv-staging
OUT=/mnt/hdd/retrotv-pi
JOBS="${1:-3}"
LOG=/home/defibeats/.retro-prep.log

mkdir -p "$OUT"

prep_one() {
    local src="$1"
    local IN=/mnt/hdd/retrotv-staging
    local OUT=/mnt/hdd/retrotv-pi
    local rel="${src#$IN/}"
    local dir; dir=$(dirname "$rel")
    local stem; stem=$(basename "$rel"); stem="${stem%.*}"
    local dst="$OUT/$dir/$stem.mp4"

    [ -s "$dst" ] && { echo "SKIP $stem"; return 0; }
    mkdir -p "$OUT/$dir"

    local codec dims w h
    codec=$(ffprobe -v error -select_streams v:0 -show_entries stream=codec_name -of csv=p=0 "$src" 2>/dev/null)
    dims=$(ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=p=0 "$src" 2>/dev/null)
    w=${dims%%,*}; h=${dims##*,}
    [ -z "$w" ] && w=9999; [ -z "$h" ] && h=9999

    # Stream-copy ONLY if it is already h264 AND already fits the 640x480
    # panel. A 1080p h264 source must still be scaled down: the Pi Zero
    # struggles to decode it and the files are ~20x larger over wifi.
    if [ "$codec" = "h264" ] && [ "$w" -le 640 ] 2>/dev/null && [ "$h" -le 480 ] 2>/dev/null; then
        # Already Pi-playable: just put it in an mp4 container.
        if ffmpeg -y -loglevel error -i "$src" -map 0:v:0 -map 0:a:0? \
              -c copy -movflags +faststart "$dst.tmp.mp4" 2>/dev/null; then
            mv "$dst.tmp.mp4" "$dst"; echo "REMUX $stem"; return 0
        fi
        rm -f "$dst.tmp.mp4"   # copy failed (odd container) -> fall through to encode
    fi

    if ffmpeg -y -loglevel error -i "$src" \
          -vf "scale='min(640,iw)':'min(480,ih)':force_original_aspect_ratio=decrease,scale=trunc(iw/2)*2:trunc(ih/2)*2" \
          -c:v libx264 -preset veryfast -crf 25 -profile:v high -level 4.0 -pix_fmt yuv420p \
          -c:a aac -b:a 128k -ac 2 -movflags +faststart "$dst.tmp.mp4" 2>/dev/null; then
        mv "$dst.tmp.mp4" "$dst"; echo "ENC   $stem ($codec)"
    else
        rm -f "$dst.tmp.mp4"; echo "FAIL  $stem ($codec)"
    fi
}
export -f prep_one

echo "=== retro-prep $(date) ===" >> "$LOG"
find "$IN" -type f \( -name "*.mkv" -o -name "*.mp4" -o -name "*.avi" \) -print0 \
  | xargs -0 -P "$JOBS" -I{} bash -c 'prep_one "$@"' _ {} >> "$LOG" 2>&1

echo "=== done $(date): $(find "$OUT" -name '*.mp4' | wc -l) files, $(du -sh "$OUT" | cut -f1) ===" >> "$LOG"
