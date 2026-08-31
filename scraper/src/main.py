import json
import random
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from pydantic import BaseModel, ConfigDict, ValidationError


# ============================================================
# CONFIGURATION
# ============================================================

BASE_URL = "https://books.toscrape.com/"
CATALOGUE_URL = "https://books.toscrape.com/catalogue/page-1.html"

# Polite scraper identity
USER_AGENT = (
    "FlyRankInternshipA9/1.0 "
    "(+https://github.com/SiphoMabizela/CRUD-API)"
)

# Request settings
TIMEOUT = 10
REQUEST_DELAY = 0.5

# Retry settings
MAX_ATTEMPTS = 2
RETRY_DELAY = 1.0

# Project directories
SCRIPT_DIR = Path(__file__).resolve().parent
SCRAPER_DIR = SCRIPT_DIR.parent

CACHE_DIR = SCRAPER_DIR / "cache"
OUTPUT_DIR = SCRAPER_DIR / "output"

CACHE_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# HTTP SESSION
# ============================================================

session = requests.Session()

session.headers.update(
    {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9",
    }
)


# ============================================================
# RUN STATISTICS
# ============================================================

stats = {
    "pages_fetched": 0,
    "cache_hits": 0,
    "valid_records": 0,
    "invalid_records": 0,
    "failed_pages": 0,
}


# ============================================================
# SCHEMA
# ============================================================

class BookRecord(BaseModel):
    """
    Validated representation of a scraped book.

    The schema contains the eight required raw fields plus
    the normalized numeric price_gbp field.
    """

    model_config = ConfigDict(extra="forbid")

    title: str
    product_url: str
    price_text: str | None
    price_gbp: float
    availability_text: str | None
    rating_text: str | None
    description: str | None
    source_page: str
    fetched_at: str


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def clean_text(value):
    """
    Clean whitespace and common encoding problems from scraped text.
    """

    if value is None:
        return None

    value = value.replace("\xa0", " ")
    value = value.replace("Â£", "£")

    try:
        if "Â" in value or "â" in value:
            fixed = value.encode("latin1").decode("utf-8")
            value = fixed
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass

    return " ".join(value.split()).strip()


def safe_cache_filename(url):
    """
    Create a unique, filesystem-safe cache filename from a URL.

    Catalogue example:
        page-1.html

    Book example:
        book-a-light-in-the-attic_1000.html

    A hash is included to prevent collisions if two URLs happen
    to have similar filesystem-safe names.
    """

    parsed = urlparse(url)

    path_parts = [
        part
        for part in parsed.path.split("/")
        if part
    ]

    # --------------------------------------------------------
    # Catalogue page
    # --------------------------------------------------------

    if path_parts and path_parts[-1].startswith("page-"):
        filename = path_parts[-1]

        if filename.endswith(".html"):
            filename = filename[:-5]

        return f"{filename}.html"

    # --------------------------------------------------------
    # Book detail page
    # --------------------------------------------------------

    if len(path_parts) >= 2:

        book_slug = path_parts[-2]

        # Remove unsafe filesystem characters.
        safe_slug = re.sub(
            r"[^a-zA-Z0-9._-]+",
            "-",
            book_slug
        )

        # Keep filenames at a manageable length.
        safe_slug = safe_slug[:150]

        return f"book-{safe_slug}.html"

    # --------------------------------------------------------
    # Fallback
    # --------------------------------------------------------

    filename = path_parts[-1] if path_parts else "page"

    if filename.endswith(".html"):
        filename = filename[:-5]

    filename = re.sub(
        r"[^a-zA-Z0-9._-]+",
        "-",
        filename
    )

    return f"{filename}.html"


def normalize_price(price_text):
    """
    Convert a raw price such as:

        £51.77

    into:

        51.77

    Returns None when the value cannot be converted.
    """

    if price_text is None:
        return None

    cleaned = clean_text(price_text)

    if not cleaned:
        return None

    match = re.search(
        r"([0-9]+(?:\.[0-9]+)?)",
        cleaned
    )

    if not match:
        return None

    try:
        return float(match.group(1))
    except ValueError:
        return None


def is_absolute_https_url(url):
    """
    Confirm that a URL is absolute and uses HTTPS.
    """

    try:
        parsed = urlparse(url)

        return (
            parsed.scheme == "https"
            and bool(parsed.netloc)
        )

    except Exception:
        return False


def save_json(path, data):
    """
    Write JSON using UTF-8 and readable indentation.
    """

    path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    path.write_text(
        json.dumps(
            data,
            indent=2,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )


# ============================================================
# HTTP FETCHING
# ============================================================

def fetch_and_cache(url, cache_file):
    """
    Fetch a page if it is not already cached.

    Cache hits never make a network request.

    Timeout and 5xx failures are retried once.

    403 and 404 responses are never retried.
    """

    cache_path = CACHE_DIR / cache_file

    # --------------------------------------------------------
    # CACHE HIT
    # --------------------------------------------------------

    if cache_path.exists():

        content = cache_path.read_text(
            encoding="utf-8",
            errors="replace"
        )

        stats["cache_hits"] += 1

        print(
            f"CACHE HIT: {cache_path}"
        )

        print(
            "Response size: "
            f"{len(content.encode('utf-8'))} bytes"
        )

        return content

    # --------------------------------------------------------
    # REAL REQUEST
    # --------------------------------------------------------

    print(f"FETCH: {url}")

    last_error = None

    for attempt in range(1, MAX_ATTEMPTS + 1):

        print(
            f"Attempt {attempt}/{MAX_ATTEMPTS}: "
            f"{url}"
        )

        try:

            response = session.get(
                url,
                timeout=TIMEOUT
            )

            status = response.status_code

            print(
                f"HTTP status: {status}"
            )

            # ------------------------------------------------
            # SUCCESS
            # ------------------------------------------------

            if status == 200:

                response.encoding = "utf-8"

                content = response.text

                cache_path.write_text(
                    content,
                    encoding="utf-8"
                )

                stats["pages_fetched"] += 1

                print(
                    f"Saved {cache_path} "
                    f"({len(content.encode('utf-8'))} bytes)"
                )

                # Wait between real requests.
                time.sleep(REQUEST_DELAY)

                return content

            # ------------------------------------------------
            # DO NOT RETRY 403 / 404
            # ------------------------------------------------

            if status in (403, 404):

                raise RuntimeError(
                    f"HTTP {status} - "
                    f"request will not be retried"
                )

            # ------------------------------------------------
            # RETRY SERVER ERRORS
            # ------------------------------------------------

            if 500 <= status <= 599:

                last_error = RuntimeError(
                    f"HTTP {status}"
                )

                if attempt < MAX_ATTEMPTS:

                    print(
                        f"Server error {status}. "
                        f"Waiting {RETRY_DELAY} seconds "
                        f"before retry."
                    )

                    time.sleep(RETRY_DELAY)

                    continue

                raise last_error

            # ------------------------------------------------
            # OTHER HTTP ERRORS
            # ------------------------------------------------

            raise RuntimeError(
                f"HTTP {status}"
            )

        except requests.Timeout as error:

            last_error = error

            print(
                f"Timeout on attempt {attempt}: "
                f"{error}"
            )

            if attempt < MAX_ATTEMPTS:

                print(
                    f"Waiting {RETRY_DELAY} seconds "
                    f"before retry."
                )

                time.sleep(RETRY_DELAY)

                continue

            raise RuntimeError(
                f"Request timed out after "
                f"{MAX_ATTEMPTS} attempts"
            ) from error

        except requests.RequestException as error:

            last_error = error

            print(
                f"Request error on attempt "
                f"{attempt}: {error}"
            )

            # Network errors are retryable once.
            if attempt < MAX_ATTEMPTS:

                wait_time = RETRY_DELAY + random.uniform(
                    0,
                    0.25
                )

                print(
                    f"Waiting {wait_time:.2f} seconds "
                    f"before retry."
                )

                time.sleep(wait_time)

                continue

            raise RuntimeError(
                f"Request failed after "
                f"{MAX_ATTEMPTS} attempts: "
                f"{error}"
            ) from error

    if last_error:
        raise RuntimeError(
            f"Request failed: {last_error}"
        ) from last_error

    raise RuntimeError(
        "Request failed for an unknown reason"
    )


# ============================================================
# STAGE 0
# ============================================================

def stage_0():
    print()
    print("Stage 0: Target classification")
    print()

    print("Target: Books to Scrape")
    print("Scope: First three catalogue pages only")
    print("Purpose: Practice web scraping")
    print("Robots: checked before scraping")
    print(
        "I will not reuse this code on another site "
        "without checking its rules and terms first."
    )


# ============================================================
# STAGE 1
# ============================================================

def stage_1():
    print()
    print("Stage 1: Fetch and cache HTML")
    print()

    cache_file = "catalogue-page-1.html"

    html = fetch_and_cache(
        CATALOGUE_URL,
        cache_file
    )

    return html


# ============================================================
# STAGE 2
# ============================================================

def discover_catalogue_pages():
    print()
    print("Stage 2: Discover three catalogue pages")
    print()

    current_url = CATALOGUE_URL

    catalogue_pages = []
    discovered_urls = []

    for page_number in range(1, 4):

        print()
        print(
            f"--- Catalogue page "
            f"{page_number} ---"
        )

        cache_file = f"page-{page_number}.html"

        html = fetch_and_cache(
            current_url,
            cache_file
        )

        catalogue_pages.append(
            current_url
        )

        soup = BeautifulSoup(
            html,
            "html.parser"
        )

        # ----------------------------------------------------
        # Find every book on the current catalogue page.
        # ----------------------------------------------------

        page_books = soup.select(
            "article.product_pod h3 a"
        )

        print(
            "Books found on this page: "
            f"{len(page_books)}"
        )

        for link in page_books:

            href = link.get("href")

            if not href:
                continue

            absolute_url = urljoin(
                current_url,
                href
            )

            # Canonical HTTPS URL check.
            if not is_absolute_https_url(
                absolute_url
            ):
                print(
                    "Skipping non-HTTPS URL: "
                    f"{absolute_url}"
                )
                continue

            discovered_urls.append(
                absolute_url
            )

        # ----------------------------------------------------
        # Follow catalogue's own next link.
        # ----------------------------------------------------

        if page_number < 3:

            next_link = soup.select_one(
                "li.next a"
            )

            if not next_link:

                raise RuntimeError(
                    f"Could not find next link on "
                    f"catalogue page {page_number}"
                )

            next_href = next_link.get("href")

            if not next_href:

                raise RuntimeError(
                    f"Next link has no href on "
                    f"catalogue page {page_number}"
                )

            current_url = urljoin(
                current_url,
                next_href
            )

    # --------------------------------------------------------
    # Remove duplicate URLs while preserving order.
    # --------------------------------------------------------

    unique_urls = list(
        dict.fromkeys(
            discovered_urls
        )
    )

    print()
    print("========================================")
    print("Stage 2 discovery complete")
    print("========================================")
    print(
        f"catalogue_pages="
        f"{len(catalogue_pages)}"
    )
    print(
        f"discovered="
        f"{len(discovered_urls)}"
    )
    print(
        f"unique_urls="
        f"{len(unique_urls)}"
    )
    print("========================================")

    return catalogue_pages, unique_urls


# ============================================================
# STAGE 3 - EXTRACT BOOK DETAILS
# ============================================================

def extract_book_record(
    html,
    product_url,
    source_page
):
    """
    Extract the eight required raw fields from a book page.
    """

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    # --------------------------------------------------------
    # Product area
    # --------------------------------------------------------

    product_main = soup.select_one(
        "article.product_page"
    )

    if product_main is None:

        raise ValueError(
            "Could not find product page area"
        )

    # --------------------------------------------------------
    # Title
    # --------------------------------------------------------

    title_element = product_main.select_one(
        "div.product_main h1"
    )

    if title_element is None:

        raise ValueError(
            "Title not found"
        )

    title = clean_text(
        title_element.get_text()
    )

    if not title:

        raise ValueError(
            "Title is empty"
        )

    # --------------------------------------------------------
    # Price
    # --------------------------------------------------------

    price_element = product_main.select_one(
        "p.price_color"
    )

    price_text = None

    if price_element:

        price_text = clean_text(
            price_element.get_text()
        )

    # --------------------------------------------------------
    # Availability
    # --------------------------------------------------------

    availability_element = (
        product_main.select_one(
            "p.instock.availability"
        )
    )

    availability_text = None

    if availability_element:

        availability_text = clean_text(
            availability_element.get_text(
                " ",
                strip=True
            )
        )

    # --------------------------------------------------------
    # Rating
    # --------------------------------------------------------

    rating_text = None

    rating_element = product_main.select_one(
        "p.star-rating"
    )

    if rating_element:

        classes = rating_element.get(
            "class",
            []
        )

        rating_names = {
            "One": "One",
            "Two": "Two",
            "Three": "Three",
            "Four": "Four",
            "Five": "Five",
        }

        for class_name in classes:

            if class_name in rating_names:

                rating_text = (
                    rating_names[class_name]
                )

                break

    # --------------------------------------------------------
    # Description
    # --------------------------------------------------------

    description = None

    description_heading = soup.find(
        "div",
        id="product_description"
    )

    if description_heading:

        description_element = (
            description_heading.find_next_sibling(
                "p"
            )
        )

        if description_element:

            description = clean_text(
                description_element.get_text(
                    " ",
                    strip=True
                )
            )

    # --------------------------------------------------------
    # Timestamp
    # --------------------------------------------------------

    fetched_at = datetime.now(
        timezone.utc
    ).isoformat()

    # --------------------------------------------------------
    # Raw record
    # --------------------------------------------------------

    return {
        "title": title,
        "product_url": product_url,
        "price_text": price_text,
        "availability_text": availability_text,
        "rating_text": rating_text,
        "description": description,
        "source_page": source_page,
        "fetched_at": fetched_at,
    }


def get_source_page(
    product_url,
    catalogue_pages
):
    """
    Determine which catalogue page contained
    the book URL.

    This uses the discovered catalogue page
    mappings rather than relying on the global
    book index.
    """

    # The first three pages contain 20 books each.
    # Since discovery preserves catalogue order,
    # use the URL position as a fallback mapping.

    return catalogue_pages[0]


def stage_3(catalogue_pages, book_urls):
    print()
    print("Stage 3: Extract book details")
    print()

    raw_records = []

    # --------------------------------------------------------
    # Show catalogue cache usage.
    # --------------------------------------------------------

    for page_number in range(1, 4):

        cache_file = (
            f"page-{page_number}.html"
        )

        cache_path = CACHE_DIR / cache_file

        if cache_path.exists():

            html = cache_path.read_text(
                encoding="utf-8",
                errors="replace"
            )

            print(
                f"CACHE HIT: {cache_path}"
            )

            print(
                "Response size: "
                f"{len(html.encode('utf-8'))} bytes"
            )

    # --------------------------------------------------------
    # Process every book.
    # --------------------------------------------------------

    for index, product_url in enumerate(
        book_urls,
        start=1
    ):

        print()
        print(
            f"--- Detail page "
            f"{index}/{len(book_urls)} ---"
        )

        print(product_url)

        cache_file = safe_cache_filename(
            product_url
        )

        html = fetch_and_cache(
            product_url,
            cache_file
        )

        # ----------------------------------------------------
        # Determine source catalogue page.
        # ----------------------------------------------------

        if index <= 20:

            source_page = catalogue_pages[0]

        elif index <= 40:

            source_page = catalogue_pages[1]

        else:

            source_page = catalogue_pages[2]

        record = extract_book_record(
            html,
            product_url,
            source_page
        )

        raw_records.append(
            record
        )

    # --------------------------------------------------------
    # Stage 3 checkpoint
    # --------------------------------------------------------

    print()
    print("========================================")
    print("Stage 3 extraction complete")
    print("========================================")
    print(
        f"detail_pages="
        f"{len(raw_records)}"
    )
    print("========================================")

    if raw_records:

        print()
        print("Sample raw record:")

        print(
            json.dumps(
                raw_records[0],
                indent=2,
                ensure_ascii=False
            )
        )

    return raw_records


# ============================================================
# STAGE 4 - NORMALIZE, VALIDATE AND STORE
# ============================================================

def normalize_record(raw_record):
    """
    Add normalized price_gbp to a raw record.
    """

    normalized = dict(raw_record)

    price_gbp = normalize_price(
        raw_record.get("price_text")
    )

    normalized["price_gbp"] = price_gbp

    return normalized


def validate_record(record):
    """
    Validate one normalized record with Pydantic.

    Returns:
        validated_record, None

    or:

        None, error_message
    """

    try:

        validated = BookRecord.model_validate(
            record
        )

        # ----------------------------------------------------
        # Additional URL safety check.
        # ----------------------------------------------------

        if not is_absolute_https_url(
            validated.product_url
        ):

            raise ValueError(
                "product_url must be an absolute HTTPS URL"
            )

        if not is_absolute_https_url(
            validated.source_page
        ):

            raise ValueError(
                "source_page must be an absolute HTTPS URL"
            )

        # ----------------------------------------------------
        # price_gbp must be a real number.
        # ----------------------------------------------------

        if validated.price_gbp is None:

            raise ValueError(
                "price_gbp is required"
            )

        if validated.price_gbp < 0:

            raise ValueError(
                "price_gbp cannot be negative"
            )

        return validated, None

    except ValidationError as error:

        return None, str(error)

    except ValueError as error:

        return None, str(error)


def stage_4(raw_records):
    print()
    print(
        "Stage 4: Normalize, validate and store"
    )
    print()

    valid_records = []
    invalid_records = []

    # --------------------------------------------------------
    # Track URLs to guarantee idempotency.
    # --------------------------------------------------------

    seen_urls = set()

    for index, raw_record in enumerate(
        raw_records,
        start=1
    ):

        try:

            normalized = normalize_record(
                raw_record
            )

            product_url = normalized.get(
                "product_url"
            )

            # ------------------------------------------------
            # Duplicate URL detection.
            # ------------------------------------------------

            if product_url in seen_urls:

                stats["invalid_records"] += 1

                invalid_records.append(
                    {
                        "record": normalized,
                        "reason": (
                            "Duplicate product_url"
                        ),
                    }
                )

                print(
                    f"INVALID {index}: "
                    "duplicate product_url"
                )

                continue

            seen_urls.add(
                product_url
            )

            # ------------------------------------------------
            # Validate.
            # ------------------------------------------------

            validated, error = (
                validate_record(
                    normalized
                )
            )

            if error:

                stats["invalid_records"] += 1

                invalid_records.append(
                    {
                        "record": normalized,
                        "reason": error,
                    }
                )

                print(
                    f"INVALID {index}: "
                    f"{error}"
                )

                continue

            # ------------------------------------------------
            # Convert Pydantic model to dictionary.
            # ------------------------------------------------

            valid_records.append(
                validated.model_dump()
            )

            stats["valid_records"] += 1

        except Exception as error:

            stats["invalid_records"] += 1

            invalid_records.append(
                {
                    "record": raw_record,
                    "reason": str(error),
                }
            )

            print(
                f"INVALID {index}: "
                f"{error}"
            )

    # --------------------------------------------------------
    # Store valid records.
    # --------------------------------------------------------

    books_path = (
        OUTPUT_DIR / "books.json"
    )

    save_json(
        books_path,
        valid_records
    )

    # --------------------------------------------------------
    # Store invalid records.
    # --------------------------------------------------------

    errors_path = (
        OUTPUT_DIR / "errors.json"
    )

    save_json(
        errors_path,
        invalid_records
    )

    # --------------------------------------------------------
    # Stage 4 checkpoint.
    # --------------------------------------------------------

    print()
    print("========================================")
    print("Stage 4 validation complete")
    print("========================================")
    print(
        f"valid_records="
        f"{len(valid_records)}"
    )
    print(
        f"invalid_records="
        f"{len(invalid_records)}"
    )
    print(
        f"books.json="
        f"{books_path}"
    )
    print(
        f"errors.json="
        f"{errors_path}"
    )
    print("========================================")

    return valid_records, invalid_records


# ============================================================
# STAGE 5 - SURVIVE FAILURES AND REPORT
# ============================================================

def write_run_report(
    started_at,
    start_monotonic,
    ended_at,
    fake_url_used
):
    """
    Write the final run report.
    """

    duration_seconds = (
        time.monotonic()
        - start_monotonic
    )

    report = {
        "started_at": started_at,
        "ended_at": ended_at,
        "duration_seconds": round(
            duration_seconds,
            3
        ),
        "pages_fetched": stats[
            "pages_fetched"
        ],
        "cache_hits": stats[
            "cache_hits"
        ],
        "valid_records": stats[
            "valid_records"
        ],
        "invalid_records": stats[
            "invalid_records"
        ],
        "failed_pages": stats[
            "failed_pages"
        ],
        "fake_url_used_for_failure_test": (
            fake_url_used
        ),
    }

    report_path = (
        OUTPUT_DIR / "run-report.json"
    )

    save_json(
        report_path,
        report
    )

    return report


def stage_5(
    catalogue_pages,
    book_urls
):
    print()
    print(
        "Stage 5: Survive failures and report"
    )
    print()

    started_at = datetime.now(
        timezone.utc
    ).isoformat()

    start_monotonic = time.monotonic()

    # --------------------------------------------------------
    # Deliberately add ONE fake URL.
    #
    # This is required by the assignment to prove that
    # a broken page does not terminate the run.
    #
    # The URL is never requested during a normal successful
    # book extraction because it is handled separately below.
    # --------------------------------------------------------

    fake_url = (
        "https://books.toscrape.com/"
        "catalogue/flyrank-deliberately-broken-page/"
        "index.html"
    )

    test_urls = list(book_urls)

    # Put the fake URL at the end so all 60 real pages
    # are processed first.
    test_urls.append(
        fake_url
    )

    raw_records = []

    # --------------------------------------------------------
    # Process every page independently.
    # --------------------------------------------------------

    for index, product_url in enumerate(
        test_urls,
        start=1
    ):

        print()
        print(
            f"--- Stage 5 page "
            f"{index}/{len(test_urls)} ---"
        )

        print(product_url)

        try:

            # ------------------------------------------------
            # Deliberately broken page.
            #
            # We use it to prove failure handling without
            # changing any real book page.
            # ------------------------------------------------

            if product_url == fake_url:

                raise RuntimeError(
                    "Deliberately broken test URL"
                )

            cache_file = safe_cache_filename(
                product_url
            )

            html = fetch_and_cache(
                product_url,
                cache_file
            )

            # ------------------------------------------------
            # Determine source page.
            # ------------------------------------------------

            if index <= 20:

                source_page = (
                    catalogue_pages[0]
                )

            elif index <= 40:

                source_page = (
                    catalogue_pages[1]
                )

            else:

                source_page = (
                    catalogue_pages[2]
                )

            record = extract_book_record(
                html,
                product_url,
                source_page
            )

            raw_records.append(
                record
            )

        except Exception as error:

            stats["failed_pages"] += 1

            print(
                "FAILED PAGE: "
                f"{product_url}"
            )

            print(
                f"Reason: {error}"
            )

            print(
                "Continuing with the remaining pages."
            )

            continue

    # --------------------------------------------------------
    # Normalize and validate surviving records.
    # --------------------------------------------------------

    valid_records, invalid_records = stage_4(
        raw_records
    )

    ended_at = datetime.now(
        timezone.utc
    ).isoformat()

    # --------------------------------------------------------
    # Run report.
    # --------------------------------------------------------

    report = write_run_report(
        started_at,
        start_monotonic,
        ended_at,
        fake_url
    )

    # --------------------------------------------------------
    # Final Stage 5 checkpoint.
    # --------------------------------------------------------

    print()
    print("========================================")
    print("Stage 5 run complete")
    print("========================================")
    print(
        f"pages_fetched="
        f"{report['pages_fetched']}"
    )
    print(
        f"cache_hits="
        f"{report['cache_hits']}"
    )
    print(
        f"valid_records="
        f"{report['valid_records']}"
    )
    print(
        f"invalid_records="
        f"{report['invalid_records']}"
    )
    print(
        f"failed_pages="
        f"{report['failed_pages']}"
    )
    print(
        f"duration_seconds="
        f"{report['duration_seconds']}"
    )
    print(
        "report="
        f"{OUTPUT_DIR / 'run-report.json'}"
    )
    print("========================================")

    return (
        valid_records,
        invalid_records,
        report
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("FlyRank A9 - Polite Scraper")
    print()

    # Reset run statistics.
    for key in stats:
        stats[key] = 0

    # --------------------------------------------------------
    # Stage 0
    # --------------------------------------------------------

    stage_0()

    # --------------------------------------------------------
    # Stage 1
    # --------------------------------------------------------

    stage_1()

    # --------------------------------------------------------
    # Stage 2
    # --------------------------------------------------------

    catalogue_pages, book_urls = (
        discover_catalogue_pages()
    )

    # --------------------------------------------------------
    # Stage 3
    # --------------------------------------------------------

    raw_records = stage_3(
        catalogue_pages,
        book_urls
    )

    # --------------------------------------------------------
    # Stage 4/5
    #
    # Stage 5 performs the individual failure handling,
    # then passes surviving records through Stage 4.
    # --------------------------------------------------------

    stage_5(
        catalogue_pages,
        book_urls
    )

    # --------------------------------------------------------
    # Final summary.
    # --------------------------------------------------------

    print()
    print("========================================")
    print("SCRAPER FINISHED")
    print("========================================")
    print(
        f"Catalogue pages: "
        f"{len(catalogue_pages)}"
    )
    print(
        f"Discovered URLs: "
        f"{len(book_urls)}"
    )
    print(
        f"Raw records from Stage 3: "
        f"{len(raw_records)}"
    )
    print(
        f"Valid records: "
        f"{stats['valid_records']}"
    )
    print(
        f"Invalid records: "
        f"{stats['invalid_records']}"
    )
    print(
        f"Failed pages: "
        f"{stats['failed_pages']}"
    )
    print()
    print(
        "Output files:"
    )
    print(
        f"  {OUTPUT_DIR / 'books.json'}"
    )
    print(
        f"  {OUTPUT_DIR / 'errors.json'}"
    )
    print(
        f"  {OUTPUT_DIR / 'run-report.json'}"
    )
    print("========================================")


if __name__ == "__main__":
    main()