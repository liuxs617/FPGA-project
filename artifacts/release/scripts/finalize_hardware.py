from lesion_fpga.common import ROOT,write_json,sha256
from pathlib import Path
from xml.etree import ElementTree as ET
import re
folder=ROOT/'artifacts/hardware'
timing=(folder/'timing_summary.rpt').read_text()
assert 'All user specified timing constraints are met.' in timing
for check in ['no_clock','unconstrained_internal_endpoints','generated_clocks','loops']:
    assert re.search(r'checking '+check+r' \(0\)',timing),check
for report in ['drc.rpt','methodology.rpt']:
    text=(folder/report).read_text()
    assert not re.search(r'\|\s*(?:Critical Warning|Error)\s*\|',text),report
assert 'VIOLATED' not in (folder/'bus_skew.rpt').read_text()
files={name:sha256(folder/name) for name in ['lesion.bit','lesion.hwh','lesion.xsa']}
tree=ET.parse(folder/'lesion.hwh');core=None
for m in tree.findall('.//MODULE'):
    if m.get('INSTANCE')=='lesion_accel_0':core=m
if core is None:raise ValueError('Missing accelerator in HWH')
registers={}
for reg in core.findall('.//REGISTER'):
    props={p.get('NAME'):p.get('VALUE') for p in reg.findall('./PROPERTY')}
    registers[reg.get('NAME')]=int(props['ADDRESS_OFFSET'])
assert registers['ap_return']==16 and registers['arena_1']==24 and registers['params_1']==36
source_files=list((ROOT/'hardware/hls').glob('*'))+list((ROOT/'hardware/vivado').glob('*'))
write_json(folder/'hardware_manifest.json',{'abi':1,'hardware_id':files['lesion.bit'][:16],
    'part':'xc7z020clg400-1','tool':'Vivado/Vitis 2025.2','files':files,
    'sources':{str(p.relative_to(ROOT)):sha256(p) for p in source_files if p.is_file()},
    'registers':registers,'board_verified':False})
print(files)
