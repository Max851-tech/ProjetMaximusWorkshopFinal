#!/usr/bin/env bash
set -u
printf '\n=== Identite et demarrage ===\n'
hostname
uptime
cat /proc/sys/kernel/random/boot_id
printf '\n=== Adresses et Wi-Fi ===\n'
hostname -I
if command -v nmcli >/dev/null; then
  nmcli device status
  nmcli -f NAME,TYPE,AUTOCONNECT connection show
fi
printf '\n=== Services ===\n'
sudo systemctl status ssh wayvnc novnc display-manager --no-pager -l
printf '\n=== Ports SSH / VNC / noVNC ===\n'
sudo ss -ltnp
printf '\n=== Webcam ===\n'
if command -v v4l2-ctl >/dev/null; then
  v4l2-ctl --list-devices
fi
printf '\n=== Alimentation / temperature ===\n'
if command -v vcgencmd >/dev/null; then
  vcgencmd get_throttled
  vcgencmd measure_temp
fi
printf '\n=== Journaux du demarrage actuel ===\n'
sudo journalctl -b -u ssh -u wayvnc -u novnc -u display-manager -n 80 --no-pager
