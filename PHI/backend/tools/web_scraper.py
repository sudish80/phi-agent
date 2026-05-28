"""Web Scraper — Scrapy-powered web scraping and data extraction.

Uses Scrapy framework for robust, concurrent web scraping with
robots.txt respect, auto-throttle, and structured data extraction.
"""

import json
import os
import logging
import tempfile
from typing import Optional, List, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    import scrapy
    from scrapy.crawler import CrawlerProcess
    from scrapy.utils.project import get_project_settings
    HAS_SCRAPY = True
except ImportError:
    HAS_SCRAPY = False


class PageItem(scrapy.Item):
    url = scrapy.Field()
    title = scrapy.Field()
    text = scrapy.Field()
    html = scrapy.Field()
    links = scrapy.Field()
    metadata = scrapy.Field()


class GenericSpider(scrapy.Spider):
    name = "generic_scraper"

    def __init__(self, urls=None, extract_text=True, extract_links=True,
                 css_selectors=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.start_urls = urls or []
        self.extract_text = extract_text
        self.extract_links = extract_links
        self.css_selectors = css_selectors or {}
        self.results = []

    def parse(self, response):
        item = PageItem()
        item["url"] = response.url
        item["title"] = response.css("title::text").get("").strip()
        item["text"] = ""
        item["html"] = ""
        item["links"] = []
        item["metadata"] = {}

        if self.extract_text:
            item["text"] = " ".join(response.css("p::text, h1::text, h2::text, h3::text, li::text").getall())

        if self.extract_links:
            item["links"] = [{"text": l.css("::text").get(""), "href": l.attrib.get("href", "")}
                             for l in response.css("a[href]")[:50]]

        for name, selector in self.css_selectors.items():
            item["metadata"][name] = response.css(selector).getall()

        self.results.append(dict(item))


async def scrape_urls(
    urls: List[str],
    extract_text: bool = True,
    extract_links: bool = False,
    css_selectors: Optional[Dict[str, str]] = None,
    respect_robots: bool = True,
    delay: float = 0.5,
    max_pages: int = 10,
) -> str:
    """Scrape content from one or more URLs using Scrapy."""
    if not HAS_SCRAPY:
        return _fallback_scrape(urls)

    urls = urls[:max_pages]
    settings = {
        "ROBOTSTXT_OBEY": respect_robots,
        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_START_DELAY": delay,
        "AUTOTHROTTLE_MAX_DELAY": 60,
        "CONCURRENT_REQUESTS": 4,
        "DOWNLOAD_DELAY": delay,
        "LOG_LEVEL": "ERROR",
        "FEEDS": {},
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        output = os.path.join(tmpdir, "output.json")
        settings["FEED_URI"] = f"file:///{output.replace(os.sep, '/')}"
        settings["FEED_FORMAT"] = "jsonlines"

        process = CrawlerProcess(settings)
        process.crawl(GenericSpider,
                      urls=urls,
                      extract_text=extract_text,
                      extract_links=extract_links,
                      css_selectors=css_selectors or {})
        process.start()

        if os.path.exists(output):
            results = []
            with open(output) as f:
                for line in f:
                    if line.strip():
                        results.append(json.loads(line))
            return json.dumps(results, indent=2, ensure_ascii=False)

    return "No results scraped"


def _fallback_scrape(urls: List[str]) -> str:
    """Fallback web scraping using requests + BeautifulSoup when Scrapy unavailable."""
    try:
        import requests
        from bs4 import BeautifulSoup
    except ImportError:
        return "Scrapy not installed and fallback (requests+bs4) not available. Install with: pip install scrapy"

    results = []
    for url in urls[:5]:
        try:
            resp = requests.get(url, timeout=15, headers={
                "User-Agent": "Mozilla/5.0 (compatible; JARVIS/1.0)"
            })
            soup = BeautifulSoup(resp.text, "html.parser")
            for tag in soup(["script", "style", "nav", "footer"]):
                tag.decompose()
            results.append({
                "url": url,
                "title": soup.title.string if soup.title else "",
                "text": soup.get_text(separator=" ", strip=True)[:5000],
            })
        except Exception as e:
            results.append({"url": url, "error": str(e)})

    return json.dumps(results, indent=2, ensure_ascii=False)


async def scrape_with_selectors(
    url: str,
    selectors: Dict[str, str],
    respect_robots: bool = True,
) -> str:
    """Scrape specific CSS selectors from a URL."""
    return await scrape_urls(
        urls=[url],
        extract_text=False,
        extract_links=False,
        css_selectors=selectors,
        respect_robots=respect_robots,
    )
