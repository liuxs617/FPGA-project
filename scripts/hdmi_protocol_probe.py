"""Load the isolated HDMI colorbar overlay; no inference or DMA is used."""
import argparse
from pathlib import Path

from pynq import Overlay, Clocks

parser = argparse.ArgumentParser()
parser.add_argument("--bit", default="artifacts/hardware/hdmi_probe/hdmi_probe.bit")
args = parser.parse_args()
bit = Path(args.bit).resolve()
if not bit.is_file() or not bit.with_suffix(".hwh").is_file():
    raise FileNotFoundError("Both diagnostic .bit and matching .hwh are required")
print("Loading isolated HDMI diagnostic:", bit, flush=True)
overlay = Overlay(str(bit))
print("Loaded:", overlay.is_loaded(), "FCLK0 MHz:", Clocks.fclk0_mhz, flush=True)
print("Configured: HDMI signaling, VIC 4, 1280x720 at 60 Hz, RGB24.", flush=True)
print("Hardware colorbars continue until another overlay is loaded or power is removed.", flush=True)
print("Visible HDMI reception must be verified separately.", flush=True)
