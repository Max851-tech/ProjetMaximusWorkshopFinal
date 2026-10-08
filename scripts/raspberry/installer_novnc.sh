#!/usr/bin/env bash
set -euo pipefail
if [ "$(id -u)" -eq 0 ]; then
  echo 'Lance bash installer_novnc.sh sans sudo devant, depuis ton utilisateur habituel.'
  exit 1
fi
pi_user="$(id -un)"
if [[ ! "$pi_user" =~ ^[a-z_][a-z0-9_-]*$ ]]; then
  echo 'Nom utilisateur incompatible avec cet installateur.'
  exit 1
fi
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
sudo -v
wifi_profile="$(nmcli -g GENERAL.CONNECTION device show wlan0)"
wifi_ssid="$(nmcli -g 802-11-wireless.ssid connection show "$wifi_profile" 2>/dev/null || true)"
if [ "$wifi_ssid" != 'iphone_hichem' ]; then
  echo 'Connecte d abord la Raspberry au Wi-Fi iphone_hichem depuis son bureau :'
  echo 'sudo nmcli --ask device wifi connect "iphone_hichem" name "PartageTelephone"'
  echo 'Entre le mot de passe du partage quand il est demande. Le changement de Wi-Fi peut couper SSH.'
  echo 'Puis reconnecte-toi et relance cet installateur.'
  exit 1
fi
sudo nmcli connection modify "$wifi_profile" connection.autoconnect yes connection.autoconnect-priority 100 connection.autoconnect-retries 0
sudo apt-get update
sudo apt-get install -y novnc websockify wayvnc
sudo raspi-config nonint do_ssh 0
sudo raspi-config nonint do_boot_behaviour B4
sudo raspi-config nonint do_vnc 0
sudo /usr/bin/python3 "$script_dir/modifier_wayvnc.py" /etc/wayvnc/config
unit_file="$(mktemp)"
trap 'rm -f "$unit_file"' EXIT
cat > "$unit_file" <<EOF
[Unit]
Description=noVNC local accessible par SSH
Wants=wayvnc.service
After=network.target wayvnc.service
StartLimitIntervalSec=0

[Service]
Type=simple
User=$pi_user
ExecStart=/usr/bin/websockify --web=/usr/share/novnc/ 127.0.0.1:6080 127.0.0.1:5900
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
sudo install -m 644 "$unit_file" /etc/systemd/system/novnc.service
sudo systemctl daemon-reload
sudo systemctl enable --now ssh
sudo systemctl enable novnc
sudo systemctl restart wayvnc novnc
echo 'Installation terminee : redemarre avec sudo reboot.'
echo 'Apres le reboot, verifie : sudo systemctl status ssh wayvnc novnc --no-pager'
echo 'Les ports 5900 et 6080 doivent ecouter seulement sur 127.0.0.1.'
echo 'Authentification par SSH : VNC local ne demandera pas de second mot de passe.'
