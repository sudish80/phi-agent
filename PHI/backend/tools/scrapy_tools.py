"""Scrapy web scraper — extracts clean content optimized for LLM consumption."""

import os, json, tempfile, subprocess, logging, asyncio
from typing import Optional, Dict, Any, List
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=2)

SPIDER_CODE = r'''
import scrapy, json

class LLMScraperSpider(scrapy.Spider):
    name = "llm_scraper"

    def __init__(self, urls_json="[]", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.start_urls = json.loads(urls_json)

    def parse(self, response):
        texts = response.css("p::text, h1::text, h2::text, h3::text, h4::text, li::text, td::text, th::text, blockquote::text, pre::text").getall()
        texts = [t.strip() for t in texts if t.strip()]
        yield {
            "url": response.url,
            "status": response.status,
            "title": response.css("title::text").get(""),
            "meta_description": response.css("meta[name=description]::attr(content)").get(""),
            "content": " ".join(texts)[:15000],
            "headings": [h.get() for h in response.css("h1::text, h2::text, h3::text") if h.get()],
            "links": [response.urljoin(a.attrib.get("href")) for a in response.css("a[href]") if a.attrib.get("href", "").startswith("http")][:30],
            "content_length": len(" ".join(texts)),
        }
'''


def _run_spider(urls: List[str], timeout: int = 30) -> List[Dict]:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(SPIDER_CODE)
        spider_path = f.name

    result_path = spider_path.replace(".py", "_out.json")
    urls_json = json.dumps(urls)

    try:
        subprocess.run(
            ["scrapy", "runspider", spider_path,
             "-a", f"urls_json={urls_json}",
             "-o", result_path, "-t", "json",
             "-s", "LOG_ENABLED=False",
             "-s", "ROBOTSTXT_OBEY=False",
             "-s", "USER_AGENT=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
             "-s", "DOWNLOAD_TIMEOUT=15",
             "-s", "RETRY_TIMES=1",
             "-s", "CONCURRENT_REQUESTS=4",
             "-s", "DOWNLOAD_DELAY=0.5"],
            capture_output=True, text=True, timeout=timeout,
        )
        if os.path.exists(result_path):
            with open(result_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, list) else [data]
        return [{"url": u, "error": "no output"} for u in urls]
    except subprocess.TimeoutExpired:
        return [{"url": u, "error": "timeout"} for u in urls]
    except Exception as e:
        logger.exception("Scrapy error")
        return [{"url": u, "error": str(e)} for u in urls]
    finally:
        for p in (spider_path, result_path):
            try: os.unlink(p)
            except: pass


async def scrape_page_scrapy(url: str) -> str:
    """Scrape a URL using Scrapy — returns LLM-optimized content."""
    loop = asyncio.get_running_loop()
    results = await loop.run_in_executor(_executor, _run_spider, [url], 30)
    return json.dumps(results[0] if results else {"error": "no result"}, indent=2)


async def scrape_multiple_scrapy(urls: List[str]) -> str:
    """Scrape multiple URLs concurrently using Scrapy."""
    loop = asyncio.get_running_loop()
    results = await loop.run_in_executor(_executor, _run_spider, urls, 60)
    return json.dumps(results, indent=2)


async def scrape_search_scrapy(query: str, max_results: int = 5) -> str:
    """Search via Scrapy (DuckDuckGo) and return results for LLM."""
    search_url = f"https://html.duckduckgo.com/html/?q={query.replace(' ', '+')}"
    loop = asyncio.get_running_loop()
    results = await loop.run_in_executor(_executor, _run_spider, [search_url], 30)
    return json.dumps(results[0] if results else {"error": "no result"}, indent=2)
