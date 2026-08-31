from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


# ============================================================
# Discover Three Catalogue Pages
# ============================================================

BASE_URL = "https://books.toscrape.com/"
CATALOGUE_START_URL = (
    "https://books.toscrape.com/catalogue/page-1.html"
)

CACHE_DIR = Path("cache")

TIMEOUT_SECONDS = 10

USER_AGENT = (
    "FlyRankInternshipA9/1.0 "
    "(https://github.com/SiphoMabizela/CRUD-API)"
)


def get_cache_filename(url):
    """
    Convert a catalogue URL into a safe cache filename.
    """

    page_name = url.rstrip("/").split("/")[-1]

    return CACHE_DIR / page_name


def fetch_and_cache(url):
    """
    Fetch a page from the website unless it already exists
    in the local cache.
    """

    cache_file = get_cache_filename(url)

    # --------------------------------------------------------
    # Use cached page if available.
    # --------------------------------------------------------
    if cache_file.exists():
        content = cache_file.read_text(encoding="utf-8")

        print(f"CACHE HIT: {cache_file}")
        print(
            f"Response size: "
            f"{len(content.encode('utf-8'))} bytes"
        )

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
    # Only HTTP 200 is considered successful.
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
    Extract all book links from a catalogue page and
    convert relative URLs into absolute URLs.
    """

    soup = BeautifulSoup(html, "html.parser")

    book_urls = []

    """
    Books to Scrape places each book inside an article
    with the product_pod class.
    """
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
    Find the catalogue's own 'next' link.

    Returns an absolute URL or None when there is no next page.
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
    Follow the catalogue's own next links and process exactly
    the first three catalogue pages.
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

        print(f"Books found on this page: {len(book_urls)}")

        all_book_urls.extend(book_urls)

        # ----------------------------------------------------
        # Website tells us where the next page is.
        # ----------------------------------------------------
        if page_number < 3:
            next_url = find_next_page(
                html,
                current_url
            )

            if next_url is None:
                print("No next page found.")
                break

            current_url = next_url

    # --------------------------------------------------------
    # Remove duplicate URLs while preserving their order.
    # --------------------------------------------------------
    unique_urls = list(dict.fromkeys(all_book_urls))

    print()
    print("========================================")
    print("Stage 2 discovery complete")
    print("========================================")
    print(f"catalogue_pages={len(catalogue_pages)}")
    print(f"discovered={len(all_book_urls)}")
    print(f"unique_urls={len(unique_urls)}")
    print("========================================")

    return catalogue_pages, unique_urls


def main():
    print("FlyRank A9 - Polite Scraper")
    print("Stage 0: Target classification")
    print("Stage 1: Fetch and cache HTML")
    print("Stage 2: Discover three catalogue pages")

    discover_catalogue_pages()


if __name__ == "__main__":
    main()