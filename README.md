# Sell Sheet Automation

Generates WestPoint Hospitality sell sheets automatically. Instead of copying
product info from the website and price list by hand, this pipeline pulls
everything into editable Illustrator files — live text, placed images, correct
layout — ready for final design touches.

**Pipeline at a glance:**

```
Master Price List ──► extract_specs.py ──► specs.csv ─┐
                                                      ├─► fetch_sellsheets.py ──► page JSONs + images
Product URLs (urls.txt) ──────────────────────────────┘              │
                                                                     ▼
                                             populate_sellsheets.jsx (Illustrator)
                                                                     │
                                                                     ▼
                                                    Towels_page_01.ai, _02.ai, ...
```

---

## One-time setup

### 1. Install Python (if you don't have it)

- **Mac:** Python 3 is preinstalled. Check with `python3 --version` in Terminal.
- **PC:** Install from [python.org](https://www.python.org/downloads/) — check
  "Add Python to PATH" during install, then use `python` instead of `python3`
  in the commands below.

### 2. Install the two required packages

```
pip3 install requests beautifulsoup4
```

### 3. Get the price list

Grab the current Master Price List xlsx from its usual internal location and
copy it into this repo folder (safe — the .gitignore prevents it from being
committed). **Do not force-add it to git.**

### 4. Generate specs.csv

The website has no dimensions or case-pack data, so those come from the price
list. Run this from the repo folder, using the file's real full name in
quotes:

```
python3 extract_specs.py "2026 WPH ABC Master Price List.xlsx"
```

(Windows: use `python` instead of `python3`. If the xlsx lives elsewhere,
drag the file into the terminal window to paste its full path instead.)

First run writes `blocks.txt` (every product block found) and
`specs_master.csv`. Check `mapping.csv` — if the products you need aren't
mapped yet, add a line per product: the Shopify handle (the last part of the
product URL) and any unique substring of the block name from blocks.txt:

```
handle,block_match
martex-cam-towel-collection,Martex Cam Towel
```

Run the command again — it now also writes `specs.csv`. Commit updated
`mapping.csv` and `specs.csv` so coworkers benefit; when a new price list
drops, re-run and re-commit.

---

## Making a sell sheet

### 1. Build urls.txt

One product URL per line, in the order they should appear (good → better →
best). Add ` *` after any product that needs the roomier 2-page layout:

```
https://www.westpointhospitality.com/products/martex-cam-towel-collection
https://www.westpointhospitality.com/products/martex-simplicity-towel-collection *
```

How pages are decided: pages fill 3 products at a time in strict order. Any
page containing a `*` product holds max 2 and uses the 2-up template. Pages
with fewer than 3 products (including a lone last product) also use the 2-up
template.

### 2. Fetch

```
python3 fetch_sellsheets.py urls.txt --title "Towels" --out ./towels_run
```

This scrapes each product page (bullets, per-size weight/GSM, colors line,
brand logo, photos), merges dims/case pack from specs.csv, and writes
`towels_run/pages/page_01.json...` plus all images. Anything missing from
specs.csv shows up as `[DIMS]` / `[CASE]` so it can't silently drop out.

If a product fails to parse, re-run with `--debug` and send the saved HTML
from `towels_run/debug/` to whoever maintains the scraper.

### 3. Populate in Illustrator

File → Scripts → Other Script… → `populate_sellsheets.jsx`

Three folder prompts: (1) the run folder from step 2, (2) the `templates/`
folder in this repo, (3) where to save the output. It generates one .ai per
page and reports any frames it couldn't find.

### 4. Finesse

- Delete bullets / spec rows that shouldn't appear on the sheet (the script
  brings everything; curating down is faster than typing)
- Fill any `[DIMS]` / `[CASE]` placeholders (then add those rows to
  specs.csv/mapping.csv so next time they're automatic)
- Swap the hero image if needed — alternates are in the run's `images/` folder
- Nudge table stripe artwork if a table runs longer/shorter than the template

---

## Template maintenance

The templates in `templates/` have named placeholder frames the script fills.
If you edit the design, keep the names intact (Layers panel). Per slot
N = 1 (top) to 3 (bottom):

| Name | Type | Filled with |
|---|---|---|
| `Logo_N` | rectangle | Brand logo SVG (fitted; rectangle auto-hides) |
| `Name_N` | text | Product title (fallback when no logo) |
| `Hero_N` | rectangle | Product photo (cover-fit; rectangle auto-hides) |
| `Copy_N` | text area | Feature bullets |
| `Specs_N` | text area | Table rows, TAB-separated (5 tab stops = 5 columns) |
| `Colors_N` | text | "Available in White and *Ecru" |
| `PageTitle` | text | Collection title (optional) |
| `PageNum` | text | "1 of 3" (optional) |

The spec table body must stay ONE text area with tab stops — not separate
frames per cell. The styled header row stays as static artwork.

---

## What never goes in this repo

- The Master Price List xlsx (or any zip of it)
- `specs_master.csv` and `blocks.txt` (derived from it)
- Run output folders and downloaded images

The .gitignore handles these — if git ever shows one of them as a new file to
commit, stop and don't commit it.
