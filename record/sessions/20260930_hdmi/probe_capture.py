import sys,time,json
from pathlib import Path
import cv2,numpy as np
root=Path(__file__).resolve().parent
sys.path.insert(0,str(root/'probe_deps'))
from cv2_enumerate_cameras import enumerate_cameras
fmt=sys.argv[1] if len(sys.argv)>1 else 'MJPG'
cam=next(c for c in enumerate_cameras(cv2.CAP_DSHOW) if c.vid==0x345f and c.pid==0x2132)
print('DEVICE',cam,flush=True)
c=cv2.VideoCapture(cam.index,cv2.CAP_DSHOW)
print('OPEN',c.isOpened(),flush=True)
results={'device':cam.name,'requested_format':fmt,'opened':c.isOpened()}
if c.isOpened():
 results['settings']={}
 for key,val in [(cv2.CAP_PROP_FOURCC,cv2.VideoWriter_fourcc(*fmt)),(cv2.CAP_PROP_FRAME_WIDTH,1280),(cv2.CAP_PROP_FRAME_HEIGHT,720),(cv2.CAP_PROP_FPS,30)]:
  results['settings'][str(key)]={'accepted':c.set(key,val),'actual':c.get(key)}
 print('SETTINGS',results['settings'],flush=True)
 frames=[]
 start=time.monotonic()
 for i in range(60):
  ok,frame=c.read()
  if ok:
   frames.append({'mean':float(frame.mean()),'std':float(frame.std()),'min':int(frame.min()),'max':int(frame.max()),'shape':list(frame.shape)})
   if len(frames)==1 or i==59: cv2.imwrite(str(root/f'capture_{fmt}.png'),frame)
  if time.monotonic()-start>12:break
 results['frames']=len(frames);results['elapsed']=time.monotonic()-start;results['first']=frames[:1];results['last']=frames[-1:]
 c.release()
(root/f'capture_{fmt}.json').write_text(json.dumps(results,indent=2))
print(json.dumps(results),flush=True)
