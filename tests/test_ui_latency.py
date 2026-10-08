import numpy as np
from lesion_fpga.ui import CachedRenderer,render
from lesion_fpga.pipeline import Parameters
from lesion_fpga.app import pending_mouse_events

def test_cached_pointer_matches_fresh_scene_and_invalidates():
    calls=[]
    def painter(*args):
        calls.append(1)
        return render(*args)
    cached=CachedRenderer(painter);p=Parameters()
    for pointer in ((640,360),(2,2),(1279,719)):
        actual=cached(None,'Ready',p,.25,0,pointer,False,None)
        assert np.array_equal(actual,render(None,'Ready',p,.25,0,pointer,False,None))
    assert len(calls)==1
    actual=cached(None,'Changed',p,.25,0,(200,200),False,None)
    assert len(calls)==2
    assert np.array_equal(actual,render(None,'Changed',p,.25,0,(200,200),False,None))

def test_mouse_drains_multiple_batches_in_order():
    class Mouse:
        def __init__(self):self.batches=iter([[1,2],[3],[4,5]])
        def read(self):
            try:return next(self.batches)
            except StopIteration:raise BlockingIOError
    assert list(pending_mouse_events(Mouse()))==[1,2,3,4,5]
