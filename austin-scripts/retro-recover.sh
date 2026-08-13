#!/bin/bash
# Recover from the double-instance transcode incident, then resume cleanly.
#   1. wait for orphaned ffmpeg workers to drain
#   2. clear leftover temp files
#   3. validate every produced mp4, delete anything corrupt (two instances
#      may have raced on the same temp path)
#   4. relaunch a single retro-prep instance
set -u
OUT=/mnt/hdd/retrotv-pi
LOG=/home/defibeats/.retro-recover.log

echo "=== recover $(date) ===" > "$LOG"

# 1. drain
for i in $(seq 1 60); do
    n=$(pgrep -f '[r]etrotv-staging' | wc -l)
    [ "$n" -eq 0 ] && break
    echo "waiting on $n workers..." >> "$LOG"
    sleep 10
done

# 2. temps
find "$OUT" -name '*.tmp.mp4' -delete 2>/dev/null
echo "temps cleared" >> "$LOG"

# 3. validate — a good file has a readable duration > 60s
bad=0; ok=0
while IFS= read -r f; do
    d=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$f" 2>/dev/null | cut -d. -f1)
    if [ -z "$d" ] || [ "$d" -lt 60 ] 2>/dev/null; then
        echo "CORRUPT $(basename "$f")" >> "$LOG"; rm -f "$f"; bad=$((bad+1))
    else
        ok=$((ok+1))
    fi
done < <(find "$OUT" -name '*.mp4')
echo "validated: $ok good, $bad removed" >> "$LOG"

# 4. resume, single instance
if ! pgrep -f '[r]etro-prep.sh' >/dev/null; then
    setsid nohup /home/defibeats/bin/retro-prep.sh 3 >/dev/null 2>&1 < /dev/null &
    echo "relaunched single instance" >> "$LOG"
fi
echo "=== recover done $(date) ===" >> "$LOG"
