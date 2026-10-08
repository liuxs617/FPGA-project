import argparse
import hashlib
import numpy as np
import torch
from .common import ROOT, read_json, write_json, sha256, event
from .model import SmallUNet, graph
from .quantization import multiplier, round_away, SHIFT, OP


def main():
    cli=argparse.ArgumentParser();cli.add_argument('--checkpoint',default=str(ROOT/'artifacts/checkpoints/baseline/best.pt'))
    cli.add_argument('--output',default=str(ROOT/'artifacts/models/baseline'));cli.add_argument('--calibration',type=int,default=64)
    args=cli.parse_args(); state=torch.load(args.checkpoint,map_location='cpu',weights_only=False)
    cfg=state['config'];torch.set_num_threads(cfg['train']['threads']);model=SmallUNet(cfg['channels'])
    model.load_state_dict(state['model']);model.eval();size=cfg['input_size']
    data=np.load(ROOT/f"artifacts/cache/isic_{size}_g{int(cfg['preprocess']['gaussian'])}.npz")
    manifest=read_json(ROOT/'artifacts/data_manifest.json');ids={v:i for i,v in enumerate(data['ids'])}
    rows=[r for r in manifest['rows'] if r['split']=='train'][:args.calibration]
    maxima={}
    with torch.inference_mode():
        for start in range(0,len(rows),8):
            x=torch.from_numpy(data['images'][[ids[r['id']] for r in rows[start:start+8]]].astype(np.float32))/255
            for name,value in model(x,trace=True).items():
                maxima[name]=max(maxima.get(name,0),float(value.abs().max()))
    nodes=graph(cfg['channels']);tensors={'input':{'shape':[3,size,size],'scale':1/127,'offset':0}}
    offset=3*size*size
    def alloc(count):
        nonlocal offset
        offset=(offset+63)//64*64;start=offset;offset+=count;return start
    params=[0]*64; weight_blocks=[]
    for node in nodes:
        src=tensors[node['inputs'][0]];ci,h,w=src['shape'];op=node['op'];name=node['name']
        if op=='conv':
            conv=model.layers[name];wf=conv.weight.detach().numpy();sf=max(float(np.abs(wf).max())/127,1e-9)
            weight=np.clip(round_away(wf/sf),-127,127).astype(np.int8)
            bias64=round_away(conv.bias.detach().numpy().astype(np.float64)/(src['scale']*sf)).astype(np.int64)
            bound=ci*node['k']**2*128*127+int(np.max(np.abs(bias64)))
            if bound>=2**31:raise OverflowError(f'INT32 accumulator overflow: {name}')
            outscale=max(maxima[name]/127,1e-7);co=node['co']
            node.update(weight_offset=alloc(weight.size),weight_count=weight.size,weight_shape=list(weight.shape),
                        bias_offset=len(params),multiplier=multiplier(src['scale']*sf/outscale),weight_scale=sf,
                        accumulator_bound=bound)
            params.extend(bias64.astype(np.int32).tolist());weight_blocks.append((node['weight_offset'],weight.tobytes()))
            shape=[co,h,w];scale=outscale
        elif op=='pool':shape=[ci,h//2,w//2];scale=src['scale']
        elif op=='up':shape=[ci,h*2,w*2];scale=src['scale']
        else:
            other=tensors[node['inputs'][1]];scale=max(src['scale'],other['scale'])
            shape=[ci+other['shape'][0],h,w]
            node['multipliers']=[multiplier(tensors[s]['scale']/scale) for s in node['inputs']]
        tensors[name]={'shape':shape,'scale':scale,'offset':alloc(int(np.prod(shape)))}
        # Descriptor dimensions refer to input for pool/up, output for cat/conv.
        desc=[OP[op],h,w,ci,shape[0],node.get('k',0),src['offset'],0,tensors[name]['offset'],
              node.get('weight_offset',0),node.get('bias_offset',0),node.get('multiplier',0),SHIFT,
              int(node.get('relu',False)),0,0]
        if op=='cat':
            desc[7]=tensors[node['inputs'][1]]['offset'];desc[13]=other['shape'][0]
            desc[11],desc[14]=node['multipliers']
        node['descriptor']=desc
    # Scratch used by preprocess, postprocess and final moments. All byte offsets aligned.
    scratch={n:alloc(count) for n,count in [('rgb',size*size*3),('processed_rgb',size*size*3),
                 ('mask0',size*size),('mask1',size*size),('valid',size*size)]}
    arena=bytearray(offset)
    for off,blob in weight_blocks:arena[off:off+len(blob)]=blob
    params=np.asarray(params,dtype='<i4');out=__import__('pathlib').Path(args.output);out.mkdir(parents=True,exist_ok=True)
    (out/'arena.bin').write_bytes(arena);params.tofile(out/'params.bin')
    np.savez(out/'fp32.npz',**{name+'.'+kind: getattr(model.layers[name],kind).detach().numpy()
                            for name in model.layers for kind in ['weight','bias']})
    meta={'abi':1,'model_id':sha256(args.checkpoint)[:16],'checkpoint_sha256':sha256(args.checkpoint),
          'limited_training':state.get('limited_training',False),'gaussian':cfg['preprocess']['gaussian'],
          'input_size':size,'channels':cfg['channels'],'nodes':nodes,'tensors':tensors,'scratch':scratch,
          'arena_bytes':offset,'arena_sha256':hashlib.sha256(arena).hexdigest(),
          'params_sha256':hashlib.sha256(params.tobytes()).hexdigest(),'fp32_sha256':sha256(out/'fp32.npz'),'calibration_ids':[r['id'] for r in rows],
          'quantization':'signed int8, symmetric, zero point 0; int32 accumulate; Q24 multiplier; half away from zero',
          'training_epoch':state['epoch']+1,'validation_dice_fp32_training_scale':state['best']}
    write_json(out/'model.json',meta)
    write_json(ROOT/'record/model_budget.json',{'arena_bytes':offset,'weight_bytes':sum(len(b) for _,b in weight_blocks),
            'feature_bytes':sum(int(np.prod(t['shape'])) for t in tensors.values()),
            'macs':sum(int(np.prod(tensors[n['name']]['shape']))*n['weight_shape'][1]*n['k']**2 for n in nodes if n['op']=='conv'),
            'note':'Allocation budget, not measured FPGA resource use or bandwidth'})
    event('model_export',model=meta['model_id'],output=str(out),calibration_count=len(rows))
    print(out)


if __name__=='__main__':main()
