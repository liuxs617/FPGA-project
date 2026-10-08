#!/bin/sh
set -eu

project=/home/xilinx/lesion_fpga
unit=lesion-fpga.service
source_unit="$project/deploy/systemd/$unit"

test "$(id -u)" -eq 0 || { echo "Run with sudo" >&2; exit 1; }
test -r "$source_unit"
test -r "$project/artifacts/hardware/hdmi_full/lesion.bit"
test -r "$project/artifacts/hardware/hdmi_full/lesion.hwh"
test -r "$project/artifacts/hardware/hdmi_full/hardware_manifest.json"

install -m 0644 "$source_unit" "/etc/systemd/system/$unit"
systemctl daemon-reload
systemctl enable "$unit"
systemctl restart "$unit"
systemctl --no-pager --full status "$unit"
