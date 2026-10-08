"""Prepare an isolated complete overlay, preserving the original release."""
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET

root=Path(__file__).resolve().parents[2]
base=Path('C:/temp/lesion_fpga')
stage=Path('C:/temp/lesion_hdmi_full')
cache=base/'build/vivado/lesion.cache/ip'
if cache.exists(): shutil.copytree(cache,stage/'ip_cache',dirs_exist_ok=True)
ip=stage/'custom_ip/rgb2hdmi'
shutil.copytree(base/'upstream/ip/rgb2dvi_v1_2',ip,dirs_exist_ok=True)
top=(ip/'src/rgb2dvi.vhd').read_text()
top=top[:top.index('architecture Behavioral')]+'''architecture Behavioral of rgb2dvi is
component hdmi_stream is
port (PixelClk, SerialClk, aRst_n : in std_logic;
vid_pData : in std_logic_vector(23 downto 0);
vid_pVDE, vid_pHSync, vid_pVSync : in std_logic;
TMDS_Clk_p, TMDS_Clk_n : out std_logic;
TMDS_Data_p, TMDS_Data_n : out std_logic_vector(2 downto 0));
end component;
begin
assert not kGenerateSerialClk report "External pixel/serial clocks required" severity failure;
assert not kRstActiveHigh report "Active-low reset required" severity failure;
core: hdmi_stream port map(PixelClk=>PixelClk, SerialClk=>SerialClk, aRst_n=>aRst_n,
vid_pData=>vid_pData,vid_pVDE=>vid_pVDE,vid_pHSync=>vid_pHSync,vid_pVSync=>vid_pVSync,
TMDS_Clk_p=>TMDS_Clk_p,TMDS_Clk_n=>TMDS_Clk_n,TMDS_Data_p=>TMDS_Data_p,TMDS_Data_n=>TMDS_Data_n);
end Behavioral;
'''
(ip/'src/rgb2dvi.vhd').write_text(top)
sources=list((root/'third_party/hdl-util-hdmi/src').glob('*.sv'))
sources=[p for p in sources if p.name not in ('hdmi.sv','serializer.sv','packet_picker.sv')]
sources += [root/'hardware/hdmi_probe/serializer.sv',root/'hardware/hdmi_probe/packet_picker.sv',root/'hardware/hdmi_stream/hdmi_stream.sv']
for p in sources: shutil.copy2(p,ip/'src'/p.name)
shutil.copy2(root/'hardware/hdmi_probe/LICENSE-MIT',ip/'LICENSE-HDMI-MIT')
# Remove old implementation constraints that refer to the old reset hierarchy.
# External dynclk clocks propagate into the encoder; the original signoff
# script also explicitly constrains SerialClk from the actual BUFIO source.
(ip/'src/rgb2dvi.xdc').write_text('# Reset is synchronized in hdmi_stream.\n')
(ip/'src/rgb2dvi_clocks.xdc').write_text('# Clocks supplied and constrained by axi_dynclk.\n')
ns='http://www.spiritconsortium.org/XMLSchema/SPIRIT/1685-2009'
ET.register_namespace('spirit',ns);ET.register_namespace('xilinx','http://www.xilinx.com')
q=lambda n:f'{{{ns}}}{n}'
tree=ET.parse(ip/'component.xml');comp=tree.getroot()
for name,value in [('vendor','project.local'),('library','video'),('name','rgb2hdmi'),('version','1.0')]: comp.find(q(name)).text=value
comp.find(q('description')).text='720p60 streaming RGB HDMI encoder with AVI/SPD InfoFrames; external clocks only.'
for group in comp.findall('./'+q('fileSets')+'/'+q('fileSet')):
    name=group.find(q('name')).text
    if 'synthesis' in name or 'behavioralsimulation' in name:
        for p in sources:
            f=ET.SubElement(group,q('file'))
            ET.SubElement(f,q('name')).text='src/'+p.name
            ET.SubElement(f,q('fileType')).text='systemVerilogSource'
            ET.SubElement(f,q('logicalName')).text='xil_defaultlib'
tree.write(ip/'component.xml',encoding='utf-8',xml_declaration=True)
(stage/'upstream').mkdir(parents=True,exist_ok=True)
for name in ('ps_preset.tcl','video.xdc'):
    shutil.copy2(base/'upstream'/name,stage/'upstream'/name)
hier=(base/'upstream/video_hierarchy.tcl').read_text().replace('digilentinc.com:ip:rgb2dvi:1.2','project.local:video:rgb2hdmi:1.0')
(stage/'upstream/video_hierarchy.tcl').write_text(hier)
(stage/'hardware/vivado').mkdir(parents=True,exist_ok=True)
(stage/'build').mkdir(exist_ok=True)
build=(root/'hardware/vivado/build.tcl').read_text()
build=build.replace('set_property target_language Verilog [current_project]',
    'set_property target_language Verilog [current_project]\nset_property ip_output_repo "$root/ip_cache" [current_project]\nset_property ip_cache_permissions {read write} [current_project]')
build=build.replace('"$root/upstream/ip" "$root/build/hls/lesion/solution1/impl/ip"',
                    '"C:/temp/lesion_fpga/upstream/ip" "$root/custom_ip" "C:/temp/lesion_fpga/build/hls/lesion/solution1/impl/ip"')
(stage/'hardware/vivado/build.tcl').write_text(build)
shutil.copy2(root/'hardware/vivado/finish.tcl',stage/'hardware/vivado/finish.tcl')
print(stage)
