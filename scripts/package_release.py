"""Create a small deployable tree; no Windows venv, training data copies or false hardware claims."""
from pathlib import Path
import shutil
import json
import hashlib
from lesion_fpga.common import ROOT,read_json,write_json,sha256

current=ROOT/'artifacts/hardware/hdmi_full'
current_manifest=read_json(current/'hardware_manifest.json')
for name,digest in current_manifest['files'].items():
    assert sha256(current/name)==digest, f'Hardware hash mismatch: {name}'
assert read_json(ROOT/'artifacts/delivery_status.json')['hardware_id']==current_manifest['hardware_id'], 'Refresh delivery status before packaging'
dest=ROOT/'artifacts/release';dest.mkdir(parents=True,exist_ok=False)
for name in ['software','configs','scripts','docs','deploy']:
    shutil.copytree(ROOT/name,dest/name,dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__'))
for name in ['pyproject.toml','README.md']:shutil.copy2(ROOT/name,dest/name)
shutil.copytree(ROOT/'artifacts/models/baseline',dest/'artifacts/models/baseline',dirs_exist_ok=True)
hardware=dest/'artifacts/hardware/hdmi_full';hardware.mkdir(parents=True,exist_ok=True)
for name in ['lesion.bit','lesion.hwh','lesion.xsa','hardware_manifest.json','timing_summary.rpt','utilization.rpt','drc.rpt','methodology.rpt','bus_skew.rpt','cdc.rpt','power_estimate.rpt']:
    if (ROOT/'artifacts/hardware/hdmi_full'/name).exists():shutil.copy2(ROOT/'artifacts/hardware/hdmi_full'/name,hardware/name)
# PYNQ 3.1.1 treats an adjacent same-stem XSA as the metadata source even
# when Overlay is called with a .bit path. Keep the export in a subdirectory.
(hardware/'archive').mkdir(exist_ok=True)
if (hardware/'lesion.xsa').exists():
    shutil.move(str(hardware/'lesion.xsa'), str(hardware/'archive/lesion.xsa'))
hardware_manifest=read_json(hardware/'hardware_manifest.json')
if 'lesion.xsa' in hardware_manifest['files']:
    hardware_manifest['files']['archive/lesion.xsa']=hardware_manifest['files'].pop('lesion.xsa')
write_json(hardware/'hardware_manifest.json',hardware_manifest)
(dest/'record').mkdir(exist_ok=True)
shutil.copy2(ROOT/'artifacts/delivery_status.json',dest/'artifacts/delivery_status.json')
ranked=sorted(read_json(ROOT/'artifacts/evaluation_test.json')['per_image'],key=lambda r:r['int8_post']['dice'])
selected={r['id'] for r in ranked[:4]+ranked[-4:]+ranked[len(ranked)//2:len(ranked)//2+4]}
demo=dest/'data/demo';demo.mkdir(parents=True,exist_ok=True)
for row in read_json(ROOT/'artifacts/data_manifest.json')['rows']:
    if row['id'] in selected:
        for key in ['image','mask']:shutil.copy2(ROOT/row[key],demo/Path(row[key]).name)
for name in ['decisions.md','open_questions.md','board_status_current.json']:shutil.copy2(ROOT/'record'/name,dest/'record'/name)
for name in ['section6_results_20260928','section7_20260930']:
    target=dest/'record'/name;target.mkdir(parents=True,exist_ok=True)
    for source in (ROOT/'record'/name).glob('*.md'):shutil.copy2(source,target/source.name)
manifest={'files':{},'board_verified':False,'note':'Includes 12 held-out demonstration images and masks (success, middle, failure). Full source and training evidence remain in the parent project.'}
for path in sorted(dest.rglob('*')):
    if path.is_file() and path.name!='release_manifest.json':manifest['files'][path.relative_to(dest).as_posix()]=sha256(path)
write_json(dest/'release_manifest.json',manifest)
print(dest)
