import ctypes
import time
import numpy as np
from .quantization import OP, threshold_code


class ArenaBackend:
    """Shared PL/native scheduling. Never silently substitutes the reference backend."""
    def _put(self, offset, x):
        flat=np.ascontiguousarray(x).view(np.int8).ravel()
        self.arena[offset:offset+len(flat)]=flat

    def _descriptor(self, op, source, output=0, second=0, extra=0):
        s=self.package.meta['input_size']
        return [OP[op],s,s,1,1,0,source,second,output,0,0,0,24,extra,0,0]

    def infer(self, rgb, gaussian=False, trace=False):
        p=self.package;s=p.meta['input_size'];sc=p.meta['scratch']
        if rgb.shape!=(s,s,3):raise ValueError('Incorrect input dimensions')
        if gaussian!=p.meta['gaussian']:raise ValueError('Preprocessing/model mismatch')
        self._put(sc['rgb'],rgb.transpose(2,0,1))
        desc=self._descriptor('preprocess',sc['rgb'],p.tensors['input']['offset'],sc['processed_rgb'],int(gaussian))
        desc[3]=desc[4]=3;self.execute(desc)
        self.sync_read()
        processed=self.arena[sc['processed_rgb']:sc['processed_rgb']+s*s*3].view(np.uint8).reshape(3,s,s).transpose(1,2,0).copy()
        values={'input':p.tensor(self.arena,'input').copy()} if trace else {}
        for node in p.meta['nodes']:
            self.execute(node['descriptor'])
            if trace:
                self.sync_read();values[node['name']]=p.tensor(self.arena,node['name']).copy()
        self.sync_read()
        return (values if trace else p.tensor(self.arena,'head')[0].copy()),processed

    def postprocess(self, logits, threshold, valid, opening, closing):
        p=self.package;sc=p.meta['scratch'];self._put(p.tensors['head']['offset'],logits)
        self._put(sc['valid'],valid.astype(np.uint8))
        code=threshold_code(threshold,p.tensors['head']['scale'])
        self.execute(self._descriptor('threshold',p.tensors['head']['offset'],sc['mask0'],sc['valid'],code))
        src,dst=sc['mask0'],sc['mask1']
        for op in (['erode','dilate'] if opening else [])+(['dilate','erode'] if closing else []):
            self.execute(self._descriptor(op,src,dst));src,dst=dst,src
        self.sync_read();s=p.meta['input_size']
        return self.arena[src:src+s*s].reshape(s,s).astype(np.uint8)*valid

    def moments(self, mask):
        off=self.package.meta['scratch']['mask0'];self._put(off,mask.astype(np.uint8))
        self.execute(self._descriptor('moments',off));self.sync_read()
        vals=self.params[32:44].astype(np.uint32).astype(np.uint64)
        return [int(vals[2*i] | (vals[2*i+1]<<np.uint64(32))) for i in range(6)]

    def close(self):pass


class NativeBackend(ArenaBackend):
    name='native-cpp-reference'
    def __init__(self, package, library):
        self.package=package;self.arena=np.frombuffer(package.blob,dtype=np.int8).copy();self.params=package.params.copy()
        self.lib=ctypes.CDLL(str(library));self.fn=self.lib.lesion_accel
        self.fn.argtypes=[ctypes.POINTER(ctypes.c_int8),ctypes.POINTER(ctypes.c_int32)];self.fn.restype=ctypes.c_int
    def execute(self, desc):
        self.params[:16]=desc
        result=self.fn(self.arena.ctypes.data_as(ctypes.POINTER(ctypes.c_int8)),self.params.ctypes.data_as(ctypes.POINTER(ctypes.c_int32)))
        if result:raise RuntimeError(f'Native kernel error {result}')
    def sync_read(self):pass


class PynqBackend(ArenaBackend):
    name='fpga-int8'
    def __init__(self, package, bitstream, timeout=30):
        from pathlib import Path
        from .common import read_json,sha256
        bitstream=Path(bitstream)
        manifest=read_json(bitstream.parent/'hardware_manifest.json')
        if manifest['abi']!=package.meta['abi']:raise ValueError('Hardware/model ABI mismatch')
        for path in [bitstream,bitstream.with_suffix('.hwh')]:
            if manifest['files'].get(path.name)!=sha256(path):raise ValueError('Hardware artifact checksum mismatch: '+path.name)
        # Imports fail explicitly on a development PC; no CPU fallback.
        from pynq import Overlay, allocate
        import pynq.lib.video  # register hierarchy/IP drivers before loading
        self.package=package;self.timeout=timeout;self.poisoned=False
        self.hardware_id=manifest['hardware_id']
        self.overlay=Overlay(str(bitstream))
        if 'lesion_accel_0' not in self.overlay.ip_dict:raise RuntimeError('Overlay lacks lesion_accel_0')
        if not hasattr(self.overlay,'video'):raise RuntimeError('Same overlay must contain video hierarchy')
        self.ip=self.overlay.lesion_accel_0
        self.arena=allocate(shape=(len(package.blob),),dtype=np.int8)
        self.params=allocate(shape=package.params.shape,dtype=np.int32)
        self.arena[:]=np.frombuffer(package.blob,dtype=np.int8);self.params[:]=package.params
        regs=self.overlay.ip_dict['lesion_accel_0']['registers']
        def address(name):
            keys=[k for k in regs if k.lower() in {name,name+'_1'}]
            if len(keys)!=1:raise RuntimeError(f'Cannot resolve {name} register: {list(regs)}')
            return regs[keys[0]]['address_offset']
        self.return_offset=address('ap_return')
        for name,buf in [('arena',self.arena),('params',self.params)]:
            off=address(name);addr=int(buf.physical_address)
            self.ip.write(off,addr & 0xffffffff);self.ip.write(off+4,addr>>32)
        self.params[:16]=0;self.arena.flush();self.params.flush()
        result=self._start()
        if result!=0x100:raise RuntimeError(f'Kernel ABI mismatch {result}')

    def _start(self):
        if self.poisoned:raise RuntimeError('Core timed out; restart overlay before reusing memory')
        self.ip.write(0,1);deadline=time.monotonic()+self.timeout
        while not (self.ip.read(0)&2):
            if time.monotonic()>deadline:
                self.poisoned=True
                raise TimeoutError('FPGA timed out; DMA buffers retained until process/overlay reset')
            time.sleep(.0001)
        value=self.ip.read(self.return_offset)
        return value if value<2**31 else value-2**32

    def execute(self, desc):
        self.params[:16]=desc
        self.arena.flush();self.params.flush()
        result=self._start()
        # PL writes must be invalidated before next CPU flush, otherwise dirty stale cache may overwrite them.
        self.sync_read()
        if result:raise RuntimeError(f'FPGA kernel error {result}')

    def sync_read(self):
        self.arena.invalidate();self.params.invalidate()

    def close(self):
        if not self.poisoned:
            self.arena.freebuffer();self.params.freebuffer()
