from pathlib import Path
import random
import hashlib
import numpy as np
from PIL import Image
from .common import ROOT, write_json, sha256, event
from .imaging import load_rgb, letterbox, fit_mask, gaussian_u8


def audit(root=ROOT / "data", seed=20260922):
    root = Path(root)
    rows, errors, pixel_groups = [], [], {}
    for source in ["Training", "Test"]:
        image_dir = root / f"ISBI2016_ISIC_Part1_{source}_Data"
        masks = root / f"ISBI2016_ISIC_Part1_{source}_GroundTruth"
        mask_lookup = {p.name:p for p in masks.rglob('*.png')}
        for image in sorted(image_dir.rglob("*.jpg")):
            mask = mask_lookup.get(f"{image.stem}_Segmentation.png", masks / f"{image.stem}_Segmentation.png")
            try:
                rgb = load_rgb(image)
                with Image.open(mask) as im:
                    gt = np.asarray(im.convert("L"))
                if gt.shape != rgb.shape[:2]:
                    raise ValueError("image/mask size mismatch")
                if not set(np.unique(gt)).issubset({0, 255}):
                    raise ValueError("non-binary ground truth")
                digest = hashlib.sha256(rgb.tobytes()).hexdigest()
                row = {"id": image.stem, "image": str(image.relative_to(ROOT)).replace("\\", "/"),
                       "mask": str(mask.relative_to(ROOT)).replace("\\", "/"), "source": source,
                       "width": rgb.shape[1], "height": rgb.shape[0], "sha256": sha256(image),
                       "mask_sha256": sha256(mask), "pixel_sha256": digest}
                rows.append(row)
                pixel_groups.setdefault(digest, []).append(row)
            except Exception as exc:
                errors.append({"image": str(image), "error": str(exc)})
    if not rows or errors:
        write_json(ROOT / "record/data_errors.json", errors)
        raise ValueError(f"Dataset invalid: {len(rows)} readable, {len(errors)} errors")
    # Duplicate train/test pixels are excluded from model fitting and final test metrics.
    conflicts = [g for g in pixel_groups.values() if len({x['source'] for x in g}) > 1]
    conflict_hashes = {g[0]['pixel_sha256'] for g in conflicts}
    groups = [k for k, v in pixel_groups.items() if v[0]['source'] == 'Training' and k not in conflict_hashes]
    random.Random(seed).shuffle(groups)
    val = set(groups[:max(1, round(len(groups)*.2))])
    for row in rows:
        row['split'] = ('excluded_overlap' if row['pixel_sha256'] in conflict_hashes else
                        'test' if row['source'] == 'Test' else
                        'validation' if row['pixel_sha256'] in val else 'train')
    manifest = {"schema_version": 1, "seed": seed, "grouping": "exact decoded pixels; patient metadata unavailable",
                "rows": rows, "counts": {s: sum(r['split'] == s for r in rows)
                                         for s in ['train', 'validation', 'test', 'excluded_overlap']},
                "duplicate_groups": [[r['id'] for r in g] for g in pixel_groups.values() if len(g)>1]}
    write_json(ROOT / "artifacts/data_manifest.json", manifest)
    event('dataset_audit', counts=manifest['counts'], duplicate_groups=manifest['duplicate_groups'])
    return manifest


def cache(manifest, size=128, gaussian=False):
    images, masks, valids, ids = [], [], [], []
    for row in manifest['rows']:
        im, g = letterbox(load_rgb(ROOT/row['image']), size)
        if gaussian:
            im = gaussian_u8(im)
        with Image.open(ROOT/row['mask']) as gt:
            mask = fit_mask(np.asarray(gt.convert('L')), g)
        images.append(im.transpose(2, 0, 1)); masks.append(mask[None]); valids.append(g.valid()[None]); ids.append(row['id'])
    path = ROOT / f'artifacts/cache/isic_{size}_g{int(gaussian)}.npz'
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, images=np.array(images), masks=np.array(masks), valids=np.array(valids), ids=ids)
    return path
