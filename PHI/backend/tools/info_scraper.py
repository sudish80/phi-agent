"""Universal Information Scraper — replaces API dependencies for information retrieval.

Uses Playwright (JS rendering) with requests+bs4 fallback, smart content extraction,
structured data parsing, search, pagination, and caching.
"""

import json
import os
import re
import logging
import time
import hashlib
import asyncio
import urllib.parse
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

_SCRAPE_CACHE: Dict[str, dict] = {}
_CACHE_TTL = 300

_HAS_PLAYWRIGHT = False
_HAS_REQUESTS = False
_HAS_BS4 = False

try:
    from playwright.async_api import async_playwright
    _HAS_PLAYWRIGHT = True
except ImportError:
    pass

try:
    import requests as _req
    _HAS_REQUESTS = True
except ImportError:
    pass

try:
    from bs4 import BeautifulSoup as _BS
    _HAS_BS4 = True
except ImportError:
    pass


def _cache_key(*args) -> str:
    raw = ":".join(str(a) for a in args)
    return hashlib.md5(raw.encode()).hexdigest()


def _cache_get(key: str) -> Optional[dict]:
    entry = _SCRAPE_CACHE.get(key)
    if entry and (time.time() - entry["ts"]) < _CACHE_TTL:
        return entry["data"]
    if entry:
        del _SCRAPE_CACHE[key]
    return None


def _cache_set(key: str, data: dict):
    _SCRAPE_CACHE[key] = {"data": data, "ts": time.time()}
    if len(_SCRAPE_CACHE) > 300:
        oldest = min(_SCRAPE_CACHE.keys(), key=lambda k: _SCRAPE_CACHE[k]["ts"])
        del _SCRAPE_CACHE[oldest]


def _strip_tags(html: str) -> str:
    return re.sub(r'<[^>]+>', ' ', html).strip()


def _clean_text(text: str) -> str:
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'\n\s*\n', '\n', text)
    return text.strip()


def _extract_metadata(soup) -> dict:
    meta = {}
    for tag in soup.find_all("meta"):
        name = tag.get("name", tag.get("property", ""))
        content = tag.get("content", "")
        if name and content:
            meta[name] = content[:500]
    return meta


def _extract_tables(soup, max_tables: int = 5) -> List[dict]:
    tables = []
    for table in soup.find_all("table")[:max_tables]:
        rows = []
        headers = []
        for th in table.find_all("th"):
            headers.append(_clean_text(th.get_text()))
        for tr in table.find_all("tr")[:50]:
            cells = []
            for td in tr.find_all(["td", "th"]):
                cells.append(_clean_text(td.get_text()))
            if cells:
                rows.append(cells)
        if rows:
            tables.append({"headers": headers, "rows": rows[:50],
                           "row_count": len(rows)})
    return tables


def _extract_lists(soup) -> List[dict]:
    lists = []
    for ul in soup.find_all(["ul", "ol"])[:20]:
        items = []
        for li in ul.find_all("li")[:30]:
            items.append(_clean_text(li.get_text()))
        if items:
            lists.append({"type": ul.name, "items": items, "count": len(items)})
    return lists


def _extract_links(soup, base_url: str, max_links: int = 100) -> List[dict]:
    links = []
    seen = set()
    for a in soup.find_all("a", href=True)[:max_links]:
        href = a["href"]
        text = _clean_text(a.get_text())
        if href.startswith("/"):
            href = urllib.parse.urljoin(base_url, href)
        if href not in seen and text:
            seen.add(href)
            links.append({"text": text[:100], "url": href})
    return links


def _extract_images(soup, base_url: str, max_images: int = 30) -> List[dict]:
    images = []
    for img in soup.find_all("img")[:max_images]:
        src = img.get("src", "")
        alt = img.get("alt", "")
        if src:
            if src.startswith("/"):
                src = urllib.parse.urljoin(base_url, src)
            images.append({"src": src, "alt": alt[:100],
                           "width": img.get("width", ""), "height": img.get("height", "")})
    return images


def _extract_prices(soup) -> List[dict]:
    prices = []
    patterns = [
        r'\$\d{1,3}(?:,\d{3})*(?:\.\d{2})?',
        r'€\d{1,3}(?:,\d{3})*(?:\.\d{2})?',
        r'£\d{1,3}(?:,\d{3})*(?:\.\d{2})?',
        r'¥\d{1,3}(?:,\d{3})*(?:\.\d{2})?',
        r'₹\d{1,3}(?:,\d{3})*(?:\.\d{2})?',
    ]
    for tag in soup.find_all(string=True):
        text = str(tag)
        for pat in patterns:
            matches = re.findall(pat, text)
            for m in matches:
                prices.append({"value": m, "context": text[:100].strip()})
    return prices[:20]


def _readability_extract(soup) -> Optional[str]:
    try:
        for tag in soup(["script", "style", "nav", "footer", "header",
                          "aside", "iframe", "noscript", "form"]):
            tag.decompose()
        article = soup.find("article") or soup.find("main") or soup.find("div", class_=re.compile(
            r"(content|article|post|entry|main|body)", re.I))
        if not article:
            article = soup.body
        if not article:
            return None
        return _clean_text(article.get_text(separator="\n"))
    except Exception:
        return None


async def _scrape_playwright(url: str, wait_js: str = "",
                             timeout: int = 15) -> Tuple[Optional[str], Optional[str]]:
    if not _HAS_PLAYWRIGHT:
        return None, "Playwright not installed. Install with: pip install playwright && playwright install chromium"
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url, wait_until="networkidle", timeout=timeout * 1000)
            if wait_js:
                await page.wait_for_function(wait_js, timeout=5000)
            html = await page.content()
            title = await page.title()
            await browser.close()
            return html, title
    except Exception as e:
        return None, f"Playwright scraping failed: {e}"


async def _scrape_requests(url: str, timeout: int = 15) -> Tuple[Optional[str], Optional[str]]:
    if not _HAS_REQUESTS or not _HAS_BS4:
        return None, "requests/bs4 not installed. Install with: pip install requests beautifulsoup4"
    try:
        resp = _req.get(url, timeout=timeout, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        })
        resp.raise_for_status()
        return resp.text, None
    except Exception as e:
        return None, str(e)


async def _detect_and_scrape(url: str, render_js: bool = False,
                             wait_js: str = "", timeout: int = 15) -> dict:
    result = {"url": url, "title": "", "text": "", "html": "",
              "metadata": {}, "error": None, "method": ""}

    if render_js and _HAS_PLAYWRIGHT:
        html, err = await _scrape_playwright(url, wait_js, timeout)
        if html:
            result["html"] = html
            result["method"] = "playwright"
            soup = _BS(html, "html.parser")
            result["title"] = soup.title.string if soup and soup.title else ""
            result["error"] = err
            return result
        result["error"] = err
        logger.warning(f"Playwright failed, trying fallback: {err}")

    html, err = await _scrape_requests(url, timeout)
    if html:
        result["html"] = html
        result["method"] = "requests"
        soup = _BS(html, "html.parser")
        result["title"] = soup.title.string if soup and soup.title else ""
        return result

    result["error"] = result.get("error") or err or "All scraping methods failed"
    return result


async def scrape_page(url: str, render_js: bool = False, wait_js: str = "",
                      extract_links: bool = True, extract_tables: bool = False,
                      extract_lists: bool = False, extract_images: bool = False,
                      extract_prices: bool = False, extract_metadata: bool = True,
                      use_readability: bool = True, timeout: int = 15) -> str:
    ck = _cache_key("scrape_page", url, str(render_js), str(use_readability))
    cached = _cache_get(ck)
    if cached:
        return json.dumps({"cached": True, **cached}, indent=2)

    result = await _detect_and_scrape(url, render_js, wait_js, timeout)
    if result["error"]:
        return json.dumps({"error": result["error"], "url": url})

    soup = _BS(result["html"], "html.parser")
    output = {"url": url, "title": result["title"], "method": result["method"],
              "length_chars": len(result["html"])}

    if use_readability:
        text = _readability_extract(soup)
        output["text"] = text[:20000] if text else ""
    else:
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()
        output["text"] = _clean_text(soup.get_text(separator="\n"))[:20000]

    if extract_metadata:
        output["metadata"] = _extract_metadata(soup)
    if extract_links:
        output["links"] = _extract_links(soup, url)
    if extract_tables:
        output["tables"] = _extract_tables(soup)
    if extract_lists:
        output["lists"] = _extract_lists(soup)
    if extract_images:
        output["images"] = _extract_images(soup, url)
    if extract_prices:
        output["prices"] = _extract_prices(soup)

    _cache_set(ck, output)
    return json.dumps(output, indent=2, ensure_ascii=False)


async def scrape_search(query: str, site: str = "", max_results: int = 10,
                        render_js: bool = False) -> str:
    if site:
        q = f"{query} site:{site}"
    else:
        q = query
    ck = _cache_key("scrape_search", q, str(max_results))
    cached = _cache_get(ck)
    if cached:
        return json.dumps({"cached": True, **cached}, indent=2)

    # DuckDuckGo Lite — works without API keys, returns clean HTML
    try:
        import urllib.request as _ur
        from bs4 import BeautifulSoup as _BS2
        search_url = f"https://lite.duckduckgo.com/lite/?q={urllib.parse.quote_plus(q)}"
        req = _ur.Request(search_url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })
        with _ur.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8")
        soup = _BS2(html, "html.parser")
        results = []
        for i, a in enumerate(soup.select("a.result-link")[:max_results]):
            href = a.get("href", "")
            if href.startswith("//"):
                href = "https:" + href
            if "/l/?uddg=" in href:
                from urllib.parse import parse_qs, urlparse
                parsed = urlparse(href)
                qs = parse_qs(parsed.query)
                if "uddg" in qs:
                    href = qs["uddg"][0]
            snippet_el = a.find_parent("tr").select_one("td.snippet") if a.find_parent("tr") else None
            snippet = _clean_text(snippet_el.get_text()) if snippet_el else ""
            results.append({
                "position": i + 1,
                "title": _clean_text(a.get_text()),
                "url": href,
                "snippet": snippet[:300],
            })
        if results:
            output = {"query": q, "results": results, "total": len(results)}
            _cache_set(ck, output)
            return json.dumps(output, indent=2, ensure_ascii=False)
    except ImportError:
        pass
    except Exception as e:
        logger.debug(f"DuckDuckGo Lite failed: {e}")

    return json.dumps({"error": "Search failed - install requests and beautifulsoup4", "query": q})


async def scrape_news(query: str = "", max_results: int = 10) -> str:
    if query:
        url = f"https://news.google.com/search?q={urllib.parse.quote_plus(query)}&hl=en-US"
    else:
        url = "https://news.google.com/?hl=en-US"
    ck = _cache_key("scrape_news", query or "*", str(max_results))
    cached = _cache_get(ck)
    if cached:
        return json.dumps({"cached": True, **cached}, indent=2)

    html, err = await _scrape_requests(url)
    if not html:
        html, err = await _scrape_playwright(url)
    if not html:
        return json.dumps({"error": f"News fetch failed: {err}"})

    soup = _BS(html, "html.parser")
    articles = []
    seen = set()
    for article in soup.find_all("article")[:max_results]:
        title_el = article.find(["h2", "h3", "h4", "a", "span"])
        link_el = article.find("a", href=True)
        if title_el:
            title = _clean_text(title_el.get_text())
            link = link_el["href"] if link_el else ""
            if link.startswith("./"):
                link = "https://news.google.com" + link[1:]
            if title and title not in seen:
                seen.add(title)
                time_el = article.find("time")
                source_el = article.find(class_=re.compile(r"(source|origin|attribution)", re.I))
                articles.append({
                    "title": title,
                    "url": link,
                    "source": _clean_text(source_el.get_text()) if source_el else "",
                    "published": time_el.get("datetime", "") if time_el else "",
                })
    if not articles:
        for a in soup.find_all("a")[:max_results * 3]:
            href = a.get("href", "")
            text = _clean_text(a.get_text())
            if text and len(text) > 20 and href and "/articles/" in href:
                if text not in seen:
                    seen.add(text)
                    articles.append({"title": text, "url": href})

    output = {"query": query or "top stories", "articles": articles[:max_results],
              "total": len(articles[:max_results])}
    _cache_set(ck, output)
    return json.dumps(output, indent=2, ensure_ascii=False)


async def scrape_stock(ticker: str, exchange: str = "") -> str:
    search_term = f"{ticker} {exchange}".strip()
    url = f"https://www.google.com/finance/quote/{ticker.upper()}"
    if exchange:
        url = f"https://www.google.com/finance/quote/{ticker.upper()}:{exchange.upper()}"
    ck = _cache_key("scrape_stock", ticker, exchange)
    cached = _cache_get(ck)
    if cached:
        return json.dumps({"cached": True, **cached}, indent=2)

    html, err = await _scrape_requests(url)
    if not html:
        html, err = await _scrape_playwright(url)
    if not html:
        return json.dumps({"error": f"Stock fetch failed: {err}", "hint": "Try a known exchange like NASDAQ, NYSE, LON"})

    soup = _BS(html, "html.parser")
    output = {"ticker": ticker.upper(), "exchange": exchange.upper() if exchange else "unknown",
              "source": "Google Finance"}

    price_el = soup.find(class_=re.compile(r"(YMlKec|price|quote)", re.I))
    if price_el:
        output["price"] = price_el.get_text().strip()

    change_el = soup.find(class_=re.compile(r"(change|J)"), attrs={"data-symbol": re.compile(ticker, re.I)})
    if not change_el:
        change_el = soup.find(class_=re.compile(r"(change|diff|J)", re.I))
    if change_el:
        text = change_el.get_text().strip()
        m = re.search(r'([+-]?\d+\.?\d*)', text)
        if m:
            output["change"] = m.group(1)
        m2 = re.search(r'\(([+-]?\d+\.?\d*%)\)', text)
        if m2:
            output["change_pct"] = m2.group(1)

    name_el = soup.find(class_=re.compile(r"(company|name|title)", re.I))
    if name_el:
        output["company_name"] = _clean_text(name_el.get_text())

    for span in soup.find_all("span"):
        text = span.get_text().strip()
        if re.match(r'^(High|Low|Open|Close|Volume|Market Cap|P/E|Dividend|Yield)$', text):
            val_el = span.find_next("div") or span.find_next("span")
            if val_el:
                output[text.lower().replace(" ", "_")] = val_el.get_text().strip()

    _cache_set(ck, output)
    return json.dumps(output, indent=2, ensure_ascii=False)


async def scrape_weather(location: str) -> str:
    url = f"https://www.google.com/search?q=weather+{urllib.parse.quote_plus(location)}"
    ck = _cache_key("scrape_weather", location)
    cached = _cache_get(ck)
    if cached:
        return json.dumps({"cached": True, **cached}, indent=2)

    html, err = await _scrape_requests(url)
    if not html:
        html, err = await _scrape_playwright(url)
    if not html:
        return json.dumps({"error": f"Weather fetch failed: {err}"})

    soup = _BS(html, "html.parser")
    output = {"location": location}

    temp_el = soup.find(class_=re.compile(r"(BNeawe|temperature|temp|wob_t)", re.I))
    if not temp_el:
        temp_el = soup.find("span", id=re.compile(r"(temp|wob_t)", re.I))
    if temp_el:
        output["temperature"] = temp_el.get_text().strip()

    desc_el = soup.find(class_=re.compile(r"(BNeawe|description|wob_dcp)", re.I))
    if not desc_el:
        desc_el = soup.find("span", id=re.compile(r"(wob_dcp)", re.I))
    if desc_el:
        output["condition"] = desc_el.get_text().strip()

    for span in soup.find_all("span"):
        text = span.get_text().strip()
        if re.match(r'^(Humidity|Wind|Precipitation|Pressure|Visibility|UV Index)$', text, re.I):
            val = span.find_next("span") or span.parent
            if val:
                output[text.lower().replace(" ", "_")] = _clean_text(val.get_text())[:50]

    _cache_set(ck, output)
    return json.dumps(output, indent=2, ensure_ascii=False)


async def scrape_wikipedia(query: str, extract_summary: bool = True,
                           extract_sections: bool = False) -> str:
    page_name = urllib.parse.quote(query.replace(" ", "_"))
    api_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{page_name}"
    ck = _cache_key("wikipedia", query, str(extract_summary), str(extract_sections))
    cached = _cache_get(ck)
    if cached:
        return json.dumps({"cached": True, **cached}, indent=2)

    try:
        import requests as _req
        resp = _req.get(api_url, timeout=10, headers={"User-Agent": "JARVIS/1.0"})
        if resp.status_code == 200:
            data = resp.json()
            output = {
                "title": data.get("title", ""),
                "summary": data.get("extract", "")[:5000],
                "url": data.get("content_urls", {}).get("desktop", {}).get("page", ""),
                "thumbnail": data.get("thumbnail", {}).get("source", ""),
                "page_id": data.get("pageid"),
            }
            if extract_sections:
                sections_url = f"https://en.wikipedia.org/w/api.php?action=parse&page={urllib.parse.quote(query)}&prop=sections&format=json"
                sec_resp = _req.get(sections_url, timeout=10)
                if sec_resp.status_code == 200:
                    sec_data = sec_resp.json()
                    sections = sec_data.get("parse", {}).get("sections", [])
                    output["sections"] = [{"index": s.get("index"), "title": s.get("line"),
                                           "level": s.get("level")} for s in sections]
                    output["section_count"] = len(sections)
            _cache_set(ck, output)
            return json.dumps(output, indent=2, ensure_ascii=False)
        return json.dumps({"error": f"Wikipedia API returned {resp.status_code}",
                           "hint": "Try a different query or check page exists"})
    except ImportError:
        pass
    except Exception as e:
        return json.dumps({"error": str(e)})

    html_url = f"https://en.wikipedia.org/wiki/{page_name}"
    html, err = await _scrape_requests(html_url)
    if not html:
        return json.dumps({"error": f"Wikipedia scraping failed: {err}"})
    soup = _BS(html, "html.parser")
    content = soup.find("div", class_="mw-content-ltr")
    if not content:
        content = soup.find("div", id="mw-content-text")
    output = {"title": soup.title.string.replace(" - Wikipedia", "") if soup.title else query,
              "url": html_url}
    if content:
        paragraphs = content.find_all("p")
        summary_text = " ".join(_clean_text(p.get_text()) for p in paragraphs[:5])
        output["summary"] = summary_text[:5000]
    _cache_set(ck, output)
    return json.dumps(output, indent=2, ensure_ascii=False)


async def scrape_recipe(query: str, max_results: int = 5) -> str:
    url = f"https://www.allrecipes.com/search?q={urllib.parse.quote_plus(query)}"
    ck = _cache_key("scrape_recipe", query, str(max_results))
    cached = _cache_get(ck)
    if cached:
        return json.dumps({"cached": True, **cached}, indent=2)

    html, err = await _scrape_requests(url)
    if not html:
        html, err = await _scrape_playwright(url)
    if not html:
        return json.dumps({"error": f"Recipe search failed: {err}"})

    soup = _BS(html, "html.parser")
    results = []
    for card in soup.find_all(["article", "div"], class_=re.compile(r"(card|recipe|search-result)", re.I))[:max_results]:
        title_el = card.find(["h2", "h3", "a", "span"], class_=re.compile(r"(title|name|heading)", re.I))
        link_el = card.find("a", href=True)
        rating_el = card.find(class_=re.compile(r"(rating|stars)", re.I))
        time_el = card.find(class_=re.compile(r"(time|cook|total)", re.I))
        if title_el:
            results.append({
                "title": _clean_text(title_el.get_text()),
                "url": link_el["href"] if link_el else "",
                "rating": _clean_text(rating_el.get_text()) if rating_el else "",
                "time": _clean_text(time_el.get_text()) if time_el else "",
            })
    if not results:
        for a in soup.find_all("a")[:max_results * 3]:
            text = _clean_text(a.get_text())
            href = a.get("href", "")
            if text and len(text) > 10 and href:
                results.append({"title": text, "url": href})

    output = {"query": query, "results": results[:max_results], "total": len(results[:max_results])}
    _cache_set(ck, output)
    return json.dumps(output, indent=2, ensure_ascii=False)


async def scrape_product(url_or_query: str, max_results: int = 5) -> str:
    if url_or_query.startswith("http"):
        html, err = await _scrape_requests(url_or_query)
        if not html:
            html, err = await _scrape_playwright(url_or_query)
        if not html:
            return json.dumps({"error": f"Failed to scrape: {err}"})
        soup = _BS(html, "html.parser")
        output = {"url": url_or_query, "title": soup.title.string if soup.title else ""}
        price_el = soup.find(class_=re.compile(r"(price|product-price|offer)", re.I))
        if price_el:
            output["price"] = _clean_text(price_el.get_text())[:100]
        desc_el = soup.find(class_=re.compile(r"(description|product-desc)", re.I))
        if desc_el:
            output["description"] = _clean_text(desc_el.get_text())[:500]
        output["metadata"] = _extract_metadata(soup)
        return json.dumps(output, indent=2, ensure_ascii=False)

    search_url = f"https://www.amazon.com/s?k={urllib.parse.quote_plus(url_or_query)}"
    html, err = await _scrape_requests(search_url)
    if not html:
        return json.dumps({"error": f"Product search failed: {err}"})
    soup = _BS(html, "html.parser")
    results = []
    for div in soup.find_all("div", class_=re.compile(r"(s-result-item|product|card)", re.I))[:max_results]:
        title_el = div.find(["h2", "a", "span"], class_=re.compile(r"(title|name|heading)", re.I))
        price_el = div.find(class_=re.compile(r"(price|a-price|offer)", re.I))
        link_el = div.find("a", href=True)
        if title_el:
            results.append({
                "title": _clean_text(title_el.get_text()),
                "price": _clean_text(price_el.get_text()) if price_el else "",
                "url": "https://www.amazon.com" + link_el["href"] if link_el and link_el["href"].startswith("/") else (link_el["href"] if link_el else ""),
            })
    output = {"query": url_or_query, "results": results[:max_results], "total": len(results[:max_results])}
    return json.dumps(output, indent=2, ensure_ascii=False)


async def scrape_social_mentions(query: str, platform: str = "reddit", max_results: int = 10) -> str:
    if platform == "reddit":
        url = f"https://old.reddit.com/search?q={urllib.parse.quote_plus(query)}&sort=relevance&t=year"
    elif platform == "hackernews":
        url = f"https://hn.algolia.com/api/v1/search?query={urllib.parse.quote_plus(query)}&hitsPerPage={max_results}"
        try:
            import requests as _req
            resp = _req.get(url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                hits = data.get("hits", [])[:max_results]
                results = [{"title": h.get("title", ""), "url": h.get("url", h.get("story_url", "")),
                            "points": h.get("points", 0), "author": h.get("author", ""),
                            "comments": h.get("num_comments", 0), "created": datetime.fromtimestamp(h.get("created_at_i", 0)).isoformat() if h.get("created_at_i") else ""}
                           for h in hits]
                return json.dumps({"query": query, "platform": "hackernews", "results": results, "total": len(results)}, indent=2)
        except Exception as e:
            return json.dumps({"error": f"HN API failed: {e}"})
    else:
        return json.dumps({"error": f"Unknown platform: {platform}. Supported: reddit, hackernews"})

    html, err = await _scrape_requests(url)
    if not html:
        return json.dumps({"error": f"Failed to fetch {platform}: {err}"})
    soup = _BS(html, "html.parser")
    results = []
    for entry in soup.find_all("div", class_=re.compile(r"(entry|thing|link)", re.I))[:max_results]:
        title_el = entry.find("a", class_=re.compile(r"(title|link)", re.I))
        if not title_el:
            title_el = entry.find("a")
        if title_el:
            results.append({
                "title": _clean_text(title_el.get_text()),
                "url": title_el.get("href", ""),
            })
    output = {"query": query, "platform": platform, "results": results[:max_results],
              "total": len(results[:max_results])}
    return json.dumps(output, indent=2, ensure_ascii=False)


async def scrape_jobs(query: str, location: str = "", max_results: int = 10) -> str:
    params = urllib.parse.quote_plus(f"{query} {location} job")
    url = f"https://www.google.com/search?q={params}"
    ck = _cache_key("scrape_jobs", query, location, str(max_results))
    cached = _cache_get(ck)
    if cached:
        return json.dumps({"cached": True, **cached}, indent=2)

    html, err = await _scrape_requests(url)
    if not html:
        return json.dumps({"error": f"Job search failed: {err}"})
    soup = _BS(html, "html.parser")
    results = []
    for div in soup.find_all("div", class_=re.compile(r"(job|result|search-result)", re.I))[:max_results]:
        title_el = div.find(["h2", "h3", "a"])
        if title_el:
            results.append({
                "title": _clean_text(title_el.get_text()),
                "snippet": _clean_text(div.get_text())[:200],
            })
    if not results:
        for a in soup.find_all("a")[:max_results]:
            text = _clean_text(a.get_text())
            if text and len(text) > 15 and ("job" in text.lower() or query.lower() in text.lower()):
                results.append({"title": text})
    output = {"query": query, "location": location, "results": results[:max_results],
              "total": len(results[:max_results])}
    _cache_set(ck, output)
    return json.dumps(output, indent=2, ensure_ascii=False)


async def scrape_movie_info(title: str) -> str:
    url = f"https://www.google.com/search?q={urllib.parse.quote_plus(title + ' movie')}"
    ck = _cache_key("scrape_movie", title.lower())
    cached = _cache_get(ck)
    if cached:
        return json.dumps({"cached": True, **cached}, indent=2)

    html, err = await _scrape_requests(url)
    if not html:
        return json.dumps({"error": f"Movie fetch failed: {err}"})
    soup = _BS(html, "html.parser")
    output = {"title": title}

    rating_el = soup.find(class_=re.compile(r"(rating|star|imdb)", re.I))
    if rating_el:
        output["rating"] = _clean_text(rating_el.get_text())[:50]

    desc_el = soup.find(class_=re.compile(r"(description|summary|BNeawe)", re.I))
    if desc_el:
        output["summary"] = _clean_text(desc_el.get_text())[:500]

    for item in soup.find_all("div", class_=re.compile(r"(row|info|detail)", re.I)):
        text = _clean_text(item.get_text())
        if "Director" in text:
            output["director"] = text.replace("Director", "").strip()[:100]
        if "Cast" in text:
            output["cast"] = text.replace("Cast", "").strip()[:200]
        if "Genre" in text:
            output["genre"] = text.replace("Genre", "").strip()[:100]

    output["metadata"] = _extract_metadata(soup)
    _cache_set(ck, output)
    return json.dumps(output, indent=2, ensure_ascii=False)


async def scrape_lyrics(artist: str, song: str) -> str:
    query = f"{artist} {song} lyrics"
    url = f"https://www.google.com/search?q={urllib.parse.quote_plus(query)}"
    html, err = await _scrape_requests(url)
    if not html:
        return json.dumps({"error": f"Lyrics fetch failed: {err}"})
    soup = _BS(html, "html.parser")
    result = soup.find(class_=re.compile(r"(lyrics|verse|BNeawe)", re.I))
    if result:
        text = result.get_text(separator="\n")
        text = re.sub(r'\n{3,}', '\n\n', text)
        return json.dumps({"artist": artist, "song": song, "lyrics": text[:3000]}, indent=2)
    return json.dumps({"error": "Could not find lyrics", "hint": "Try exact artist and song name"})


async def scrape_define(word: str) -> str:
    url = f"https://www.google.com/search?q=define+{urllib.parse.quote_plus(word)}"
    ck = _cache_key("scrape_define", word.lower())
    cached = _cache_get(ck)
    if cached:
        return json.dumps({"cached": True, **cached}, indent=2)

    html, err = await _scrape_requests(url)
    if not html:
        return json.dumps({"error": f"Definition fetch failed: {err}"})
    soup = _BS(html, "html.parser")
    output = {"word": word}

    definition_el = soup.find(class_=re.compile(r"(definition|BNeawe)", re.I))
    if definition_el:
        output["definition"] = _clean_text(definition_el.get_text())[:500]

    phonetic_el = soup.find(class_=re.compile(r"(phonetic|pronunciation)", re.I))
    if phonetic_el:
        output["phonetic"] = _clean_text(phonetic_el.get_text())[:100]

    examples = []
    for el in soup.find_all(class_=re.compile(r"(example|BNeawe)", re.I)):
        text = _clean_text(el.get_text())
        if word.lower() in text.lower() and text not in examples:
            examples.append(text[:200])
    if examples:
        output["examples"] = examples[:3]

    _cache_set(ck, output)
    return json.dumps(output, indent=2, ensure_ascii=False)


async def scrape_dictionary(search_term: str, lang: str = "en") -> str:
    return await scrape_define(search_term)


async def scrape_translate(text: str, target_lang: str = "es") -> str:
    url = f"https://translate.google.com/m?tl={target_lang}&q={urllib.parse.quote_plus(text)}"
    html, err = await _scrape_requests(url)
    if not html:
        return json.dumps({"error": f"Translation failed: {err}"})
    soup = _BS(html, "html.parser")
    result = soup.find("div", class_="result-container")
    if result:
        return json.dumps({"text": text, "translation": _clean_text(result.get_text()),
                           "target_language": target_lang}, indent=2)
    return json.dumps({"error": "Translation not found"})


async def scrape_facts(query: str = "", count: int = 5) -> str:
    url = "https://en.wikipedia.org/wiki/Special:Random"
    if query:
        url = f"https://www.google.com/search?q={urllib.parse.quote_plus(query + ' facts')}"
    html, err = await _scrape_requests(url)
    if not html:
        return json.dumps({"error": f"Facts fetch failed: {err}"})
    soup = _BS(html, "html.parser")
    facts = []
    for li in soup.find_all("li")[:count * 3]:
        text = _clean_text(li.get_text())
        if text and len(text) > 30 and len(text) < 300:
            facts.append(text)
        if len(facts) >= count:
            break
    if not facts:
        for tag in soup.find_all(["p", "div"])[:count * 3]:
            text = _clean_text(tag.get_text())
            if text and len(text) > 40 and len(text) < 300:
                facts.append(text)
            if len(facts) >= count:
                break
    return json.dumps({"query": query or "random", "facts": facts[:count],
                       "total": len(facts[:count])}, indent=2, ensure_ascii=False)


# --- Unified Information Retrieval ---

async def search_information(query: str, max_sources: int = 3) -> str:
    """Search multiple sources and return the best consolidated result.
    Tries DuckDuckGo, Wikipedia, and news in parallel, returns combined answer.
    """
    results = {}
    errors = []
    async def _try_search():
        r = await scrape_search(query, max_results=5)
        return json.loads(r)
    async def _try_wiki():
        r = await scrape_wikipedia(query)
        return json.loads(r)
    async def _try_news():
        r = await scrape_news(query, max_results=3)
        return json.loads(r)
    tasks = {}
    tasks["search"] = asyncio.create_task(_try_search())
    tasks["wikipedia"] = asyncio.create_task(_try_wiki())
    if any(w in query.lower() for w in ("news", "latest", "today", "update", "breaking")):
        tasks["news"] = asyncio.create_task(_try_news())
    for name, task in tasks.items():
        try:
            result = await asyncio.wait_for(task, timeout=8)
            if "error" not in result or name == "search":
                results[name] = result
            elif result.get("error"):
                errors.append(f"{name}: {result['error']}")
        except asyncio.TimeoutError:
            errors.append(f"{name}: timed out")
        except Exception as e:
            errors.append(f"{name}: {e}")
    consolidated = {"query": query, "sources_used": list(results.keys()), "errors": errors[:3]}

    if "wikipedia" in results and results["wikipedia"].get("summary"):
        consolidated["answer"] = results["wikipedia"]["summary"][:2000]
        consolidated["source"] = "wikipedia"
        consolidated["url"] = results["wikipedia"].get("url", "")
        return json.dumps(consolidated, indent=2, ensure_ascii=False)

    if "search" in results:
        results_list = results["search"].get("results", [])
        if results_list:
            top = results_list[0]
            if top.get("url"):
                try:
                    page = await scrape_page(top["url"], use_readability=True)
                    page_data = json.loads(page)
                    if "text" in page_data and len(page_data["text"]) > 100:
                        consolidated["answer"] = page_data["text"][:2000]
                        consolidated["source"] = "web"
                        consolidated["url"] = top["url"]
                        consolidated["title"] = top.get("title", "")
                        return json.dumps(consolidated, indent=2, ensure_ascii=False)
                except Exception:
                    pass
            snippet = top.get("snippet", "") or top.get("title", "")
            consolidated["answer"] = snippet[:500]
            consolidated["source"] = "search"
            consolidated["url"] = top.get("url", "")
            consolidated["title"] = top.get("title", "")
            consolidated["results"] = [{"title": r.get("title", ""), "url": r.get("url", ""),
                                         "snippet": r.get("snippet", "") or r.get("title", "")} for r in results_list[:5]]

    if "news" in results:
        consolidated["news"] = results["news"].get("articles", [])[:3]

    return json.dumps(consolidated, indent=2, ensure_ascii=False)


async def ask_question(question: str) -> str:
    """Ask a direct question and get the best answer from web sources."""
    import re as _re
    wiki_query = _re.sub(r'^(what|who|where|when|why|how|is|are|was|were|do|does|did|can|could|would|will|shall|should|has|have|had)\s+', '', question.strip().rstrip('?'), flags=_re.I).strip()
    if not wiki_query:
        wiki_query = question
    try:
        if wiki_query:
            wr = await scrape_wikipedia(wiki_query)
            wd = json.loads(wr)
            if wd.get("summary") and len(wd["summary"]) > 20:
                return json.dumps({
                    "question": question,
                    "answer": wd["summary"][:1500],
                    "source": "wikipedia",
                    "url": wd.get("url", ""),
                    "title": wd.get("title", ""),
                }, indent=2, ensure_ascii=False)
    except Exception:
        pass
    return await search_information(question)
