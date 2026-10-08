"""ABI 1 integer arithmetic shared with HLS; no PyTorch dependency on board."""
from pathlib import Path
import hashlib
import math
import numpy as np
from .common import read_json

ABI = 1
OP = {'conv': 1, 'pool': 2, 'up': 3, 'cat': 4, 'threshold': 5,
      'erode': 6, 'dilate': 7, 'preprocess': 8, 'moments': 9}
SHIFT = 24


def round_away(x):
    return np.copysign(np.floor(np.abs(x)+.5), x)


def requant(x, multiplier, shift=SHIFT, relu=False):
    x = np.asarray(x, dtype=np.int64)*np.int64(multiplier)
    y = (np.abs(x)+(1 << (shift-1))) >> shift
    y = np.where(x < 0, -y, y)
    return np.clip(y, 0 if relu else -128, 127).astype(np.int8)


def multiplier(ratio):
    value = int(math.floor(ratio*(1 << SHIFT)+.5))
    if not 0 < value < 2**31:
        raise ValueError(f'Requant multiplier out of int32 range: {ratio}')
    return value


def threshold_code(probability, scale):
    if not 0 <= probability <= 1: raise ValueError('Threshold outside [0,1]')
    if probability == 0: return -129
    if probability == 1: return 128
    return max(-129, min(128, math.ceil(math.log(probability/(1-probability))/scale)))


def conv_reference(x, weight, bias, mul, relu):
    # Integer dot product through numpy, INT32 bounds are checked at export.
    ci, h, w = x.shape; co, _, k, _ = weight.shape
    padded=np.pad(x.astype(np.int32), ((0,0),(k//2,k//2),(k//2,k//2)))
    windows=np.lib.stride_tricks.sliding_window_view(padded,(k,k),axis=(1,2))
    cols=windows.transpose(1,2,0,3,4).reshape(h*w,ci*k*k)
    acc=cols @ weight.astype(np.int32).reshape(co,-1).T
    acc=acc.astype(np.int64)+bias.astype(np.int64)
    return requant(acc,mul,relu=relu).reshape(h,w,co).transpose(2,0,1)


class ModelPackage:
    def __init__(self, directory):
        self.directory=Path(directory); self.meta=read_json(self.directory/'model.json')
        if self.meta['abi'] != ABI: raise ValueError('Model ABI mismatch')
        self.blob=(self.directory/'arena.bin').read_bytes()
        if hashlib.sha256(self.blob).hexdigest()!=self.meta['arena_sha256']:
            raise ValueError('Model arena checksum mismatch')
        self.params=np.fromfile(self.directory/'params.bin',dtype='<i4')
        if hashlib.sha256(self.params.tobytes()).hexdigest()!=self.meta['params_sha256']:
            raise ValueError('Model params checksum mismatch')
        if len(self.blob)!=self.meta['arena_bytes'] or len(self.params)<64:
            raise ValueError('Invalid model allocation')
        self.tensors=self.meta['tensors']
        for t in self.tensors.values():
            if t['offset']<0 or t['offset']+int(np.prod(t['shape']))>len(self.blob):
                raise ValueError('Tensor outside arena')
        if not 8 <= self.meta['input_size'] <= 256 or self.meta['input_size']%8:
            raise ValueError('Unsupported input size')
        seen={'input'}
        for n in self.meta['nodes']:
            if n['op'] not in OP or not all(s in seen for s in n['inputs']):raise ValueError('Invalid graph order')
            d=n['descriptor']
            if len(d)!=16 or d[0]!=OP[n['op']] or d[6]!=self.tensors[n['inputs'][0]]['offset'] or d[8]!=self.tensors[n['name']]['offset']:
                raise ValueError('Descriptor/tensor mismatch')
            if n['op']=='conv':
                if n['weight_offset']<0 or n['weight_offset']+n['weight_count']>len(self.blob):raise ValueError('Weight range invalid')
                if n['bias_offset']<64 or n['bias_offset']+n['co']>len(self.params):raise ValueError('Bias range invalid')
            seen.add(n['name'])

    def tensor(self, arena, name):
        t=self.tensors[name]
        return arena[t['offset']:t['offset']+int(np.prod(t['shape']))].reshape(t['shape'])


class IntegerBackend:
    name='integer-reference'
    def __init__(self, package):
        self.package=package

    def infer(self, rgb, gaussian=False, trace=False):
        from .imaging import gaussian_u8
        p=self.package
        if gaussian != p.meta['gaussian']:
            raise ValueError('Preprocessing differs from calibrated model; select a matching model package')
        rgb=gaussian_u8(rgb) if gaussian else rgb
        x=((rgb.astype(np.int32)*127+127)//255).astype(np.int8).transpose(2,0,1)
        values={'input':x}
        arena=np.frombuffer(p.blob,dtype=np.int8)
        for n in p.meta['nodes']:
            source=values[n['inputs'][0]]; op=n['op']
            if op=='conv':
                weights=arena[n['weight_offset']:n['weight_offset']+n['weight_count']].reshape(n['weight_shape'])
                b=p.params[n['bias_offset']:n['bias_offset']+n['co']]
                out=conv_reference(source,weights,b,n['multiplier'],n['relu'])
            elif op=='pool':
                c,h,w=source.shape;out=source.reshape(c,h//2,2,w//2,2).max((2,4))
            elif op=='up': out=source.repeat(2,1).repeat(2,2)
            elif op=='cat':
                out=np.concatenate([requant(values[s],m) for s,m in zip(n['inputs'],n['multipliers'])],axis=0)
            else: raise ValueError(op)
            values[n['name']]=out
        return (values if trace else values['head'][0]),rgb

    def postprocess(self, logits, threshold, valid, opening, closing):
        from .imaging import morphology
        return morphology(((logits >= threshold_code(threshold,self.package.tensors['head']['scale'])) & valid),opening,closing)*valid

    def moments(self, mask):
        from .imaging import moments
        return moments(mask)

    def close(self): pass
