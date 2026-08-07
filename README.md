# photo-collage

Turns a folder of photos into print-ready sheets: each photo is cropped/resized
to a content cell, and 4 cells are tiled 2x2 onto a 12.7x17.6cm sheet with a
3mm margin/gutter (same width on all four sides of every photo) and dotted
cut guides down the middle of each gutter.

## Setup

Requires Python >=3.12 and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
```

## Usage

Put your source photos in `pics/` (jpg, jpeg, png, heic, webp are picked up),
then run the two scripts in order from the project root.

### 1. Prepare cells

Crops/resizes each photo to fit the cell aspect ratio and saves it to
`output/cells/`.

```bash
uv run python scripts/prepare.py [input_dir] [output_dir] [--crop {smart,center,top,bottom}]
```

- `input_dir` — defaults to `pics`
- `output_dir` — defaults to `output/cells`
- `--crop` — which crop strategy to use for every photo in the run (default: `smart`)

Crop strategies:

| mode     | behavior |
|----------|----------|
| `smart`  | saliency detection (edges/entropy/skin tone) picks the most interesting crop window |
| `center` | crops evenly off both sides/ends |
| `top`    | crops evenly off the sides, anchored to the top edge |
| `bottom` | crops evenly off the sides, anchored to the bottom edge |

The photo is also tried rotated 90° and whichever orientation discards less
area is kept. If a photo needs more than 40% of its area discarded, a
warning is printed — that's usually a sign `--crop smart` picked a bad spot
and it's worth re-running just that photo with `center`/`top`/`bottom`
instead, e.g.:

```bash
uv run python scripts/prepare.py pics/some_photo.jpg output/cells --crop center
```

Examples:

```bash
# default (smart crop)
uv run python scripts/prepare.py

# custom folders, centered crop
uv run python scripts/prepare.py pics output/cells --crop center
```

Photos that fail to read are copied to `output/errors/` (or retried once
with truncated-image recovery) and skipped.

### 2. Build print sheets

Tiles the prepared cells 2x2 onto print sheets and writes a manifest.

```bash
uv run python scripts/layout.py [cells_dir] [output_dir]
```

- `cells_dir` — defaults to `output/cells`
- `output_dir` — defaults to `output/sheets`

Output: `sheet_001.jpg`, `sheet_002.jpg`, ... at 300dpi, plus a
`manifest.csv` mapping each sheet position back to its source file.

## Output layout

```
output/
├── cells/       # one image per photo, cropped to cell size
├── sheets/      # 2x2 print sheets + manifest.csv
└── errors/      # copies of photos that errored during prepare
```
