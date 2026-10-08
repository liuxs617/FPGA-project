"""Exercise the live application's exception path without a physical FPGA."""
from concurrent.futures import Future
from types import SimpleNamespace
import itertools
import sys
import numpy as np
from lesion_fpga import app

def test_live_backend_error_clears_previous_result_and_closes(monkeypatch,tmp_path):
    (tmp_path/'sample.jpg').write_bytes(b'fake; fake pipeline does not decode')
    states=[]; events=[]; closed=[]
    class Output:
        def configure(self,*args): pass
        def start(self): pass
        def newframe(self): return np.zeros((720,1280,3),dtype=np.uint8)
        def writeframe(self,frame): pass
        def stop(self): closed.append('video')
    backend=SimpleNamespace(name='fake-fpga',hardware_id='fake',overlay=SimpleNamespace(video=SimpleNamespace(hdmi_out=Output())),close=lambda:closed.append('backend'))
    class FakePipeline:
        def __init__(self,b): self.calls=0
        def reset(self): pass
        def run(self,path,par,ver,gt):
            self.calls+=1
            if self.calls==2: raise RuntimeError('injected pipeline failure')
            return dict(parameter_version=ver,frame_id=1,model_id='test',timing={},path=str(path),parameters={})
    class Pool:
        def __init__(self,**kwargs): pass
        def submit(self,fn,*args):
            f=Future()
            try:f.set_result(fn(*args))
            except Exception as exc:f.set_exception(exc)
            return f
        def shutdown(self,**kwargs): closed.append('pool')
    e=lambda typ,code,value:SimpleNamespace(type=typ,code=code,value=value)
    batches=iter([[],[e(2,0,-402),e(2,1,313),e(1,272,1)],[e(2,0,979),e(1,272,1)]])
    drained=[False]
    def read_batch():
        if drained[0]:
            drained[0]=False
            raise BlockingIOError
        value=next(batches)
        drained[0]=bool(value)
        return value
    mouse=SimpleNamespace(fd=3,capabilities=lambda:{2:[0],1:[272]},read=read_batch,close=lambda:closed.append('mouse'))
    monkeypatch.setattr(app,'ModelPackage',lambda p:SimpleNamespace(meta={'gaussian':False}))
    monkeypatch.setattr(app,'PynqBackend',lambda *a:backend)
    monkeypatch.setattr(app,'Pipeline',FakePipeline)
    monkeypatch.setattr(app,'ThreadPoolExecutor',Pool)
    monkeypatch.setattr(app,'render',lambda result,status,*a:states.append((result,status)) or np.zeros((720,1280,3),dtype=np.uint8))
    monkeypatch.setattr(app,'event',lambda kind,**kw:events.append((kind,kw)))
    monkeypatch.setattr(app.select,'select',lambda *a:([3],[],[]))
    ticks=itertools.count(10)
    monkeypatch.setattr(app.time,'monotonic',lambda:next(ticks))
    monkeypatch.setitem(sys.modules,'pynq.lib.video',SimpleNamespace(VideoMode=lambda *a:a,PIXEL_RGB='RGB'))
    monkeypatch.setitem(sys.modules,'evdev',SimpleNamespace(InputDevice=lambda p:mouse,list_devices=lambda:['fake-mouse'],
        ecodes=SimpleNamespace(EV_REL=2,EV_KEY=1,REL_X=0,REL_Y=1,BTN_LEFT=272)))
    monkeypatch.setattr(sys,'argv',['app','--model',str(tmp_path),'--images',str(tmp_path)])
    app.main()
    assert states[0][0]['frame_id']==1
    assert any(r is None and 'injected pipeline failure' in s for r,s in states)
    assert any(kind=='runtime_error' for kind,_ in events)
    assert set(closed)=={'video','backend','pool','mouse'}
