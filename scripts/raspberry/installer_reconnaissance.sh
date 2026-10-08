#!/usr/bin/env bash
set -euo pipefail
if [ "$(id -u)" -eq 0 ]; then
  echo 'Lance bash installer_reconnaissance.sh avec ton utilisateur habituel, sans sudo devant.'
  exit 1
fi
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
project_root="$(cd -- "$script_dir/../.." && pwd)"
sudo apt-get update
sudo apt-get install -y python3-opencv python3-numpy alsa-utils pulseaudio-utils v4l-utils
sudo usermod -aG video,audio "$(id -un)"
/usr/bin/python3 - <<'PY'
import cv2 as cv
import numpy as np
import re
version = tuple(int(part) for part in re.findall(r'\d+', cv.__version__)[:2])
if version < (4, 8) or not hasattr(cv, 'FaceDetectorYN') or not hasattr(cv, 'FaceRecognizerSF'):
    raise SystemExit('OpenCV recent (4.8+) avec FaceDetectorYN et FaceRecognizerSF requis.')
print('OpenCV :', cv.__version__, '| NumPy :', np.__version__)
PY
/usr/bin/python3 "$project_root/src/reconnaissance_visage_2.py" --setup
echo 'Reconnaissance installee. Reouvre ta session pour prendre en compte les groupes video/audio.'
echo 'Puis ouvre un terminal DANS le bureau noVNC et lance :'
echo "bash \"$script_dir/lancer_reconnaissance.sh\""
