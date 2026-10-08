import json,time
from pathlib import Path
import numpy as np
from PIL import Image
from lesion_fpga.ui import render,CachedRenderer
from lesion_fpga.pipeline import Parameters
r=Path("record/section7_20260930/saved")
f=sorted(r.glob("*/result.json"))[0]
a=json.loads(f.read_text())
a["rgb"]=np.asarray(Image.open(a["path"]).convert("RGB"))
a["original_mask"]=(np.asarray(Image.open(f.parent/"mask.png"))>0).astype(np.uint8)
a["processed"]=np.asarray(Image.fromarray(a["rgb"]).resize((128,128)))
a["mask"]=np.asarray(Image.fromarray(a["original_mask"]).resize((128,128)))
values=[]
for i in range(10):
 t=time.perf_counter();render(a,"Ready",Parameters(**a["parameters"]),pointer=(640+i,360));values.append((time.perf_counter()-t)*1000)
print(json.dumps({"render_ms":values}),flush=True)

compose=CachedRenderer(render)
values=[]
for i in range(11):
 t=time.perf_counter();compose(a,"Ready",Parameters(**a["parameters"]),.25,0,(640+i,360),False,None);values.append((time.perf_counter()-t)*1000)
print(json.dumps({"cached_render_ms":values}),flush=True)
