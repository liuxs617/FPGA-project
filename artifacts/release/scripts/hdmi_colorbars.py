"""Board-only colorbars using the SAME integrated overlay as inference."""
import argparse
import time
import numpy as np
from lesion_fpga.common import ROOT
from lesion_fpga.quantization import ModelPackage
from lesion_fpga.backends import PynqBackend


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', default=str(ROOT/'artifacts/models/baseline'))
    parser.add_argument('--bitstream', default=str(ROOT/'artifacts/hardware/lesion.bit'))
    parser.add_argument('--seconds', type=int, default=30)
    parser.add_argument('--mode', choices=['720p60', '1080p60', '480p60'], default='720p60')
    args = parser.parse_args()
    if args.seconds <= 0:
        parser.error('--seconds must be positive')
    width, height = {'720p60': (1280, 720), '1080p60': (1920, 1080),
                     '480p60': (640, 480)}[args.mode]
    print('Loading integrated overlay', flush=True)
    backend = PynqBackend(ModelPackage(args.model), args.bitstream)
    from pynq.lib.video import VideoMode, PIXEL_RGB
    hdmi = backend.overlay.video.hdmi_out
    try:
        print(f'Configuring {width}x{height} 60Hz RGB24', flush=True)
        hdmi.configure(VideoMode(width, height, 24, 60), PIXEL_RGB)
        hdmi.start()
        colors = np.array([[255,255,255], [255,255,0], [0,255,255], [0,255,0],
                           [255,0,255], [255,0,0], [0,0,255], [0,0,0]], np.uint8)
        frame = hdmi.newframe()
        for index, color in enumerate(colors):
            frame[:, index*width//8:(index+1)*width//8] = color
        hdmi.writeframe(frame)
        print(f'Frame submitted; holding for {args.seconds}s (visual confirmation required)', flush=True)
        time.sleep(args.seconds)
    finally:
        try:
            hdmi.close()
        finally:
            backend.close()
        print('HDMI stopped', flush=True)


if __name__ == '__main__':
    main()
