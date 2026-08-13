# Retro TV — full rebuild runbook

Everything needed to recreate the Simpsons-TV box from nothing.
Written 2026-08-12, the day its SD card died and was rebuilt in one evening.

**Hardware:** Raspberry Pi Zero W + Waveshare 2.8" DPI LCD (640x480) + speaker
on GPIO19 (PWM audio) + power button on GPIO26.
**Host:** `retrotv`, static **192.168.1.127**, tailnet **100.124.27.37**.

---

## 0. What lives where

| Thing | Location |
|---|---|
| Code (this repo) | `pi-scripts/` — all Pi-side logic |
| Secrets (NOT in git) | Austin RAID: `/mnt/cold/backups/retrotv-rescue/` |
| Weather video generators | this repo root (`generate_*.py`, `video_renderer.py`) |
| Episode prep scripts | Austin `~/bin/retro-prep.sh`, `flatten.py`, `retro-push.sh` |
| Web remote app | Austin `~/tvremote/` |

## 1. Flash the card

Raspberry Pi OS **Lite, Buster (2021-05-07)**. Buster specifically — the whole
thing depends on `omxplayer`, which does not exist after Buster.

```
sudo dd if=2021-05-07-raspios-buster-armhf-lite.img of=/dev/rdiskN bs=4m
```

Use a **128GB endurance-class** card (SanDisk Max Endurance / Samsung PRO
Endurance). The stock card that died had been looping video 15h/day for months.

## 2. Pre-stage the boot partition (before first boot)

```
touch /Volumes/boot/ssh                                    # enable sshd
cp SECRETS/wpa_supplicant.conf /Volumes/boot/               # wifi
cp boot/config.txt              /Volumes/boot/              # LCD timings
cp boot/waveshare-28dpi-*.dtbo  /Volumes/boot/overlays/     # NOT in stock OS
cp firstrun.sh                  /Volumes/boot/              # see below
cp SECRETS/authorized_keys      /Volumes/boot/retrotv-authorized_keys
```

`cmdline.txt`: keep the **new card's PARTUUID**, but use the original console
flags so Linux boot text never appears on the TV:

```
console=serial0,115200 console=tty3 root=PARTUUID=<NEW> rootfstype=ext4 \
 elevator=deadline fsck.repair=yes rootwait consoleblank=0 logo.nologo quiet splash \
 init=/usr/lib/raspi-config/init_resize.sh \
 systemd.run=/boot/firstrun.sh systemd.run_success_action=reboot systemd.unit=kernel-command-line.target
```

`firstrun.sh` sets the hostname to `retrotv`, installs `authorized_keys`, then
deletes itself and strips the `systemd.run` flags. Three boots follow: resize,
firstrun, normal. ~10 min on a Zero W.

## 3. Packages

Buster is EOL, so the default apt repo 404s. Point at the archive first:

```
sudo sed -i 's|http://raspbian.raspberrypi.org/raspbian/|http://legacy.raspbian.org/raspbian/|' /etc/apt/sources.list
sudo apt-get update && sudo apt-get install -y omxplayer
```

## 4. Restore the system

```
cp simpsonstv/*            /home/pi/simpsonstv/     ; chmod +x /home/pi/simpsonstv/*.{py,sh}
sudo cp usr-local-bin/*    /usr/local/bin/          ; sudo chmod +x /usr/local/bin/*
sudo cp systemd/*.service  /etc/systemd/system/
sudo cp etc/rc.local etc/dhcpcd.conf /etc/          ; sudo chmod +x /etc/rc.local
crontab cron/pi-crontab
sudo systemctl daemon-reload
sudo systemctl enable tvplayer bgstatic tvbutton touchskip
mkdir -p /home/pi/simpsonstv/{videos,commercials}
```

Tailscale (identity, so it returns as the same node — no re-auth):

```
curl -LO https://pkgs.tailscale.com/stable/tailscale_<ver>_arm.tgz   # 'arm' = ARMv6, works on Zero W
sudo cp tailscale_*/tailscaled /usr/sbin/ ; sudo cp tailscale_*/tailscale /usr/bin/
sudo cp etc/tailscaled /etc/default/tailscaled
sudo mkdir -p /var/lib/tailscale
sudo cp SECRETS/tailscaled.state /var/lib/tailscale/ ; sudo chmod 600 /var/lib/tailscale/tailscaled.state
sudo systemctl enable --now tailscaled
```

## 5. THE THREE TRAPS

These cost hours. Read before debugging anything.

### Black screen / no backlight
The panel backlight is **GPIO18, active-high**, and it latches on a
**LOW→HIGH EDGE after power-up** — holding the pin high does nothing.
`gpio=18=op,dh` in config.txt actively *breaks* it (firmware raises the pin
before the panel powers up, so no edge ever happens). The fix is in `rc.local`:

```
raspi-gpio set 18 op dl ; sleep 1 ; raspi-gpio set 18 op dh
```

Diagnostic ladder: firmware rainbow splash visible = panel/ribbon/backlight are
fine, blame software. A black screen with `console=tty3` is *normal* and
intentional. `raspi-gpio get 0,2,5` showing `alt=2` DPI functions means the Pi
is driving the signal.

### Mute silences the wrong thing
Two omxplayers run at once (background static on layer 1, show on layer 10) and
they fight over the dbus name `org.mpris.MediaPlayer2.omxplayer`. Whoever
registers first wins — that's the background player, so `mute` silences static
noise while the cartoon plays on. Fix: `bgstatic.service` passes
`--dbus_name org.mpris.MediaPlayer2.bgstatic`, leaving the default name for the show.

### The web remote breaks if the IP moves
Austin's `~/tvremote/app.py` SSHes to a hardcoded `pi@192.168.1.127` with
`StrictHostKeyChecking=yes` and a forced command. After any rebuild:
- the Pi must be on **192.168.1.127** (now pinned statically in `dhcpcd.conf`)
- Austin needs the new host key:
  `ssh-keygen -R 192.168.1.127 && ssh-keyscan -H 192.168.1.127 >> ~/.ssh/known_hosts`

## 6. Episodes

`player.py` does a **flat** `os.listdir(videos/)` and picks a channel with
`filename.lower().startswith(channel)`. So: no subdirectories, and each file
must START with `doug` / `hey` / `pokemon` / `rugrats` / `spongebob`. Sonarr
names break this silently (accented "Pokémon", `[OtakuMura] Pokemon`, a
"SpongBob" typo, season folders).

Pipeline on Austin:
1. `~/bin/retro-prep.sh` — normalize to h264 **640x480** mp4.
   Stream-copy ONLY if already h264 *and* already ≤640x480; a 1080p h264 file
   must still be scaled (else 1.35GB files the Zero W can barely decode).
2. `~/bin/flatten.py` — hardlink into `/mnt/hdd/retrotv-flat/`, strip accents,
   force the channel prefix from the Sonarr series folder.
3. `~/bin/retro-push.sh` — rsync to the Pi. Slow (~1MB/s) and drops; the script
   retries and resumes. Disable wifi power save or it is 40% slower still
   (already in `rc.local`).

Commercials: `/mnt/hdd/media/nick-commercials` → `~/simpsonstv/commercials/`.

## 7. Daily rhythm (crontab)

```
10 8  * * *  update_weather.sh        # pull all 7 channel videos
20 8  * * *  passive on               # start 8.5-min screen rotation
*/15 8-22 *  update_weather.sh live   # refresh Austin + RIGHT NOW
0  23 * * *  broadcast off            # sign-off test card overnight
```

## 8. Verify

```
static atx ; static today ; static now      # each channel paints
mode tv ; channel all ; mute                # shuffle + mute (check volume=0 via dbus)
passive on                                  # rotation
ssh -i ~/.ssh/tvremote_ed25519 pi@192.168.1.127 status   # from Austin = web remote path
```
