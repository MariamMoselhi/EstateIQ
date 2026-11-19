from app.scraping.utils import (
    PROCESSED_DIR, crawl, make_requests_fetcher, save_json, sitemap_urls,
)

BASE_URL = "https://www.darglobal.co.uk"   # verify in your browser
MAX_PAGES = 80


def run():
    seeds = [BASE_URL + "/"] + sitemap_urls(BASE_URL)
    records = crawl(
        source="DarGlobal",
        base_url=BASE_URL,
        fetcher=make_requests_fetcher(delay=1.0),
        seeds=seeds,
        max_pages=MAX_PAGES,
    )
    save_json(records, PROCESSED_DIR / "darglobal.json")
    print(f"DarGlobal: {len(records)} pages")


if __name__ == "__main__":
    run()