#!/usr/bin/env python3
"""Flatten transcoded episodes into the layout player.py expects.

player.py does a FLAT os.listdir(videos/) and picks a channel with
    f.lower().startswith(channel.lower())
so there can be no subdirectories and each filename must START with the
channel name. Release names can't be trusted for that ("[OtakuMura] Pokemon",
"SpongBob.SquarePants" typo, accented "Pokémon"), so the channel is derived
from the Sonarr series folder and forced onto the front of the name.

Hardlinks — no extra disk on the same filesystem. Idempotent.
"""
import os
import shutil
import unicodedata

SRC = "/mnt/hdd/retrotv-pi"
DST = "/mnt/hdd/retrotv-flat"
CHANNELS = ("doug", "hey", "pokemon", "rugrats", "spongebob")

# Sonarr series folder -> channel name the CLI/player uses
SERIES_MAP = {
    "doug": "Doug",
    "hey arnold": "Hey Arnold",
    "rugrats": "Rugrats",
    "spongebob": "SpongeBob",
    "pokemon": "Pokemon",
    "pokémon": "Pokemon",
}


def channel_for(path):
    rel = os.path.relpath(path, SRC)
    top = rel.split(os.sep)[0].lower()
    for key, name in SERIES_MAP.items():
        if top.startswith(key):
            return name
    return None


def ascii_clean(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return s.replace("'", "").strip()


if os.path.isdir(DST):
    shutil.rmtree(DST)          # rebuild clean; hardlinks are free
os.makedirs(DST, exist_ok=True)

linked = skipped = 0
for root, _, files in os.walk(SRC):
    for f in files:
        if not f.lower().endswith(".mp4") or ".tmp.mp4" in f.lower():
            skipped += 1        # in-progress transcode
            continue
        ch = channel_for(os.path.join(root, f))
        if ch is None:
            skipped += 1
            continue
        clean = ascii_clean(f)
        if not clean.lower().startswith(ch.lower()):
            clean = f"{ch} - {clean}"
        dst = os.path.join(DST, clean)
        if os.path.exists(dst):
            continue
        try:
            os.link(os.path.join(root, f), dst)
            linked += 1
        except OSError:
            pass

names = os.listdir(DST)
print(f"linked: {linked}   skipped(in-progress/unknown): {skipped}")
for ch in CHANNELS:
    print(f"  {ch}: {sum(1 for n in names if n.lower().startswith(ch))}")
odd = [n for n in names if not n.lower().startswith(CHANNELS)]
print("unmatched:", len(odd))
for n in odd[:5]:
    print("   ", n)
