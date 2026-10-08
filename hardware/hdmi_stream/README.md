# Streaming HDMI integration for section 7

The successful standalone colorbar diagnostic cannot display application
frames or run inference. `hdmi_stream.sv` adapts the existing PYNQ video stream
to HDMI packet signaling while preserving its VDMA, VTC, dynamic clocks,
inference accelerator and register map. It supports the application's fixed
1280x720 at 60 Hz mode only; other output modes are not advertised or tested.

The Digilent parallel interface uses R,B,G byte order. The adapter converts
this to RGB, delays video and sync by 12 pixels, and uses that lookahead to
insert the eight-symbol preamble and two-symbol video guard band. During
each 370-pixel horizontal blank it sends ten data-island packets. AVI identifies
VIC 4, RGB full range and 16:9. No audio sample clock is supplied.

`stream_tb.sv` checks a complete frame, exact active-pixel and guard counts,
non-overlap of packets with video, AVI checksum/VIC, known TMDS symbols and
TMDS decode back to RGB. Physical receive verification remains necessary.

Run `python hardware/hdmi_stream/prepare.py` then run Vivado on
`C:/temp/lesion_hdmi_full/hardware/vivado/build.tcl`. This creates a separate
IP (`project.local:video:rgb2hdmi:1.0`) and a separate full project. The original
release and build are retained. The IP preserves the original entity/port
names for hierarchy compatibility, with a new implementation and VLNV.

For incremental integration, once the new block design has generated its HWH
and IP wrapper, run Vivado on `hardware/hdmi_stream/integrate.tcl`. This
synthesizes the replacement encoder, substitutes just the HDMI output cell
in `C:/temp/lesion_fpga/build/signed_off.dcp`, then performs placement, routing,
timing and DRC signoff. `package.py` verifies the entire HWH memory map and
accelerator register map against the original release and records the base
checkpoint hash. This route produces bit/HWH; it does not claim a new XSA.

The integration script explicitly unroutes and unplaces the imported design
before reimplementation, retaining constraint-fixed board pins. Reusing the
post-route placement state directly caused Place 30-4 despite only 50.2% LUT
and 34.4% register utilization. Do not disable utilization checks. The
`reuse_linked` argument resumes from the saved linked checkpoint after the
encoder replacement; it is only valid while those inputs are unchanged.

The external interface/package and wrapper derive from Digilent rgb2dvi,
whose BSD license stays in the copied VHDL header. Packet/ECC/TMDS/SERDES
modules derive from hdl-util/hdmi at 83b1c9543a91b776671a44e68e130f81cae437b7,
under MIT (`hardware/hdmi_probe/LICENSE-MIT`). Original source is in
`third_party/hdl-util-hdmi`; reviewed local changes are in `hardware/hdmi_probe`.

Keep the generated full-overlay `lesion.bit`, matching `lesion.hwh`, and a
new hardware manifest together in a separate directory. Run the application
with `--bitstream` pointing there, retaining checksum/ABI validation.
Do not place a same-name XSA beside the board bitstream: current PYNQ may
mistake it for the active metadata source. Keep XSA in an archive directory.
