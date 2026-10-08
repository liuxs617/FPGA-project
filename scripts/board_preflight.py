"""Read-only board checks. Run on the PYNQ ARM, not on the Windows host."""
import json
import platform
from pathlib import Path
import pynq
from evdev import InputDevice, list_devices
print(json.dumps({'platform':platform.platform(),'pynq':pynq.__version__,
    'memory':Path('/proc/meminfo').read_text().splitlines()[:5],
    'input_devices':[{'path':p,'name':InputDevice(p).name} for p in list_devices()]},indent=2))
