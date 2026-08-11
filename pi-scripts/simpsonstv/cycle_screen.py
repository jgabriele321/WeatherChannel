#!/usr/bin/python3
import sys
sys.path.append('/home/pi/simpsonstv')
from mode_manager import ModeManager

# This is a hack - we need to track state in a file
import os

STATE_FILE = '/tmp/static_screen_state'

# Read current state
if os.path.exists(STATE_FILE):
    with open(STATE_FILE, 'r') as f:
        current_screen = int(f.read().strip())
else:
    current_screen = 0

# Cycle to next screen
next_screen = (current_screen + 1) % 8

# Save new state
with open(STATE_FILE, 'w') as f:
    f.write(str(next_screen))

# Show the screen
manager = ModeManager()
manager.show_static_screen(next_screen)
