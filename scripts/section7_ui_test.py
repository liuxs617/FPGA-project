"""Board-side section 7 automation through a temporary evdev mouse.

Runs the real HDMI application and real FPGA backend. It does not emulate
inference. Physical mouse unplug/replug and visible capture remain manual.
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image
from evdev import UInput, InputDevice, ecodes as E
from lesion_fpga.common import ROOT, read_json, write_json
from lesion_fpga.ui import button_boxes, image_rect, pick_result
from lesion_fpga.imaging import Geometry, components_and_fill, restore
from lesion_fpga.quantization import ModelPackage, IntegerBackend

p=argparse.ArgumentParser()
p.add_argument('--bitstream',required=True)
p.add_argument('--output',default='record/section7_20260930')
p.add_argument('--inject-mouse',help='Observed physical evdev path when this kernel lacks uinput')
a=p.parse_args()
out=Path(a.output).resolve();out.mkdir(parents=True,exist_ok=True)
cases=out/'cases';cases.mkdir(exist_ok=True)
source=sorted((ROOT/'data/demo').glob('*.jpg'))[0]
with Image.open(source) as im:
    rgb=im.convert('RGB');rgb.save(cases/'00_landscape.jpg')
    rgb.transpose(Image.Transpose.ROTATE_90 if hasattr(Image,'Transpose') else Image.ROTATE_90).save(cases/'01_portrait.jpg')
    rgb.save(cases/'02_unlabelled.jpg')
gt=source.with_name(source.stem+'_Segmentation.png')
if not gt.exists():
    matches=list((ROOT/'data/demo').rglob(source.stem+'_Segmentation.png'))
    if matches:gt=matches[0]
if gt.exists():
    with Image.open(gt) as im:
        im.save(cases/'00_landscape_Segmentation.png')
        im.transpose(Image.Transpose.ROTATE_90 if hasattr(Image,'Transpose') else Image.ROTATE_90).save(cases/'01_portrait_Segmentation.png')
(cases/'03_broken.jpg').write_bytes(b'Intentional corrupt JPEG for section 7')
event_path=ROOT/'record/events.jsonl'
offset=event_path.stat().st_size if event_path.exists() else 0
seen=[];checks=[];proc=None
mouse=InputDevice(a.inject_mouse) if a.inject_mouse else UInput({E.EV_REL:[E.REL_X,E.REL_Y],E.EV_KEY:[E.BTN_LEFT]},name='Section7 test mouse')
mouse_path=a.inject_mouse if a.inject_mouse else mouse.device.path
# Flush any unfinished packet from an interrupted injector before app opens.
mouse.write(E.EV_SYN,E.SYN_REPORT,0)
log=(out/'app.log').open('w')
xy=[640,360]

def refresh():
    global offset
    if event_path.exists():
        with event_path.open() as f:
            f.seek(offset)
            while True:
                start=f.tell();line=f.readline()
                if not line or not line.endswith('\n'):
                    offset=start;break
                try:seen.append(json.loads(line))
                except json.JSONDecodeError:break
                offset=f.tell()
    return seen

def wait(predicate,label,timeout=180):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        refresh()
        value=predicate()
        if value:return value
        if proc.poll() is not None:raise RuntimeError(f'App exited while waiting for {label}: {proc.returncode}')
        time.sleep(.05)
    raise TimeoutError(label)

def point(x,y):
    mouse.write(E.EV_REL,E.REL_X,int(x)-xy[0]);mouse.write(E.EV_REL,E.REL_Y,int(y)-xy[1]);mouse.write(E.EV_SYN,E.SYN_REPORT,0)
    xy[:]=[int(x),int(y)]
    mouse.write(E.EV_KEY,E.BTN_LEFT,1);mouse.write(E.EV_SYN,E.SYN_REPORT,0)
    mouse.write(E.EV_KEY,E.BTN_LEFT,0);mouse.write(E.EV_SYN,E.SYN_REPORT,0)

def click(key):
    refresh();start=len(seen)
    box=next(b for k,b,_ in button_boxes() if k==key)
    point((box[0]+box[2])//2,(box[1]+box[3])//2)
    return wait(lambda:next((v for v in seen[start:] if v['event']=='ui_action' and v['key']==key),None),key)

def completed(version=None):
    if version is None:
        refresh();version=max(v['parameter_version'] for v in seen if v['event']=='frame_requested')
    return wait(lambda:next((v for v in reversed(seen) if v['event']=='frame_complete' and v['parameter_version']==version),None),'frame complete')

def check(name,condition,**details):
    entry=dict(name=name,passed=bool(condition),**details);checks.append(entry)
    write_json(out/'checks.json',checks)
    print(json.dumps(entry),flush=True)
    if not condition:raise AssertionError(name)

def save():
    refresh();start=len(seen);click('save')
    info=wait(lambda:next((v for v in seen[start:] if v['event']=='result_saved'),None),'saved result')
    return Path(info['folder']),read_json(Path(info['folder'])/'result.json')

def pick_checks(folder,result,label):
    with Image.open(result['path']) as im:rgb=np.asarray(im.convert('RGB'))
    with Image.open(folder/'mask.png') as im:mask=np.asarray(im)>0
    minimal={'rgb':rgb,'original_mask':mask}
    rx,ry,rw,rh=image_rect(rgb.shape,(468,397,884,612))
    for expected in (True,False):
        target=next(((x,y) for y in range(ry,ry+rh,2) for x in range(rx,rx+rw,2)
                     if pick_result(minimal,x,y,0)==expected),None)
        if target is None:
            checks.append(dict(name=label+'_selection_'+str(expected),passed=None,reason='No such region in this mask'));continue
        refresh();start=len(seen);point(*target)
        action=wait(lambda:next((v for v in seen[start:] if v['event']=='ui_action'),None),'selection')
        check(label+'_selection_'+str(expected),action['selected']==expected)
    refresh();start=len(seen);point(461,365)
    action=wait(lambda:next((v for v in seen[start:] if v['event']=='ui_action'),None),'padding click')
    check(label+'_padding_not_selected',action['selected'] is False)

try:
    time.sleep(.3)
    cmd=[sys.executable,'-u','-m','lesion_fpga.app','--backend','fpga','--bitstream',str(Path(a.bitstream).resolve()),
         '--images',str(cases),'--output',str(out/'saved'),'--mouse',mouse_path]
    proc=subprocess.Popen(cmd,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
    wait(lambda:any(v['event']=='frame_requested' for v in seen),'startup')
    first=completed();check('startup_fpga_frame',first['backend']=='fpga-int8')
    folder,result=save();pick_checks(folder,result,'landscape')
    for key in ('threshold_up','opening','closing','largest','fill'):
        action=click(key);frame=completed(action['parameter_version'])
        check(key+'_reuses_network',frame['timing']['network_reused'])
    frame=completed()
    for key in ('alpha','view','view','view'):
        action=click(key);time.sleep(.2);refresh()
        latest=[v for v in seen if v['event']=='frame_complete'][-1]
        check(key+'_redraw_only',latest['frame_id']==frame['frame_id'] and action['frame_id']==frame['frame_id'])
    action=click('run');frame=completed(action['parameter_version'])
    check('run_forces_inference',not frame['timing']['network_reused'])
    for i in range(10):action=click('next' if i%2==0 else 'threshold_up')
    frame=completed(action['parameter_version'])
    check('burst_latest_request_only',frame['path']==action['path'] and frame['parameters']==action['parameters'])
    action=click('reset');frame=completed(action['parameter_version'])
    policy=read_json(ROOT/'artifacts/models/baseline/policy.json')['parameters']
    check('reset_frozen_policy',all(frame['parameters'][k]==v for k,v in policy.items()) and not frame['timing']['network_reused'])
    folder,result=save();pick_checks(folder,result,'portrait')
    for key,value in (('threshold_down',0.0),('threshold_up',1.0)):
        for _ in range(20):action=click(key)
        frame=completed(action['parameter_version']);folder,result=save()
        check('threshold_'+str(value),result['parameters']['threshold']==value)
        # At endpoints the integer comparison is independent of logit values:
        # threshold 0 accepts all int8 logits, threshold 1 rejects all of them.
        g=Geometry(**result['geometry']);par=result['parameters']
        reference=IntegerBackend(ModelPackage(ROOT/'artifacts/models/baseline'))
        expected=reference.postprocess(np.zeros((g.size,g.size),np.int8),value,g.valid(),par['opening'],par['closing'])
        expected,_=components_and_fill(expected,g.valid(),par['largest'],par['fill'])
        with Image.open(folder/'mask.png') as im:actual=np.asarray(im)>0
        check('threshold_'+str(value)+'_integer_reference',
              np.array_equal(actual,restore(expected,g).astype(bool)) and result['metrics']['area_px2']==int(expected.sum()))
        if value==1:
            check('empty_mask_no_crash',result['metrics']['area_px2']==0)
    action=click('reset');completed(action['parameter_version'])
    action=click('next');completed(action['parameter_version']);folder,result=save()
    check('unlabelled_accuracy_na',result['accuracy'] is None)
    refresh();start=len(seen);click('next')
    wait(lambda:any(v['event']=='runtime_error' for v in seen[start:]),'corrupt JPEG error')
    action=click('save');check('corrupt_image_clears_result',action['frame_id'] is None)
    action=click('next');frame=completed(action['parameter_version'])
    check('recover_after_corrupt_image',Path(frame['path']).name=='00_landscape.jpg')
    click('quit');proc.wait(timeout=60);check('clean_exit',proc.returncode==0)
finally:
    if proc is not None and proc.poll() is None:
        # SIGINT allows the application's finally block to stop HDMI and close.
        proc.send_signal(2)
        try:proc.wait(timeout=60)
        except subprocess.TimeoutExpired:print('App did not exit; do not start another overlay.',flush=True)
    refresh();write_json(out/'events.json',seen);write_json(out/'checks.json',checks)
    mouse.close();log.close()
