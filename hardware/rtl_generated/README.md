# Generated Verilog

这些 .v 文件由 hardware/hls/lesion_accel.cpp 经 Vitis HLS 2025.2 生成，已经运行 C/RTL 联合仿真。不要手工修改生成文件；修改 HLS 源文件后重新构建。

集成 FPGA 需要 AXI IP 元数据、PYNQ 视频 IP、PS 配置和约束，不能仅把此目录 .v 加到空工程后当成完整系统。运行 scripts/build_hls.ps1、scripts/build_video_ip.ps1 和 scripts/build_overlay.ps1 生成同一 overlay 的 bit/hwh。
