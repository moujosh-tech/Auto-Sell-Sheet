# Maintainer Guide (Josh)

Everything coworkers don't touch: fetching data, the price list, mappings,
and debugging. Requires Python 3 with:

```
pip3 install requests beautifulsoup4 openpyxl
```

## Adding a collection to runs/ (the routine task)

1. Create/edit `urls.txt` in the repo root (gitignored — it's scratch):
   one product URL per line, good → better → best order. Flags:
   ` *` = product needs the roomier 2-up layout (its page holds max 2);
   ` **` = product gets a full page to itself (the 1-up template).
   Pages hold 3 products otherwise; the template always matches the page's
   product count (x3/x2/x1).

2. Fetch into a committed run folder (straight quotes only — beware macOS
   smart quotes if copying commands from Notes):

   ```
   python3 fetch_sellsheets.py urls.txt --title "Blankets" --out ./runs/blankets
   ```

3. Sanity-check the console output (page assignments, any `!` warnings),
   then commit + push `runs/blankets` so coworkers can pull it.

Re-running with the same --out refreshes a collection in place (after site
copy changes, new products, etc.). Commit the diff.

## Price list refresh (when a new master list drops)

1. Copy the new xlsx into the repo folder (gitignored) — shorten the name to
   `pricelist.xlsx` to save typing
2. `python3 extract_specs.py pricelist.xlsx`
3. Check the console counts, spot-check `specs.csv`, commit `specs.csv`
4. Delete the xlsx from the folder when done if you don't want it syncing to
   OneDrive

The extractor understands all five tab layouts in the workbook: towels
(lbs/dz + GSM), blankets (Weight), sheets (Cut/Finish Size + Hem/Depth, with
fitted pocket depth appended to dimensions), oz-based categories (bedspreads,
duvets, pillows, protectors, pads), and it skips the misc SKU tab. Weight
values > 50 with no GSM column are treated as GSM (Atelier Luxe quirk).

## mapping.csv (connecting price list blocks to products)

One line per product: Shopify handle (last part of the product URL) +
a distinctive substring of the block header from `blocks.txt`:

```
handle,block_match
martex-cam-towel-collection,Martex Cam Towel
```

Rules learned the hard way:
- Make block_match specific. Brand names repeat across categories — "Grand
  Patrician" alone would attach bed-sheet rows to the blanket product. Use
  "Grand Patrician - Cotton Blanket".
- When a product's colors are separate price-list blocks (e.g. Millennium
  White and Millennium Bone), map BOTH blocks to the same handle — that's
  what powers the `*` alt-color row marking.
- Star logic is differential: rows are starred only when SOME sizes come in
  the alt color. If all sizes do, no stars (the Colors line covers it).

## How the fetcher decides what goes in the spec table

- Page has per-size sections with "X lbs / Y GSM" bullets (towels): table is
  built from the page, dims/case merged from specs.csv by handle+size+GSM.
- Page has no size data (blankets, sheets, pillows, pads): the entire table
  comes from specs.csv rows for that handle, in price-list order. Item-type
  headers (Flat Sheet / Fitted Sheet / Pillow Case) are emitted as their own
  lines; empty cells are dropped, so sheets tables come out 3-column
  (Size | Dims | Case).
- Missing specs.csv rows render as `[DIMS]` / `[CASE]` — never silently
  dropped. When a coworker reports placeholders, fix mapping.csv or the
  price-list extract and refresh the run.

## Debugging a product that parses wrong

```
python3 fetch_sellsheets.py urls.txt --title "X" --out ./test_run --debug
```

`test_run/debug/<handle>.html` is the raw page — send it to Claude with a
description of what's missing/wrong. test_run/ is gitignored.

## JSX maintenance notes

- The script unlocks all layers before populating and restores lock/visibility
  states before saving. SVG logos import via groupItems.createFromFile (vector);
  rasters via placedItems. Placement failures go to the end-of-run warning
  list rather than stopping the run.
- Copy_N receives plain lines — bullet characters come from the template's
  paragraph style.
- Frame lookup is by exact name, first match wins. Keep names unique per
  template (one artboard, no leftover placeholder boards).

## Repo hygiene

- Coworkers: Settings → Collaborators on GitHub
- The nightmare scenario is the price list entering git history — a commit is
  forever even after deletion. The .gitignore blocks it; the habit that
  actually protects you is reading the file list before every commit.
