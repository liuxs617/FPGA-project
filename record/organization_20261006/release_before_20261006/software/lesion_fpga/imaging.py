from dataclasses import dataclass, asdict
import cv2
import numpy as np
from PIL import Image, ImageOps


@dataclass(frozen=True)
class Geometry:
    original_w: int
    original_h: int
    size: int
    width: int
    height: int
    left: int
    top: int

    def valid(self):
        v = np.zeros((self.size, self.size), bool)
        v[self.top:self.top+self.height, self.left:self.left+self.width] = True
        return v

    def to_dict(self):
        return asdict(self)


def load_rgb(path):
    with Image.open(path) as im:
        return np.asarray(ImageOps.exif_transpose(im).convert("RGB")).copy()


def letterbox(image, size=128):
    h, w = image.shape[:2]
    if min(h, w) <= 0 or size < 8 or size % 8:
        raise ValueError("Input size must be positive and divisible by 8")
    ratio = min(size/w, size/h)
    nw, nh = max(1, round(w*ratio)), max(1, round(h*ratio))
    g = Geometry(w, h, size, nw, nh, (size-nw)//2, (size-nh)//2)
    out = np.zeros((size, size, 3), np.uint8)
    out[g.top:g.top+nh, g.left:g.left+nw] = cv2.resize(image, (nw, nh), interpolation=cv2.INTER_LINEAR)
    return out, g


def fit_mask(mask, g):
    out = np.zeros((g.size, g.size), np.uint8)
    out[g.top:g.top+g.height, g.left:g.left+g.width] = cv2.resize(
        (mask > 0).astype(np.uint8), (g.width, g.height), interpolation=cv2.INTER_NEAREST)
    return out


def restore(mask, g):
    cropped = mask[g.top:g.top+g.height, g.left:g.left+g.width]
    return cv2.resize(cropped.astype(np.uint8), (g.original_w, g.original_h), interpolation=cv2.INTER_NEAREST)


def gaussian_u8(rgb):
    # Replicate border; exact integer [1 2 1] outer product, ties upwards.
    p = np.pad(rgb.astype(np.uint16), ((1, 1), (1, 1), (0, 0)), mode="edge")
    h, w = rgb.shape[:2]
    total = sum(p[y:y+h, x:x+w] * ([1, 2, 1][y]*[1, 2, 1][x])
                for y in range(3) for x in range(3))
    return ((total + 8)//16).astype(np.uint8)


def morphology(mask, opening=False, closing=False):
    x = mask.astype(np.uint8)
    k = np.ones((3, 3), np.uint8)
    def erode(a):
        return cv2.erode(a, k, borderType=cv2.BORDER_CONSTANT, borderValue=0)
    def dilate(a):
        return cv2.dilate(a, k, borderType=cv2.BORDER_CONSTANT, borderValue=0)
    if opening:
        x = dilate(erode(x))
    if closing:
        x = erode(dilate(x))
    return x


def components_and_fill(mask, valid, largest=True, fill=True):
    m = ((mask > 0) & valid).astype(np.uint8)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(m, connectivity=8, ltype=cv2.CV_32S)
    count = n-1
    if largest and count:
        # Ties resolved by first raster-order label.
        m = (labels == (1 + np.argmax(stats[1:, cv2.CC_STAT_AREA]))).astype(np.uint8)
    if fill and m.any():
        p = np.pad(m, 1)
        cv2.floodFill(p, None, (0, 0), 2, flags=4)
        m = ((p[1:-1, 1:-1] != 2) & valid).astype(np.uint8)
    return m, {"components_before": count, "empty": not bool(m.any()),
               "touches_valid_border": bool(np.any(m & (valid & ~cv2.erode(valid.astype(np.uint8),
                    np.ones((3, 3), np.uint8), borderType=cv2.BORDER_CONSTANT, borderValue=0).astype(bool))))}


def overlap(pred, truth):
    a, b = pred.astype(bool), truth.astype(bool)
    if a.shape != b.shape:
        raise ValueError("Metric shapes differ")
    intersection = int(np.count_nonzero(a & b))
    union = int(np.count_nonzero(a | b))
    total = int(a.sum() + b.sum())
    return {"dice": 2*intersection/total if total else 1., "iou": intersection/union if union else 1.}


def moments(mask):
    y, x = np.nonzero(mask)
    x, y = x.astype(np.int64), y.astype(np.int64)
    return [len(x), int(x.sum()), int(y.sum()), int((x*x).sum()), int((x*y).sum()), int((y*y).sum())]


def shape_metrics(mask, valid, sums=None):
    a, sx, sy, sxx, sxy, syy = moments(mask) if sums is None else sums
    result = {"area_px2": int(a), "area_ratio": a/int(valid.sum()), "valid": bool(a)}
    if not a:
        return {**result, "reason": "empty mask"}
    center = np.array([sx/a, sy/a])
    cov = np.array([[sxx/a-center[0]**2, sxy/a-center.prod()],
                    [sxy/a-center.prod(), syy/a-center[1]**2]])
    vals, vecs = np.linalg.eigh(cov)
    vals = np.maximum(vals, 0)
    contours, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
    perimeter = sum(float(cv2.arcLength(c, True)) for c in contours)
    result.update(centroid=center.tolist(), major_axis_px=float(4*np.sqrt(vals[1])),
                  minor_axis_px=float(4*np.sqrt(vals[0])), perimeter_px=perimeter,
                  circularity=4*np.pi*a/perimeter**2 if perimeter else None,
                  axis_unstable=bool(vals[1] == 0 or (vals[1]-vals[0])/vals[1] < .05))
    # Inverse nearest-neighbour reflection on a padded canvas, avoiding clipped masks.
    size = max(mask.shape)*3
    canvas = np.zeros((size, size), np.uint8)
    offset = max(mask.shape)
    canvas[offset:offset+mask.shape[0], offset:offset+mask.shape[1]] = mask
    c = center + offset
    scores = []
    for axis in vecs.T:
        r = 2*np.outer(axis, axis)-np.eye(2)
        affine = np.column_stack((r, c-r@c))
        reflected = cv2.warpAffine(canvas, affine, (size, size), flags=cv2.INTER_NEAREST,
                                   borderMode=cv2.BORDER_CONSTANT, borderValue=0)
        scores.append(1-overlap(canvas, reflected)["iou"])
    result["asymmetry"] = float(np.mean(scores)) if a > 1 else None
    return result


def overlay(rgb, mask, alpha=.25):
    out = rgb.copy()
    m = mask.astype(bool)
    out[m] = np.rint((1-alpha)*rgb[m] + alpha*np.array([0, 220, 100])).astype(np.uint8)
    edge = m & ~cv2.erode(m.astype(np.uint8), np.ones((3, 3), np.uint8),
                         borderType=cv2.BORDER_CONSTANT, borderValue=0).astype(bool)
    out[edge] = [255, 220, 0]
    return out
