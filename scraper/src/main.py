import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


# ============================================================
#Extract Book Details
# ============================================================

BASE_URL = "https://books.toscrape.com/"
CATALOGUE_START_URL = (
    "https://books.toscrape.com/catalogue/page-1.html"
)

CACHE_DIR = Path("cache")

TIMEOUT_SECONDS = 10
REQUEST_DELAY_SECONDS = 0.5

USER_AGENT = (
    "FlyRankInternshipA9/1.0 "
    "(https://github.com/SiphoMabizela/CRUD-API)"
)


def get_cache_filename(url):
    """
    Convert a URL into a safe local cache filename.
    """

    if "/catalogue/page-" in url:
        filename = url.rstrip("/").split("/")[-1]
    else:
        filename = url.rstrip("/").split("/")[-1]

    return CACHE_DIR / filename


def fetch_and_cache(url):
    """
    Fetch a page unless it already exists in the local cache.

    Returns:
        str | None: HTML content if successful, otherwise None.
    """

    cache_file = get_cache_filename(url)

    # --------------------------------------------------------
    # Use the local cache when available.
    # --------------------------------------------------------
    if cache_file.exists():
        content = cache_file.read_text(encoding="utf-8")

        print(f"CACHE HIT: {cache_file}")

        return content

    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    print(f"FETCH: {url}")

    headers = {
        "User-Agent": USER_AGENT
    }

    try:
        response = requests.get(
            url,
            headers=headers,
            timeout=TIMEOUT_SECONDS
        )

    except requests.RequestException as error:
        print(f"FETCH FAILED: {error}")
        return None

    # --------------------------------------------------------
    # Only HTTP 200 is considered a successful page.
    # --------------------------------------------------------
    if response.status_code != 200:
        print(
            f"FETCH FAILED: HTTP {response.status_code}"
        )
        return None

    cache_file.write_text(
        response.text,
        encoding="utf-8"
    )

    print(
        f"Saved {cache_file} "
        f"({len(response.content)} bytes)"
    )

    return response.text


def extract_book_links(html, page_url):
    """
    Extract book URLs from a catalogue page.
    """

    soup = BeautifulSoup(html, "html.parser")

    book_urls = []

    for article in soup.select("article.product_pod"):
        link = article.select_one("h3 a")

        if link is None:
            continue

        href = link.get("href")

        if not href:
            continue

        absolute_url = urljoin(page_url, href)

        book_urls.append(absolute_url)

    return book_urls


def find_next_page(html, current_url):
    """
    Find the next catalogue page using the website's own
    next-page link.
    """

    soup = BeautifulSoup(html, "html.parser")

    next_link = soup.select_one("li.next a")

    if next_link is None:
        return None

    href = next_link.get("href")

    if not href:
        return None

    return urljoin(current_url, href)


def discover_catalogue_pages():
    """
    Discover the first three catalogue pages and return
    their URLs plus the 60 unique book URLs.
    """

    current_url = CATALOGUE_START_URL

    catalogue_pages = []
    all_book_urls = []

    for page_number in range(1, 4):

        print()
        print(f"--- Catalogue page {page_number} ---")

        html = fetch_and_cache(current_url)

        if html is None:
            print(
                f"Could not retrieve catalogue page "
                f"{page_number}."
            )
            break

        catalogue_pages.append(current_url)

        book_urls = extract_book_links(
            html,
            current_url
        )

        print(
            f"Books found on this page: "
            f"{len(book_urls)}"
        )

        all_book_urls.extend(book_urls)

        if page_number < 3:
            next_url = find_next_page(
                html,
                current_url
            )

            if next_url is None:
                print("No next page found.")
                break

            current_url = next_url

    unique_urls = list(dict.fromkeys(all_book_urls))

    return catalogue_pages, unique_urls


def extract_text(element):
    """
    Safely extract cleaned text from a BeautifulSoup element.
    """

    if element is None:
        return None

    text = element.get_text(
        " ",
        strip=True
    )

    if not text:
        return None

    return text


def extract_book_record(
    html,
    product_url,
    source_page
):
    """
    Extract the eight required raw fields from a book page.
    """

    soup = BeautifulSoup(html, "html.parser")

    # --------------------------------------------------------
    # Product information table
    # --------------------------------------------------------
    product_info = {}

    for row in soup.select("table.table.table-striped tr"):
        heading = row.find("th")
        value = row.find("td")

        if heading and value:
            key = heading.get_text(
                strip=True
            )

            product_info[key] = value.get_text(
                " ",
                strip=True
            )

    # --------------------------------------------------------
    # Title
    # --------------------------------------------------------
    title_element = soup.select_one(
        "div.product_main h1"
    )

    title = extract_text(title_element)

    # --------------------------------------------------------
    # Price
    # --------------------------------------------------------
    price_element = soup.select_one(
        "div.product_main p.price_color"
    )

    price_text = extract_text(price_element)

    # --------------------------------------------------------
    # Availability
    # --------------------------------------------------------
    availability_text = product_info.get(
        "Availability"
    )

    # --------------------------------------------------------
    # Rating
    # --------------------------------------------------------
    rating_element = soup.select_one(
        "div.product_main p.star-rating"
    )

    rating_text = None

    if rating_element:
        classes = rating_element.get("class", [])

        rating_names = {
            "One",
            "Two",
            "Three",
            "Four",
            "Five"
        }

        for class_name in classes:
            if class_name in rating_names:
                rating_text = class_name
                break

    # --------------------------------------------------------
    # Description
    # --------------------------------------------------------
    description_element = soup.select_one(
        "#product_description + p"
    )

    description = extract_text(
        description_element
    )

    # --------------------------------------------------------
    # Fetch timestamp
    # --------------------------------------------------------
    fetched_at = datetime.now(
        timezone.utc
    ).isoformat()

    return {
        "title": title,
        "product_url": product_url,
        "price_text": price_text,
        "availability_text": availability_text,
        "rating_text": rating_text,
        "description": description,
        "source_page": source_page,
        "fetched_at": fetched_at
    }


def scrape_book_pages(
    catalogue_pages,
    book_urls
):
    """
    Fetch and extract every discovered book page.

    Returns:
        list of raw book records
    """

    records = []

    # --------------------------------------------------------
    # Map each book URL back to the catalogue page where it
    # was discovered. This provides provenance.
    # --------------------------------------------------------
    source_page_by_url = {}

    for source_page in catalogue_pages:

        html = fetch_and_cache(source_page)

        if html is None:
            continue

        page_book_urls = extract_book_links(
            html,
            source_page
        )

        for book_url in page_book_urls:
            source_page_by_url[book_url] = source_page

    # --------------------------------------------------------
    # Visit every unique book URL.
    # --------------------------------------------------------
    for index, product_url in enumerate(
        book_urls,
        start=1
    ):

        print()
        print(
            f"--- Detail page {index}/{len(book_urls)} ---"
        )
        print(product_url)

        html = fetch_and_cache(product_url)

        if html is None:
            print("Skipping failed page.")
            continue

        source_page = source_page_by_url.get(
            product_url
        )

        record = extract_book_record(
            html,
            product_url,
            source_page
        )

        records.append(record)

        # ----------------------------------------------------
        # Wait before the next REAL request.
        #
        # Cached pages return immediately and do not need
        # a delay.
        # ----------------------------------------------------
        if index < len(book_urls):
            cache_file = get_cache_filename(
                product_url
            )

            if cache_file.exists():
                pass
            else:
                time.sleep(
                    REQUEST_DELAY_SECONDS
                )

    return records


def main():

    print("FlyRank A9 - Polite Scraper")
    print("Stage 0: Target classification")
    print("Stage 1: Fetch and cache HTML")
    print("Stage 2: Discover three catalogue pages")
    print("Stage 3: Extract book details")
    print()

    catalogue_pages, book_urls = (
        discover_catalogue_pages()
    )

    print()
    print(
        f"catalogue_pages={len(catalogue_pages)}"
    )
    print(
        f"discovered={len(book_urls)}"
    )
    print()

    records = scrape_book_pages(
        catalogue_pages,
        book_urls
    )

    print()
    print("========================================")
    print("Stage 3 extraction complete")
    print("========================================")
    print(
        f"detail_pages={len(records)}"
    )
    print("========================================")


    if records:
        print()
        print("Sample raw record:")
        print(records[0])


if __name__ == "__main__":
    main()