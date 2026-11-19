import requests
from app.scraping.utils import USER_AGENT, extract_page

for u in ["https://wasalt.sa/en/s/wasalt-business",
          "https://wasalt.sa/en/property/sale/apartment-14706-sqm-with-4-bedrooms-5913021"]:
    r = requests.get(u, headers={"User-Agent": USER_AGENT}, timeout=30)
    p = extract_page(r.text, u)
    print(r.status_code, len(r.text), "html chars |", len(p["text"]), "text chars")
    print(p["text"][:600], "\n---")