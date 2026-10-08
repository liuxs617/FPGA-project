# 2026-09-27 Vivado 重建检查

检查对象：本次 08:48:30 启动的 build_overlay.ps1 构建；最终报告来自 C:/temp/lesion_fpga/build，报告生成时间约 09:10–09:11。不是 9 月 23 日旧报告。

## 最终结论（09:15 更新）

导出故障已修复，第 4.2 步的硬件文件发布及清单校验已完成。当前 artifacts/hardware 的 hardware_id 为 `8a111a4f13c4f851`，board_verified 仍为 false。

用户终端证实错误为 Common 17-69：write_hw_platform 无法从 implementation run 取得 BIT。finish.tcl 原先只写 release/lesion.bit，而 XSA 导出从实现运行目录查找 bitstream。已修改 finish.tcl，将刚生成的签核 bitstream 同步到 impl_1 目录下的顶层名称 .bit 后再导出。

恢复时复用现有本次 bitstream，仅重新打开工程并导出 XSA，没有重新综合、布线或重新生成 bitstream。record/vivado_export_recovery.log 记录正常导出和退出。Python ZipFile 完整性检查通过，XSA 内 lesion.bit 与 release/lesion.bit 逐字节相同；复制报告及 bit/hwh/xsa 后 finalize_hardware.py 校验通过。

旧 artifacts/hardware 已备份到 record/sessions/20260927_export_recovery/hardware_before。未执行后续整套应用打包，未声称板上已验证。

## 初次检查时的中断情况

最终实现报告通过现有工程的主要发布门槛，但整个 4.2 发布流程未完成。09:11:31 新 lesion.bit 已生成，release 中也有本次 lesion.hwh；Vivado 进程结束后未见 lesion.xsa，日志止于 write_hw_platform 耗时行，没有正常退出行。项目 artifacts/hardware 中的 bit/hwh/xsa 和 hardware_manifest.json 仍是旧版本。原因尚未确定，需核对用户原 PowerShell 窗口报错；不能把旧清单视为本次发布成功证据。

## 报告结果

| 检查 | 本次结果 |
|---|---|
| 建立时间 | WNS +0.011 ns，TNS 0，失败端点 0 |
| 保持时间 | WHS +0.051 ns，THS 0，失败端点 0 |
| 脉宽 | WPWS 0.000 ns，失败端点 0 |
| 时钟/内部约束 | no_clock、unconstrained_internal_endpoints、generated_clocks、loops 均为 0 |
| 总线偏斜 | 报告路径为 MET，未见 VIOLATED |
| 资源 | LUT 45.84%，寄存器 34.35%，BRAM 17.14%，DSP 75.45%；Slice 占用 82.58% |
| DRC | 无 Error/Critical Warning；172 条 Warning、1 条 Advisory |
| Methodology | 无 Error/Critical Warning；23 条 Warning |
| CDC | CDC-7 Critical 3 条，CDC-6 Warning 2 条；与指导记录的类别和位置相符 |
| 功耗 | 工具估算 2.100 W，置信度 Low；不是板上实测 |

## 保留问题和解释

- 时序通过但建立余量仅 11 ps，后续改动必须重新实现并检查。
- CDC-7 位于保留的 HDMI 输入 dvi2rgb LockLostReset 到三个 SyncBaseOvf 异步复位路径；当前 SD 卡输入流程不使用 HDMI 输入。启用 HDMI 输入前仍需专项验证复位及失锁恢复。
- CDC-6 位于 HDMI 输入/输出 VTC 多位读数据同步路径，不能声称全设计 CDC 零告警。
- 有 5 个无 input delay 的输入端口、7 个无 output delay 的输出端口，涉及 HDMI 数据、DDC、HPD 和输出时钟。内部时序通过不等于外部接口电气时序已完整签核，仍需板上 HDMI 验证。
- DRC 的 DSP 流水线建议涉及性能；LUT 方程、无负载网络和 RAM 模式提示需保留记录。VDMA RAMB18 异步控制和 AXI/FIFO 的 LUT 异步复位提示不能由静态时序通过自动排除，板上复位、连续视频运行和异常恢复仍应验证。
- Methodology 的时钟覆盖提示与 finish.tcl 中显式修正时钟约束相符；控制集和 Slice 占用提示布局余量有限。
- 中间 route_design 的负 WNS 和 SerialClk 约束告警已在 finish.tcl 修正及物理优化后的最终报告中消除，不应把中间结果当作最终失败结论。

未修改计算逻辑；本次仅修复导出路径并恢复发布。后续可以按指导继续发布打包和真实板卡验证，上述保留风险仍有效。
