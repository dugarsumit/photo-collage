"""Tile prepared cells 2x2 onto 13x18cm print sheets."""

import csv
import sys
from pathlib import Path

from PIL import Image, ImageDraw

from common import (
    CELL_H_PX,
    CELL_W_PX,
    CELLS_PER_SHEET,
    CUT_LINE_COLOR,
    CUT_LINE_DASH_PX,
    CUT_LINE_GAP_PX,
    CUT_LINE_WIDTH_PX,
    DPI,
    SHEET_H_PX,
    SHEET_W_PX,
)

POSITIONS = [(0, 0), (1, 0), (0, 1), (1, 1)]  # (col, row) within the 2x2 grid


def draw_dotted_line(draw: ImageDraw.ImageDraw, start, end):
    (x0, y0), (x1, y1) = start, end
    length = max(abs(x1 - x0), abs(y1 - y0))
    step = CUT_LINE_DASH_PX + CUT_LINE_GAP_PX
    n_steps = int(length // step) + 1
    dx = (x1 - x0) / length if length else 0
    dy = (y1 - y0) / length if length else 0
    for i in range(n_steps):
        seg_start = i * step
        seg_end = min(seg_start + CUT_LINE_DASH_PX, length)
        draw.line(
            [
                (x0 + dx * seg_start, y0 + dy * seg_start),
                (x0 + dx * seg_end, y0 + dy * seg_end),
            ],
            fill=CUT_LINE_COLOR,
            width=CUT_LINE_WIDTH_PX,
        )


def draw_cut_guides(sheet: Image.Image):
    draw = ImageDraw.Draw(sheet)
    draw_dotted_line(draw, (CELL_W_PX, 0), (CELL_W_PX, SHEET_H_PX))
    draw_dotted_line(draw, (0, CELL_H_PX), (SHEET_W_PX, CELL_H_PX))


def run(cells_dir: Path, output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)
    cell_paths = sorted(cells_dir.glob("*_cell.jpg"))
    if not cell_paths:
        print(f"No prepared cells found in {cells_dir}")
        return

    manifest_rows = []
    for sheet_idx in range(0, len(cell_paths), CELLS_PER_SHEET):
        batch = cell_paths[sheet_idx : sheet_idx + CELLS_PER_SHEET]
        sheet_num = sheet_idx // CELLS_PER_SHEET + 1
        sheet = Image.new("RGB", (SHEET_W_PX, SHEET_H_PX), (255, 255, 255))

        for pos, cell_path in zip(POSITIONS, batch):
            col, row = pos
            with Image.open(cell_path) as cell:
                sheet.paste(cell, (col * CELL_W_PX, row * CELL_H_PX))
            manifest_rows.append({
                "sheet": sheet_num,
                "position": f"col{col}_row{row}",
                "source_file": cell_path.name,
            })

        draw_cut_guides(sheet)

        out_path = output_dir / f"sheet_{sheet_num:03d}.jpg"
        sheet.save(out_path, quality=95, dpi=(DPI, DPI))
        print(f"  sheet {sheet_num}: {len(batch)} photo(s) -> {out_path.name}")

    manifest_path = output_dir / "manifest.csv"
    with open(manifest_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["sheet", "position", "source_file"])
        writer.writeheader()
        writer.writerows(manifest_rows)

    n_sheets = (len(cell_paths) + CELLS_PER_SHEET - 1) // CELLS_PER_SHEET
    print(f"Wrote {n_sheets} sheet(s) ({SHEET_W_PX}x{SHEET_H_PX}px @ {DPI}dpi, "
          f"~13x18cm) and {manifest_path}")


if __name__ == "__main__":
    cells_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("output/cells")
    output_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("output/sheets")
    run(cells_dir, output_dir)
