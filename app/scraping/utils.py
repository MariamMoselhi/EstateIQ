import json
import logging
import re
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from urllib.parse import urldefrag, urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("scraper")

USER_AGENT = "Mozilla/5.0 (compatible; RealEstateAssistantBot/1.0; educational technical assignment)"
RAW_DIR = Path("data/raw")
PROCESSED_DIR = Path("data/processed")
SKIP_EXT = (".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".pdf", ".zip",
            ".mp4", ".css", ".js", ".ico", ".xml", ".json", ".woff", ".woff2")


# robots.txt
# class Robots:
#     def __init__(self, base_url: str):
#         self.rp = RobotFileParser()
#         self.rp.set_url(urljoin(base_url, "/robots.txt"))
#         try:
#             self.rp.read()
#         except Exception as e:
#             log.warning("Could not read robots.txt: %s", e)

#     def allowed(self, url: str) -> bool:
#         try:
#             return self.rp.can_fetch(USER_AGENT, url)
#         except Exception:
#             return True
class Robots:
    def __init__(self, base_url: str):
        self.rp = RobotFileParser()
        try:
            r = requests.get(urljoin(base_url, "/robots.txt"),
                             headers={"User-Agent": USER_AGENT}, timeout=15)
            if r.status_code == 200:
                self.rp.parse(r.text.splitlines())
            else:  
                log.warning("robots.txt returned %s, treating as allow-all", r.status_code)
                self.rp.parse([])
        except Exception as e:
            log.warning("Could not read robots.txt: %s", e)
            self.rp.parse([])

    def allowed(self, url: str) -> bool:
        try:
            return self.rp.can_fetch(USER_AGENT, url)
        except Exception:
            return True

# HTTP 
def make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"})
    return s


def make_requests_fetcher(delay: float = 1.0) -> Callable[[str], str]:
    session = make_session()

    def fetch(url: str) -> str:
        time.sleep(delay)
        for attempt in range(3):
            try:
                r = session.get(url, timeout=25)
                if r.status_code == 200:
                    return r.text
                log.warning("HTTP %s for %s", r.status_code, url)
                if r.status_code in (403, 404):
                    return ""
            except requests.RequestException as e:
                log.warning("Attempt %d failed for %s: %s", attempt + 1, url, e)
            time.sleep(2 ** attempt)
        return ""

    return fetch


# sitemap 
def sitemap_urls(base_url: str, session: requests.Session | None = None, limit: int = 2000) -> list[str]:
    session = session or make_session()
    candidates = [urljoin(base_url, "/sitemap.xml"), urljoin(base_url, "/sitemap_index.xml")]
    try:  # robots.txt may declare sitemaps
        txt = session.get(urljoin(base_url, "/robots.txt"), timeout=15).text
        candidates += re.findall(r"(?im)^sitemap:\s*(\S+)", txt)
    except requests.RequestException:
        pass

    seen_maps, urls = set(), []
    queue = deque(dict.fromkeys(candidates))
    while queue and len(urls) < limit:
        sm = queue.popleft()
        if sm in seen_maps:
            continue
        seen_maps.add(sm)
        try:
            r = session.get(sm, timeout=20)
            if r.status_code != 200:
                continue
        except requests.RequestException:
            continue
        for loc in re.findall(r"<loc>\s*(.*?)\s*</loc>", r.text, flags=re.S):
            loc = loc.replace("&amp;", "&")
            if loc.endswith(".xml") or "sitemap" in loc.lower().rsplit("/", 1)[-1]:
                queue.append(loc)
            else:
                urls.append(loc)
        time.sleep(0.5)
    log.info("Sitemap discovery found %d URLs", len(urls))
    return list(dict.fromkeys(urls))


# parsing
def extract_page(html: str, url: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(strip=True) if soup.title else ""
    meta = soup.find("meta", attrs={"name": "description"})
    description = meta["content"].strip() if meta and meta.get("content") else ""

    links = []
    for a in soup.find_all("a", href=True):
        href, _ = urldefrag(urljoin(url, a["href"]))
        links.append(href)

    for tag in soup(["script", "style", "noscript", "svg", "nav", "footer", "header", "form", "iframe"]):
        tag.decompose()
    main = soup.find("main") or soup.body or soup
    lines = [ln.strip() for ln in main.get_text("\n").splitlines()]
    text = "\n".join(ln for ln in lines if ln)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return {"title": title, "description": description, "text": text, "links": links}


# crawler
def crawl(
    source: str,
    base_url: str,
    fetcher: Callable[[str], str],
    seeds: list[str],
    max_pages: int = 80,
    exclude: tuple[str, ...] = (),
    include: tuple[str, ...] = (),
    min_chars: int = 200,
) -> list[dict]:
    robots = Robots(base_url)
    host = urlparse(base_url).netloc.replace("www.", "")
    queue, seen, records = deque(seeds), set(), []

    def ok(u: str) -> bool:
        p = urlparse(u)
        if p.netloc.replace("www.", "") != host or p.path.lower().endswith(SKIP_EXT):
            return False
        if any(x in u for x in exclude):
            return False
        return True

    while queue and len(records) < max_pages:
        url = queue.popleft()
        if url in seen or not ok(url):
            continue
        seen.add(url)
        if not robots.allowed(url):
            log.info("Blocked by robots.txt: %s", url)
            continue

        log.info("[%d/%d] %s", len(records) + 1, max_pages, url)
        html = fetcher(url)
        if not html:
            continue
        page = extract_page(html, url)

        if len(page["text"]) >= min_chars:
            records.append({
                "source": source,
                "url": url,
                "title": page["title"],
                "description": page["description"],
                "text": page["text"],
                "scraped_at": datetime.now(timezone.utc).isoformat(),
            })
        for link in page["links"]:
            if link not in seen and ok(link) and (not include or any(i in link for i in include)):
                queue.append(link)
    return records


def save_json(data, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("Saved %s", path)