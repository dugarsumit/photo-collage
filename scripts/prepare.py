"""Crop/resize kept photos to the 6.5x9cm cell size and bake in a 3mm border."""

import shutil
import sys
from pathlib import Path

import smartcrop
from PIL import Image, ImageFile, ImageOps
from tqdm import tqdm

from common import (
    BORDER_COLOR,
    BORDER_PX,
    CELL_H_PX,
    CELL_W_PX,
    CONTENT_ASPECT,
    CONTENT_H_PX,
    CONTENT_W_PX,
    DPI,
    unique_path,
)


HEAVY_CROP_WARN_THRESHOLD = 0.40  # warn if we're discarding more than this fraction of area

_SMART_CROPPER = smartcrop.SmartCrop()


def _crop_size_for_aspect(size: tuple[int, int], target_aspect: float):
    """Largest box of target_aspect (width/height) that fits inside size, plus the
    fraction of area that a crop to that box would discard."""
    w, h = size
    if w / h > target_aspect:
        new_w, new_h = round(h * target_aspect), h
    else:
        new_w, new_h = w, round(w / target_aspect)
    discarded_fraction = 1 - (new_w * new_h) / (w * h)
    return new_w, new_h, discarded_fraction


def smart_crop_to_aspect(img: Image.Image, target_aspect: float):
    """Crop to target_aspect (width/height) without rotating, keeping the photo upright.
    Uses saliency detection (edges/entropy/skin tone) to position the crop window so it
    keeps the most interesting content instead of always cutting evenly off both sides.
    Returns (cropped_img, fraction_of_area_discarded)."""
    new_w, new_h, discarded_fraction = _crop_size_for_aspect(img.size, target_aspect)
    box = _SMART_CROPPER.crop(img, new_w, new_h)["top_crop"]
    cropped = img.crop((box["x"], box["y"], box["x"] + box["width"], box["y"] + box["height"]))
    return cropped, discarded_fraction


def best_orientation_crop(img: Image.Image, target_aspect: float):
    """Try the photo as-is and rotated 90°, keep whichever needs less crop.
    Returns (cropped_img, discarded_fraction, rotated)."""
    candidates = []
    for rotated in (False, True):
        candidate = img.rotate(-90, expand=True) if rotated else img
        _, _, discarded_fraction = _crop_size_for_aspect(candidate.size, target_aspect)
        candidates.append((discarded_fraction, rotated, candidate))
    _, rotated, candidate = min(candidates, key=lambda c: c[0])
    cropped, discarded_fraction = smart_crop_to_aspect(candidate, target_aspect)
    return cropped, discarded_fraction, rotated


def make_cell(src_path: Path, allow_truncated: bool = False):
    ImageFile.LOAD_TRUNCATED_IMAGES = allow_truncated  # type: ignore[assignment]
    img = ImageOps.exif_transpose(Image.open(src_path)).convert("RGB")
    img, discarded_fraction, rotated = best_orientation_crop(img, CONTENT_ASPECT)
    img = img.resize((CONTENT_W_PX, CONTENT_H_PX), Image.Resampling.LANCZOS)
    cell = ImageOps.expand(img, border=BORDER_PX, fill=BORDER_COLOR)
    assert cell.size == (CELL_W_PX, CELL_H_PX), cell.size
    return cell, discarded_fraction, rotated


def copy_to_errors(p: Path, errors_dir: Path):
    errors_dir.mkdir(parents=True, exist_ok=True)
    dest = unique_path(errors_dir / p.name)
    shutil.copy2(p, dest)
    return dest


def run(input_dir: Path, output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)
    errors_dir = output_dir.parent / "errors"

    paths = sorted(
        p for p in input_dir.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".heic", ".webp"}
    )

    written = []
    recovered = []
    failed = []
    for p in tqdm(paths, desc="Preparing cells", unit="photo"):
        try:
            cell, discarded_fraction, rotated = make_cell(p)
        except OSError as e:
            tqdm.write(f"  ⚠ error reading {p.name}: {e} — retrying with truncated-image recovery")
            copy_to_errors(p, errors_dir)
            try:
                cell, discarded_fraction, rotated = make_cell(p, allow_truncated=True)
            except OSError as e2:
                failed.append(p)
                tqdm.write(f"  ✗ skipping {p.name}: unrecoverable: {e2}")
                continue
            recovered.append(p)
            tqdm.write(f"  ⚠ recovered {p.name} after error: {e}")
        out_path = unique_path(output_dir / f"{p.stem}_cell.jpg")
        cell.save(out_path, quality=95, dpi=(DPI, DPI))
        written.append(out_path)
        rot_note = ", rotated 90°" if rotated else ""
        warn = f"  ⚠ heavy crop, {discarded_fraction:.0%} of area discarded" \
            if discarded_fraction > HEAVY_CROP_WARN_THRESHOLD else ""
        tqdm.write(f"  {p.name} -> {out_path.name} ({CELL_W_PX}x{CELL_H_PX}px @ {DPI}dpi{rot_note}){warn}")

    print(f"Prepared {len(written)} cell(s) in {output_dir}")
    if recovered:
        print(f"Recovered {len(recovered)} file(s) with errors (copied to {errors_dir}):")
        for p in recovered:
            print(f"  {p.name}")
    if failed:
        print(f"Skipped {len(failed)} unreadable file(s) (copied to {errors_dir}):")
        for p in failed:
            print(f"  {p.name}")
    return written


if __name__ == "__main__":
    input_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("pics")
    output_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("output/cells")
    run(input_dir, output_dir)
