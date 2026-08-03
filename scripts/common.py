"""Shared print geometry: 6.5x9cm cells (border included), 4 per 13x18cm sheet."""

from pathlib import Path

import pillow_heif

pillow_heif.register_heif_opener()


def unique_path(path: Path) -> Path:
    """Return path unchanged if free, otherwise the same name with a `_2`, `_3`, ... postfix
    so an existing file is never overwritten."""
    if not path.exists():
        return path
    n = 2
    while True:
        candidate = path.with_stem(f"{path.stem}_{n}")
        if not candidate.exists():
            return candidate
        n += 1

DPI = 300


def cm_to_px(cm: float) -> int:
    return round(cm / 2.54 * DPI)


CELL_W_CM, CELL_H_CM = 6.5, 9.0
BORDER_CM = 0.3  # 3mm — cutting tolerance, not a decorative frame

CELL_W_PX = cm_to_px(CELL_W_CM)
CELL_H_PX = cm_to_px(CELL_H_CM)
BORDER_PX = cm_to_px(BORDER_CM)

CONTENT_W_PX = CELL_W_PX - 2 * BORDER_PX
CONTENT_H_PX = CELL_H_PX - 2 * BORDER_PX
CONTENT_ASPECT = CONTENT_W_PX / CONTENT_H_PX  # width / height, portrait

# Sheet = 2x2 cells, sized as an exact multiple of the cell so tiling has zero gaps.
SHEET_W_PX = CELL_W_PX * 2
SHEET_H_PX = CELL_H_PX * 2
CELLS_PER_SHEET = 4

BORDER_COLOR = (255, 255, 255)

# Cut guide lines, drawn down the seam between adjacent cells (light so they're a guide,
# not part of the visible design once cut).
CUT_LINE_COLOR = (180, 180, 180)
CUT_LINE_DASH_PX = 8
CUT_LINE_GAP_PX = 6
CUT_LINE_WIDTH_PX = 1
