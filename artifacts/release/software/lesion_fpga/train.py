import argparse
import json
import random
import time
from pathlib import Path
import numpy as np
import torch
from torch.utils.data import DataLoader, TensorDataset
from .common import ROOT, read_json, write_json, event, environment
from .dataset import audit, cache
from .model import SmallUNet


def loss_fn(logits, target, valid):
    bce = (torch.nn.functional.binary_cross_entropy_with_logits(logits, target, reduction='none')*valid).sum()/valid.sum()
    p = logits.sigmoid()*valid; t=target*valid
    dice = (2*(p*t).sum((1,2,3))+1)/(p.sum((1,2,3))+t.sum((1,2,3))+1)
    return bce + 1-dice.mean()


def main():
    p=argparse.ArgumentParser(); p.add_argument('--config', default=str(ROOT/'configs/default.json'))
    p.add_argument('--epochs', type=int); p.add_argument('--limit', type=int, default=0)
    p.add_argument('--run', default='baseline'); p.add_argument('--resume', action='store_true')
    args=p.parse_args(); cfg=read_json(args.config); tc=cfg['train']; seed=cfg['seed']
    random.seed(seed); np.random.seed(seed); torch.manual_seed(seed); torch.set_num_threads(tc['threads'])
    manifest_path=ROOT/'artifacts/data_manifest.json'
    manifest=read_json(manifest_path) if manifest_path.exists() else audit(seed=seed)
    size=cfg['input_size']; gaussian=cfg['preprocess']['gaussian']
    cp=ROOT/f'artifacts/cache/isic_{size}_g{int(gaussian)}.npz'
    if not cp.exists(): cache(manifest,size,gaussian)
    data=np.load(cp); indexed={v:i for i,v in enumerate(data['ids'])}
    def ds(split):
        idx=[indexed[r['id']] for r in manifest['rows'] if r['split']==split]
        if args.limit: idx=idx[:args.limit]
        return TensorDataset(*(torch.from_numpy(data[k][idx].astype(np.float32)) for k in ['images','masks','valids']))
    train=DataLoader(ds('train'), batch_size=tc['batch_size'], shuffle=True, num_workers=0)
    validation=DataLoader(ds('validation'), batch_size=tc['batch_size'], num_workers=0)
    model=SmallUNet(cfg['channels']); opt=torch.optim.Adam(model.parameters(),lr=tc['learning_rate'])
    out=ROOT/'artifacts/checkpoints'/args.run; out.mkdir(parents=True,exist_ok=True)
    start, best, stale=0, -1., 0
    if args.resume:
        checkpoint=torch.load(out/'last.pt',map_location='cpu',weights_only=False)
        if checkpoint['config'] != cfg: raise ValueError('Resume config mismatch')
        model.load_state_dict(checkpoint['model']); opt.load_state_dict(checkpoint['optimizer'])
        start=checkpoint['epoch']+1; best=checkpoint['best']; stale=checkpoint['stale']
        torch.set_rng_state(checkpoint['rng']); random.setstate(checkpoint['python_rng']); np.random.set_state(checkpoint['numpy_rng'])
    event('train_start',run=args.run,config=cfg,environment=environment(),limited=bool(args.limit))
    for epoch in range(start,args.epochs or tc['epochs']):
        tick=time.perf_counter(); model.train(); losses=[]
        for x,y,v in train:
            # Geometrically consistent flips; no interpolation changes to masks.
            if random.random()<.5: x,y,v=(a.flip(-1) for a in (x,y,v))
            if random.random()<.5: x,y,v=(a.flip(-2) for a in (x,y,v))
            opt.zero_grad(set_to_none=True); loss=loss_fn(model(x/255),y,v)
            loss.backward(); opt.step(); losses.append(loss.item())
        model.eval(); scores=[]; ious=[]
        with torch.inference_mode():
            for x,y,v in validation:
                pr=(model(x/255)>=0)*v; gt=y*v
                intersection=(pr*gt).sum((1,2,3)); denom=(pr+gt).sum((1,2,3)); union=denom-intersection
                scores.extend(torch.where(denom>0,2*intersection/denom,1).tolist())
                ious.extend(torch.where(union>0,intersection/union,1).tolist())
        score=float(np.mean(scores)); improved=score>best
        stale=0 if improved else stale+1; best=max(best,score)
        snapshot={'model':model.state_dict(),'optimizer':opt.state_dict(),'epoch':epoch,'best':best,'stale':stale,
                  'config':cfg,'rng':torch.get_rng_state(),'python_rng':random.getstate(),'numpy_rng':np.random.get_state(),
                  'limited_training':bool(args.limit)}
        torch.save(snapshot,out/'last.pt')
        if improved: torch.save(snapshot,out/'best.pt')
        row={'epoch':epoch+1,'loss':float(np.mean(losses)),'validation_dice':score,'validation_iou':float(np.mean(ious)),
             'seconds':time.perf_counter()-tick,'best':best}
        with (out/'history.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(row)+'\n')
        print(json.dumps(row),flush=True)
        write_json(ROOT/'record/training_latest.json',{'run':args.run,'limited':bool(args.limit),**row})
        if stale>=tc['patience']: break
    event('train_finished',run=args.run,best_validation_dice=best,epochs=epoch+1)


if __name__=='__main__': main()
