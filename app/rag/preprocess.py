"""Clean scraped pages and split them into retrieval chunks.

Input : data/processed/darglobal.json, data/processed/wasalt.json
Output: data/processed/chunks.jsonl  (one chunk per line)
"""
import hashlib
import json
import re
from pathlib import Path

PROCESSED = Path("data/processed")
MAX_CHARS, OVERLAP = 1100, 150
AR = re.compile(r"[\u0600-\u06FF]")

DG_NOISE = {
    ".", "|", "Register Your Interest", "Please provide your details to register interest.",
    "Gallery", "Show more", "View All Images", "Download Brochure", "Book Unit",
    "Photo Gallery", "Live Feed", "SUBMIT", "Submit",
}
DG_NOISE_RE = re.compile(r"^(\d{1,2}|Discover exclusive luxury real estate.*)$")


def arabic_ratio(s: str) -> float:
    letters = [c for c in s if c.isalpha()]
    return sum(bool(AR.match(c)) for c in letters) / max(len(letters), 1)


# ---------------- DarGlobal ----------------
def clean_darglobal(text: str) -> str:
    out = []
    for ln in text.split("\n"):
        ln = ln.strip()
        if not ln or ln in DG_NOISE or DG_NOISE_RE.match(ln):
            continue
        out.append(ln)
    return "\n".join(out)


# ---------------- Wasalt listings ----------------
PTYPES = ["rest house", "apartment", "villa", "floor", "building", "land", "room", "chalet",
          "duplex", "office", "shop", "warehouse", "farm", "showroom"]
FURN = re.compile(r"^(Un-|Semi-)?Furnished$", re.I)
SPEC_LABELS = {"bedroom", "bedrooms", "bathroom", "bathrooms", "guest room", "guest rooms",
               "living room", "living rooms", "kitchen", "kitchens", "maid room", "maid rooms"}


def parse_listing(text: str, url: str):
    L = [x.strip() for x in text.split("\n") if x.strip()]
    i = next((k for k, x in enumerate(L) if x in ("For Sale", "For Rent")), None)
    if i is None or i == 0 or "Map view" not in L[i:]:
        return None
    purpose = "sale" if L[i] == "For Sale" else "rent"
    title = L[i - 1]
    j0, furnishing = i + 1, None
    if j0 < len(L) and FURN.match(L[j0]):
        furnishing, j0 = L[j0], j0 + 1
    if j0 < len(L) and L[j0] == title:
        j0 += 1
    j = L.index("Map view", i)
    location = ", ".join(x for x in L[j0:j] if x != ",")

    end = next((k for k in range(j, len(L)) if "people viewed" in L[k]), min(j + 25, len(L)))
    seg = L[j + 1:end]
    specs, area, price, period = [], None, None, None
    for k, x in enumerate(seg):
        nxt = seg[k + 1] if k + 1 < len(seg) else ""
        if nxt.lower() in SPEC_LABELS and re.fullmatch(r"\d+", x):
            specs.append(f"{x} {nxt.lower()}")
        elif nxt == "SQM" and re.fullmatch(r"[\d,.]+", x):
            kind = seg[k + 2] if k + 2 < len(seg) else ""
            area = f"{x} sqm" + (f" ({kind})" if kind in ("built-up area", "land area") else "")
        elif price is None and re.fullmatch(r"\d{1,3}(,\d{3})+", x):
            price = x
            if nxt.startswith("/") and len(nxt) > 1:
                period = nxt.strip("/ ").lower()
    keep = {}
    if "Additional Information" in L and "Property Description" in L:
        a_, b_ = L.index("Additional Information"), L.index("Property Description")
        seg2 = L[a_ + 1:b_]
        for k in range(0, len(seg2) - 1, 2):
            if seg2[k] in ("Property usage", "Age", "Facade", "Street width") and not AR.search(seg2[k + 1]):
                keep[seg2[k]] = seg2[k + 1]

    desc = []
    if "Property Description" in L:
        rest = L[L.index("Property Description") + 1:]
        for k, x in enumerate(rest):
            nxt = rest[k + 1] if k + 1 < len(rest) else ""
            if AR.search(x) or "FAL License" in x or x.startswith("Ref no") \
                    or nxt.startswith(("Ref no", "FAL License")):   # next line is the broker block
                break
            if re.match(r"^(Price|Land Area|Built up Area)\s*:", x):
                continue
            desc.append(re.sub(r"^-\s+", "", x))
    m = re.search(r"Last updated:\s*([^\n]+)", text)

    tl = title.lower()
    ptype = next((t for t in PTYPES if re.match(rf"^(un-|semi-)?(furnished )?{t}\b", tl)), None) \
        or next((t for t in PTYPES if t in tl), tl.split(" ")[0])

    parts = [f"{title} - {ptype} for {purpose} in {location}."]
    if furnishing:
        parts.append(f"Furnishing: {furnishing}.")
    if specs:
        parts.append(", ".join(specs).capitalize() + ".")
    if area:
        parts.append(f"Area: {area}.")
    if price:
        parts.append(f"Price: {price} SAR" + (f" per {period}" if period else "") + ".")
    if keep:
        parts.append(" ".join(f"{k}: {v}." for k, v in keep.items()))
    if len(desc) > 1:
        parts.append(" ".join(desc[1:]))
    if m:
        parts.append(f"Listing last updated: {m.group(1).strip()}.")
    parts.append("Source: Wasalt.sa. Prices and availability change; check the live listing.")
    return " ".join(parts), {"purpose": purpose, "ptype": ptype}


# ---------------- chunking ----------------
def split_text(text: str, max_chars=MAX_CHARS, overlap=OVERLAP):
    paras, chunks, cur = [p for p in text.split("\n") if p.strip()], [], ""
    for p in paras:
        if len(cur) + len(p) + 1 > max_chars and cur:
            chunks.append(cur)
            tail = cur[-overlap:]
            tail = tail[tail.find(" ") + 1:] if " " in tail else ""
            cur = tail + "\n" if tail else ""
        cur += p + "\n"
        while len(cur) > max_chars * 1.5:           # very long single paragraph
            chunks.append(cur[:max_chars]); cur = cur[max_chars - overlap:]
            cur = cur[cur.find(" ") + 1:]
    if cur.strip():
        chunks.append(cur)
    return [c.strip() for c in chunks if len(c.strip()) > 80]


def main():
    chunks, seen = [], set()

    def add(source, url, title, kind, text, meta=None):
        h = hashlib.md5(text.lower().encode()).hexdigest()
        if h in seen:
            return
        seen.add(h)
        chunks.append({"id": f"c{len(chunks):05d}", "source": source, "url": url,
                       "title": title, "kind": kind, "text": text, **(meta or {})})

    for r in json.load(open(PROCESSED / "darglobal.json", encoding="utf-8")):
        body = clean_darglobal(r["text"])
        for c in split_text(body):
            add("DarGlobal", r["url"], r["title"], "page", f'{r["title"]}\n{c}')

    for r in json.load(open(PROCESSED / "wasalt.json", encoding="utf-8")):
        if r["kind"] == "listing":
            parsed = parse_listing(r["text"], r["url"])
            if parsed:
                add("Wasalt", r["url"], r["title"], "listing", parsed[0], parsed[1])
        elif arabic_ratio(r["text"]) < 0.3:            # skip Arabic-only static pages
            body = r["text"]
            if r["kind"] == "home":                    # drop search-link spam
                body = body.split("Popular searches")[0]
            parts = split_text(body)
            if r["kind"] == "static":                  # legal pages: keep the opening only
                parts = parts[:6]
            for c in parts:
                add("Wasalt", r["url"], r["title"], r["kind"], c)

    with open(PROCESSED / "chunks.jsonl", "w", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    from collections import Counter
    print(len(chunks), "chunks |", dict(Counter((c["source"], c["kind"]) for c in chunks)))


if __name__ == "__main__":
    main()
