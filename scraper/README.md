# FlyRank A9 — The Polite Scraper

A Python scraping pipeline built for the FlyRank Backend Internship.

The scraper downloads the first three catalogue pages from Books to Scrape, discovers all 60 book pages, extracts book information, normalizes and validates the records, handles failures without crashing, and produces a run report.

---

## Target Classification

### Target

**Books to Scrape**

https://books.toscrape.com/

Books to Scrape is a public practice sandbox specifically designed for learning and practising web scraping.

This assignment uses only this practice sandbox.

### Scope

This scraper processes exactly:

- The first 3 catalogue pages
- The 60 book pages linked from those catalogue pages

The scraper does not crawl beyond the first three catalogue pages.

### Data Collected

For every book, the scraper collects these raw fields:

- `title`
- `product_url`
- `price_text`
- `availability_text`
- `rating_text`
- `description`
- `source_page`
- `fetched_at`

The normalized record also contains:

- `price_gbp`

The scraper does not invent missing information. If an optional description is not present, the value is stored as `null`.

### Robots Check

I requested:

https://books.toscrape.com/robots.txt

Result:

**HTTP 404 — no robots.txt file was found.**

A missing robots.txt file was treated as a missing file, not as permission to scrape other websites.

Books to Scrape is explicitly a practice sandbox, which is why it is appropriate for this assignment.

I will not reuse this code on another site without checking its rules and terms first.

---

## Project Structure

```text
scraper/
├── src/
│   └── main.py
├── output/
│   ├── books.json
│   ├── errors.json
│   └── run-report.json
├── cache/
├── README.md
└── .gitignore