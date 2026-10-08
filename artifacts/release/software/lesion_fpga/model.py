import torch
from torch import nn
from torch.nn import functional as F


class SmallUNet(nn.Module):
    """No BN/dropout; graph names are shared with the hardware export."""
    def __init__(self, channels=(16, 32, 64, 128)):
        super().__init__()
        self.channels = tuple(channels)
        self.layers = nn.ModuleDict()
        c = 3
        for i, out in enumerate(channels):
            self.layers[f'e{i}a'] = nn.Conv2d(c, out, 3, padding=1)
            self.layers[f'e{i}b'] = nn.Conv2d(out, out, 3, padding=1)
            c = out
        for i in [2, 1, 0]:
            out = channels[i]
            self.layers[f'd{i}a'] = nn.Conv2d(c+out, out, 3, padding=1)
            self.layers[f'd{i}b'] = nn.Conv2d(out, out, 3, padding=1)
            c = out
        self.layers['head'] = nn.Conv2d(c, 1, 1)

    def forward(self, x, trace=False):
        values = {'input': x}
        skips = []
        for i in range(4):
            for suffix in ['a', 'b']:
                name = f'e{i}{suffix}'
                x = F.relu(self.layers[name](x)); values[name] = x
            if i < 3:
                skips.append(x)
                x = F.max_pool2d(x, 2); values[f'p{i}'] = x
        for i in [2, 1, 0]:
            x = F.interpolate(x, scale_factor=2, mode='nearest'); values[f'u{i}'] = x
            x = torch.cat([x, skips[i]], dim=1); values[f'c{i}'] = x
            for suffix in ['a', 'b']:
                name = f'd{i}{suffix}'
                x = F.relu(self.layers[name](x)); values[name] = x
        x = self.layers['head'](x); values['head'] = x
        return values if trace else x


def graph(channels=(16, 32, 64, 128)):
    nodes, prev = [], 'input'
    for i in range(4):
        for suffix in ['a', 'b']:
            name = f'e{i}{suffix}'
            nodes.append(dict(name=name, op='conv', inputs=[prev], co=channels[i], k=3, relu=True)); prev=name
        if i < 3:
            name=f'p{i}'; nodes.append(dict(name=name, op='pool', inputs=[prev])); prev=name
    for i in [2, 1, 0]:
        name=f'u{i}'; nodes.append(dict(name=name, op='up', inputs=[prev])); prev=name
        name=f'c{i}'; nodes.append(dict(name=name, op='cat', inputs=[prev, f'e{i}b'])); prev=name
        for suffix in ['a', 'b']:
            name=f'd{i}{suffix}'
            nodes.append(dict(name=name, op='conv', inputs=[prev], co=channels[i], k=3, relu=True)); prev=name
    nodes.append(dict(name='head', op='conv', inputs=[prev], co=1, k=1, relu=False))
    return nodes
