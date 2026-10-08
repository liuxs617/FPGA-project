"""Section 6.4: run demo cases without HDMI; retain masks and exact moments."""
import argparse
import hashlib
from pathlib import Path
from PIL import Image
from lesion_fpga.common import ROOT, read_json, write_json
from lesion_fpga.quantization import ModelPackage
from lesion_fpga.backends import NativeBackend, PynqBackend
from lesion_fpga.pipeline import Pipeline, Parameters
from lesion_fpga.app import save_result
from lesion_fpga.ui import render

p = argparse.ArgumentParser()
p.add_argument('--fpga', action='store_true')
p.add_argument('--images', required=True)
p.add_argument('--output', required=True)
a = p.parse_args()
package = ModelPackage(ROOT/'artifacts/models/baseline')
policy = read_json(ROOT/'artifacts/models/baseline/policy.json')
assert policy['model_id'] == package.meta['model_id'] and not policy['limited']
params = Parameters(gaussian=package.meta['gaussian'], **policy['parameters'])
backend = (PynqBackend(package, ROOT/'artifacts/hardware/lesion.bit') if a.fpga
           else NativeBackend(package, ROOT/'build/native/lesion.dll'))
out = Path(a.output)
out.mkdir(parents=True, exist_ok=True)
rows = []
try:
    pipeline = Pipeline(backend)
    for path in sorted(Path(a.images).glob('*.jpg')):
        truth = path.with_name(path.stem+'_Segmentation.png')
        r = pipeline.run(path, params, ground_truth=truth if truth.exists() else None)
        folder = save_result(r, out/path.stem)
        Image.fromarray(render(r, 'Section 6.4 / '+backend.name, params)).save(folder/'snapshot.png')
        row = {k:r[k] for k in ['parameters','metrics','flags','accuracy','model_id','hardware_id','backend']}
        row.update(image=path.name, geometry=r['geometry'].to_dict(),
                   mask_sha256=hashlib.sha256(r['original_mask'].tobytes()).hexdigest(),
                   network_mask_sha256=hashlib.sha256(r['mask'].tobytes()).hexdigest(),
                   moments=backend.moments(r['mask']))
        rows.append(row)
        write_json(out/'summary.json', rows)
        print('CASE_PASS', path.name, row['mask_sha256'], flush=True)
finally:
    backend.close()
assert rows, 'No images found'
print('CASES_COMPLETE', len(rows), flush=True)
