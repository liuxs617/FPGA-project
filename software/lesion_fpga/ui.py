"""720p RGB compositor shared by HDMI runtime and visual QA."""
from pathlib import Path
from functools import lru_cache
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from .imaging import overlay

# PYNQ images may ship Pillow 9.0, before the Resampling enum was added.
RESAMPLING = getattr(Image, 'Resampling', Image)

BUTTONS=[('prev','Prev'),('next','Next'),('run','Run'),('threshold_down','T -'),('threshold_up','T +'),
         ('opening','Open'),('closing','Close'),('largest','Main'),('fill','Fill'),
         ('alpha','Alpha'),('view','View'),('reset','Reset'),('save','Save'),('quit','Exit')]

@lru_cache(maxsize=16)
def font(size=18):
    for path in ['/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf','C:/Windows/Fonts/segoeui.ttf']:
        if Path(path).exists():return ImageFont.truetype(path,size)
    return ImageFont.load_default()


class CachedRenderer:
    """Retain the static scene; pointer motion must not recompose all tiles."""
    def __init__(self, painter):
        self.painter=painter;self.key=None;self.result=None;self.report=None;self.base=None
        cursor=Image.new('RGBA',(18,19))
        ImageDraw.Draw(cursor).polygon([(0,0),(4,18),(9,12),(17,11)],fill='white',outline='black')
        self.cursor=np.asarray(cursor)

    def __call__(self,result,status,parameters,alpha,view,pointer,selected,report):
        key=(status,parameters,alpha,view,selected)
        if self.base is None or result is not self.result or report is not self.report or key!=self.key:
            self.base=self.painter(result,status,parameters,alpha,view,None,selected,report)
            self.key=key;self.result=result;self.report=report
        im=self.base.copy()
        if pointer:
            x,y=pointer
            x0,y0=max(0,x),max(0,y);x1,y1=min(im.shape[1],x+18),min(im.shape[0],y+19)
            if x1>x0 and y1>y0:
                patch=self.cursor[y0-y:y1-y,x0-x:x1-x]
                target=im[y0:y1,x0:x1];mask=patch[:,:,3]>0
                target[mask]=patch[:,:,:3][mask]
        return im

def button_boxes():
    return [(key,(18+i*89,652,101+i*89,694),label) for i,(key,label) in enumerate(BUTTONS)]

def hit_button(x,y):
    return next((key for key,(x0,y0,x1,y1),_ in button_boxes() if x0<=x<=x1 and y0<=y<=y1),None)

def image_rect(shape,box):
    h,w=shape[:2];x0,y0,x1,y1=box;r=min((x1-x0)/w,(y1-y0)/h)
    nw,nh=max(1,round(w*r)),max(1,round(h*r))
    return x0+(x1-x0-nw)//2,y0+(y1-y0-nh)//2,nw,nh

def pick_result(result,x,y,view):
    if result is None or view!=0:return False
    rx,ry,rw,rh=image_rect(result['rgb'].shape,(468,397,884,612))
    if not(rx<=x<rx+rw and ry<=y<ry+rh):return False
    ox=min(result['rgb'].shape[1]-1,int((x-rx)*result['rgb'].shape[1]/rw))
    oy=min(result['rgb'].shape[0]-1,int((y-ry)*result['rgb'].shape[0]/rh))
    return bool(result['original_mask'][oy,ox])

def render(result=None,status='Ready',parameters=None,alpha=.25,view=0,pointer=None,selected=False,report=None):
    im=Image.new('RGB',(1280,720),(14,22,34));d=ImageDraw.Draw(im);f=font(17);small=font(14);title=font(25)
    d.text((20,15),'PYNQ-Z2  |  Lesion Segmentation',font=title,fill=(234,242,249))
    d.text((20,51),status[:125],font=f,fill=(70,210,190))
    def tile(rgb,box,label,nearest=False):
        x0,y0,x1,y1=box;d.rounded_rectangle(box,8,fill=(25,37,52));d.text((x0+10,y0+7),label,font=f,fill='white')
        rx,ry,w,h=image_rect(rgb.shape,(x0+8,y0+34,x1-8,y1-8))
        im.paste(Image.fromarray(rgb).resize((w,h),RESAMPLING.NEAREST if nearest else RESAMPLING.BILINEAR),(rx,ry))
    if result is not None:
        if view==0:
            tile(result['rgb'],(18,92,450,351),'Original RGB')
            tile(result['processed'],(460,92,892,351),'Processed' if result['parameters']['gaussian'] else 'Preprocess bypass')
            tile(np.repeat((result['mask']*255)[:,:,None],3,2),(18,363,450,620),'Final mask',True)
            tile(overlay(result['rgb'],result['original_mask'],alpha),(460,363,892,620),'Overlay'+(' / selected' if selected else ''))
        elif view==1:tile(overlay(result['rgb'],result['original_mask'],alpha),(18,92,892,620),'Overlay / full view')
        else:
            d.text((30,105),'Measured results / version-bound evidence',font=title,fill='white')
            lines=['Current backend: '+result['backend'],'Model: '+result['model_id'],
                   'HDMI timing: 720p60 (not inference FPS)','Resources require implementation reports.']
            lines.extend([f'{k}: {v}' for k,v in report.items() if isinstance(v,(str,int,float))] if report else ['No benchmark report loaded; no speedup claimed.'])
            for i,line in enumerate(lines[:15]):d.text((30,155+i*28),line[:82],font=f,fill=(198,215,230))
        lines=[Path(result['path']).name,f"Frame {result['frame_id']} / config {result['parameter_version']}",
               f"Backend: {result['backend']}",f"Area: {result['metrics']['area_px2']} px2",f"Area ratio: {result['metrics']['area_ratio']:.2%}"]
        for k,label in [('perimeter_px','Perimeter px'),('major_axis_px','Major axis px'),('minor_axis_px','Minor axis px'),('circularity','Circularity'),('asymmetry','Asymmetry')]:
            val=result['metrics'].get(k);lines.append(f'{label}: '+(f'{val:.3f}' if val is not None else 'N/A'))
        if result['metrics'].get('axis_unstable'):lines.append('Principal axis unstable')
        if result['flags']['touches_valid_border']:lines.append('Region touches image border')
        acc=result['accuracy'];lines.append(f"Dice {acc['dice']:.3f} / IoU {acc['iou']:.3f}" if acc else 'No ground truth / accuracy N/A')
        t=result['timing'];lines.extend([f"Inference: {t['inference_ms']:.1f} ms",f"Postprocess: {t['postprocess_ms']:.1f} ms",f"Processing: {t['processing_ms']:.1f} ms",'Network output reused' if t['network_reused'] else 'Full inference'])
        for i,line in enumerate(lines):d.text((910,103+i*25),line[:35],font=small,fill=(220,230,241))
    else:
        d.text((40,180),'Select an image and run processing.',font=title,fill=(190,204,220))
        d.text((40,225),'Results are cleared on errors and input changes.',font=f,fill=(150,175,195))
    if parameters:d.text((20,627),f'Threshold {parameters.threshold:.2f}  |  Open {parameters.opening}  Close {parameters.closing}  Main {parameters.largest}  Fill {parameters.fill}  Alpha {alpha:.2f}',font=small,fill=(146,181,198))
    for key,box,label in button_boxes():
        d.rounded_rectangle(box,6,fill=(34,61,78),outline=(62,99,117));d.text((box[0]+10,box[1]+10),label,font=f,fill='white')
    d.text((20,699),'Engineering demonstration only. Not for clinical diagnosis.',font=font(12),fill=(140,158,176))
    if pointer:
        x,y=pointer;d.polygon([(x,y),(x+4,y+18),(x+9,y+12),(x+17,y+11)],fill='white',outline='black')
    return np.asarray(im).copy()
