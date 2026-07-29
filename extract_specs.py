#!/usr/bin/env python3
"""
extract_specs.py — build specs.csv for fetch_sellsheets.py from the WPH
Master Price List workbook.

Pass 1 (always): scans the numbered category sheets, finds product blocks and
their SKU rows, writes:
    specs_master.csv   every row found: sheet, block, size_type, dimensions,
                       gsm, weight, case_pack, color
    blocks.txt         distinct product-block names (for building mapping.csv)

Pass 2 (if mapping.csv exists): joins blocks to Shopify handles and writes
    specs.csv          handle,size,gsm,dimensions,case_pack  (fetcher format)

mapping.csv format — block_match is a case-insensitive substring of the
price-list block header:
    handle,block_match
    martex-cam-towel-collection,Martex Cam Towel

Usage:
    python3 extract_specs.py "2026 WPH ABC Master Price List.xlsx" [--map mapping.csv]
"""

import argparse
import csv
import re
import sys
from collections import OrderedDict

from openpyxl import load_workbook

DIMS_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*[xX]\s*(\d+(?:\.\d+)?)\s*$")

# description prefixes that name the size/type shown in the sell sheet table
TYPE_PREFIX_RE = re.compile(r"^([A-Za-z /&'-]+?)\s*-\s")


def norm(s):
    return re.sub(r"\s+", " ", str(s or "")).strip()


def fmt_dims(raw):
    m = DIMS_RE.match(str(raw or ""))
    if m:
        return f'{m.group(1)}" x {m.group(2)}"'
    return norm(raw)


def find_header(ws):
    """Locate the header row and map column names -> index."""
    for row in ws.iter_rows(min_row=1, max_row=8):
        names = {}
        for cell in row:
            v = norm(cell.value).replace("\n", " ").upper()
            if v and v not in names:  # keep first — headers repeat in the
                names[v] = cell.column - 1  # "Old SKU Info" area to the right
        if "GSM" in names and "DESCRIPTION" in names:
            cols = {
                "size": names.get("SIZE"),
                "weight": names.get("LBS/DZ"),
                "gsm": names.get("GSM"),
                "desc": names.get("DESCRIPTION"),
                "color": names.get("COLOR"),
                "small": names.get("SMALL CASE"),
                "large": names.get("LARGE CASE"),
            }
            return row[0].row, cols
    return None, None


def is_block_header(rowvals, cols):
    """A block header has long text in col A and no GSM/desc data."""
    a = norm(rowvals[0] if rowvals else "")
    if len(a) < 30:
        return False
    gsm = rowvals[cols["gsm"]] if cols["gsm"] is not None and cols["gsm"] < len(rowvals) else None
    desc = rowvals[cols["desc"]] if cols["desc"] is not None and cols["desc"] < len(rowvals) else None
    return gsm in (None, "") and desc in (None, "")


def cellv(rowvals, idx):
    if idx is None or idx >= len(rowvals):
        return ""
    return norm(rowvals[idx])


def size_type_from_desc(desc):
    m = TYPE_PREFIX_RE.match(desc)
    return norm(m.group(1)) if m else ""


def num(s):
    s = norm(s)
    if not s:
        return ""
    try:
        f = float(s)
        return str(int(f)) if f == int(f) else str(f)
    except ValueError:
        return s


def extract(path):
    wb = load_workbook(path, read_only=True, data_only=True)
    records = []
    for ws in wb.worksheets:
        if not ws.title.strip().isdigit():
            continue
        hdr_row, cols = find_header(ws)
        if not cols:
            continue
        block = ""
        for row in ws.iter_rows(min_row=hdr_row + 1, values_only=True):
            rowvals = list(row)
            if is_block_header(rowvals, cols):
                block = norm(rowvals[0])
                continue
            desc = cellv(rowvals, cols["desc"])
            gsm = num(cellv(rowvals, cols["gsm"]))
            if not desc:
                continue
            case = num(cellv(rowvals, cols["small"])) or num(cellv(rowvals, cols["large"]))
            records.append({
                "sheet": ws.title,
                "block": block,
                "size_type": size_type_from_desc(desc) or cellv(rowvals, cols["size"]),
                "dimensions": fmt_dims(cellv(rowvals, cols["size"])),
                "gsm": re.sub(r"\s*GSM$", "", gsm, flags=re.I),
                "weight": num(cellv(rowvals, cols["weight"])),
                "case_pack": case,
                "color": cellv(rowvals, cols["color"]),
                "description": desc,
            })
    return records


def write_master(records, path="specs_master.csv"):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(records[0].keys()))
        w.writeheader()
        w.writerows(records)
    print(f"Wrote {path} ({len(records)} rows)")


def write_blocks(records, path="blocks.txt"):
    seen = OrderedDict()
    for r in records:
        if r["block"]:
            seen.setdefault(r["block"], r["sheet"])
    with open(path, "w", encoding="utf-8") as f:
        for block, sheet in seen.items():
            f.write(f"[tab {sheet}] {block}\n")
    print(f"Wrote {path} ({len(seen)} product blocks)")


def write_specs(records, mapping_path, path="specs.csv"):
    mapping = []
    with open(mapping_path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            h, m = norm(row.get("handle")), norm(row.get("block_match"))
            if h and m:
                mapping.append((h, m.upper()))

    out, seen = [], set()
    for r in records:
        blk = r["block"].upper()
        for handle, match in mapping:
            if match in blk:
                key = (handle, r["size_type"].upper(), r["gsm"])
                if key in seen:  # White + Ecru rows collapse to one spec row
                    continue
                seen.add(key)
                out.append({
                    "handle": handle,
                    "size": r["size_type"],
                    "gsm": r["gsm"],
                    "dimensions": r["dimensions"],
                    "case_pack": r["case_pack"],
                })
                break

    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["handle", "size", "gsm", "dimensions", "case_pack"])
        w.writeheader()
        w.writerows(out)
    print(f"Wrote {path} ({len(out)} rows for {len(mapping)} mapped handles)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("workbook")
    ap.add_argument("--map", default="mapping.csv")
    args = ap.parse_args()

    records = extract(args.workbook)
    if not records:
        print("No records extracted — check the workbook structure.")
        return 1
    write_master(records)
    write_blocks(records)

    import os
    if os.path.exists(args.map):
        write_specs(records, args.map)
    else:
        print(f"(no {args.map} found — create it from blocks.txt to generate specs.csv)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
