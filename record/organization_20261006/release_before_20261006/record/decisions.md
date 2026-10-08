# 架构决定与证据

## 2026-09-22 初始决定

- 用户确认保留 U-Net INT8 PL 推理；允许 ARM 辅助和电脑离线训练；HDMI 显示器与 USB 鼠标。
- 竞赛 PDF 第 4、6、7 页：允许片上处理器，要求 PL 承担核心计算；基础处理至少三类，至少一种智能分析；ISIC 2016 为推荐数据。此为赛事要求。
- 小组 DOCX：P0/P1、1 个百分点量化损失、128 输入等为小组目标或建议，不是赛事硬门槛。
- 本机 CPU Ultra 9 285H，约 32 GB RAM，集成 Arc 140T；以 CPU 训练为默认，不以显示内存当成独立 CUDA 显存。
- Vivado/Vitis 2025.2 位于 C:/AMDDesignTools/2025.2；已检查命令可以启动和 XC7Z020 安装条目。
- 当前没有板卡连接信息。上板测试不能由 C 仿真替代。
- 单 overlay 同时含推理 IP 与 HDMI 输出；DDR 缓存特征；ARM 负责最大连通域和复杂形态分析。
- 计算接口 ABI 1：CHW int8 arena，16 个 int32 描述字；所有量化舍入为最近值，恰半远离零。
- 模型默认不使用 BatchNorm，避免部署时融合与训练状态差异；最终层输出量化 logit，阈值在 logit 域比较，与 sigmoid 概率等价。
- 高斯使用边缘复制；形态学使用零边界。统计仅使用有效区域；背景填洞采用 4 邻域，与前景 8 邻域互补。

## 官方资料

- PYNQ 3.1 changelog: https://pynq.readthedocs.io/en/v3.1/changelog.html （基础 overlay 使用 Vivado 2024.1）
- PYNQ source: https://github.com/Xilinx/PYNQ
- 芯片资料：用户提供 UG585、DS187、UG1165；UG1165 为旧版教学流程，不直接当作 2025.2 构建脚本。

后续变更须追加理由、验证命令和证据路径；不得覆盖历史实验以制造已验证状态。

## 2026-09-23 实验与修正

- 数据解压目录多了一层同名目录，扫描改为递归；发现 3 组跨官方训练和测试集的精确重复，排除两侧 6 张；另有 1 组训练集重复，按组划分。实际训练 718、验证 179、测试 376。
- Windows Python 环境为 3.14.5；初次 pip 索引依赖解析失败，改为官方 PyPI 完成安装，未修改用户全局环境。
- Vitis HLS 拒绝工程路径空格，改为 C:/temp/lesion_fpga 暂存构建，源代码仍在工作区。初次错误保存在 hls_build_initial.log。
- 首次综合重标定为过长组合路径。独立流水化重标定函数，并将共享 AXI 口的帧操作改为顺序调度。修正后 HLS 估计周期 8.560 ns；最终时序仍以布局布线报告为准。
- C/RTL 联合仿真第一次因测试平台缓冲长度小于 m_axi depth 失败，扩展测试平台 arena 至 8388608 字节后通过，失败日志保留。
- 生成了 Verilog RTL 并保存在 hardware/rtl_generated；正式 PL 计算由这些 RTL 实现，不是板上 ARM 执行 HLS C++。
- Vivado Tcl make_bd_intf_pins_external 的返回值不适合作为新端口对象，改为显式创建端口并连接，保留失败日志。
- 高斯模型配置必须与训练及校准一致，因此当前 GUI 不允许未经验证的临时去噪开关；通过对应模型包选择预处理。形态学/高斯首版采用 DDR 窗口扫描，而非独立 AXI 流式行缓存，已在说明文档明确。
- 缺少捆绑 LibreOffice，render_docx.py 报错已记录；使用本机 Word COM 导出 PDF，再由捆绑 PDFium 渲染，逐页检查 6 页，移除了模板中蓝色标题边框。
- 验证集 INT8 原始 Dice 相对 FP32 下降约 0.000563，未触发 QAT 门槛；没有将 QAT 当作已执行实验。


## 2026-09-23：RTL 联合仿真与实现修复

- 用户明确授权调用 Vivado/Vitis，发现仿真问题立即修复。计算 IP 由可综合 HLS C++ 导出 Verilog，生成源码在 hardware/rtl_generated；并非仅在 CPU 执行的 C++ 项目。
- 扩展测试平台覆盖全部操作码（ABI、卷积、池化、上采样、拼接、阈值端点、开闭基础算子、高斯、矩），Vitis C/RTL 联合仿真 PASS，见 rtl_all_ops_cosim.log。整网 25 层另与整数参考对齐，但不冒充整网 RTL 仿真。
- 初次布线 WNS -0.047 ns，交付门禁拒绝发布。保留 vivado_build.log；继续 post-route AggressiveExplore 物理优化，不降低 100 MHz 计算时钟。
- 官方 rgb2dvi_clocks.xdc 将外接 SerialClk 的源写为 PixelClk，但实际二者分别来自同一 MMCM 的 BUFIO 和 BUFR /5 支路。2025.2 报无逻辑路径。集成工程将生成时钟源修正到实际 BUFIO 输入，divide_by 1，保留真实 MMCM 时钟关系，不添加假路径掩盖。
- 调试中 Vivado 不支持 delete_clocks 命令；改用同名 create_generated_clock 覆盖约束。层级名称实际为 axi_dynclk（非 axi_dynclk_0），通过已布线检查点查询确认。

- 最终约束审查还发现保留的 HDMI 输入 IP 将 120 MHz 周期写成 8.334 ns，导致接收 MMCM 静态计算 VCO 为 599.952 MHz，略低于 600 MHz 下限。将周期向更严格方向取整为 8.333 ns（不是放宽时序）。图像输入仍来自 SD 卡，不依赖 HDMI 输入。DRC 和 methodology 的 Error/Critical Warning、总线偏斜违规、无时钟/未约束内部端点/无效生成时钟现均进入交付校验。
- 普通告警仍须留痕：官方 IP 内部异步复位、DSP 流水级建议、HDMI 源同步输出及 DDC/HPD 外部延迟、CDC 识别提示。工具通过不代表物理板卡信号完整性、鼠标和显示器已验收。

- 最终 bitstream ID 94e0bc1d5316b159。WNS +0.011 ns、WHS +0.051 ns；LUT 45.84%、FF 34.35%、BRAM 17.14%、DSP 75.45%。DRC/methodology 无 Error/Critical Warning，总线偏斜满足。独立 CDC 报告另有保留 HDMI 输入 dvi2rgb 的 3 条 CDC-7（LockLostReset 到 SyncBaseOvf 异步清零）及 VTC 2 条 CDC-6；不将其隐藏或称为 CDC 全通过。当前应用不启用 HDMI 输入，未来启用须专项验证。
