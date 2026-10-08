# PYNQ-Z2 HDMI protocol diagnostic

Independent 720p60 RGB colorbar overlay, using HDMI preambles, guard bands,
data islands and AVI/SPD InfoFrames. This does not contain the inference IP,
VDMA or mouse interface and must not replace `artifacts/hardware/lesion.*`.
The purpose is to test the unproven hypothesis that the USB capture receiver
rejects the existing Digilent rgb2dvi output.

Upstream: https://github.com/hdl-util/hdmi at
`83b1c9543a91b776671a44e68e130f81cae437b7`, selected MIT license, copyright
2019 Sameer Puri. Full license is retained in `third_party/hdl-util-hdmi/LICENSE-MIT`.
Local adapted files retain upstream module names and are selected instead of
their upstream equivalents:

- `serializer.sv`: correct the direction of the Xilinx serialized-output
  assignment so the OSERDESE2 outputs drive the top-level signals.
- `packet_picker.sv`: use deterministic zeros for Null packets and reset
  packet selection; AVI explicitly advertises full-range RGB and 16:9.

No audio sample clock is supplied. The test focuses on video reception;
it is not an HDMI compliance certification or an audio test.

The PS preset is extracted from pinned PYNQ 3.1.1 by
`scripts/prepare_hardware.py` into `C:/temp/lesion_fpga/upstream`.
Build with Vivado 2025.2:

```powershell
& C:/AMDDesignTools/2025.2/Vivado/bin/vivado.bat -mode batch -source hardware/hdmi_probe/build.tcl -tclargs $PWD.Path
```

Output staging: `C:/temp/lesion_hdmi_probe/hdmi_probe.bit` and matching `.hwh`.
The build rejects negative setup/hold slack and Error/Critical Warning DRCs.
`protocol_tb.sv` validates a complete 1650x750 raster, 921600 active pixels,
known TMDS symbols, HDMI data islands, AVI VIC4/RGB and AVI checksum.
Simulation replaces only the physical serializer with a stub; routing/DRC and
actual capture remain separate acceptance requirements.

On the board, load using `sudo` and the existing PYNQ Python environment:
`python3 scripts/hdmi_protocol_probe.py`. Output remains running in FPGA logic
after Python exits. To restore the application, load the original `lesion.bit`
through the normal `hdmi_colorbars.py` or application launcher. No boot files
or SD firmware are changed.
