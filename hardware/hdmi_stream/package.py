"""Publish the separately signed-off full HDMI overlay, without replacing DVI."""
from pathlib import Path
import hashlib
import json
import re
import shutil
import tarfile
import xml.etree.ElementTree as ET

root=Path(__file__).resolve().parents[2];stage=Path('C:/temp/lesion_hdmi_full')
dest=root/'artifacts/hardware/hdmi_full'
timing=(stage/'build/timing_summary.rpt').read_text()
assert 'All user specified timing constraints are met.' in timing
for name in ('no_clock','unconstrained_internal_endpoints','generated_clocks','loops'):
    assert re.search(r'checking '+name+r' \(0\)',timing),name
for name in ('drc.rpt','methodology.rpt'):
    assert not re.search(r'\|\s*(?:Critical Warning|Error)\s*\|',(stage/'build'/name).read_text()),name
assert 'VIOLATED' not in (stage/'build/bus_skew.rpt').read_text()
# The retained HDMI input hierarchy has three pre-existing reset CDC alerts.
# No new critical clock-domain pair is allowed by this output-only change.
cdc=(stage/'build/cdc.rpt').read_text()
critical=[line.split() for line in cdc.splitlines() if line.startswith('Critical ')]
assert len(critical)==1 and critical[0][1:3]==['hdmi_in_PixelClk','clk_fpga_2']
assert critical[0][-5:]==['6','3','0','3','0'],critical
tree=ET.parse(stage/'release/lesion.hwh')
old_tree=ET.parse(root/'artifacts/hardware/lesion.hwh')
memory_map=lambda t:sorted(tuple(sorted(x.attrib.items())) for x in t.findall('.//MEMRANGE'))
assert memory_map(tree)==memory_map(old_tree),'Address map changed'
assert any('project.local:video:rgb2hdmi:1.0' in str(m.attrib) for m in tree.findall('.//MODULE'))
core=next(m for m in tree.findall('.//MODULE') if m.get('INSTANCE')=='lesion_accel_0')
registers={}
for reg in core.findall('.//REGISTER'):
    fields={p.get('NAME'):p.get('VALUE') for p in reg.findall('./PROPERTY')}
    registers[reg.get('NAME')]=int(fields['ADDRESS_OFFSET'])
old=json.loads((root/'artifacts/hardware/hardware_manifest.json').read_text())
assert registers==old['registers'],'Accelerator ABI changed'
dest.mkdir(parents=True,exist_ok=True)
(dest/'archive').mkdir(exist_ok=True)
for name in ('lesion.bit','lesion.hwh'):shutil.copy2(stage/'release'/name,dest/name)
if (stage/'release/lesion.xsa').exists():
    shutil.copy2(stage/'release/lesion.xsa',dest/'archive/lesion.xsa')
for p in (stage/'build').glob('*.rpt'):shutil.copy2(p,dest/p.name)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
files={name:sha(dest/name) for name in ('lesion.bit','lesion.hwh')}
source_dirs=('hardware/hls','hardware/vivado','hardware/hdmi_stream','hardware/hdmi_probe')
sources={str(p.relative_to(root)):sha(p) for d in source_dirs for p in (root/d).glob('*') if p.is_file()}
manifest=dict(abi=old['abi'],hardware_id=files['lesion.bit'][:16],part=old['part'],tool='Vivado/Vitis 2025.2',
    files=files,registers=registers,sources=sources,board_verified=False,
    video='720p60 RGB full-range HDMI with AVI/SPD; streaming encoder',
    upstream_hdmi_commit='83b1c9543a91b776671a44e68e130f81cae437b7')
manifest['integration']='Replace only rgb2dvi_0 in previously signed-off full checkpoint, then reimplement/sign off'
manifest['base_hardware_id']=old['hardware_id']
manifest['base_checkpoint_sha256']=sha(Path('C:/temp/lesion_fpga/build/signed_off.dcp'))
manifest['retained_cdc_alerts']='Three existing unknown asynchronous reset paths in HDMI input; output-only test does not exercise HDMI input'
(dest/'hardware_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
with tarfile.open(stage/'section7.tar.gz','w:gz') as tar:
    for name in ('lesion.bit','lesion.hwh','hardware_manifest.json'):
        tar.add(dest/name,arcname='artifacts/hardware/hdmi_full/'+name)
    for name in ('software/lesion_fpga/app.py','scripts/section7_ui_test.py'):
        tar.add(root/name,arcname=name)
print('hardware_id:',manifest['hardware_id'])
print('archive bytes:',(stage/'section7.tar.gz').stat().st_size)
