"""Crop/resize kept photos to the 6.5x9cm cell size and bake in a 3mm border."""

import argparse
import shutil
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

CROP_MODES = ("smart", "center", "top", "bottom")
DEFAULT_CROP_MODE = "smart"

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


def crop_to_aspect(img: Image.Image, target_aspect: float, mode: str = DEFAULT_CROP_MODE):
    """Crop to target_aspect (width/height) without rotating, keeping the photo upright.
    `mode` picks where the crop window is placed:
      - "smart": saliency detection (edges/entropy/skin tone) picks the most interesting spot
      - "center": crop evenly off both sides/ends
      - "top"/"bottom": crop evenly off both sides, anchored to the top or bottom edge
    Returns (cropped_img, fraction_of_area_discarded)."""
    w, h = img.size
    new_w, new_h, discarded_fraction = _crop_size_for_aspect(img.size, target_aspect)
    if mode == "smart":
        box = _SMART_CROPPER.crop(img, new_w, new_h)["top_crop"]
        x, y = box["x"], box["y"]
    elif mode == "center":
        x, y = (w - new_w) // 2, (h - new_h) // 2
    elif mode == "top":
        x, y = (w - new_w) // 2, 0
    elif mode == "bottom":
        x, y = (w - new_w) // 2, h - new_h
    else:
        raise ValueError(f"unknown crop mode: {mode!r} (choose from {CROP_MODES})")
    cropped = img.crop((x, y, x + new_w, y + new_h))
    return cropped, discarded_fraction


def best_orientation_crop(img: Image.Image, target_aspect: float, mode: str = DEFAULT_CROP_MODE):
    """Try the photo as-is and rotated 90°, keep whichever needs less crop.
    Returns (cropped_img, discarded_fraction, rotated)."""
    candidates = []
    for rotated in (False, True):
        candidate = img.rotate(-90, expand=True) if rotated else img
        _, _, discarded_fraction = _crop_size_for_aspect(candidate.size, target_aspect)
        candidates.append((discarded_fraction, rotated, candidate))
    _, rotated, candidate = min(candidates, key=lambda c: c[0])
    cropped, discarded_fraction = crop_to_aspect(candidate, target_aspect, mode)
    return cropped, discarded_fraction, rotated


def make_cell(src_path: Path, allow_truncated: bool = False, crop_mode: str = DEFAULT_CROP_MODE):
    ImageFile.LOAD_TRUNCATED_IMAGES = allow_truncated  # type: ignore[assignment]
    img = ImageOps.exif_transpose(Image.open(src_path)).convert("RGB")
    img, discarded_fraction, rotated = best_orientation_crop(img, CONTENT_ASPECT, crop_mode)
    img = img.resize((CONTENT_W_PX, CONTENT_H_PX), Image.Resampling.LANCZOS)
    cell = ImageOps.expand(img, border=BORDER_PX, fill=BORDER_COLOR)
    assert cell.size == (CELL_W_PX, CELL_H_PX), cell.size
    return cell, discarded_fraction, rotated


def copy_to_errors(p: Path, errors_dir: Path):
    errors_dir.mkdir(parents=True, exist_ok=True)
    dest = unique_path(errors_dir / p.name)
    shutil.copy2(p, dest)
    return dest


def run(input_dir: Path, output_dir: Path, crop_mode: str = DEFAULT_CROP_MODE):
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
            cell, discarded_fraction, rotated = make_cell(p, crop_mode=crop_mode)
        except OSError as e:
            tqdm.write(f"  ⚠ error reading {p.name}: {e} — retrying with truncated-image recovery")
            copy_to_errors(p, errors_dir)
            try:
                cell, discarded_fraction, rotated = make_cell(p, allow_truncated=True, crop_mode=crop_mode)
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_dir", type=Path, nargs="?", default=Path("pics"))
    parser.add_argument("output_dir", type=Path, nargs="?", default=Path("output/cells"))
    parser.add_argument(
        "--crop",
        dest="crop_mode",
        choices=CROP_MODES,
        default=DEFAULT_CROP_MODE,
        help=f"crop strategy to use for every photo in this run (default: {DEFAULT_CROP_MODE})",
    )
    args = parser.parse_args()
    run(args.input_dir, args.output_dir, crop_mode=args.crop_mode)
