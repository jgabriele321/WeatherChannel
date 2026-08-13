#!/bin/bash
# retrotv first-boot restore, stage 1: identity + key access.
# Runs once via systemd.run from cmdline.txt, then removes itself.
# Deliberately minimal and defensive — anything that fails must NOT
# leave the Pi in a reboot loop.

set +e

# --- hostname back to retrotv ---
CURRENT=$(cat /etc/hostname 2>/dev/null | tr -d '[:space:]')
echo "retrotv" > /etc/hostname
sed -i "s/127.0.1.1.*$CURRENT/127.0.1.1\tretrotv/g" /etc/hosts
grep -q "127.0.1.1" /etc/hosts || echo -e "127.0.1.1\tretrotv" >> /etc/hosts

# --- restore SSH authorized_keys (recovered from the dead card) ---
if [ -f /boot/retrotv-authorized_keys ]; then
    install -d -m 700 -o pi -g pi /home/pi/.ssh
    install -m 600 -o pi -g pi /boot/retrotv-authorized_keys /home/pi/.ssh/authorized_keys
    rm -f /boot/retrotv-authorized_keys
fi

# --- make sure sshd is on ---
systemctl enable ssh >/dev/null 2>&1
systemctl start ssh >/dev/null 2>&1

# --- clean up so this never runs again ---
rm -f /boot/firstrun.sh
sed -i 's| systemd.run=[^ ]*||g; s| systemd.run_success_action=[^ ]*||g; s| systemd.unit=[^ ]*||g' /boot/cmdline.txt

exit 0
