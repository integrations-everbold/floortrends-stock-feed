import csv
import requests
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed

SITEMAP_URL = "https://www.floortrends.ie/sitemap.xml"
OUTPUT_FILE = "stock.csv"
DEFAULT_QTY = 3
MAX_WORKERS = 8

HEADERS = {
    "User-Agent": "Mozilla/5.0 (MacCarthys Stock Feed)"
}

BLOCKED_WORDS = [
    "login", "account", "cart", "checkout", "wishlist",
    "contact", "privacy", "terms", "search", "blog", "news"
]

def get_url(url):
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    return response.text

def is_allowed_url(url):
    lower = url.lower()
    if not lower.startswith("https://www.floortrends.ie/"):
        return False
    return not any(word in lower for word in BLOCKED_WORDS)

def read_sitemap(url):
    xml_text = get_url(url)
    root = ET.fromstring(xml_text)

    urls = set()
    sitemaps = []

    for elem in root.iter():
        tag = elem.tag.lower()
        if tag.endswith("loc") and elem.text:
            loc = elem.text.strip()

            if loc.endswith(".xml"):
                sitemaps.append(loc)
            elif is_allowed_url(loc):
                urls.add(loc)

    for sitemap in sitemaps:
        try:
            urls.update(read_sitemap(sitemap))
        except Exception as error:
            print(f"Skipped sitemap {sitemap}: {error}")

    return urls

def scrape_page(url):
    try:
        html = get_url(url)
        soup = BeautifulSoup(html, "html.parser")

        rows = []

        for block in soup.select(".product-variant-line"):
            sku_el = block.select_one(".sku .value")
            stock_el = block.select_one(".availability .value")

            if not sku_el:
                continue

            sku = sku_el.get_text(strip=True)
            stock_text = stock_el.get_text(strip=True) if stock_el else ""

            if not sku:
                continue

            quantity = DEFAULT_QTY if stock_text.lower() == "in stock" else 0

            rows.append({
                "SKU": sku,
                "QTY": quantity
            })

        if rows:
            print(f"Found {len(rows)} SKUs: {url}")

        return rows

    except Exception as error:
        print(f"Skipped {url}: {error}")
        return []

print("Reading XML sitemap...")
urls = sorted(read_sitemap(SITEMAP_URL))
print(f"URLs found in sitemap: {len(urls)}")

all_rows = []
seen_skus = set()

print("Scraping pages...")

with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
    futures = [executor.submit(scrape_page, url) for url in urls]

    for future in as_completed(futures):
        rows = future.result()

        for row in rows:
            sku = row["SKU"]

            if sku in seen_skus:
                continue

            seen_skus.add(sku)
            all_rows.append(row)

if len(all_rows) < 10:
    raise Exception(f"Only found {len(all_rows)} SKUs. Stopping safely.")

all_rows = sorted(all_rows, key=lambda row: row["SKU"])

with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as file:
    writer = csv.DictWriter(file, fieldnames=["SKU", "QTY"])
    writer.writeheader()
    writer.writerows(all_rows)

print(f"Created {OUTPUT_FILE}")
print(f"Total SKUs found: {len(all_rows)}")
