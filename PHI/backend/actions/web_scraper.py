"""Web scraping module for J.A.R.V.I.S.

Extracts content from any URL with:
  - Static HTML parsing (BeautifulSoup)
  - Dynamic JS-rendered content (Playwright headless browser)
  - Structured data extraction (JSON-LD, meta tags, microdata)
  - Article/content extraction (readability)
  - Table extraction
  - Product/price extraction
  - Robots.txt compliance
  - Caching and rate limiting
  - Automatic encoding detection
"""

import asyncio
import logging
import re
import hashlib
import json
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse, urljoin
from collections import OrderedDict

import aiohttp
from bs4 import BeautifulSoup, Tag

from backend.shared.config import settings

logger = logging.getLogger(__name__)


# ============================================================
# Cache
# ============================================================

class ScrapeCache:
    """In-memory cache with TTL for scraped pages."""

    def __init__(self, max_size: int = 100, ttl_seconds: int = 300):
        self._cache: OrderedDict = OrderedDict()
        self._max_size = max_size
        self._ttl = ttl_seconds

    def _key(self, url: str) -> str:
        return hashlib.md5(url.encode()).hexdigest()

    def get(self, url: str) -> Optional[Dict]:
        key = self._key(url)
        if key in self._cache:
            entry = self._cache[key]
            if datetime.now(timezone.utc) - entry["timestamp"] < timedelta(seconds=self._ttl):
                self._cache.move_to_end(key)
                return entry["data"]
            else:
                del self._cache[key]
        return None

    def set(self, url: str, data: Dict):
        key = self._key(url)
        self._cache[key] = {"data": data, "timestamp": datetime.now(timezone.utc)}
        if len(self._cache) > self._max_size:
            self._cache.popitem(last=False)

    def clear(self):
        self._cache.clear()

    @property
    def size(self) -> int:
        return len(self._cache)


scrape_cache = ScrapeCache()


# ============================================================
# Robots.txt cache
# ============================================================

_robots_cache: Dict[str, bool] = {}
_robots_timestamp: Dict[str, datetime] = {}


async def _can_fetch(url: str, user_agent: str = "JARVIS/1.0") -> bool:
    """Check robots.txt before scraping."""
    parsed = urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    if base in _robots_cache:
        if datetime.now(timezone.utc) - _robots_timestamp.get(base, datetime.min) < timedelta(hours=1):
            return _robots_cache[base]

    robots_url = f"{base}/robots.txt"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(robots_url, timeout=5) as resp:
                if resp.status == 200:
                    text = await resp.text()
                    from urllib.robotparser import RobotFileParser
                    rp = RobotFileParser()
                    rp.parse(text.splitlines())
                    allowed = rp.can_fetch(user_agent, url)
                    _robots_cache[base] = allowed
                    _robots_timestamp[base] = datetime.now(timezone.utc)
                    return allowed
    except Exception as e:
        logger.debug(f"Robots.txt check failed for {base}: {e}")

    _robots_cache[base] = True  # Default to allowed if cannot check
    _robots_timestamp[base] = datetime.now(timezone.utc)
    return True


# ============================================================
# HTML Fetching
# ============================================================

async def _fetch_html(url: str, headers: dict = None, timeout: float = 15) -> Optional[str]:
    """Fetch HTML content from a URL."""
    default_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }
    if headers:
        default_headers.update(headers)

    async with aiohttp.ClientSession(headers=default_headers) as session:
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout),
                                   allow_redirects=True) as resp:
                if resp.status != 200:
                    logger.warning(f"HTTP {resp.status} for {url}")
                    return None
                content_type = resp.headers.get("Content-Type", "")
                if "text/html" not in content_type and "application/xhtml" not in content_type:
                    logger.debug(f"Non-HTML content type: {content_type}")
                    return await resp.text()
                return await resp.text()
        except asyncio.TimeoutError:
            logger.warning(f"Timeout fetching {url}")
            return None
        except Exception as e:
            logger.warning(f"Error fetching {url}: {e}")
            return None


# ============================================================
# Dynamic JS rendering (Playwright)
# ============================================================

_playwright_available = None
_playwright_browser = None


async def _ensure_playwright():
    """Lazy-load Playwright for JS-rendered pages."""
    global _playwright_available, _playwright_browser
    if _playwright_available is False:
        return False
    if _playwright_available is True and _playwright_browser:
        return True

    try:
        from playwright.async_api import async_playwright
        p = await async_playwright().start()
        _playwright_browser = await p.chromium.launch(headless=True)
        _playwright_available = True
        logger.info("Playwright browser launched")
        return True
    except Exception as e:
        logger.warning(f"Playwright not available: {e}")
        _playwright_available = False
        return False


async def _fetch_html_dynamic(url: str, wait_selector: str = None,
                               timeout: float = 30) -> Optional[str]:
    """Fetch HTML from JS-rendered pages using Playwright."""
    if not await _ensure_playwright():
        return None

    try:
        from playwright.async_api import async_playwright
        page = await _playwright_browser.new_page()
        await page.goto(url, wait_until="networkidle", timeout=int(timeout * 1000))

        if wait_selector:
            try:
                await page.wait_for_selector(wait_selector, timeout=10000)
            except Exception:
                pass

        await asyncio.sleep(2)
        content = await page.content()
        await page.close()
        return content
    except Exception as e:
        logger.warning(f"Dynamic fetch failed for {url}: {e}")
        return None


# ============================================================
# Content Extraction
# ============================================================

def _make_soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


def _extract_title(soup: BeautifulSoup) -> str:
    title = soup.title.string if soup.title else ""
    return title.strip() if title else ""


def _extract_meta_description(soup: BeautifulSoup) -> str:
    meta = soup.find("meta", attrs={"name": "description"}) or \
           soup.find("meta", attrs={"property": "og:description"})
    return meta.get("content", "").strip() if meta else ""


def _extract_meta_keywords(soup: BeautifulSoup) -> List[str]:
    meta = soup.find("meta", attrs={"name": "keywords"})
    if meta and meta.get("content"):
        return [k.strip() for k in meta["content"].split(",")]
    return []


def _extract_json_ld(soup: BeautifulSoup) -> List[Dict]:
    """Extract structured data from JSON-LD scripts."""
    results = []
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string)
            results.append(data if isinstance(data, list) else [data])
        except (json.JSONDecodeError, TypeError):
            continue
    return [item for sublist in results for item in sublist]


def _extract_open_graph(soup: BeautifulSoup) -> Dict[str, str]:
    """Extract Open Graph meta tags."""
    og = {}
    for meta in soup.find_all("meta"):
        prop = meta.get("property", "") or meta.get("name", "")
        if prop.startswith("og:"):
            og[prop[3:]] = meta.get("content", "")
    return og


def _extract_main_content(soup: BeautifulSoup) -> str:
    """Extract the main article/content from a page."""
    # Try common content selectors
    for selector in ["article", "[role='main']", "main", ".post-content",
                     ".article-content", ".entry-content", "#content",
                     ".content", "#main-content"]:
        element = soup.select_one(selector)
        if element:
            return _clean_text(element.get_text(separator="\n", strip=True))

    # Remove nav, header, footer, sidebar
    for tag in soup.find_all(["nav", "header", "footer", "aside",
                              ".sidebar", "#sidebar", ".nav", ".menu"]):
        tag.decompose()

    body = soup.find("body")
    if body:
        return _clean_text(body.get_text(separator="\n", strip=True))

    return _clean_text(soup.get_text(separator="\n", strip=True))


def _clean_text(text: str) -> str:
    """Clean extracted text: remove excessive whitespace, normalize."""
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r' {2,}', ' ', text)
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text)
    return text.strip()


def _extract_headlines(soup: BeautifulSoup) -> List[Dict[str, str]]:
    """Extract all headlines (h1-h3) with hierarchy."""
    headlines = []
    for tag in soup.find_all(["h1", "h2", "h3"]):
        text = tag.get_text(strip=True)
        if text and len(text) > 5:
            headlines.append({
                "level": tag.name,
                "text": text,
            })
    return headlines


def _extract_links(soup: BeautifulSoup, base_url: str, max_links: int = 50) -> List[Dict[str, str]]:
    """Extract all links from a page."""
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        text = a.get_text(strip=True)
        full_url = urljoin(base_url, href)
        if full_url.startswith(("http://", "https://")):
            links.append({
                "url": full_url,
                "text": text[:100] if text else full_url[:100],
            })
    return links[:max_links]


def _extract_tables(soup: BeautifulSoup) -> List[Dict[str, Any]]:
    """Extract HTML tables as structured data."""
    tables = []
    for i, table in enumerate(soup.find_all("table")):
        rows = []
        headers = []
        for th in table.find_all("th"):
            headers.append(th.get_text(strip=True))

        for tr in table.find_all("tr"):
            cells = []
            for td in tr.find_all(["td", "th"]):
                cells.append(td.get_text(strip=True))
            if cells:
                rows.append(cells)

        if rows:
            tables.append({
                "index": i,
                "headers": headers,
                "rows": rows[:50],
                "row_count": len(rows),
            })
    return tables


def _extract_images(soup: BeautifulSoup, base_url: str, max_images: int = 20) -> List[Dict]:
    """Extract image URLs and alt text."""
    images = []
    for img in soup.find_all("img", src=True):
        src = urljoin(base_url, img["src"])
        alt = img.get("alt", "")
        if src and not src.startswith("data:"):
            images.append({
                "url": src,
                "alt": alt[:100] if alt else "",
                "width": img.get("width", ""),
                "height": img.get("height", ""),
            })
    return images[:max_images]


def _extract_prices(soup: BeautifulSoup) -> List[Dict[str, Any]]:
    """Extract potential prices from a page using common patterns."""
    prices = []
    price_patterns = [
        r'\$\d{1,3}(?:,\d{3})*(?:\.\d{2})?',
        r'€\d{1,3}(?:,\d{3})*(?:\.\d{2})?',
        r'£\d{1,3}(?:,\d{3})*(?:\.\d{2})?',
        r'₹\d{1,3}(?:,\d{3})*(?:\.\d{2})?',
        r'\d{1,3}(?:,\d{3})*(?:\.\d{2})?\s*(?:USD|EUR|GBP|INR)',
    ]
    for price_class in ["price", "Price", "product-price", "sale-price",
                        "current-price", "[data-price]", ".amount"]:
        elements = soup.select(price_class)
        for el in elements:
            text = el.get_text(strip=True)
            for pattern in price_patterns:
                match = re.search(pattern, text)
                if match:
                    prices.append({
                        "price": match.group(),
                        "context": text[:50],
                    })
                    break

    body_text = soup.get_text()
    for pattern in price_patterns:
        for match in re.finditer(pattern, body_text):
            context_start = max(0, match.start() - 30)
            context_end = min(len(body_text), match.end() + 30)
            prices.append({
                "price": match.group(),
                "context": body_text[context_start:context_end].strip(),
            })

    seen = set()
    unique_prices = []
    for p in prices:
        if p["price"] not in seen:
            seen.add(p["price"])
            unique_prices.append(p)
    return unique_prices[:20]


# ============================================================
# Main Scrape Function
# ============================================================

async def scrape_url(url: str, extract_type: str = "auto",
                     dynamic: bool = False, wait_selector: str = None,
                     respect_robots: bool = True) -> Dict[str, Any]:
    """Scrape a URL and extract structured content.

    Args:
        url: The URL to scrape
        extract_type: 'auto', 'article', 'headlines', 'table', 'links',
                     'images', 'prices', 'metadata', 'full'
        dynamic: Use Playwright headless browser for JS-rendered pages
        wait_selector: CSS selector to wait for (dynamic mode only)
        respect_robots: Check robots.txt before scraping

    Returns:
        Dict with extracted content
    """
    start = datetime.now(timezone.utc)

    # Check cache
    cache_key = f"{url}:{extract_type}:{dynamic}"
    cached = scrape_cache.get(cache_key)
    if cached:
        return cached

    # Robots.txt check
    if respect_robots:
        allowed = await _can_fetch(url)
        if not allowed:
            return {
                "url": url,
                "error": "Blocked by robots.txt",
                "success": False,
                "elapsed_ms": 0,
            }

    # Fetch HTML
    if dynamic:
        html = await _fetch_html_dynamic(url, wait_selector)
    else:
        html = await _fetch_html(url)

    if not html:
        # Try dynamic fallback
        if not dynamic:
            html = await _fetch_html_dynamic(url, wait_selector)

    if not html:
        return {
            "url": url,
            "error": "Could not fetch URL",
            "success": False,
            "elapsed_ms": (datetime.now(timezone.utc) - start).total_seconds() * 1000,
        }

    soup = _make_soup(html)
    base_url = f"{urlparse(url).scheme}://{urlparse(url).netloc}"

    result = {
        "url": url,
        "success": True,
        "title": _extract_title(soup),
        "meta_description": _extract_meta_description(soup),
        "meta_keywords": _extract_meta_keywords(soup),
        "open_graph": _extract_open_graph(soup),
        "json_ld": _extract_json_ld(soup),
        "elapsed_ms": (datetime.now(timezone.utc) - start).total_seconds() * 1000,
        "content_length": len(html),
    }

    # Extract based on type
    if extract_type in ("auto", "full", "article"):
        result["content"] = _extract_main_content(soup)[:10000]
        result["word_count"] = len(result.get("content", "").split())

    if extract_type in ("auto", "full", "headlines"):
        result["headlines"] = _extract_headlines(soup)

    if extract_type in ("auto", "full", "links"):
        result["links"] = _extract_links(soup, base_url)

    if extract_type in ("auto", "full", "table", "tables"):
        result["tables"] = _extract_tables(soup)

    if extract_type in ("auto", "full", "images"):
        result["images"] = _extract_images(soup, base_url)

    if extract_type in ("auto", "full", "prices"):
        result["prices"] = _extract_prices(soup)

    if extract_type == "metadata":
        pass  # Already included basic metadata

    # Cache result
    scrape_cache.set(cache_key, result)

    return result


# ============================================================
# Specialized Scrapers
# ============================================================

async def scrape_amazon_product(url: str) -> Dict[str, Any]:
    """Specialized scraper for Amazon product pages."""
    result = await scrape_url(url, extract_type="full", dynamic=True)
    if not result.get("success"):
        return result

    soup = _make_soup(await _fetch_html_dynamic(url) or "")

    product = {
        "title": result.get("title", ""),
        "price": "",
        "rating": "",
        "availability": "",
        "description": "",
        "features": [],
    }

    price_el = soup.select_one(".a-price-whole") or \
               soup.select_one("#priceblock_ourprice") or \
               soup.select_one(".a-offscreen")
    if price_el:
        product["price"] = price_el.get_text(strip=True)

    rating_el = soup.select_one(".a-star-rating") or \
                soup.select_one("[data-hook='rating-out-of-text']")
    if rating_el:
        product["rating"] = rating_el.get_text(strip=True)

    for feat in soup.select("#feature-bullets .a-list-item"):
        text = feat.get_text(strip=True)
        if text:
            product["features"].append(text)

    desc_el = soup.select_one("#productDescription") or \
              soup.select_one("[data-feature-name='description']")
    if desc_el:
        product["description"] = desc_el.get_text(strip=True)[:500]

    avail_el = soup.select_one("#availability span")
    if avail_el:
        product["availability"] = avail_el.get_text(strip=True)

    result["product"] = product
    return result


async def scrape_wikipedia(topic: str) -> Dict[str, Any]:
    """Scrape Wikipedia for a topic."""
    import urllib.parse
    formatted = topic.replace(" ", "_")
    url = f"https://en.wikipedia.org/wiki/{urllib.parse.quote(formatted)}"
    result = await scrape_url(url, extract_type="article")
    return result


async def scrape_hn_frontpage() -> Dict[str, Any]:
    """Scrape Hacker News front page."""
    result = await scrape_url("https://news.ycombinator.com", extract_type="headlines")
    if not result.get("success"):
        return result

    soup = _make_soup(await _fetch_html("https://news.ycombinator.com") or "")
    items = []
    for row in soup.select(".athing"):
        title_el = row.select_one(".titleline a")
        if title_el:
            items.append({
                "title": title_el.get_text(strip=True),
                "url": title_el.get("href", ""),
            })
    result["items"] = items[:30]
    return result


async def scrape_github_trending(language: str = "", since: str = "daily") -> Dict[str, Any]:
    """Scrape GitHub trending repositories."""
    url = "https://github.com/trending"
    if language:
        url += f"/{language}"
    url += f"?since={since}"

    result = await scrape_url(url, extract_type="full")
    if not result.get("success"):
        return result

    soup = _make_soup(await _fetch_html(url) or "")
    repos = []
    for article in soup.select("article.Box-row"):
        name_el = article.select_one("h2 a")
        desc_el = article.select_one("p")
        stars_el = article.select_one(".d-inline-block.float-sm-right")
        if name_el:
            repos.append({
                "name": name_el.get_text(strip=True).replace(" ", ""),
                "url": f"https://github.com{name_el.get('href', '')}",
                "description": desc_el.get_text(strip=True)[:200] if desc_el else "",
                "stars": stars_el.get_text(strip=True) if stars_el else "",
            })
    result["repositories"] = repos[:25]
    return result


async def scrape_weather_city(city: str) -> Dict[str, Any]:
    """Scrape weather from weather.com."""
    import urllib.parse
    formatted = urllib.parse.quote(f"{city} weather")
    url = f"https://weather.com/weather/today/l/{formatted}"
    result = await scrape_url(url, extract_type="full", dynamic=True)
    return result


# ============================================================
# Search and aggregate
# ============================================================

async def scrape_search(query: str, num_results: int = 5) -> List[Dict[str, str]]:
    """Scrape search results from DuckDuckGo (no API key needed)."""
    import urllib.parse
    url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
    html = await _fetch_html(url)
    if not html:
        return []

    soup = _make_soup(html)
    results = []
    for i, result_div in enumerate(soup.select(".result")):
        if i >= num_results:
            break
        title_el = result_div.select_one(".result__title a")
        snippet_el = result_div.select_one(".result__snippet")
        if title_el:
            results.append({
                "title": title_el.get_text(strip=True),
                "url": title_el.get("href", ""),
                "snippet": snippet_el.get_text(strip=True) if snippet_el else "",
            })
    return results


# ============================================================
# Utility
# ============================================================

async def compare_prices(product_name: str) -> str:
    """Compare prices for a product across multiple sites."""
    search_results = await scrape_search(f"buy {product_name} price", 5)
    lines = [f"**Price comparison for '{product_name}':**"]
    for r in search_results:
        lines.append(f"  - {r['title'][:60]}: {r['snippet'][:100]}")
    return "\n".join(lines) if len(lines) > 1 else "No price data found."
