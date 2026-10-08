import argparse
import numpy as np
from lesion_fpga.common import ROOT,read_json,write_json
from lesion_fpga.quantization import ModelPackage,IntegerBackend
from lesion_fpga.backends import NativeBackend,PynqBackend
from lesion_fpga.imaging import load_rgb,letterbox
p=argparse.ArgumentParser();p.add_argument('--model',default=str(ROOT/'artifacts/models/baseline'))
p.add_argument('--fpga',action='store_true');p.add_argument('--bitstream',default=str(ROOT/'artifacts/hardware/lesion.bit'));a=p.parse_args()
package=ModelPackage(a.model);row=next(r for r in read_json(ROOT/'artifacts/data_manifest.json')['rows'] if r['split']=='validation')
rgb,g=letterbox(load_rgb(ROOT/row['image']),package.meta['input_size'])
reference,_=IntegerBackend(package).infer(rgb,package.meta['gaussian'],trace=True)
backend=PynqBackend(package,a.bitstream) if a.fpga else NativeBackend(package,ROOT/'build/native/lesion.dll')
try:actual,_=backend.infer(rgb,package.meta['gaussian'],trace=True)
finally:backend.close()
rows=[]
for name,expected in reference.items():
    diff=np.abs(expected.astype(np.int16)-actual[name].astype(np.int16))
    rows.append({'layer':name,'shape':list(expected.shape),'different_elements':int(np.count_nonzero(diff)),'max_abs':int(diff.max())})
report={'model_id':package.meta['model_id'],'backend':backend.name,'image':row['id'],'pass':all(r['different_elements']==0 for r in rows),'layers':rows}
trace_dir=ROOT/'artifacts/traces';trace_dir.mkdir(parents=True,exist_ok=True)
np.savez_compressed(trace_dir/('fpga_layers.npz' if a.fpga else 'reference_layers.npz'),**actual)
write_json(ROOT/('record/layer_compare_fpga.json' if a.fpga else 'record/layer_compare_native.json'),report)
print(report)
if not report['pass']:raise SystemExit(1)
