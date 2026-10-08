"""Save all held-out masks and a small set of annotated demonstration examples."""
from pathlib import Path
import numpy as np
from PIL import Image
from lesion_fpga.common import ROOT,read_json,write_json
from lesion_fpga.quantization import ModelPackage
from lesion_fpga.backends import NativeBackend
from lesion_fpga.pipeline import Pipeline,Parameters
from lesion_fpga.app import save_result
from lesion_fpga.ui import render
package=ModelPackage(ROOT/'artifacts/models/baseline');policy=read_json(package.directory/'policy.json')
backend=NativeBackend(package,ROOT/'build/native/lesion.dll');pipeline=Pipeline(backend)
parameters=Parameters(gaussian=package.meta['gaussian'],**policy['parameters'])
evaluation=read_json(ROOT/'artifacts/evaluation_test.json')
ranked=sorted(evaluation['per_image'],key=lambda r:r['int8_post']['dice'])
selected={r['id'] for r in ranked[:4]+ranked[-4:]+ranked[len(ranked)//2:len(ranked)//2+4]}
out=ROOT/'artifacts/predictions';out.mkdir(parents=True,exist_ok=True);entries=[]
try:
    for i,row in enumerate(r for r in read_json(ROOT/'artifacts/data_manifest.json')['rows'] if r['split']=='test'):
        result=pipeline.run(ROOT/row['image'],parameters,ground_truth=ROOT/row['mask'])
        Image.fromarray(result['original_mask']*255).save(out/(row['id']+'_mask.png'))
        entries.append({'id':row['id'],'accuracy':result['accuracy'],'flags':result['flags']})
        if row['id'] in selected:
            folder=save_result(result,ROOT/'artifacts/demo_cases')
            Image.fromarray(render(result,'Recorded development inference / native C++',parameters)).save(folder/'screen.png')
        if (i+1)%50==0:print(f'Predictions {i+1}',flush=True)
finally:backend.close()
write_json(out/'index.json',{'model_id':package.meta['model_id'],'backend':backend.name,'records':entries})
