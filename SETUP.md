# Sell Sheet Automation — Setup & Run

## One-time template prep (Illustrator)

Open `x2_per_page.ai` and `x3_per_page.ai`. In the **Layers panel**, rename the
placeholder objects in each product slot (N = 1 top slot, 2 middle, 3 bottom):

| Frame name | Object type | Gets filled with |
|---|---|---|
| `Logo_N` | rectangle | Brand logo SVG from the site (fitted, centered; rectangle auto-hidden) |
| `Name_N` | text frame | Product title — only used if no `Logo_N` exists / logo missing |
| `Hero_N` | rectangle | First product photo (cover-fit, centered; rectangle auto-hidden) |
| `Copy_N` | text area | Feature bullets, one per line with "•  " prefix |
| `Specs_N` | text area | Spec table rows, TAB-separated: Size → Dimensions → GSM → Weight → Case Pack |
| `Colors_N` | text frame | "Available in White and *Ecru" line |
| `PageTitle` | text frame | Collection title (optional) |
| `PageNum` | text frame | "1 of 3" (optional) |

**Specs table:** make each table body ONE text area (not a grid of little
frames). Set five tab stops in its paragraph style matching the column
positions of the table artwork. Keep the styled header row as static artwork —
the script writes only the data rows. Alternating row stripes stay as
background art; nudge them after the fact if a table runs long/short.

To rename: click the object, then double-click its entry in the Layers panel
and type the name. Names are case-sensitive.

## Per-run workflow

1. **urls.txt** — one product URL per line, in good→better→best order.
   Append ` *` to any product that needs the roomier 2-up layout:

   ```
   https://www.westpointhospitality.com/products/martex-cam-towel-collection
   https://www.westpointhospitality.com/products/martex-simplicity *
   ```

   Pagination: pages fill 3-up in strict order; any page containing a flagged
   product holds max 2 products and uses the 2-up template. Pages with fewer
   than 3 products (including a lone final product) use the 2-up template.

2. **Fetch:**

   ```
   pip3 install requests beautifulsoup4     # first time only
   python3 fetch_sellsheets.py urls.txt --title "Towels" --out ./towels_run
   ```

   Add `--debug` to save each product's raw HTML (send these to Claude if a
   page fails to parse). Output: `towels_run/pages/page_NN.json`,
   `towels_run/images/`, `manifest.json`.

3. **Populate:** In Illustrator, File → Scripts → Other Script… →
   `populate_sellsheets.jsx`. Pick (1) the run folder, (2) the folder holding
   the two templates, (3) an output folder. It generates
   `Towels_page_01.ai`, `Towels_page_02.ai`, … with live text and placed
   images, then reports any frames it couldn't find.

4. **Finesse:** delete unwanted bullets/spec rows, fill any `[DIMS]`/`[CASE]`
   placeholders, swap the hero image if the first CDN image isn't the best
   one (extra downloaded images are in `images/`).

## Generating specs.csv from the Master Price List

```
python3 extract_specs.py "2026 WPH ABC Master Price List.xlsx"
```

This writes `specs_master.csv` (every SKU row found on the numbered tabs) and
`blocks.txt` (all product-block names). To map blocks to Shopify products, add
lines to `mapping.csv` — `block_match` is any case-insensitive substring of
the block header from blocks.txt:

```
handle,block_match
martex-cam-towel-collection,Martex Cam Towel
```

Re-run the same command and it also writes `specs.csv` ready for the fetcher.
White/Ecru duplicate rows collapse automatically. When a new price list comes
out, just re-run against the new workbook — the mapping carries over.

## specs.csv (Dimensions + Case Pack)

The site has no dimensions or case pack data, so they merge from `specs.csv`:

```
handle,size,gsm,dimensions,case_pack
martex-cam-towel-collection,Bath Towel,568,"24"" x 54""",12
martex-cam-towel-collection,Bath Towel,513,"24"" x 50""",12
martex-cam-towel-collection,Hand Towel,475,"16"" x 27""",24
```

Key = handle + size + GSM (GSM disambiguates duplicate sizes; leave gsm blank
to match any row of that size). Rows missing from the CSV render as
`[DIMS]` / `[CASE]` so nothing silently drops out.
