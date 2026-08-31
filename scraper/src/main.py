import time
from pathlib import Path

import requests


# ============================================================
# FlyRank Internship - Backend Track - Week 5 - Assignment A9
# Stage 1: Fetch and Cache HTML
# ============================================================

BASE_URL = "https://books.toscrape.com/"
CATALOGUE_PAGE_1 = "https://books.toscrape.com/catalogue/page-1.html"

CACHE_DIR = Path("cache")
CACHE_FILE = CACHE_DIR / "catalogue-page-1.html"

TIMEOUT_SECONDS = 10

USER_AGENT = (
    "FlyRankInternshipA9/1.0 "
    "(https://github.com/SiphoMabizela/CRUD-API)"
)


def fetch_and_cache_catalogue_page():
    """
    Fetch the first catalogue page from Books to Scrape.

    If the page has already been cached locally, use the cached
    copy instead of making another request to the website.
    """

    # --------------------------------------------------------
    # Stage 1: Use the cache if it already exists.
    # --------------------------------------------------------
    if CACHE_FILE.exists():
        content = CACHE_FILE.read_text(encoding="utf-8")

        print(f"CACHE HIT: {CACHE_FILE}")
        print(f"Response size: {len(content.encode('utf-8'))} bytes")

        return content

    # --------------------------------------------------------
    # Create the cache directory if necessary.
    # --------------------------------------------------------
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    print(f"FETCH: {CATALOGUE_PAGE_1}")

    headers = {
        "User-Agent": USER_AGENT
    }

    try:
        response = requests.get(
            CATALOGUE_PAGE_1,
            headers=headers,
            timeout=TIMEOUT_SECONDS
        )

    except requests.RequestException as error:
        print(f"FETCH FAILED: {error}")
        return None

    # --------------------------------------------------------
    # Only HTTP 200 is considered a successful fetch.
    # --------------------------------------------------------
    if response.status_code != 200:
        print(
            f"FETCH FAILED: HTTP {response.status_code}"
        )
        return None

    # --------------------------------------------------------
    # Save the successful response to the local cache.
    # --------------------------------------------------------
    CACHE_FILE.write_text(
        response.text,
        encoding="utf-8"
    )

    response_size = len(response.content)

    print(
        f"Saved {CACHE_FILE} "
        f"({response_size} bytes)"
    )

    return response.text


def main():
    print("FlyRank A9 - Polite Scraper")
    print("Stage 0: Target classification")
    print("Stage 1: Fetch and cache HTML")
    print()

    fetch_and_cache_catalogue_page()


if __name__ == "__main__":
    main()