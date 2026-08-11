#!/usr/bin/python3
import os
import time

class ModeManager:
    def __init__(self):
        self.current_mode = "TV"
        self.static_screen = 0
        
    def switch_to_tv_mode(self):
        print("Switching to TV mode")
        self.current_mode = "TV"
        os.system("pkill -f 'simpsonstv/(videos|no_signal|ATXweather|LDNweather|BATSweather|AQIweather|HOLIDAYchannel|NOWweather|BROADCAST_END)' > /dev/null 2>&1")
        time.sleep(0.5)
        os.system('sudo systemctl start tvplayer.service > /dev/null 2>&1')
        
    def switch_to_static_mode(self):
        print("Switching to STATIC mode")
        self.current_mode = "STATIC"
        os.system('sudo systemctl stop tvplayer.service > /dev/null 2>&1')
        time.sleep(0.5)
        os.system("pkill -f 'simpsonstv/(videos|no_signal|ATXweather|LDNweather|BATSweather|AQIweather|HOLIDAYchannel|NOWweather|BROADCAST_END)' > /dev/null 2>&1")
        time.sleep(0.5)
        self.static_screen = 0
        self.show_static_screen(0)
        
    def show_static_screen(self, screen_num):
        os.system("pkill -f 'simpsonstv/(videos|no_signal|ATXweather|LDNweather|BATSweather|AQIweather|HOLIDAYchannel|NOWweather|BROADCAST_END)' > /dev/null 2>&1")
        time.sleep(0.2)
        
        if screen_num == 0:
            # NO SIGNAL
            os.system('omxplayer --layer 10 --loop --no-osd /home/pi/simpsonstv/no_signal.mp4 > /dev/null 2>&1 &')
        elif screen_num == 1:
            # noise IS the bgstatic background layer — no foreground needed
            pass
        elif screen_num == 2:
            # Austin weather
            os.system('omxplayer --layer 10 --loop --no-osd /home/pi/simpsonstv/ATXweather.mp4 > /dev/null 2>&1 &')
        elif screen_num == 3:
            # London weather
            os.system('omxplayer --layer 10 --loop --no-osd /home/pi/simpsonstv/LDNweather.mp4 > /dev/null 2>&1 &')
        elif screen_num == 4:
            # Austin bats
            os.system('omxplayer --layer 10 --loop --no-osd /home/pi/simpsonstv/BATSweather.mp4 > /dev/null 2>&1 &')
        elif screen_num == 5:
            # Air quality / pollen
            os.system('omxplayer --layer 10 --loop --no-osd /home/pi/simpsonstv/AQIweather.mp4 > /dev/null 2>&1 &')
        elif screen_num == 6:
            # Holiday channel
            os.system('omxplayer --layer 10 --loop --no-osd /home/pi/simpsonstv/HOLIDAYchannel.mp4 > /dev/null 2>&1 &')
        elif screen_num == 7:
            # NOW Austin (live current conditions)
            os.system('omxplayer --layer 10 --loop --no-osd /home/pi/simpsonstv/NOWweather.mp4 > /dev/null 2>&1 &')
            
    def cycle_static_screen(self):
        if self.current_mode == "STATIC":
            self.static_screen = (self.static_screen + 1) % 8  # 8 screens (incl. bats, aqi, holiday, now)
            self.show_static_screen(self.static_screen)
