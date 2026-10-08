"""Section 7.3: deterministic fault injection, without touching live AXI."""
import pytest
from lesion_fpga.backends import PynqBackend

class StuckIP:
    def __init__(self): self.writes=[]
    def write(self, offset, value): self.writes.append((offset,value))
    def read(self, offset): return 0

class Buffer:
    def __init__(self): self.freed=False
    def freebuffer(self): self.freed=True

def test_timeout_poison_prevents_reuse_and_keeps_dma_buffers(monkeypatch):
    backend=PynqBackend.__new__(PynqBackend)
    backend.ip=StuckIP(); backend.timeout=.01; backend.poisoned=False
    backend.arena=Buffer(); backend.params=Buffer(); backend.return_offset=16
    ticks=iter([0,.02])
    monkeypatch.setattr('lesion_fpga.backends.time.monotonic',lambda:next(ticks))
    with pytest.raises(TimeoutError): backend._start()
    assert backend.poisoned and backend.ip.writes==[(0,1)]
    with pytest.raises(RuntimeError,match='restart overlay'): backend._start()
    assert backend.ip.writes==[(0,1)]
    backend.close()
    assert not backend.arena.freed and not backend.params.freed
