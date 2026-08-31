# FlyRank A9 — The Polite Scraper

A Python scraping pipeline built for the FlyRank Backend Internship.

## Target Classification

### Target

Books to Scrape:

https://books.toscrape.com/

Books to Scrape is a public practice sandbox specifically designed for learning and practising web scraping.

### Scope

This scraper will collect data from:

- The first 3 catalogue pages
- The 60 book pages linked from those catalogue pages

The scraper will not crawl beyond the first three catalogue pages.

### Data Collected

For each book, the scraper will collect:

- title
- product_url
- price_text
- availability_text
- rating_text
- description
- source_page
- fetched_at

The normalized records will also contain:

- price_gbp

### Robots Check

I checked:

https://books.toscrape.com/robots.txt

Result:

TODO — record the result after checking the file.

### Politeness

The scraper will:

- identify itself with a User-Agent
- use request timeouts
- wait at least 500 ms between real requests
- cache downloaded pages during development
- check HTTP status codes
- avoid unnecessary requests
- retry only appropriate failures

I will not reuse this code on another site without checking its rules and terms first.

## Ethics

I will use an official API when one exists.

I will never bypass logins, paywalls, or blocks.

I will collect only the data needed for this assignment.


### Robots Check

I requested:

https://books.toscrape.com/robots.txt

Result:

No robots file found (HTTP 404).
