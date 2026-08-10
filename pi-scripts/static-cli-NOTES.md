# /usr/local/bin/static — reconstructed knowledge (read Aug 10 2026)

- Passive-disable hook at top: if run WITHOUT PASSIVE=1 env and /tmp/passive_active
  exists -> remove flag + pkill passive-loop.
- STATE_FILE=/tmp/static_screen_state
- Screens: 0 signal(no_signal.mp4) 1 noise(bgstatic layer only) 2 atx 3 ldn
  4 bats 5 aqi 6 holiday 7 now  (name aliases: austin, london, bat, air/pollen/
  allergy, today/day, current/live). "next" = (current+1) % 8.
- show(): pkill -9 -f 'simpsonstv/(no_signal|ATXweather|LDNweather|BATSweather|
  AQIweather|HOLIDAYchannel|NOWweather|BROADCAST_END)' ; pkill -9 -f videos/ ;
  sleep 0.3 ; write state ; then
  sudo bash -c "nohup omxplayer --layer 10 --loop --no-osd /home/pi/simpsonstv/<file> &"
  (screen 1 = no foreground player, bgstatic.service noise IS the background)
- If tvplayer.service active: systemctl stop tvplayer first.
- mode_manager.py show_static_screen mirrors the same 0-7 table with omxplayer
  --layer 10; cycle_static_screen does %8.

# Services on the Pi (systemd): tvplayer.service (player.py), bgstatic.service
# (looping static_noise.mp4 at --layer 1), tvbutton.service (buttons),
# touchskip.service. player.py drives episodes + commercials with omxplayer
# --layer 10 --aspect-mode fill and dbus volume control.
# Cron: 8:10 update_weather.sh all; */15 8-22h update_weather.sh live.
# Display: LCD 640x480 via tvservice [LCD], /dev/fb0.
# SSH: Tailscale SSH + real sshd on LAN; web remote key forced-command
# in /home/pi/.ssh/authorized_keys -> /usr/local/bin/tvremote-wrapper.
