#!/bin/bash
# Push episodes + commercials to the Pi over its (slow, flaky) 2.4GHz wifi.
#
# Real throughput measured ~1 MB/s and the link drops every so often, so this
# is built to be interrupted: rsync resumes partial files, and the whole thing
# retries until it completes. Safe to re-run any time; also picks up newly
# transcoded episodes.
#
# Phase 1 sends a small spread across every channel so the TV is watchable
# quickly; phase 2 backfills everything else.
set -u
PI=pi@192.168.1.128
SRC=/mnt/hdd/retrotv-flat
LOG=/home/defibeats/.retro-push.log

RSH="ssh -o BatchMode=yes -o ServerAliveInterval=20 -o ServerAliveCountMax=6 -o ConnectTimeout=15"
RSYNC_OPTS="-a --partial --append-verify --bwlimit=1200 --timeout=300"

log() { echo "$(date '+%H:%M:%S') $*" >> "$LOG"; }

echo "=== push $(date) ===" >> "$LOG"

# --- phase 1: 5 episodes per channel ---
STARTER=/tmp/retro-starter.txt
: > "$STARTER"
for ch in Doug Hey Pokemon Rugrats SpongeBob; do
    ls -1 "$SRC" | grep -i "^$ch" | head -5 >> "$STARTER"
done
log "phase 1: $(wc -l < "$STARTER") starter episodes"
for attempt in $(seq 1 20); do
    if rsync $RSYNC_OPTS -e "$RSH" --files-from="$STARTER" "$SRC/" "$PI:/home/pi/simpsonstv/videos/" >> "$LOG" 2>&1; then
        log "phase 1 COMPLETE"; break
    fi
    log "phase 1 attempt $attempt dropped, retrying"
    sleep 20
done

# --- phase 2: everything ---
log "phase 2: full library"
for attempt in $(seq 1 60); do
    if rsync $RSYNC_OPTS -e "$RSH" "$SRC/" "$PI:/home/pi/simpsonstv/videos/" >> "$LOG" 2>&1; then
        log "phase 2 COMPLETE"; break
    fi
    log "phase 2 attempt $attempt dropped, retrying"
    sleep 30
done

# --- commercials ---
for attempt in $(seq 1 20); do
    if rsync $RSYNC_OPTS -e "$RSH" /mnt/hdd/media/nick-commercials/ "$PI:/home/pi/simpsonstv/commercials/" >> "$LOG" 2>&1; then
        log "commercials COMPLETE"; break
    fi
    log "commercials attempt $attempt dropped, retrying"
    sleep 30
done

echo "=== push finished $(date) ===" >> "$LOG"
