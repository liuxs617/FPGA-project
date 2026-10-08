"""Extract the pinned upstream PYNQ video hierarchy and exact PYNQ-Z2 PS preset.

No version-check bypass: our own minimal BD is assembled from these reviewed
hierarchy procedures. Current IP catalog compatibility is validated by Vivado.
"""
import argparse
import re
import shutil
import subprocess
from pathlib import Path
from lesion_fpga.common import ROOT, write_json, sha256

p=argparse.ArgumentParser();p.add_argument('--stage',default='C:/temp/lesion_fpga');a=p.parse_args()
stage=Path(a.stage);up=ROOT/'third_party/PYNQ'
expected='bae140919443940cccd1c7761d59ceed1d8dfc70'
revision=subprocess.check_output(['git','-C',str(up),'rev-parse','HEAD'],text=True).strip()
if revision!=expected:raise RuntimeError('Unexpected PYNQ commit; review before adapting')
base=up/'boards/Pynq-Z2/base';source=(base/'base.tcl').read_text()
dest=stage/'upstream';dest.mkdir(parents=True,exist_ok=True)
shutil.copytree(up/'boards/ip',dest/'ip',dirs_exist_ok=True)
shutil.copy2(up/'LICENSE',dest/'LICENSE')
names=['frontend_1','frontend','hdmi_out','hdmi_in','video']
parts=['# Derived from Xilinx/PYNQ 3.1.1, BSD-3-Clause; see upstream/LICENSE\n']
for name in names:
    match=re.search(r'proc create_hier_cell_'+name+r' \{.*?(?=\n# Hierarchical cell:|\nproc create_root_design)',source,re.S)
    if not match:raise RuntimeError(name)
    parts.append(match.group(0))
(dest/'video_hierarchy.tcl').write_text('\n'.join(parts))
ps=re.search(r'  set ps7_0 \[ create_bd_cell.*?\] \$ps7_0',source,re.S).group(0)
(dest/'ps_preset.tcl').write_text(ps)
xdc=(base/'vivado/constraints/base.xdc').read_text()
lines=[l for l in xdc.splitlines() if any(s in l for s in ['hdmi','CFGBVS','CONFIG_VOLTAGE'])]
(dest/'video.xdc').write_text('# PYNQ-Z2 official pin subset; BSD-3-Clause\n'+'\n'.join(lines)+'\n')
for name in ['color_convert','pixel_pack','pixel_unpack']:
    folder=dest/'ip/hls'/name
    script=f'''open_project -reset {name}
set_top {name}
add_files {name}/{name}.cpp
open_solution -reset solution1 -flow_target vivado
set_part xc7z020clg400-1
create_clock -period 7
csynth_design
export_design -format ip_catalog -vendor xilinx.com -library hls -version 1.0
exit
'''
    (dest/'ip/hls'/f'build_{name}.tcl').write_text(script)
shutil.copytree(ROOT/'hardware/vivado',stage/'hardware/vivado',dirs_exist_ok=True)
write_json(ROOT/'record/upstream_lock.json',{'repository':'https://github.com/Xilinx/PYNQ','tag':'3.1.1',
    'commit':revision,'base_tcl_sha256':sha256(base/'base.tcl'),'stage':str(stage),
    'adaptation':'video + PS preset only; no MicroBlaze/audio/trace cores'})
print(stage)
