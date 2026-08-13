import RPi.GPIO as GPIO
import time
import os
import sys

# Add the simpsonstv directory to path
sys.path.append('/home/pi/simpsonstv')
from mode_manager import ModeManager

os.system('raspi-gpio set 19 ip')
GPIO.setmode(GPIO.BCM)
GPIO.setup(26, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(18, GPIO.OUT)

mode_manager = ModeManager()

def turnOnScreen():
    os.system('raspi-gpio set 19 op a5')
    GPIO.output(18, GPIO.HIGH)

def turnOffScreen():
    os.system('raspi-gpio set 19 ip')
    GPIO.output(18, GPIO.LOW)

# Start with screen on; mode follows the physical power button position
turnOnScreen()
button_state = bool(GPIO.input(26))  # True = button ON = TV, False = OFF = STATIC
if button_state:
    mode_manager.switch_to_tv_mode()
else:
    mode_manager.switch_to_static_mode()


while True:
    input = GPIO.input(26)
    
    # Button pressed (state changed)
    if input != button_state:
        button_state = input
        # Any button toggle disables passive mode
        if os.path.exists('/tmp/passive_active'): os.system("sudo rm -f /tmp/passive_active 2>/dev/null; sudo pkill -f passive-loop 2>/dev/null")
        
        if button_state:
            # Button to ON position = TV mode
            mode_manager.switch_to_tv_mode()
        else:
            # Button to OFF position = Static mode
            mode_manager.switch_to_static_mode()
            
    time.sleep(0.3)
