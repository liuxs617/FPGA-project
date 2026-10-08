import argparse
import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace, asdict
from pathlib import Path
import select
import time
import numpy as np
from PIL import Image
from .common import ROOT, read_json, write_json, event
from .quantization import ModelPackage, IntegerBackend
from .backends import NativeBackend, PynqBackend
from .pipeline import Pipeline, Parameters
from .ui import render,hit_button,pick_result,CachedRenderer


def pending_mouse_events(mouse):
    """Drain queued batches in order, with a bound against input starvation."""
    for _ in range(64):
        try: batch=list(mouse.read())
        except BlockingIOError: return
        if not batch:return
        yield from batch

def save_result(result,folder):
    base=Path(folder)/f"frame_{result['frame_id']:06d}_v{result['parameter_version']}";folder=base;count=1
    while folder.exists():folder=base.with_name(base.name+f'_{count}');count+=1
    folder.mkdir(parents=True,exist_ok=False)
    Image.fromarray(result['original_mask']*255).save(folder/'mask.png')
    from .imaging import overlay
    Image.fromarray(overlay(result['rgb'],result['original_mask'])).save(folder/'overlay.png')
    fields={k:v for k,v in result.items() if k not in ['rgb','processed','mask','original_mask','geometry']}
    fields['geometry']=result['geometry'].to_dict();write_json(folder/'result.json',fields)
    event('result_saved',folder=str(folder),frame_id=result['frame_id'],parameter_version=result['parameter_version'])
    return folder

def main():
    p=argparse.ArgumentParser();p.add_argument('--model',default=str(ROOT/'artifacts/models/baseline'))
    p.add_argument('--bitstream',default=str(ROOT/'artifacts/hardware/lesion.bit'))
    p.add_argument('--backend',choices=['fpga','integer','native'],default='fpga')
    p.add_argument('--images',default=str(ROOT/'data'));p.add_argument('--image');p.add_argument('--snapshot')
    p.add_argument('--mouse');p.add_argument('--report');p.add_argument('--output',default=str(ROOT/'artifacts/runs'))
    p.add_argument('--latency-log',help='JSONL timestamps for mouse-to-frame diagnostics')
    args=p.parse_args();package=ModelPackage(args.model)
    event('app_start',backend=args.backend,bitstream=args.bitstream,images=args.images)
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
    event('hdmi_started',width=1280,height=720,refresh_hz=60,hardware_id=backend.hardware_id)
    report=read_json(args.report) if args.report else None
    if report and report.get('model_id')!=package.meta['model_id']:raise ValueError('Benchmark report model mismatch')
    mouse=None;x,y=640,360;index=0;version=0;view=0;alpha=.25;result=None;selected=False
    status='Ready';desired=None;future=None;alive=True;last_draw_start=0;last_draw_state=None;last_probe=0
    latency_log=open(args.latency_log,'a',buffering=1) if args.latency_log else None
    motion_pending=None
    pool=ThreadPoolExecutor(max_workers=1)
    compose=CachedRenderer(render)
    def request(reset=False):
        nonlocal version,desired,result,status,selected
        version+=1;desired=(images[index],params,version,reset);result=None;selected=False;status='Processing '+images[index].name
        event('frame_requested',path=str(images[index]),parameter_version=version,parameters=asdict(params),force_inference=reset)
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
                        if ecodes.REL_X in caps.get(ecodes.EV_REL,[]) and ecodes.BTN_LEFT in caps.get(ecodes.EV_KEY,[]):
                            mouse=candidate;event('mouse_connected',device=str(device));break
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
                        event('frame_complete',frame_id=result['frame_id'],parameter_version=version,model_id=result['model_id'],backend=backend.name,timing=result['timing'],path=result['path'],parameters=result['parameters'])
                except Exception as exc:
                    result=None;status=f'ERROR: {type(exc).__name__}: {exc}';event('runtime_error',message=str(exc))
                future=None
            if mouse:
                try:
                    if select.select([mouse.fd],[],[],.005)[0]:
                        motion_count=0;kernel_time=None;read_tick=time.monotonic()
                        for e in pending_mouse_events(mouse):
                            if e.type==ecodes.EV_REL:
                                if e.code==ecodes.REL_X:x=max(0,min(1279,x+e.value));motion_count+=1
                                elif e.code==ecodes.REL_Y:y=max(0,min(719,y+e.value));motion_count+=1
                                if hasattr(e,'sec'):kernel_time=e.sec+e.usec/1e6
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
                                event('ui_action',key=key,x=x,y=y,path=str(images[index]),parameter_version=version,
                                      frame_id=result['frame_id'] if result else None,parameters=asdict(params),alpha=alpha,view=view,selected=selected)
                        if motion_count:motion_pending=(kernel_time,read_tick,motion_count,x,y)
                except OSError:
                    event('mouse_disconnected')
                    mouse.close();mouse=None;status='Mouse disconnected; reconnect USB mouse'
            else:time.sleep(.01)
            draw_state=(id(result),status,params,alpha,view,x,y,selected,id(report))
            # VDMA keeps showing the last submitted frame. Submit only when
            # the scene changed, and rate-limit from draw start (not submit
            # completion) so a 30 Hz capture preview does not trail input.
            if draw_state!=last_draw_state and time.monotonic()-last_draw_start>=1/30:
                draw_start=time.monotonic();frame=output.newframe();frame[:]=compose(result,status,params,alpha,view,(x,y),selected,report)
                output.writeframe(frame);submit_done=time.monotonic()
                last_draw_start=draw_start;last_draw_state=draw_state
                if latency_log and motion_pending:
                    kt,rt,count,mx,my=motion_pending
                    latency_log.write(json.dumps(dict(kernel_time=kt,read_monotonic=rt,draw_start=draw_start,
                        submit_done=submit_done,events=count,x=mx,y=my))+"\n")
                    motion_pending=None
    finally:
        pool.shutdown(wait=True,cancel_futures=True)
        if mouse:mouse.close()
        if latency_log:latency_log.close()
        output.stop();backend.close()

if __name__=='__main__':main()
