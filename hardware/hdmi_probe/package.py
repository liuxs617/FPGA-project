"""Package the validated isolated diagnostic for serial transfer."""
import hashlib
import json
import shutil
import tarfile
from pathlib import Path

root = Path(__file__).resolve().parents[2]
stage = Path("C:/temp/lesion_hdmi_probe")
log = (stage / "implement.log").read_text(errors="replace")
if "HDMI_PROBE_BUILD_OK" not in log:
    raise RuntimeError("Build has not passed all validation gates")
dest = root / "artifacts/hardware/hdmi_probe"
dest.mkdir(parents=True, exist_ok=True)
files = {}
for name in ("hdmi_probe.bit", "hdmi_probe.hwh", "timing.rpt", "drc.rpt", "utilization.rpt"):
    shutil.copy2(stage / name, dest / name)
    files[name] = hashlib.sha256((dest / name).read_bytes()).hexdigest()
manifest = {
    "purpose": "isolated HDMI capture compatibility diagnostic; no inference IP",
    "upstream_hdmi_commit": "83b1c9543a91b776671a44e68e130f81cae437b7",
    "format": "1280x720p60 RGB24 full range, VIC4, HDMI data islands and InfoFrames",
    "pixel_clock_mhz": 74.25,
    "serial_clock_mhz": 371.25,
    "files_sha256": files,
    "hardware_reception": "not yet verified",
}
(dest / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
with tarfile.open(stage / "hdmi_probe.tar.gz", "w:gz") as archive:
    for name in ("hdmi_probe.bit", "hdmi_probe.hwh", "manifest.json"):
        archive.add(dest / name, arcname=f"artifacts/hardware/hdmi_probe/{name}")
    archive.add(root / "scripts/hdmi_protocol_probe.py", arcname="scripts/hdmi_protocol_probe.py")
print(json.dumps(manifest, indent=2))
print("Transfer archive bytes:", (stage / "hdmi_probe.tar.gz").stat().st_size)
