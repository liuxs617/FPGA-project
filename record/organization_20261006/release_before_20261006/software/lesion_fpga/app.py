import argparse
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
import select
import time
import numpy as np
from PIL import Image
from .common import ROOT, read_json, write_json, event
from .quantization import ModelPackage, IntegerBackend
from .backends import NativeBackend, PynqBackend
from .pipeline import Pipeline, Parameters
from .ui import render,hit_button,pick_result

def save_result(result,folder):
    base=Path(folder)/f"frame_{result['frame_id']:06d}_v{result['parameter_version']}";folder=base;count=1
    while folder.exists():folder=base.with_name(base.name+f'_{count}');count+=1
    folder.mkdir(parents=True,exist_ok=False)
    Image.fromarray(result['original_mask']*255).save(folder/'mask.png')
    from .imaging import overlay
    Image.fromarray(overlay(result['rgb'],result['original_mask'])).save(folder/'overlay.png')
    fields={k:v for k,v in result.items() if k not in ['rgb','processed','mask','original_mask','geometry']}
    fields['geometry']=result['geometry'].to_dict();write_json(folder/'result.json',fields)
    return folder

def main():
    p=argparse.ArgumentParser();p.add_argument('--model',default=str(ROOT/'artifacts/models/baseline'))
    p.add_argument('--bitstream',default=str(ROOT/'artifacts/hardware/lesion.bit'))
    p.add_argument('--backend',choices=['fpga','integer','native'],default='fpga')
    p.add_argument('--images',default=str(ROOT/'data'));p.add_argument('--image');p.add_argument('--snapshot')
    p.add_argument('--mouse');p.add_argument('--report');p.add_argument('--output',default=str(ROOT/'artifacts/runs'))
    args=p.parse_args();package=ModelPackage(args.model)
    backend=PynqBackend(package,args.bitstream) if args.backend=='fpga' else NativeBackend(package,ROOT/'build/native/lesion.dll') if args.backend=='native' else IntegerBackend(package)
    pipeline=Pipeline(backend)
    policy_path=Path(args.model)/'policy.json'
    policy=read_json(policy_path) if policy_path.exists() else None
    if policy and (policy['model_id']!=package.meta['model_id'] or policy['limited']):raise ValueError('Invalid frozen policy')
    defaults=Parameters(gaussian=package.meta['gaussian'],**(policy['parameters'] if policy else {}));params=defaults
    images=[Path(args.image)] if args.image else sorted(Path(args.images).rglob('*.jpg'))
    if not images:raise ValueError('No JPEG images found')
    masks={p.name:p for p in Path(args.images).rglob('*_Segmentation.png')}
    def ground_truth(path):return masks.get(path.stem+'_Segmentation.png')
    if args.snapshot:
        try:
            result=pipeline.run(images[0],params,ground_truth=ground_truth(images[0]))
            Image.fromarray(render(result,'Development snapshot / '+backend.name,params)).save(args.snapshot)
            print(save_result(result,args.output))
        finally:backend.close()
        return
    if args.backend!='fpga':raise RuntimeError('Live HDMI requires --backend fpga; use --snapshot for desktop QA')
    from pynq.lib.video import VideoMode, PIXEL_RGB
    from evdev import InputDevice,list_devices,ecodes
    output=backend.overlay.video.hdmi_out;output.configure(VideoMode(1280,720,24),PIXEL_RGB);output.start()
    report=read_json(args.report) if args.report else None
    if report and report.get('model_id')!=package.meta['model_id']:raise ValueError('Benchmark report model mismatch')
    mouse=None;x,y=640,360;index=0;version=0;view=0;alpha=.25;result=None;selected=False
    status='Ready';desired=None;future=None;alive=True;last_draw=0;last_probe=0
    pool=ThreadPoolExecutor(max_workers=1)
    def request(reset=False):
        nonlocal version,desired,result,status,selected
        version+=1;desired=(images[index],params,version,reset);result=None;selected=False;status='Processing '+images[index].name
    def work(path,par,ver,reset):
        if reset:pipeline.reset()
        return pipeline.run(path,par,ver,ground_truth(path))
    request()
    try:
        while alive:
            if mouse is None and time.monotonic()-last_probe>2:
                last_probe=time.monotonic()
                for device in ([args.mouse] if args.mouse else list_devices()):
                    try:
                        candidate=InputDevice(device);caps=candidate.capabilities()
                        if ecodes.REL_X in caps.get(ecodes.EV_REL,[]) and ecodes.BTN_LEFT in caps.get(ecodes.EV_KEY,[]):mouse=candidate;break
                        candidate.close()
                    except OSError:continue
                if mouse is None:status='USB mouse missing; reconnect to continue'
            if future is None and desired is not None:
                job=desired;desired=None;future=pool.submit(work,*job)
            if future is not None and future.done():
                try:
                    candidate=future.result()
                    if candidate['parameter_version']==version:
                        result=candidate;status='Ready / '+images[index].name
                        event('frame_complete',frame_id=result['frame_id'],parameter_version=version,model_id=result['model_id'],backend=backend.name,timing=result['timing'])
                except Exception as exc:
                    result=None;status=f'ERROR: {type(exc).__name__}: {exc}';event('runtime_error',message=str(exc))
                future=None
            if mouse:
                try:
                    if select.select([mouse.fd],[],[],.005)[0]:
                        for e in mouse.read():
                            if e.type==ecodes.EV_REL:
                                if e.code==ecodes.REL_X:x=max(0,min(1279,x+e.value))
                                elif e.code==ecodes.REL_Y:y=max(0,min(719,y+e.value))
                            if e.type==ecodes.EV_KEY and e.code==ecodes.BTN_LEFT and e.value==1:
                                key=hit_button(x,y)
                                if key in ['prev','next']:index=(index+(1 if key=='next' else -1))%len(images);request()
                                elif key=='run':request(True)
                                elif key in ['threshold_up','threshold_down']:
                                    params=replace(params,threshold=round(max(0,min(1,params.threshold+(.05 if key=='threshold_up' else -.05))),2));request()
                                elif key in ['opening','closing','largest','fill']:params=replace(params,**{key:not getattr(params,key)});request()
                                elif key=='alpha':alpha={0:.25,.25:.5,.5:0}[alpha]
                                elif key=='view':view=(view+1)%3
                                elif key=='reset':params=defaults;alpha=.25;request(True)
                                elif key=='save' and result:status='Saved '+str(save_result(result,args.output))
                                elif key=='quit':alive=False
                                elif key is None:selected=pick_result(result,x,y,view)
                except OSError:
                    mouse.close();mouse=None;status='Mouse disconnected; reconnect USB mouse'
            else:time.sleep(.01)
            if time.monotonic()-last_draw>.05:
                frame=output.newframe();frame[:]=render(result,status,params,alpha,view,(x,y),selected,report)
                output.writeframe(frame);last_draw=time.monotonic()
    finally:
        pool.shutdown(wait=True,cancel_futures=True)
        if mouse:mouse.close()
        output.stop();backend.close()

if __name__=='__main__':main()
