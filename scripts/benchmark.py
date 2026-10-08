"""Run on target board for board claims. Explicit development backends remain labelled."""
import argparse
import time
import os
# Freeze CPU baseline BLAS threading before importing NumPy. Board and desktop use the same setting.
for variable in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:
    os.environ[variable]='1'
import numpy as np
from lesion_fpga.common import ROOT,read_json,write_json,environment
from lesion_fpga.quantization import ModelPackage,IntegerBackend
from lesion_fpga.backends import PynqBackend,NativeBackend
from lesion_fpga.float_backend import FloatBackend
from lesion_fpga.pipeline import Pipeline,Parameters
from lesion_fpga.ui import render
p=argparse.ArgumentParser();p.add_argument('--backend',choices=['fpga','fp32','native','integer'],default='fpga')
p.add_argument('--model',default=str(ROOT/'artifacts/models/baseline'));p.add_argument('--image',required=True)
p.add_argument('--bitstream',default=str(ROOT/'artifacts/hardware/lesion.bit'));p.add_argument('--runs',type=int,default=100)
p.add_argument('--hdmi',action='store_true');p.add_argument('--output',default=str(ROOT/'record/benchmark.json'));a=p.parse_args()
if a.runs<1:raise ValueError('runs must be positive')
package=ModelPackage(a.model)
b=PynqBackend(package,a.bitstream) if a.backend=='fpga' else FloatBackend(package) if a.backend=='fp32' else NativeBackend(package,ROOT/'build/native/lesion.dll') if a.backend=='native' else IntegerBackend(package)
policy=read_json(package.directory/'policy.json');params=Parameters(gaussian=package.meta['gaussian'],**policy['parameters'])
pipeline=Pipeline(b);output=None
if a.hdmi:
    if a.backend!='fpga':raise ValueError('--hdmi requires FPGA backend')
    from pynq.lib.video import VideoMode,PIXEL_RGB
    output=b.overlay.video.hdmi_out;output.configure(VideoMode(1280,720,24),PIXEL_RGB);output.start()
measurements=[];total=time.perf_counter()
try:
    for i in range(a.runs+3):
        pipeline.reset();start=time.perf_counter();result=pipeline.run(a.image,params,i)
        if output:
            frame=output.newframe();frame[:]=render(result,'Benchmark',params);output.writeframe(frame)
        elapsed=(time.perf_counter()-start)*1000
        if i==2:total=time.perf_counter()
        if i>=3:measurements.append({**result['timing'],'total_ms':elapsed})
    wall=time.perf_counter()-total
    summary={'model_id':package.meta['model_id'],'backend':b.name,'runs':a.runs,'environment':environment(),
             'cpu_blas_threads':1,
             'includes_hdmi_submission':a.hdmi,'boundary':'file read through result; optional HDMI frame submission (not physical photon latency)',
             'throughput_fps':a.runs/wall,'samples':measurements}
    for name in ['inference_ms','postprocess_ms','processing_ms','total_ms']:
        values=[r[name] for r in measurements];summary[name+'_mean']=float(np.mean(values));summary[name+'_p95']=float(np.percentile(values,95))
    write_json(a.output,summary);print({k:v for k,v in summary.items() if k!='samples'})
finally:
    if output:output.stop()
    b.close()
