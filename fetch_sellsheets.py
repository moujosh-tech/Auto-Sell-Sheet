#!/usr/bin/env python3
"""
WestPoint Hospitality sell sheet fetcher.

Reads an ordered list of product URLs, scrapes each product page (rendered HTML
+ Shopify .json), merges Dimensions / Case Pack from specs.csv, paginates into
2-up / 3-up pages, downloads images, and writes one JSON file per page for the
Illustrator populate_sellsheets.jsx script.

Usage:
    python3 fetch_sellsheets.py urls.txt --title "Towels" --out ./output

urls.txt format (order = good/better/best order, * = needs the 2-up layout):
    https://www.westpointhospitality.com/products/martex-cam-towel-collection
    https://www.westpointhospitality.com/products/martex-simplicity *
    https://www.westpointhospitality.com/products/five-star-hotel-collection-towels

specs.csv format (same folder, or pass --specs path):
    handle,size,gsm,dimensions,case_pack
    martex-cam-towel-collection,Bath Towel,568,24 x 54,12

Requires: requests, beautifulsoup4   (pip install requests beautifulsoup4)
"""

import argparse
import csv
import json
import os
import re
import sys
import unicodedata
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) SellSheetBot/1.0"}

SIZE_WORDS = [
    "BATH SHEET", "BATH TOWEL", "HAND TOWEL", "WASH CLOTH", "WASHCLOTH",
    "BATH MAT", "TUB MAT", "BATH RUG", "POOL TOWEL",
]

WEIGHT_GSM_RE = re.compile(
    r"(?P<weight>[\d.]+)\s*lbs?\s*/\s*(?P<gsm>\d+)\s*GSM(?P<note>.*)", re.I
)
GSM_ONLY_RE = re.compile(r"(?P<gsm>\d+)\s*GSM", re.I)
WEIGHT_ONLY_RE = re.compile(r"(?P<weight>[\d.]+)\s*lbs?\b", re.I)


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", s or "")
    return re.sub(r"\s+", " ", s).strip()


def norm_size(s: str) -> str:
    """Normalize a size name for matching against specs.csv."""
    s = norm(s).upper().lstrip("*").strip()
    s = s.replace("WASHCLOTH", "WASH CLOTH")
    return s


def handle_from_url(url: str) -> str:
    path = urlparse(url).path.rstrip("/")
    return path.split("/")[-1].replace(".json", "")


def fetch(url: str) -> requests.Response:
    r = requests.get(url, headers=UA, timeout=30)
    r.raise_for_status()
    return r


def load_specs(path):
    """specs.csv -> {"lookup": {(handle, SIZE, gsm): {...}},
                     "by_handle": {handle: [row, ...] in file order}}"""
    specs = {"lookup": {}, "by_handle": {}}
    if not path or not os.path.exists(path):
        return specs
    with open(path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            h = norm(row.get("handle", ""))
            size = norm(row.get("size", ""))
            gsm = norm(str(row.get("gsm", "")))
            if not h or not size:
                continue
            rec = {
                "item_type": norm(row.get("item_type", "")),
                "size": size,
                "gsm": gsm,
                "dimensions": norm(row.get("dimensions", "")),
                "weight": norm(str(row.get("weight", ""))),
                "case_pack": norm(str(row.get("case_pack", ""))),
            }
            specs["lookup"][(h, norm_size(size), gsm)] = rec
            specs["by_handle"].setdefault(h, []).append(rec)
    return specs


def spec_lookup(specs, handle, size, gsm):
    size = norm_size(size)
    gsm = norm(str(gsm))
    lk = specs.get("lookup", {})
    return (
        lk.get((handle, size, gsm))
        or lk.get((handle, size, ""))
        or {"dimensions": "[DIMS]", "case_pack": "[CASE]"}
    )


def text_of(el) -> str:
    return norm(el.get_text(" ", strip=True))


def is_heading(el) -> bool:
    if el.name in ("h1", "h2", "h3", "h4", "h5", "h6"):
        return True
    if el.name in ("p", "strong", "b", "div", "summary"):
        t = text_of(el)
        return bool(t) and len(t) < 60
    return False


def find_section_list(soup, title_texts):
    """Find the first <ul>/<ol> that follows an element whose text equals one
    of title_texts (case-insensitive)."""
    wanted = {t.upper() for t in title_texts}
    for el in soup.find_all(True):
        t = text_of(el).upper().strip("#: ")
        if t in wanted and el.name not in ("script", "style", "a"):
            lst = el.find_next(["ul", "ol"])
            if lst:
                return lst
    return None


def parse_details_bullets(soup):
    lst = find_section_list(soup, ["Details"])
    if not lst:
        return []
    out = []
    for li in lst.find_all("li", recursive=False) or lst.find_all("li"):
        t = text_of(li)
        if t:
            out.append(t)
    if len(out) >= 3:
        return out
    # sparse primary list (sheets-style pages put bullets under per-item
    # subheadings): walk from Details to the next major section, prefixing
    # each bullet with its subheading
    out2, sub = [], ""
    STOP = {"MANUFACTURING", "CARE INSTRUCTIONS", "RESOURCES"}
    start = None
    for el in soup.find_all(True):
        if text_of(el).upper().strip("#: ") == "DETAILS":
            start = el
            break
    if not start:
        return out
    for el in start.find_all_next(True):
        t = text_of(el).upper().strip("#: ")
        if t in STOP:
            break
        if el.name in ("h3", "h4", "h5", "strong") and text_of(el) and len(text_of(el)) < 40:
            sub = text_of(el)
        elif el.name == "li":
            txt = text_of(el)
            if txt:
                out2.append(f"{sub}: {txt}" if sub else txt)
    return out2 or out


def parse_size_sections(soup):
    """Return ordered list of (size_name, [bullet texts]) for per-size spec
    sections like '#### Bath Towel'."""
    sections = []
    seen = set()
    for el in soup.find_all(True):
        t = text_of(el).upper().strip("#: ")
        if t in SIZE_WORDS and is_heading(el):
            key = (t, id(el))
            if key in seen:
                continue
            seen.add(key)
            lst = el.find_next(["ul", "ol"])
            bullets = [text_of(li) for li in lst.find_all("li")] if lst else []
            sections.append((norm(el.get_text()), bullets))
    return sections


def parse_availability(soup):
    """Prefer short 'Available in White and Ecru*'-style lines (from the
    per-size sections) over marketing prose; normalize 'Ecru*' -> '*Ecru'."""
    candidates = []
    for m in soup.find_all(string=re.compile(r"Available in ", re.I)):
        t = norm(str(m))
        mm = re.search(r"Available in [^.\n]*", t, re.I)
        if mm:
            candidates.append(mm.group(0).strip())
    # keep lines that mention a color word and are short (not paragraphs)
    colorish = [c for c in candidates
                if re.search(r"White|Ecru|Ivory|Grey|Gray|Beige", c, re.I)
                and len(c) < 60]
    starred = [c for c in colorish if "*" in c]
    pick = min(starred or colorish or candidates or [""], key=len)
    # 'Ecru*' -> '*Ecru' to match sell sheet convention
    pick = re.sub(r"\b([A-Za-z]+)\*", r"*\1", pick)
    return pick


def parse_brand_logo(soup):
    img = soup.find("img", alt=re.compile("Brand Logo", re.I))
    if not img:
        img = soup.find("img", src=re.compile(r"\.svg", re.I))
    if img and img.get("src"):
        src = img["src"]
        if src.startswith("//"):
            src = "https:" + src
        return src
    return ""


SPEC_FIELDS = [("Size", 0), ("Dimensions", 1), ("GSM", 2),
               ("Weight lbs/dz", 3), ("Case Pack", 4)]


def build_spec_table(raw_rows, weight_header="Weight lbs/dz"):
    """raw_rows: list of 5-cell rows [size, dims, gsm, weight, case] and
    1-cell group-header rows. Returns {"headers": [...], "rows": [...]}
    keeping only columns that contain data; group rows stay 1-cell."""
    data_rows = [r for r in raw_rows if len(r) > 1]
    keep = []
    for name, idx in SPEC_FIELDS:
        if any(len(r) > idx and str(r[idx]).strip() for r in data_rows):
            if name == "Weight lbs/dz":
                name = weight_header
            keep.append((name, idx))
    headers = [n for n, _ in keep]
    rows = []
    for r in raw_rows:
        if len(r) == 1:
            rows.append(r)
        else:
            rows.append([str(r[i]) if i < len(r) else "" for _, i in keep])
    return {"headers": headers, "rows": rows}


def build_spec_rows(handle, size_sections, specs):
    """Turn per-size bullet sections into table rows:
    [size, dimensions, gsm, weight, case_pack]. One row per weight/GSM bullet.
    A '*' in the source bullet (Ecru marker) is carried onto the size name."""
    rows = []
    for size_name, bullets in size_sections:
        matched = False
        for b in bullets:
            m = WEIGHT_GSM_RE.search(b)
            if m:
                matched = True
                star = "*" if "*" in b else ""
                gsm = m.group("gsm")
                sp = spec_lookup(specs, handle, size_name, gsm)
                rows.append([
                    star + size_name,
                    sp["dimensions"],
                    gsm,
                    m.group("weight"),
                    sp["case_pack"],
                ])
        if not matched:
            # fall back: separate GSM / weight bullets (e.g. Bath Mat sections)
            gsm = weight = ""
            star = ""
            for b in bullets:
                if "*" in b:
                    star = "*"
                if not gsm:
                    g = GSM_ONLY_RE.search(b)
                    if g:
                        gsm = g.group("gsm")
                if not weight:
                    w = WEIGHT_ONLY_RE.search(b)
                    if w and "GSM" not in b.upper():
                        weight = w.group("weight")
            if gsm or weight:
                sp = spec_lookup(specs, handle, size_name, gsm)
                rows.append([star + size_name, sp["dimensions"], gsm, weight,
                             sp["case_pack"]])
    return rows


def scrape_product(url, specs, img_dir, debug_dir=None):
    handle = handle_from_url(url)
    page = fetch(url)
    if debug_dir:
        with open(os.path.join(debug_dir, handle + ".html"), "w",
                  encoding="utf-8") as f:
            f.write(page.text)
    soup = BeautifulSoup(page.text, "html.parser")

    # Shopify .json for clean title + image list
    pj = {}
    try:
        pj = fetch(url.rstrip("/") + ".json").json().get("product", {})
    except Exception as e:
        print(f"  ! .json fetch failed for {handle}: {e}")

    title = norm(pj.get("title") or (soup.find("h1") and text_of(soup.find("h1"))) or handle)
    # description: body_html paragraphs -> plain text, blank line between paras
    desc = ""
    if pj.get("body_html"):
        dsoup = BeautifulSoup(pj["body_html"], "html.parser")
        paras = [norm(p.get_text(" ", strip=True))
                 for p in dsoup.find_all(["p", "div"])] or [norm(dsoup.get_text(" ", strip=True))]
        desc = "\n\n".join(p for p in paras if p)
    images = [im["src"] for im in pj.get("images", [])]
    logo = parse_brand_logo(soup)
    bullets = parse_details_bullets(soup)
    size_sections = parse_size_sections(soup)
    raw = build_spec_rows(handle, size_sections, specs)
    weight_header = "Weight lbs/dz"
    if not raw:
        # pages with no per-size sections (blankets, sheets, pillows...):
        # build the whole table from specs.csv rows for this handle, in file
        # order; item-type changes insert 1-cell group-header rows
        weight_header = "Weight"
        last_type = None
        for r in specs.get("by_handle", {}).get(handle, []):
            if r["item_type"] and r["item_type"] != last_type:
                raw.append([r["item_type"]])
                last_type = r["item_type"]
            raw.append([r["size"], r["dimensions"], r["gsm"], r["weight"],
                        r["case_pack"]])
    spec_table = build_spec_table(raw, weight_header)
    # legacy tabbed-frame rows: drop empty cells
    rows = [r if len(r) == 1 else [c for c in r if str(c).strip()]
            for r in raw]
    colors = parse_availability(soup)

    # download hero + logo
    os.makedirs(img_dir, exist_ok=True)
    hero_path = logo_path = ""
    if images:
        hero_path = download(images[0], os.path.join(img_dir, handle + "_hero"))
    if logo:
        logo_path = download(logo, os.path.join(img_dir, handle + "_logo"))
    extra = []
    for i, src in enumerate(images[1:], start=2):
        extra.append(download(src, os.path.join(img_dir, f"{handle}_{i}")))

    missing = []
    if not bullets:
        missing.append("details bullets")
    if not rows:
        missing.append("spec rows (not on page AND no specs.csv rows for this handle)")
    if missing:
        print(f"  ! {handle}: could not parse {', '.join(missing)} — "
              f"check debug HTML and tell Claude.")

    return {
        "handle": handle,
        "url": url,
        "name": title,
        "logo": os.path.basename(logo_path) if logo_path else "",
        "hero": os.path.basename(hero_path) if hero_path else "",
        "extra_images": [os.path.basename(p) for p in extra],
        "description": desc,
        "bullets": bullets,
        "spec_rows": rows,
        "spec_table": spec_table,
        "colors_line": colors,
    }


def download(url, dest_no_ext):
    try:
        r = fetch(url)
        ext = os.path.splitext(urlparse(url).path)[1] or ".jpg"
        dest = dest_no_ext + ext
        with open(dest, "wb") as f:
            f.write(r.content)
        return dest
    except Exception as e:
        print(f"  ! image download failed {url}: {e}")
        return ""


def paginate(products):
    """Strict order. Page capacity: 3 normally, 2 if any product on the page
    is flagged '*', 1 if flagged '**'. Template matches the product count:
    x3 / x2 / x1 (x1 falls back to x2 in Illustrator if the template is
    missing)."""
    pages, current = [], []

    def cap(items):
        if any(p.get("solo") for p in items):
            return 1
        return 2 if any(p["flagged"] for p in items) else 3

    for p in products:
        if current and len(current) + 1 > cap(current + [p]):
            pages.append(current)
            current = []
        current.append(p)
    if current:
        pages.append(current)

    return [{
        "template": "x" + str(min(len(pg), 3)),
        "products": pg,
    } for pg in pages]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("urls_file")
    ap.add_argument("--title", default="", help="Collection title for PageTitle frame")
    ap.add_argument("--out", default="./output")
    ap.add_argument("--specs", default="specs.csv")
    ap.add_argument("--debug", action="store_true", help="Save raw HTML per product")
    args = ap.parse_args()

    entries = []
    with open(args.urls_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            solo = line.rstrip().endswith("**")
            flagged = line.rstrip().endswith("*")
            url = line.rstrip("* \t")
            entries.append((url, flagged, solo))

    os.makedirs(args.out, exist_ok=True)
    img_dir = os.path.join(args.out, "images")
    pages_dir = os.path.join(args.out, "pages")
    os.makedirs(pages_dir, exist_ok=True)
    debug_dir = None
    if args.debug:
        debug_dir = os.path.join(args.out, "debug")
        os.makedirs(debug_dir, exist_ok=True)

    specs = load_specs(args.specs)
    if not specs:
        print("(!) No specs.csv found/loaded — Dimensions and Case Pack will be "
              "[DIMS]/[CASE] placeholders.")

    products = []
    for url, flagged, solo in entries:
        tag = " [solo flag]" if solo else (" [2-up flag]" if flagged else "")
        print(f"Fetching {url}{tag}")
        prod = scrape_product(url, specs, img_dir, debug_dir)
        prod["flagged"] = flagged
        prod["solo"] = solo
        products.append(prod)

    pages = paginate(products)
    manifest = {
        "collection": args.title,
        "page_count": len(pages),
        "pages": [],
    }
    for i, page in enumerate(pages, start=1):
        page_data = {
            "collection": args.title,
            "page": i,
            "page_count": len(pages),
            "template": page["template"],
            "products": page["products"],
        }
        fname = f"page_{i:02d}.json"
        with open(os.path.join(pages_dir, fname), "w", encoding="utf-8") as f:
            json.dump(page_data, f, indent=2, ensure_ascii=False)
        manifest["pages"].append({
            "file": fname,
            "template": page["template"],
            "products": [p["handle"] for p in page["products"]],
        })
        print(f"Page {i}: {page['template']}  ->  "
              + ", ".join(p["name"] for p in page["products"]))

    with open(os.path.join(args.out, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print(f"\nDone. {len(pages)} page(s) written to {pages_dir}")
    print("Next: run populate_sellsheets.jsx in Illustrator and point it at the "
          "output folder.")


if __name__ == "__main__":
    sys.exit(main())
