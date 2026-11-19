# import time
# from playwright.sync_api import sync_playwright


# from app.scraping.utils import (
#     PROCESSED_DIR, RAW_DIR, USER_AGENT, crawl, log, save_json, sitemap_urls,
# )


# BASE_URL = "https://wasalt.sa"   
# MAX_PAGES = 60


# class RenderedFetcher:
#     """Headless-browser fetcher that also records JSON (XHR/fetch) responses."""

#     def __init__(self, delay: float = 1.5):
#         self.delay = delay
#         self.api_hits: list[dict] = []

#     def __enter__(self):
#         # from playwright.sync_api import sync_playwright
#         self.pw = sync_playwright().start()
#         self.browser = self.pw.chromium.launch(headless=True)
#         self.ctx = self.browser.new_context(user_agent=USER_AGENT, locale="en-US")
#         return self

#     def __exit__(self, *exc):
#         self.browser.close()
#         self.pw.stop()

#     def _on_response(self, resp):
#         try:
#             if resp.request.resource_type in ("xhr", "fetch") and "json" in resp.headers.get("content-type", ""):
#                 if len(self.api_hits) < 200:
#                     self.api_hits.append({"url": resp.url, "status": resp.status, "data": resp.json()})
#         except Exception:
#             pass

#     def __call__(self, url: str) -> str:
#         time.sleep(self.delay)
#         page = self.ctx.new_page()
#         page.on("response", self._on_response)
#         try:
#             page.goto(url, wait_until="networkidle", timeout=45000)
#             for _ in range(4):  # trigger lazy-loaded listings
#                 page.mouse.wheel(0, 2500)
#                 page.wait_for_timeout(600)
#             return page.content()
#         except Exception as e:
#             log.warning("Render failed for %s: %s", url, e)
#             return ""
#         finally:
#             page.close()


# # def run():
# #     seeds = [BASE_URL + "/en", BASE_URL + "/"] + sitemap_urls(BASE_URL)
# #     with RenderedFetcher() as fetcher:
# #         records = crawl(
# #             source="Wasalt",
# #             base_url=BASE_URL,
# #             fetcher=fetcher,
# #             seeds=seeds,
# #             max_pages=MAX_PAGES,
# #             exclude=("/ar/", "/ar?"),   # keep English pages only
# #         )
# #         save_json(fetcher.api_hits, RAW_DIR / "wasalt_api_responses.json")
# #     save_json(records, PROCESSED_DIR / "wasalt.json")
# #     print(f"Wasalt: {len(records)} pages, API hits saved to data/raw/")
# from app.scraping.utils import Robots  # add to imports

# def run():
#     robots = Robots(BASE_URL)
#     seeds = [BASE_URL + "/en", BASE_URL + "/"] + [
#         u for u in sitemap_urls(BASE_URL) if robots.allowed(u) and "/ar/" not in u
#     ]
#     log.info("Allowed seeds: %d", len(seeds))
#     with RenderedFetcher() as fetcher:
#         records = crawl(
#             source="Wasalt",
#             base_url=BASE_URL,
#             fetcher=fetcher,
#             seeds=seeds,
#             max_pages=MAX_PAGES,
#             exclude=("/ar/", "/ar?"),
#         )
#         save_json(fetcher.api_hits, RAW_DIR / "wasalt_api_responses.json")
#     save_json(records, PROCESSED_DIR / "wasalt.json")
#     print(f"Wasalt: {len(records)} pages")

# if __name__ == "__main__":
#     run()
# import json
# import random
# import re
# import time
# from collections import defaultdict
# from datetime import datetime, timezone

# import requests
# from bs4 import BeautifulSoup

# from playwright.sync_api import sync_playwright

# from app.scraping.utils import (
#     PROCESSED_DIR, RAW_DIR, USER_AGENT, Robots, extract_page, log, save_json, sitemap_urls,
# )

# BASE_URL = "https://wasalt.sa"
# N_LISTINGS = 150
# SEED = 42


# class RenderedFetcher:
#     """Headless-browser fetcher that also records JSON (XHR/fetch) responses."""

#     def __init__(self, delay: float = 1.5):
#         self.delay = delay
#         self.api_hits: list[dict] = []

#     def __enter__(self):
#         # from playwright.sync_api import sync_playwright
#         self.pw = sync_playwright().start()
#         self.browser = self.pw.chromium.launch(headless=True)
#         self.ctx = self.browser.new_context(user_agent=USER_AGENT, locale="en-US")
#         return self

#     def __exit__(self, *exc):
#         self.browser.close()
#         self.pw.stop()

#     def _on_response(self, resp):
#         try:
#             if resp.request.resource_type in ("xhr", "fetch") and "json" in resp.headers.get("content-type", ""):
#                 if len(self.api_hits) < 200:
#                     self.api_hits.append({"url": resp.url, "status": resp.status, "data": resp.json()})
#         except Exception:
#             pass

#     def __call__(self, url: str) -> str:
#         time.sleep(self.delay)
#         page = self.ctx.new_page()
#         page.on("response", self._on_response)
#         try:
#             page.goto(url, wait_until="networkidle", timeout=45000)
#             page.wait_for_timeout(800)
#             return page.content()
#         except Exception as e:
#             log.warning("Render failed for %s: %s", url, e)
#             return ""
#         finally:
#             page.close()


# def stratified_sample(urls: list[str], n: int) -> list[str]:
#     """Pick n listings spread across (sale/rent, property type)."""
#     rng = random.Random(SEED)
#     groups = defaultdict(list)
#     for u in urls:
#         m = re.search(r"/property/(sale|rent)/([a-z]+)", u)
#         if m:
#             groups[(m.group(1), m.group(2))].append(u)
#     for g in groups.values():
#         rng.shuffle(g)
#     picked, keys = [], list(groups)
#     while len(picked) < n and any(groups.values()):
#         for k in keys:
#             if groups[k] and len(picked) < n:
#                 picked.append(groups[k].pop())
#     log.info("Listing groups: %s", {f"{a}/{b}": len(v) for (a, b), v in groups.items()})
#     return picked


# def json_ld(html: str) -> list:
#     soup = BeautifulSoup(html, "html.parser")
#     out = []
#     for tag in soup.find_all("script", type="application/ld+json"):
#         try:
#             out.append(json.loads(tag.string or ""))
#         except Exception:
#             pass
#     return out


# def record(url: str, page: dict, kind: str, extra=None) -> dict:
#     return {
#         "source": "Wasalt", "kind": kind, "url": url,
#         "title": page["title"], "description": page["description"],
#         "text": page["text"], "structured": extra or [],
#         "scraped_at": datetime.now(timezone.utc).isoformat(),
#     }


# def run():
#     robots = Robots(BASE_URL)
#     records = []

#     # 1) llms.txt: Wasalt's own description of itself, published for AI tools
#     try:
#         r = requests.get(BASE_URL + "/llms.txt", headers={"User-Agent": USER_AGENT}, timeout=20)
#         if r.status_code == 200 and len(r.text) > 100:
#             records.append({
#                 "source": "Wasalt", "kind": "llms", "url": BASE_URL + "/llms.txt",
#                 "title": "Wasalt llms.txt", "description": "", "text": r.text.strip(),
#                 "structured": [], "scraped_at": datetime.now(timezone.utc).isoformat(),
#             })
#             log.info("Saved llms.txt (%d chars)", len(r.text))
#     except requests.RequestException as e:
#         log.warning("llms.txt failed: %s", e)

#     # 2) split sitemap URLs
#     all_urls = [u for u in sitemap_urls(BASE_URL) if robots.allowed(u)]
#     static = [u for u in all_urls if "/en/s/" in u or u.rstrip("/").endswith("/en")]
#     listings = stratified_sample([u for u in all_urls if "/en/property/" in u], N_LISTINGS)
#     targets = [(BASE_URL + "/en/", "home")] + [(u, "static") for u in static] + [(u, "listing") for u in listings]
#     log.info("Targets: %d (static %d, listings %d)", len(targets), len(static), len(listings))

#     with RenderedFetcher() as fetcher:
#         for i, (url, kind) in enumerate(targets, 1):
#             log.info("[%d/%d] %s", i, len(targets), url)
#             html = fetcher(url)
#             if not html:
#                 continue
#             if kind == "listing" and not (RAW_DIR / "sample_listing.html").exists():
#                 RAW_DIR.mkdir(parents=True, exist_ok=True)
#                 (RAW_DIR / "sample_listing.html").write_text(html, encoding="utf-8")
#             page = extract_page(html, url)
#             if len(page["text"]) >= 100:
#                 records.append(record(url, page, kind, json_ld(html)))
#         save_json(fetcher.api_hits, RAW_DIR / "wasalt_api_responses.json")

#     save_json(records, PROCESSED_DIR / "wasalt.json")
#     by_kind = defaultdict(int)
#     for r in records:
#         by_kind[r["kind"]] += 1
#         print("Wasalt:", dict(by_kind))



# if __name__ == "__main__":
#     run()

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