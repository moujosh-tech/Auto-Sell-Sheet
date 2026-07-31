# Sell Sheet Automation

This repo generates WestPoint Hospitality sell sheets as editable Illustrator
files — live text, placed images, correct layout — so nobody retypes product
info from the website or price list.

**If you just need to produce sell sheets, you only need Illustrator and
GitHub Desktop.** The data fetching is already done and lives in this repo.

## Producing a sell sheet (the normal workflow)

1. **Get the latest files.** Open GitHub Desktop → this repo → **Fetch
   origin / Pull**. (First time: File → Clone Repository → pick
   `Auto-Sell-Sheet`.)

2. **Find your collection** in the `runs/` folder — e.g. `runs/blankets`,
   `runs/towels`. Each contains the prepared data (`pages/`) and images for
   that collection. If the collection you need isn't there, ask Josh to add
   it (see MAINTAINER.md).

3. **Run the script in Illustrator:**
   File → Scripts → Other Script… → `populate_sellsheets.jsx`

   It asks for three folders, in this order:
   1. the collection's run folder (e.g. `runs/blankets`)
   2. the `templates/` folder in this repo
   3. wherever you want the generated .ai files saved (NOT inside the repo)

   It generates one .ai per page (`Blankets_page_01.ai`, …) and finishes with
   a summary. If the summary lists "missing frames," tell Josh — that means a
   template got renamed.

4. **Finesse in Illustrator:**
   - Delete feature bullets or spec-table rows that shouldn't appear (the
     script brings in everything available; curating down beats retyping)
   - Fill any `[DIMS]` / `[CASE]` placeholders and report them to Josh so
     they're automatic next time
   - Swap the main photo if a better one exists — alternates are in the run's
     `images/` folder
   - Nudge the table stripe artwork if a table runs longer or shorter than
     the template

That's the whole job. Everything below and in MAINTAINER.md is setup and
data-plumbing that's already been done.

## Rules

- **Never commit the Master Price List** (or any .xlsx/.zip) to this repo.
  The .gitignore blocks it, but don't fight the .gitignore. If GitHub Desktop
  ever shows a price list file as a change to commit, stop and tell Josh.
- Don't rename layers/objects in the template files — the script finds frames
  by name.
- Save your generated .ai files outside the repo folder (they're deliverables,
  not shared tooling).

## Editing the templates (designers)

The design is fully editable EXCEPT the placeholder frame names. Per product
slot N (1 = top):

| Frame | Type | Script fills it with |
|---|---|---|
| `Logo_N` | rectangle | Brand logo (vector, fitted; rectangle auto-hides) |
| `Name_N` | text | Product title (only used when no logo exists) |
| `Hero_N` | rectangle | Product photo (cover-fit; rectangle auto-hides) |
| `Copy_N` | text area | Feature bullets (template's paragraph style supplies the bullet characters) |
| `Specs_Col_H1..` + `Specs_Col1..` | text frames | Spec table as per-column frames: `Specs_Col_H1` = column 1's header, `Specs_Col1` = column 1's body (one row per line — keep identical leading across columns so rows align). On multi-product templates use `Specs_2_Col1` etc. for slot 2+. Unused columns are blanked; leave a header frame unnamed to keep it static |
| `Specs_N` | text area | LEGACY spec table: single text area with tab-separated rows (used only when no column frames exist) |
| `Colors_N` | text | Availability line ("Available in White and *Ecru") |
| `PageTitle` / `PageNum` | text | Collection title / page number (optional) |

Templates: `x1_per_page.ai` (optional — 1-product pages fall back to the
2-up if absent), `x2_per_page.ai`, `x3_per_page.ai`. Templates must have
exactly ONE artboard. Keep the spec-table header row and
stripe artwork as static art — the script writes only the data rows.
