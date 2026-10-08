#!/usr/bin/env python3
"""Configure WayVNC pour un acces local protege par SSH uniquement."""
from datetime import datetime
from pathlib import Path
import re
import shutil
import sys


def update(path):
    original = path.read_text()
    result = original
    for key, value in {'address': '127.0.0.1', 'port': '5900', 'enable_auth': 'false'}.items():
        pattern = re.compile(r'^\s*' + key + r'\s*=.*$', re.MULTILINE)
        found = False

        def replacement(match):
            nonlocal found
            if found:
                return '# Ligne redondante retiree : ' + key
            found = True
            return key + '=' + value

        result = pattern.sub(replacement, result)
        if not found:
            result = result.rstrip('\n') + '\n' + key + '=' + value + '\n'
    if result != original:
        backup = path.with_name(path.name + '.avant-novnc-ssh-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
        shutil.copy2(path, backup)
        path.write_text(result)
        print('Configuration precedente sauvegardee :', backup)
    print('WayVNC : 127.0.0.1:5900 ; acces distant authentifie par SSH.')


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('Usage : modifier_wayvnc.py /etc/wayvnc/config')
    update(Path(sys.argv[1]))
