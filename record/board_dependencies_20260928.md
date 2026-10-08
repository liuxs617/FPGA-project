# 板端依赖检查：2026-09-28

目标：PYNQ 3.1.1，ARMv7l，Python 3.10.4。通过 COM9 串口离线完成，无需网线或再次拔 SD 卡。

- 从 PyPI 下载 evdev 1.6.1 源码包（26146 字节），验证 PyPI 提供的 SHA256：299db8628cc73b237fc1cc57d3c2948faa0756e2a58b6194b5bf81dc2081f1e3。
- 分块串口传输后再次核对相同哈希，板端使用已有 GCC、Python 开发头文件编译安装。
- 安装位置 `/home/xilinx/lesion_fpga/.board_deps`，未替换 PYNQ 系统依赖。源码留在板端 `~/lesion_offline/evdev-1.6.1.tar.gz` 和电脑 `artifacts/offline/evdev-1.6.1.tar.gz`。
- 离线安装命令：`python3 -m pip install --no-index --no-deps --no-build-isolation --target .board_deps ~/lesion_offline/evdev-1.6.1.tar.gz`（在项目目录执行）。
- 保留 NumPy 1.21.5、OpenCV 4.5.4、Pillow 9.0.1。实际测试发现 Pillow 9.0.1 缺少 Image.Resampling，已在 ui.py 使用兼容常量选择，电脑及板端同步修改。
- 电脑和 ARM 板端均通过 test_imaging.py 与 test_pipeline.py 共 7 项测试，覆盖几何转换、形态学、连通域、填洞、指标、定点舍入、高斯、流水线缓存及 720p 界面合成。板端日志：record/board_compat_tests.log。
- board_preflight.py 以 xilinx 用户运行成功，结果位于板端 record/board_environment.json。当前用户确认未接鼠标，input_devices 为空是预期；未验证实际鼠标读取权限、HDMI 输出或 FPGA 加载。
- 板端 release_manifest.json 已同步已改文件，原始清单仍保留。文档不进入本次板端包。
- 检查后 EXT4 errors_count 为 0。

每次重新登录，先执行：

```bash
cd ~/lesion_fpga
source scripts/board_env.sh
```

后续需要 root 的硬件命令仍按指导传递 `sudo env PYTHONPATH="$PYTHONPATH" "$BOARD_PY" ...`。这会保留本地 evdev 路径；仅 `sudo python3` 不能保证采用同一环境。

此结论是运行环境和软件兼容性验证，不是板上推理、HDMI 或鼠标实测通过。
