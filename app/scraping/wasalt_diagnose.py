import collections
from urllib.parse import urlparse

import requests

from app.scraping.utils import USER_AGENT, Robots, sitemap_urls

BASE = "https://wasalt.sa"
resp = requests.get(BASE + "/robots.txt", headers={"User-Agent": USER_AGENT}, timeout=15)
print("robots.txt status:", resp.status_code)
print(resp.text[:3000])

robots = Robots(BASE)
urls = sitemap_urls(BASE)
allowed = [u for u in urls if robots.allowed(u)]
print(f"\nsitemap URLs: {len(urls)} | allowed: {len(allowed)}")

groups = collections.Counter("/".join(urlparse(u).path.split("/")[:3]) for u in allowed)
print("allowed URL groups:", groups.most_common(25))
print("sample allowed:", allowed[:30])
for u in [BASE + "/", BASE + "/en"]:
    print(u, "->", robots.allowed(u))