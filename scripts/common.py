"""Shared print geometry: 4 photos per 12.7x17.6cm sheet, arranged 2x2. The gutter
between photos is cut down its middle, so it's sized at 2x the outer margin — each
half of the cut gutter then matches the outer margin, giving every trimmed photo an
equal border on all four sides."""

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


SHEET_W_CM, SHEET_H_CM = 12.7, 17.6  # actual photo paper size
BORDER_CM = 0.3  # 3mm — the border each trimmed photo ends up with on all four sides

SHEET_W_PX = cm_to_px(SHEET_W_CM)
SHEET_H_PX = cm_to_px(SHEET_H_CM)
BORDER_PX = cm_to_px(BORDER_CM)
GUTTER_PX = 2 * BORDER_PX  # cut down the middle, so each half matches the outer margin

# 2x2 grid: margin | content | gutter | content | margin
CONTENT_W_PX = (SHEET_W_PX - 2 * BORDER_PX - GUTTER_PX) // 2
CONTENT_H_PX = (SHEET_H_PX - 2 * BORDER_PX - GUTTER_PX) // 2
CONTENT_ASPECT = CONTENT_W_PX / CONTENT_H_PX  # width / height, portrait

CELLS_PER_SHEET = 4

SHEET_BG_COLOR = (255, 255, 255)

# Cut guide lines, drawn down the middle of the gutter between adjacent photos (light so
# they're a guide, not part of the visible design once cut).
CUT_LINE_COLOR = (180, 180, 180)
CUT_LINE_DASH_PX = 8
CUT_LINE_GAP_PX = 6
CUT_LINE_WIDTH_PX = 1
CUT_LINE_X_PX = BORDER_PX + CONTENT_W_PX + GUTTER_PX // 2
CUT_LINE_Y_PX = BORDER_PX + CONTENT_H_PX + GUTTER_PX // 2
