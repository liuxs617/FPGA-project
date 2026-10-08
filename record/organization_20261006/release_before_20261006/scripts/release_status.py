import re
from pathlib import Path
from lesion_fpga.common import ROOT,read_json,write_json,sha256

hardware=ROOT/'artifacts/hardware'
evaluation=read_json(ROOT/'artifacts/evaluation_test.json')
tests=(ROOT/'record/tests.log').read_text()
cosim=(ROOT/'record/rtl_all_ops_cosim.log').read_text()
layer=read_json(ROOT/'record/layer_compare_native.json')
status={'model_id':evaluation['model_id'],'code':'implemented','training':'completed with early stopping',
        'data_counts':read_json(ROOT/'artifacts/data_manifest.json')['counts'],
        'unit_tests':tests.strip().splitlines()[-1],'native_full_network_bit_exact':layer['pass'],
        'rtl_cosimulation':'passed' if 'co-simulation finished: PASS' in cosim else 'not verified',
        'rtl_cosimulation_scope':'testbench vectors: ABI, convolution, pooling, upsample, concat, threshold endpoints, erosion, dilation, moments, Gaussian; whole network compared in native C++ only',
        'bitstream':'generated and timing checked' if (hardware/'hardware_manifest.json').exists() else 'build pending or blocked; inspect record/vivado_build.log',
        'board_validation':'pending: no connected board','physical_hdmi':'pending','physical_usb_mouse':'pending',
        'fpga_latency_throughput_power':'not measured','accuracy_test_original_size':evaluation['int8_post'],
        'quantization_gate':evaluation['quantization_gate_pass'],'docx_visual_qa':'6 pages inspected after Word PDF export',
        'implementation_notes':['Preprocessing/morphology use DDR frame neighbourhood scans, not a standalone line-stream pipeline.',
          'Gaussian switching requires a matching trained and calibrated model package; default package bypasses Gaussian.',
          'Native C++ timings are development measurements, never FPGA timings.'],
        'remaining_acceptance':['Load bit/hwh on PYNQ-Z2 and verify ABI / allocated memory.',
          'Run compare_layers.py --fpga and compare final masks.',
          'Verify RGB bars, 720p display, mouse disconnect/reconnect and latest-result submission.',
          'Run 100-frame FPGA benchmark with and without HDMI; test timeout/reset and capture report.']}
status['cdc_review']='3 CDC-7 reset paths in retained, unused HDMI input dvi2rgb; 2 CDC-6 in VTC. Not waived. Review record/open_questions.md HW04 before enabling HDMI input.'
if (hardware/'hardware_manifest.json').exists():status['hardware_id']=read_json(hardware/'hardware_manifest.json')['hardware_id']
if 'hardware_id' in status:
    report=(hardware/'timing_summary.rpt').read_text()
    match=re.search(r'WNS\(ns\).*?\n\s*[- ]+\n\s*([^\n]+)',report,re.S)
    values=match.group(1).split()
    status['timing_ns']={'setup_wns':float(values[0]),'hold_whs':float(values[4])}
    utilization=(hardware/'utilization.rpt').read_text()
    status['resource_percent']={}
    for name in ['Slice LUTs','Slice Registers','Block RAM Tile','DSPs']:
        row=re.search(r'\| '+name+r'\s*\|([^\n]+)',utilization).group(1)
        status['resource_percent'][name]=float(row.strip().strip('|').split('|')[-1])
write_json(ROOT/'artifacts/delivery_status.json',status)
sources={}
for folder in ['software','hardware/hls','hardware/vivado','scripts','configs','tests','docs']:
    for path in (ROOT/folder).rglob('*'):
        if path.is_file() and '__pycache__' not in path.parts:sources[path.relative_to(ROOT).as_posix()]=sha256(path)
write_json(ROOT/'record/source_hashes.json',sources)
summary=f'''# 实际验收摘要

- 模型：{status['model_id']}
- 数据：训练 {status['data_counts']['train']}，验证 {status['data_counts']['validation']}，测试 {status['data_counts']['test']}。
- 单元测试：{status['unit_tests']}
- 软件整数参考对原生 C++：整网逐层逐元素一致。
- C/RTL 联合仿真：{status['rtl_cosimulation']}，范围为测试平台向量，非整网实测。
- bitstream：{status['bitstream']}。
- 独立测试 Dice {evaluation['int8_post']['dice']:.4f}，IoU {evaluation['int8_post']['iou']:.4f}（原生 C++ INT8 加后处理）。
- 板上验收：待连接板卡；HDMI、鼠标、板上速度与实际功耗尚未验证。
- CDC：保留但未使用的 HDMI 输入存在 3 条复位 CDC-7，详见 record/open_questions.md HW04；不宣称全设计 CDC 零告警。

## 后续上板顺序

1. 校验硬件文件哈希并运行 board_preflight。
2. 同一 overlay 加载计算核心和 HDMI；显示 RGB 色条。
3. 运行 scripts/compare_layers.py --fpga。
4. 启动 HDMI 应用，执行切图、调参、鼠标断开重连、重置及错误处理。
5. 运行 scripts/benchmark.py --backend fpga --hdmi，记录实际边界和 100 帧统计。

详细证据在 record 和 artifacts，不能把源码完成或仿真通过视为板上验收完成。
'''
(ROOT/'docs/验收摘要.md').write_text(summary,encoding='utf-8')
print(status)
