import os
import random
import time
from subprocess import Popen

BASE = os.path.dirname(os.path.realpath(__file__))
VIDEO_DIR = os.path.join(BASE, "videos")
COMM_DIR = os.path.join(BASE, "commercials")
CHANNEL_FILE = "/tmp/current_channel"
INTERVAL_FILE = os.path.join(BASE, "commercial_interval")


def get_channel():
    try:
        with open(CHANNEL_FILE) as f:
            ch = f.read().strip()
            return ch if ch else "ALL"
    except (IOError, OSError):
        return "ALL"


def get_videos(channel):
    files = [f for f in os.listdir(VIDEO_DIR) if f.lower().endswith(".mp4")]
    if channel.upper() != "ALL":
        files = [f for f in files if f.lower().startswith(channel.lower())]
    return [os.path.join(VIDEO_DIR, f) for f in files]


def get_commercial_interval():
    """Read commercial interval. 0 = off. Default 1 (one ad per episode)."""
    try:
        with open(INTERVAL_FILE) as f:
            return int(f.read().strip())
    except Exception:
        return 1


def get_commercials():
    if not os.path.isdir(COMM_DIR):
        return []
    return [os.path.join(COMM_DIR, f) for f in os.listdir(COMM_DIR)
            if f.lower().endswith(".mp4")]


def play(path):
    """Play one file foreground; arm mute-apply; block until exit."""
    proc = Popen(["omxplayer", "--layer", "10", "--no-osd",
                  "--aspect-mode", "fill", path])
    Popen(["bash", "-c",
           "for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do "
           "sleep 0.4; "
           "if [ -e /tmp/omxplayerdbus.root ] && /usr/local/bin/mute apply 2>/dev/null; then "
           "exit 0; fi; done"])
    proc.wait()


episode_count = 0

while True:
    channel = get_channel()
    videos = get_videos(channel)
    if not videos:
        time.sleep(5)
        continue
    random.shuffle(videos)
    for video in videos:
        if get_channel() != channel:
            break
        play(video)
        episode_count += 1

        # After every Nth episode, drop a commercial (if interval>0 and we have any)
        interval = get_commercial_interval()
        if interval > 0 and episode_count % interval == 0:
            comms = get_commercials()
            if comms and get_channel() == channel:
                play(random.choice(comms))
