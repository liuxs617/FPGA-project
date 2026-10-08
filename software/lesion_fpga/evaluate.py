"""Validation selects policy; test only consumes a frozen policy."""
import argparse
from dataclasses import asdict
import itertools
import time
from pathlib import Path
import numpy as np
from PIL import Image
import torch
import cv2
from .common import ROOT,read_json,write_json,environment,event
from .model import SmallUNet
from .quantization import ModelPackage,IntegerBackend,threshold_code
from .backends import NativeBackend,PynqBackend
from .imaging import load_rgb,letterbox,fit_mask,restore,overlap,morphology,components_and_fill

def main():
    p=argparse.ArgumentParser();p.add_argument('--split',choices=['validation','test'],default='validation')
    p.add_argument('--model',default=str(ROOT/'artifacts/models/baseline'))
    p.add_argument('--checkpoint',default=str(ROOT/'artifacts/checkpoints/baseline/best.pt'))
    p.add_argument('--backend',choices=['native','integer','fpga'],default='native')
    p.add_argument('--bitstream',default=str(ROOT/'artifacts/hardware/lesion.bit'))
    p.add_argument('--limit',type=int,default=0);args=p.parse_args()
    package=ModelPackage(args.model);state=torch.load(args.checkpoint,map_location='cpu',weights_only=False)
    from .common import sha256
    if sha256(args.checkpoint)!=package.meta['checkpoint_sha256']:raise ValueError('Checkpoint/model package mismatch')
    torch.set_num_threads(state['config']['train']['threads']);fp=SmallUNet(package.meta['channels']);fp.load_state_dict(state['model']);fp.eval()
    backend=NativeBackend(package,ROOT/'build/native/lesion.dll') if args.backend=='native' else IntegerBackend(package) if args.backend=='integer' else PynqBackend(package,args.bitstream)
    manifest=read_json(ROOT/'artifacts/data_manifest.json');rows=[r for r in manifest['rows'] if r['split']==args.split]
    if args.limit:rows=rows[:args.limit]
    policy_path=Path(args.model)/'policy.json';candidates=[]
    if args.split=='validation':
        for threshold in [.35,.4,.45,.5,.55,.6,.65]:
            for opening,closing,largest,fill in itertools.product([False,True],repeat=4):
                candidates.append(dict(threshold=threshold,opening=opening,closing=closing,largest=largest,fill=fill))
    else:
        saved=read_json(policy_path)
        if saved['model_id']!=package.meta['model_id'] or saved['limited']:raise ValueError('No complete frozen validation policy')
        candidates=[saved['parameters']]
    totals=np.zeros((len(candidates),2));records=[];float_times=[];integer_times=[];start=time.perf_counter()
    try:
        with torch.inference_mode():
            for index,row in enumerate(rows):
                rgb,g=letterbox(load_rgb(ROOT/row['image']),package.meta['input_size'])
                with Image.open(ROOT/row['mask']) as gt:truth=np.asarray(gt.convert('L'))>0
                valid=g.valid()
                # Exact original-size nearest-neighbour metric without resizing every candidate.
                indices=np.arange(g.size*g.size,dtype=np.int32).reshape(g.size,g.size)
                mapped=cv2.resize(indices[g.top:g.top+g.height,g.left:g.left+g.width],(g.original_w,g.original_h),interpolation=cv2.INTER_NEAREST)
                counts=np.bincount(mapped.ravel(),minlength=g.size*g.size)
                positives=np.bincount(mapped[truth],minlength=g.size*g.size);gt_count=int(truth.sum())
                def score_original(mask):
                    fg=mask.astype(bool).ravel();pred=int(counts[fg].sum());intersection=int(positives[fg].sum())
                    total=pred+gt_count;union=total-intersection
                    return {'dice':2*intersection/total if total else 1.,'iou':intersection/union if union else 1.}
                t=time.perf_counter();q,processed=backend.infer(rgb,package.meta['gaussian']);integer_times.append((time.perf_counter()-t)*1000)
                t=time.perf_counter();f=fp(torch.from_numpy(processed.transpose(2,0,1).copy()).float()[None]/255)[0,0].numpy();float_times.append((time.perf_counter()-t)*1000)
                fscore=score_original((f>=0)&valid);qscore=score_original((q>=0)&valid)
                scores=[]
                for j,c in enumerate(candidates):
                    mask=morphology((q>=threshold_code(c['threshold'],package.tensors['head']['scale']))&valid,c['opening'],c['closing'])
                    mask,_=components_and_fill(mask,valid,c['largest'],c['fill'])
                    score=score_original(mask);totals[j]+=[score['dice'],score['iou']];scores.append(score)
                records.append({'id':row['id'],'fp32_raw':fscore,'int8_raw':qscore,'policies':scores})
                if (index+1)%20==0:print(f'{args.split}: {index+1}/{len(rows)}',flush=True)
    finally:backend.close()
    best=int(np.argmax(totals[:,0]));chosen=candidates[best]
    if args.split=='validation':write_json(policy_path,{'model_id':package.meta['model_id'],'limited':bool(args.limit),'parameters':chosen,'selection':'mean original-size validation Dice, deterministic candidate order'})
    for r in records:r['int8_post']=r.pop('policies')[best]
    average=lambda key:{m:float(np.mean([r[key][m] for r in records])) for m in ['dice','iou']}
    fmean,qmean=average('fp32_raw'),average('int8_raw')
    report={'model_id':package.meta['model_id'],'split':args.split,'count':len(rows),'limited':bool(args.limit),
            'backend':backend.name,'environment':environment(),'cpu_threads':state['config']['train']['threads'],
            'fp32_raw':fmean,'int8_raw':qmean,'int8_post':average('int8_post'),'policy':chosen,
            'quantization_gate_pass':all(fmean[k]-qmean[k]<=.01 for k in ['dice','iou']),
            'integer_execution_ms_mean':float(np.mean(integer_times)),'fp32_execution_ms_mean':float(np.mean(float_times)),
            'timing_note':'Development measurements include backend-specific preprocessing/transfer overhead; not board acceleration claim. No HDMI timing included.',
            'elapsed_seconds':time.perf_counter()-start,'per_image':records}
    write_json(ROOT/f'artifacts/evaluation_{args.split}.json',report)
    event('evaluation',split=args.split,count=len(rows),fp32=fmean,int8=qmean,post=report['int8_post'],gate=report['quantization_gate_pass'])
    print({k:v for k,v in report.items() if k!='per_image'})

if __name__=='__main__':main()
