"""Crop/resize kept photos to the 6.5x9cm cell size and bake in a 4mm border."""

import csv
import sys
from pathlib import Path

from PIL import Image, ImageOps

from common import (
    BORDER_COLOR,
    BORDER_PX,
    CELL_H_PX,
    CELL_W_PX,
    CONTENT_ASPECT,
    CONTENT_H_PX,
    CONTENT_W_PX,
    DPI,
)


HEAVY_CROP_WARN_THRESHOLD = 0.40  # warn if we're discarding more than this fraction of area


def center_crop_to_aspect(img: Image.Image, target_aspect: float):
    """Crop to target_aspect (width/height) without rotating, keeping the photo upright.
    Returns (cropped_img, fraction_of_area_discarded)."""
    w, h = img.size
    current_aspect = w / h
    if current_aspect > target_aspect:
        # too wide: crop width, keep full height
        new_w = round(h * target_aspect)
        left = (w - new_w) // 2
        cropped = img.crop((left, 0, left + new_w, h))
    else:
        # too tall: crop height, keep full width
        new_h = round(w / target_aspect)
        top = (h - new_h) // 2
        cropped = img.crop((0, top, w, top + new_h))
    discarded_fraction = 1 - (cropped.size[0] * cropped.size[1]) / (w * h)
    return cropped, discarded_fraction


def make_cell(src_path: Path):
    img = ImageOps.exif_transpose(Image.open(src_path)).convert("RGB")
    img, discarded_fraction = center_crop_to_aspect(img, CONTENT_ASPECT)
    img = img.resize((CONTENT_W_PX, CONTENT_H_PX), Image.Resampling.LANCZOS)
    cell = ImageOps.expand(img, border=BORDER_PX, fill=BORDER_COLOR)
    assert cell.size == (CELL_W_PX, CELL_H_PX), cell.size
    return cell, discarded_fraction


def run(input_dir: Path, dedup_csv: Path, output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)

    kept_names = None
    if dedup_csv.exists():
        with open(dedup_csv) as f:
            reader = csv.DictReader(f)
            kept_names = {row["filename"] for row in reader if row["kept"] == "True"}
        print(f"Using dedup result: {len(kept_names)} photo(s) kept")
    else:
        print(f"No dedup CSV at {dedup_csv}, processing all photos in {input_dir}")

    paths = sorted(
        p for p in input_dir.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".heic"}
    )
    if kept_names is not None:
        paths = [p for p in paths if p.name in kept_names]

    written = []
    for p in paths:
        cell, discarded_fraction = make_cell(p)
        out_path = output_dir / f"{p.stem}_cell.jpg"
        cell.save(out_path, quality=95, dpi=(DPI, DPI))
        written.append(out_path)
        warn = f"  ⚠ heavy crop, {discarded_fraction:.0%} of area discarded" \
            if discarded_fraction > HEAVY_CROP_WARN_THRESHOLD else ""
        print(f"  {p.name} -> {out_path.name} ({CELL_W_PX}x{CELL_H_PX}px @ {DPI}dpi){warn}")

    print(f"Prepared {len(written)} cell(s) in {output_dir}")
    return written


if __name__ == "__main__":
    input_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("pics")
    dedup_csv = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("output/dedup.csv")
    output_dir = Path(sys.argv[3]) if len(sys.argv) > 3 else Path("output/cells")
    run(input_dir, dedup_csv, output_dir)
