"""Portable NumPy FP32 baseline, including on ARM without a PyTorch wheel."""
import numpy as np
from .common import sha256
from .imaging import gaussian_u8,morphology,moments

class FloatBackend:
    name='cpu-fp32-numpy'
    def __init__(self,package):
        self.package=package;path=package.directory/'fp32.npz'
        if sha256(path)!=package.meta['fp32_sha256']:raise ValueError('FP32 weights checksum mismatch')
        self.weights=np.load(path)
    def infer(self,rgb,gaussian=False,trace=False):
        if gaussian!=self.package.meta['gaussian']:raise ValueError('Preprocessing mismatch')
        rgb=gaussian_u8(rgb) if gaussian else rgb
        values={'input':rgb.astype(np.float32).transpose(2,0,1)/255}
        for n in self.package.meta['nodes']:
            x=values[n['inputs'][0]];c,h,w=x.shape;name=n['name']
            if n['op']=='conv':
                k=n['k'];pad=np.pad(x,((0,0),(k//2,k//2),(k//2,k//2)))
                windows=np.lib.stride_tricks.sliding_window_view(pad,(k,k),axis=(1,2))
                cols=windows.transpose(1,2,0,3,4).reshape(h*w,c*k*k)
                out=(cols @ self.weights[name+'.weight'].reshape(n['co'],-1).T+self.weights[name+'.bias']).reshape(h,w,n['co']).transpose(2,0,1)
                if n['relu']:out=np.maximum(out,0)
            elif n['op']=='pool':out=x.reshape(c,h//2,2,w//2,2).max((2,4))
            elif n['op']=='up':out=x.repeat(2,1).repeat(2,2)
            else:out=np.concatenate([values[s] for s in n['inputs']],axis=0)
            values[name]=out
        return (values if trace else values['head'][0]),rgb
    def postprocess(self,logits,threshold,valid,opening,closing):
        value=-np.inf if threshold==0 else np.inf if threshold==1 else np.log(threshold/(1-threshold))
        return morphology((logits>=value)&valid,opening,closing)*valid
    def moments(self,mask):return moments(mask)
    def close(self):self.weights.close()
