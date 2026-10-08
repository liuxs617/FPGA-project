# PYNQ Z2 皮肤病灶分割与 HDMI 展示

该工程以板上 FPGA 执行轻量 U-Net INT8 网络及基础图像处理，以 ARM 完成文件输入、复杂形态分析和 HDMI 界面合成。最终系统的运行计算全部在 PYNQ-Z2 上完成，开发电脑用于训练与构建。

**当前入口：[项目整理说明（2026-10-06）](docs/项目整理说明_20261006.md)。** 当前应用硬件为 `artifacts/hardware/hdmi_full`，硬件 ID `abe0c39aea79af7e`。9 月 30 日已完成新版 28/28 板端回归、四宫格显示确认和启动顺序修复后的重启验证；尚未全部验收。详见 `artifacts/delivery_status.json` 及 `record/section7_20260930/状态.md`。

## 快速入口

- `docs/项目说明.md`：结构、接口、构建、部署、验证与故障排查。
- `docs/项目说明.docx`：历史可打印版；当前连接和部署步骤以 Markdown 操作指导为准。
- `docs/后续操作指导_仿真上板与代码修正.md`：当前实际验证步骤，采用 Micro USB 串口控制、U 盘离线传文件，不需要网线。
- `configs/default.json`：训练和系统初始配置。
- `artifacts/models/baseline`：真实训练模型、量化权重、冻结后处理策略。
- `artifacts/hardware`：硬件报告及构建成功后发布的 bit/hwh/xsa。
- `hardware/hls`：可综合计算核心与测试平台；HLS 输出为 Verilog RTL。
- `hardware/vivado`：将计算核心与官方 PYNQ 视频层集成的 Vivado Tcl。
- `record`：决策、失败、修正、工具日志、数值对照和待上板事项。

## Windows 开发

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m lesion_fpga.train --resume
.\.venv\Scripts\python.exe -m lesion_fpga.export
.\.venv\Scripts\python.exe scripts/compare_layers.py
.\.venv\Scripts\python.exe -m lesion_fpga.evaluate --split validation
.\.venv\Scripts\python.exe -m lesion_fpga.evaluate --split test
.\scripts\build_hls.ps1 -Cosim
.\.venv\Scripts\python.exe scripts/prepare_hardware.py
.\scripts\build_video_ip.ps1
.\scripts\build_overlay.ps1
```

首次创建环境：Python 虚拟环境内执行 `pip install -e .[train,test]`。训练不需要 CUDA。硬件默认工具目录 `C:\AMDDesignTools\2025.2`，HLS 暂存目录 `C:\temp\lesion_fpga`，避免工作目录空格触发 HLS 错误。

## PYNQ 板上

当前连接方式：电脑 Micro USB 数据线接板卡 PROG/UART，J9 设 USB 时同时供电；JP1 设 SD 启动。通过 PuTTY 打开实际 COM 口，使用 115200、8N1、无流控。下面的 Linux 命令在板端串口终端执行，不在 Windows PowerShell 执行。部署包用 U 盘复制到板端 SD 卡，缺少的依赖也需准备适配板端环境的离线包。完整挂载、校验和结果取回步骤见 `docs/后续操作指导_仿真上板与代码修正.md` 第 5、6.3、11.1.1 节。

HDMI OUT 接独立显示器的输入口；通常不能直接接笔记本 HDMI 输出口。Micro USB 不传画面，也不自动提供文件传输或网络连接。

将工程软件、模型、图像与匹配的 `lesion.bit`、`lesion.hwh` 复制到板上同一工程目录。使用已包含 PYNQ 的系统 Python 环境，安装可用的 NumPy、Pillow、OpenCV、evdev。不要用 Windows 的虚拟环境覆盖板上 Python。

```bash
python3 -m pip install -e . --no-deps
python3 scripts/board_preflight.py
sudo -E python3 -m lesion_fpga.app --backend fpga \
  --model artifacts/models/baseline \
  --bitstream artifacts/hardware/hdmi_full/lesion.bit --images data/demo
```

主画面支持 Prev/Next、Run、阈值、开闭运算、最大域、填洞、Alpha、视图、重置和保存。USB 鼠标连接 PYNQ-Z2 USB Host，HDMI 接显示器。桌面预览必须显式指定 `--backend native --snapshot 文件.png`，不会静默替代 FPGA。

医学图像仅用于工程教学与算法演示，不作为临床诊断依据。
