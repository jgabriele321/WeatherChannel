import struct
import os
import time
import sys

# Add the simpsonstv directory to path
sys.path.append('/home/pi/simpsonstv')

# We need to share mode state - let's check if we're in static mode
def is_static_mode():
    # Check if tvplayer service is stopped (indicates static mode)
    result = os.system('systemctl is-active --quiet tvplayer.service')
    return result != 0  # Returns 0 if active, non-zero if stopped

event_file = open('/dev/input/event0', 'rb')

print("Touch control enabled")

touch_start_time = 0
LONG_PRESS_THRESHOLD = 0.7

while True:
    data = event_file.read(16)
    if data:
        (tv_sec, tv_usec, type, code, value) = struct.unpack('IIHHi', data)
        
        if type == 3 and code == 57 and value >= 0:
            touch_start_time = time.time()
        
        if type == 3 and code == 57 and value == -1:
            if touch_start_time > 0:
                touch_duration = time.time() - touch_start_time
                # Any touch interaction disables passive mode
                if os.path.exists('/tmp/passive_active'): os.system("sudo rm -f /tmp/passive_active 2>/dev/null; sudo pkill -f passive-loop 2>/dev/null")
                
                if is_static_mode():
                    # In static mode - tap cycles screens
                    print("STATIC MODE - Cycling screen")
                    os.system('python3 /home/pi/simpsonstv/cycle_screen.py')
                else:
                    # In TV mode - normal pause/skip
                    if touch_duration >= LONG_PRESS_THRESHOLD:
                        print("LONG PRESS - Next video")
                        # Same as `channel next` from the remote: kill only foreground
                        # content (videos + commercials). Spares bgstatic so the
                        # static layer fills the omxplayer-restart gap.
                        os.system("pkill -9 -f 'simpsonstv/(videos|commercials)/'")
                        time.sleep(0.5)
                    else:
                        print("TAP - Toggle Pause")
                        os.system('sudo /usr/local/bin/dbuscontrol.sh pause >/dev/null 2>&1')
                        time.sleep(0.3)
                
                touch_start_time = 0
