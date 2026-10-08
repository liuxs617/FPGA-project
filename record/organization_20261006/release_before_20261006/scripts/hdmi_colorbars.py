"""Board-only smoke test using the SAME integrated overlay as inference."""
import argparse
import time
import numpy as np
from lesion_fpga.common import ROOT
from lesion_fpga.quantization import ModelPackage
from lesion_fpga.backends import PynqBackend
p=argparse.ArgumentParser();p.add_argument('--model',default=str(ROOT/'artifacts/models/baseline'))
p.add_argument('--bitstream',default=str(ROOT/'artifacts/hardware/lesion.bit'));p.add_argument('--seconds',type=int,default=30);a=p.parse_args()
backend=PynqBackend(ModelPackage(a.model),a.bitstream)
from pynq.lib.video import VideoMode,PIXEL_RGB
hdmi=backend.overlay.video.hdmi_out
try:
    hdmi.configure(VideoMode(1280,720,24),PIXEL_RGB);hdmi.start()
    colors=np.array([[255,255,255],[255,255,0],[0,255,255],[0,255,0],[255,0,255],[255,0,0],[0,0,255],[0,0,0]],np.uint8)
    frame=hdmi.newframe()
    for index,color in enumerate(colors):frame[:,index*160:(index+1)*160]=color
    hdmi.writeframe(frame);time.sleep(a.seconds)
finally:hdmi.stop();backend.close()
