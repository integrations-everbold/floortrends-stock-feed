import csv
import time
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.floortrends.ie"
SITEMAP_URL = "https://www.floortrends.ie/sitemap"
OUTPUT_FILE = "stock.csv"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (MacCarthys Stock Feed)"
}

BLOCKED_WORDS = [
    "login",
    "account",
    "cart",
    "checkout",
    "wishlist",
    "contact",
    "privacy",
    "terms",
    "search",
    "blog",
    "news",
    "sitemap",
]

def clean_url(href):
    full_url = urljoin(BASE_URL, href)
    parsed = urlparse(full_url)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

def get_soup(url):
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")

def is_allowed_url(url):
    if not url.startswith(BASE_URL):
        return False

    lower_url = url.lower()

    for word in BLOCKED_WORDS:
        if word in lower_url:
            return False

    return True

def get_links_from_page(url):
    soup = get_soup(url)
    links = set()

    for a in soup.select("a[href]"):
        link = clean_url(a["href"])

        if is_allowed_url(link):
            links.add(link)

    return links

def scrape_product_page(url):
    soup = get_soup(url)
    rows = []

    for block in soup.select(".product-variant-line"):
        sku_el = block.select_one(".sku .value")
        stock_el = block.select_one(".availability .value")

        if not sku_el:
            continue

        sku = sku_el.get_text(strip=True)

        if not sku:
            continue

        stock_text = stock_el.get_text(strip=True) if stock_el else ""

        if stock_text.lower() == "in stock":
            quantity = 3
        else:
            quantity = 0

        rows.append({
            "SKU": sku,
            "QTY": quantity
        })

    return rows

print("Step 1: Reading sitemap/category links")
category_links = get_links_from_page(SITEMAP_URL)
print(f"Links found from sitemap: {len(category_links)}")

print("Step 2: Finding product pages")
product_links = set()

for category_url in sorted(category_links):
    try:
        links = get_links_from_page(category_url)

        for link in links:
            rows = scrape_product_page(link)

            if rows:
                product_links.add(link)
                print(f"Product page found: {link}")

        time.sleep(0.5)

    except Exception as error:
        print(f"Skipped category {category_url}: {error}")

print(f"Product pages found: {len(product_links)}")

print("Step 3: Scraping variant stock")
all_rows = []
seen_skus = set()

for product_url in sorted(product_links):
    try:
        rows = scrape_product_page(product_url)

        for row in rows:
            sku = row["SKU"]

            if sku in seen_skus:
                continue

            seen_skus.add(sku)
            all_rows.append(row)

        time.sleep(0.5)

    except Exception as error:
        print(f"Skipped product {product_url}: {error}")

if len(all_rows) < 10:
    raise Exception(f"Only found {len(all_rows)} SKUs. Stopping safely.")

with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as file:
    writer = csv.DictWriter(file, fieldnames=["SKU", "QTY"])
    writer.writeheader()
    writer.writerows(all_rows)

print(f"Created {OUTPUT_FILE}")
print(f"Total SKUs found: {len(all_rows)}")
