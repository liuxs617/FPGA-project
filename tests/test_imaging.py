import numpy as np
import pytest
from lesion_fpga.imaging import letterbox,fit_mask,restore,overlap,components_and_fill,morphology,shape_metrics,moments,gaussian_u8
from lesion_fpga.quantization import requant,threshold_code

def test_geometry_and_mask():
    small,g=letterbox(np.zeros((57,103,3),np.uint8));mask=fit_mask(np.ones((57,103),np.uint8),g)
    assert np.array_equal(mask.astype(bool),g.valid()) and restore(mask,g).all()
    assert overlap(mask,mask)=={'dice':1.,'iou':1.}

def test_morphology_boundary_and_fill():
    m=np.zeros((20,20),np.uint8);m[3:12,4:13]=1;m[6:9,7:10]=0;m[17,17]=1
    out,flags=components_and_fill(m,np.ones_like(m,bool))
    assert out.sum()==81 and flags['components_before']==2
    assert morphology(m,opening=True)[17,17]==0

def test_empty_and_single():
    m=np.zeros((16,16),np.uint8);v=np.ones_like(m,bool)
    assert shape_metrics(m,v)['valid'] is False and overlap(m,m)['dice']==1
    m[2,3]=1;r=shape_metrics(m,v)
    assert r['centroid']==[3.,2.] and r['perimeter_px']==0 and r['circularity'] is None
    assert moments(m)==[1,3,2,9,6,4]

def test_full_and_touching():
    m=np.ones((16,16),np.uint8);out,f=components_and_fill(m,m.astype(bool))
    assert f['touches_valid_border'] and out.sum()==256 and shape_metrics(out,m.astype(bool))['area_ratio']==1

def test_round_and_threshold():
    assert requant(np.array([-3,-1,1,3]),1,1).tolist()==[-2,-1,1,2]
    assert requant(np.array([-300,300]),1<<24).tolist()==[-128,127]
    assert threshold_code(0,.1)==-129 and threshold_code(1,.1)==128 and threshold_code(.5,.1)==0
    with pytest.raises(ValueError):threshold_code(1.01,.1)

def test_gaussian_integer():
    m=np.full((8,8,3),255,np.uint8);assert np.array_equal(gaussian_u8(m),m)
    m[:]=0;m[4,4]=255;assert gaussian_u8(m)[4,4,0]==64
