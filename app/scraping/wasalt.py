import hashlib
import random
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone

import requests

from app.scraping.utils import (
    PROCESSED_DIR, USER_AGENT, Robots, extract_page, log,
    make_requests_fetcher, save_json, sitemap_urls,
)

BASE_URL = "https://wasalt.sa"
N_LISTINGS = 150
SEED = 42
LIMIT = int(sys.argv[1]) if len(sys.argv) > 1 else None  # smoke test: python -m ... 6


def stratified_sample(urls, n):
    """Pick n listings spread across (sale/rent, property type)."""
    rng = random.Random(SEED)
    groups = defaultdict(list)
    for u in urls:
        m = re.search(r"/property/(sale|rent)/([a-z]+)", u)
        if m:
            groups[(m.group(1), m.group(2))].append(u)
    for g in groups.values():
        rng.shuffle(g)
    picked, keys = [], list(groups)
    while len(picked) < n and any(groups.values()):
        for k in keys:
            if groups[k] and len(picked) < n:
                picked.append(groups[k].pop())
    log.info("Listing groups: %s", {f"{a}/{b}": len(v) for (a, b), v in groups.items()})
    return picked


def now():
    return datetime.now(timezone.utc).isoformat()


def run():
    robots = Robots(BASE_URL)
    fetch = make_requests_fetcher(delay=1.0)
    records, seen_hashes, fails = [], set(), 0

    # 1) llms.txt: Wasalt's own description, published for AI tools
    try:
        r = requests.get(BASE_URL + "/llms.txt", headers={"User-Agent": USER_AGENT}, timeout=20)
        if r.status_code == 200 and len(r.text) > 100:
            records.append({"source": "Wasalt", "kind": "llms", "url": BASE_URL + "/llms.txt",
                            "title": "Wasalt llms.txt", "description": "",
                            "text": r.text.strip(), "scraped_at": now()})
            log.info("Saved llms.txt (%d chars)", len(r.text))
    except requests.RequestException as e:
        log.warning("llms.txt failed: %s", e)

    # 2) build targets
    all_urls = [u for u in sitemap_urls(BASE_URL) if robots.allowed(u)]
    static = [u for u in all_urls if "/en/s/" in u]
    listings = stratified_sample([u for u in all_urls if "/en/property/" in u], N_LISTINGS)
    targets = [(BASE_URL + "/en/", "home")] + [(u, "static") for u in static] + [(u, "listing") for u in listings]
    if LIMIT:
        targets = targets[:LIMIT]
    log.info("Targets: %d (static %d, listings %d)", len(targets), len(static), len(listings))

    try:
        for i, (url, kind) in enumerate(targets, 1):
            log.info("[%d/%d] %s", i, len(targets), url)
            html = fetch(url)
            if not html:
                fails += 1
                if fails >= 5:
                    log.error("5 failures in a row, aborting.")
                    break
                continue
            fails = 0
            page = extract_page(html, url)
            if len(page["text"]) < 100:
                continue
            h = hashlib.md5(page["text"].encode()).hexdigest()
            if h in seen_hashes:
                log.info("  duplicate content, skipped")
                continue
            seen_hashes.add(h)
            records.append({"source": "Wasalt", "kind": kind, "url": url,
                            "title": page["title"], "description": page["description"],
                            "text": page["text"], "scraped_at": now()})
    finally:  # runs on Ctrl+C or a crash too, so partial data is kept
        save_json(records, PROCESSED_DIR / "wasalt.json")
        counts = defaultdict(int)
        for r in records:
            counts[r["kind"]] += 1
        print("Wasalt:", dict(counts))


if __name__ == "__main__":
    run()
