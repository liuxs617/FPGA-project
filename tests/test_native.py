import ctypes
import numpy as np
import pytest
from lesion_fpga.common import ROOT
from lesion_fpga.quantization import conv_reference
from lesion_fpga.imaging import gaussian_u8,morphology,moments

@pytest.fixture
def core():
    path=ROOT/'build/native/lesion.dll'
    if not path.exists():pytest.skip('Run scripts/native_core.ps1 first')
    lib=ctypes.CDLL(str(path));fn=lib.lesion_accel
    fn.argtypes=[ctypes.POINTER(ctypes.c_int8),ctypes.POINTER(ctypes.c_int32)];fn.restype=ctypes.c_int
    a=np.zeros(1<<20,np.int8);p=np.zeros(4096,np.int32)
    def run(d):
        p[:16]=d
        ret=fn(a.ctypes.data_as(ctypes.POINTER(ctypes.c_int8)),p.ctypes.data_as(ctypes.POINTER(ctypes.c_int32)))
        assert ret==0
    return a,p,run

@pytest.mark.parametrize('ci,co,k,h,w',[(3,16,3,13,11),(16,17,3,8,8),(9,1,1,8,16)])
def test_conv_tails_and_signed(core,ci,co,k,h,w):
    a,p,run=core;rng=np.random.default_rng(42)
    x=rng.integers(-127,128,(ci,h,w),dtype=np.int8);weight=rng.integers(-20,21,(co,ci,k,k),dtype=np.int8)
    bias=rng.integers(-100,100,co,dtype=np.int32);mul=256001
    a[:x.size]=x.ravel();a[100000:100000+weight.size]=weight.ravel();p[64:64+co]=bias
    run([1,h,w,ci,co,k,0,0,200000,100000,64,mul,24,0,0,0])
    np.testing.assert_array_equal(a[200000:200000+co*h*w].reshape(co,h,w),conv_reference(x,weight,bias,mul,False))

def test_preprocess_and_morph(core):
    a,p,run=core;rng=np.random.default_rng(7);rgb=rng.integers(0,256,(16,16,3),dtype=np.uint8)
    a[:rgb.size]=rgb.transpose(2,0,1).copy().view(np.int8).ravel()
    run([8,16,16,3,3,0,0,1000,2000,0,0,0,24,1,0,0])
    expected=gaussian_u8(rgb)
    np.testing.assert_array_equal(a[1000:1768].view(np.uint8).reshape(3,16,16).transpose(1,2,0),expected)
    np.testing.assert_array_equal(a[2000:2768].reshape(3,16,16),((expected.astype(np.int32)*127+127)//255).transpose(2,0,1))
    m=rng.integers(0,2,(16,16),dtype=np.int8);a[:256]=m.ravel()
    run([6,16,16,1,1,0,0,0,1000,0,0,0,24,0,0,0]);run([7,16,16,1,1,0,1000,0,2000,0,0,0,24,0,0,0])
    np.testing.assert_array_equal(a[2000:2256].reshape(16,16),morphology(m,opening=True))
    run([9,16,16,1,1,0,0,0,0,0,0,0,24,0,0,0]);assert p[32:44:2].tolist()==moments(m)

def test_pool_upsample_concat_threshold(core):
    from lesion_fpga.quantization import requant
    a,p,run=core;x=np.arange(-32,32,dtype=np.int8).reshape(1,8,8);a[:64]=x.ravel()
    run([2,8,8,1,1,0,0,0,100,0,0,0,24,0,0,0]);pooled=x.reshape(1,4,2,4,2).max((2,4))
    np.testing.assert_array_equal(a[100:116].reshape(1,4,4),pooled)
    run([3,4,4,1,1,0,100,0,200,0,0,0,24,0,0,0]);up=pooled.repeat(2,1).repeat(2,2)
    np.testing.assert_array_equal(a[200:264].reshape(1,8,8),up)
    run([4,8,8,1,2,0,0,200,400,0,0,1<<23,24,1,1<<24,0])
    np.testing.assert_array_equal(a[400:528].reshape(2,8,8),np.concatenate([requant(x,1<<23),up]))
    a[600:664]=1
    for threshold in [-129,0,128]:
        run([5,8,8,1,1,0,0,600,700,0,0,0,24,threshold,0,0])
        np.testing.assert_array_equal(a[700:764],(x.ravel()>=threshold).astype(np.int8))
