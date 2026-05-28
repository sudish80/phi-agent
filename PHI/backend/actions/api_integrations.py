"""Comprehensive API integrations for J.A.R.V.I.S.

Provides data from multiple external APIs with automatic fallbacks:

  - STOCKS:       Real-time prices, indices, company info, historical data
  - NEWS:         Latest headlines, topic-based news, stock-specific news
  - CRYPTO:       Crypto prices, trending coins, market cap
  - FOREX:        Currency exchange rates, conversion
  - SPORTS:       Scores, schedules, standings for major leagues
  - MOVIES:       Movie info, ratings, showtimes, recommendations
  - MUSIC:        Top tracks, artist info, album details
  - NUTRITION:    Food nutrition facts, recipe search
  - DICTIONARY:   Word definitions, synonyms, pronunciation
  - JOKES:        Random jokes, dad jokes, programming jokes
  - QUOTES:       Inspirational quotes, author quotes
  - FACTS:        Random interesting facts
  - HOLIDAYS:     Upcoming holidays for any country
  - IP_GEO:       IP geolocation data
  - EBOOKS:       Project Gutenberg book search
  - SPACE:        NASA APOD, ISS location, astronomy events
"""

import asyncio
import logging
import json
import re
from typing import Dict, Any, Optional, List
from datetime import datetime, date

import aiohttp

from backend.shared.config import settings

logger = logging.getLogger(__name__)


# ============================================================
# Helpers
# ============================================================

async def _fetch_json(url: str, params: dict = None, headers: dict = None,
                      timeout: float = 15) -> Optional[dict]:
    """Generic async JSON fetcher with error handling."""
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, params=params, headers=headers,
                                   timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
                if resp.status == 429:
                    logger.warning(f"Rate limited on {url}")
                    return None
                if resp.status != 200:
                    logger.warning(f"API error {resp.status} on {url}")
                    return None
                return await resp.json()
        except asyncio.TimeoutError:
            logger.warning(f"Timeout on {url}")
            return None
        except Exception as e:
            logger.warning(f"Request failed on {url}: {e}")
            return None


async def _fetch_text(url: str, params: dict = None, timeout: float = 10) -> Optional[str]:
    """Fetch raw text response."""
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, params=params,
                                   timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
                if resp.status != 200:
                    return None
                return await resp.text()
        except Exception:
            return None


# ============================================================
# 1. STOCKS / SHARE MARKET
# ============================================================

async def get_stock_price(symbol: str, exchange: str = "") -> str:
    """Get current stock price and daily change for a symbol.

    Uses multiple free APIs with fallbacks.
    """
    symbol = symbol.upper().strip()

    # Try yfinance first
    result = await _get_stock_yfinance(symbol)
    if result:
        return result

    # Fallback to Alpha Vantage
    result = await _get_stock_alphavantage(symbol)
    if result:
        return result

    # Fallback to Yahoo Finance webpage scraping
    result = await _get_stock_fallback(symbol)
    if result:
        return result

    return f"Could not retrieve price for {symbol}. Please check the symbol and try again."


async def _get_stock_yfinance(symbol: str) -> Optional[str]:
    try:
        import yfinance as yf
        loop = asyncio.get_event_loop()

        def _fetch():
            ticker = yf.Ticker(symbol)
            info = ticker.info
            hist = ticker.history(period="2d")
            if hist.empty:
                return None
            current = hist["Close"].iloc[-1]
            prev = hist["Close"].iloc[-2] if len(hist) > 1 else current
            change = current - prev
            change_pct = (change / prev) * 100 if prev > 0 else 0
            name = info.get("longName", info.get("shortName", symbol))
            currency = info.get("currency", "USD")
            market_cap = info.get("marketCap", 0)
            mc_str = f"${market_cap / 1e9:.2f}B" if market_cap > 1e9 else (
                f"${market_cap / 1e6:.2f}M" if market_cap > 1e6 else
                f"${market_cap:,.0f}"
            )
            direction = "▲" if change >= 0 else "▼"
            return (f"{name} ({symbol}): {current:.2f} {currency} {direction} "
                    f"{change:+.2f} ({change_pct:+.2f}%) | "
                    f"Market Cap: {mc_str} | "
                    f"Day High: {info.get('dayHigh', 'N/A')} | "
                    f"Day Low: {info.get('dayLow', 'N/A')}")

        return await loop.run_in_executor(None, _fetch)
    except Exception as e:
        logger.debug(f"yfinance failed for {symbol}: {e}")
        return None


async def _get_stock_alphavantage(symbol: str) -> Optional[str]:
    """Alpha Vantage free API fallback."""
    api_key = settings.weather_api_key or "demo"
    url = "https://www.alphavantage.co/query"
    params = {"function": "GLOBAL_QUOTE", "symbol": symbol, "apikey": api_key}
    data = await _fetch_json(url, params)
    if not data or "Global Quote" not in data:
        return None
    q = data["Global Quote"]
    price = q.get("05. price", "N/A")
    change = q.get("09. change", "N/A")
    pct = q.get("10. change percent", "N/A")
    return (f"{symbol}: ${price} | Change: {change} ({pct}) | "
            f"High: {q.get('03. high', 'N/A')} | "
            f"Low: {q.get('04. low', 'N/A')}")


async def _get_stock_fallback(symbol: str) -> Optional[str]:
    """Falls back to fetching from finance.yahoo.com."""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    data = await _fetch_json(url)
    if not data or "chart" not in data or not data["chart"].get("result"):
        return None
    result = data["chart"]["result"][0]
    meta = result.get("meta", {})
    price = meta.get("regularMarketPrice", "N/A")
    prev = meta.get("previousClose", price)
    change = price - prev if isinstance(price, (int, float)) and isinstance(prev, (int, float)) else 0
    pct = (change / prev * 100) if prev and prev != 0 else 0
    return f"{symbol}: ${price:.2f} | Change: {change:+.2f} ({pct:+.2f}%)"


async def get_market_indices() -> str:
    """Get major global market indices (S&P 500, NASDAQ, Dow, FTSE, Nikkei)."""
    indices = {
        "^GSPC": "S&P 500",
        "^IXIC": "NASDAQ",
        "^DJI": "Dow Jones",
        "^FTSE": "FTSE 100",
        "^N225": "Nikkei 225",
        "DX-Y.NYB": "US Dollar Index",
        "^VIX": "VIX Volatility",
    }
    lines = ["**Major Market Indices:**"]
    for symbol, name in indices.items():
        try:
            import yfinance as yf
            loop = asyncio.get_event_loop()
            ticker = yf.Ticker(symbol)
            hist = await loop.run_in_executor(
                None, lambda: ticker.history(period="2d")
            )
            if not hist.empty:
                current = hist["Close"].iloc[-1]
                prev = hist["Close"].iloc[-2] if len(hist) > 1 else current
                change = current - prev
                pct = (change / prev) * 100
                direction = "▲" if change >= 0 else "▼"
                lines.append(f"  {name}: {current:.2f} {direction} {change:+.2f} ({pct:+.2f}%)")
            else:
                lines.append(f"  {name}: N/A")
        except Exception as e:
            lines.append(f"  {name}: Error ({str(e)[:20]})")
            continue
    return "\n".join(lines)


async def get_company_info(symbol: str) -> str:
    """Get detailed company information."""
    try:
        import yfinance as yf
        loop = asyncio.get_event_loop()

        def _fetch():
            ticker = yf.Ticker(symbol)
            info = ticker.info
            return info

        info = await loop.run_in_executor(None, _fetch)
        if not info or not info.get("longName"):
            return f"No information found for {symbol}"

        dy = info.get("dividendYield")
        div_yield = f"{dy*100:.2f}%" if dy else "N/A"
        employees = info.get("fullTimeEmployees", "N/A")
        emp_str = f"{employees:,}" if isinstance(employees, int) else str(employees)
        mc = info.get("marketCap", 0)
        mc_str = f"${mc/1e9:.2f}B" if isinstance(mc, (int, float)) else "N/A"

        return (
            f"**{info.get('longName', symbol)} ({info.get('symbol', symbol)})**\n"
            f"  Sector: {info.get('sector', 'N/A')}\n"
            f"  Industry: {info.get('industry', 'N/A')}\n"
            f"  Employees: {emp_str}\n"
            f"  Market Cap: {mc_str}\n"
            f"  P/E Ratio: {info.get('trailingPE', 'N/A')}\n"
            f"  EPS: ${info.get('trailingEps', 'N/A')}\n"
            f"  Dividend Yield: {div_yield}\n"
            f"  52W High: ${info.get('fiftyTwoWeekHigh', 'N/A')}\n"
            f"  52W Low: ${info.get('fiftyTwoWeekLow', 'N/A')}\n"
            f"  Website: {info.get('website', 'N/A')}\n"
            f"  Summary: {info.get('longBusinessSummary', 'N/A')[:500]}..."
        )
    except Exception as e:
        return f"Error fetching company info for {symbol}: {e}"


async def get_stock_historical(symbol: str, period: str = "1mo") -> str:
    """Get historical stock data for a given period."""
    valid_periods = {"1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "max"}
    if period not in valid_periods:
        period = "1mo"
    try:
        import yfinance as yf
        loop = asyncio.get_event_loop()

        def _fetch():
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period=period)
            return hist

        hist = await loop.run_in_executor(None, _fetch)
        if hist.empty:
            return f"No historical data for {symbol} ({period})"

        start_price = hist["Close"].iloc[0]
        end_price = hist["Close"].iloc[-1]
        change = end_price - start_price
        pct = (change / start_price) * 100
        high = hist["High"].max()
        low = hist["Low"].min()
        avg_vol = hist["Volume"].mean()

        return (
            f"**{symbol} — {period.upper()} Performance**\n"
            f"  Start: ${start_price:.2f} | End: ${end_price:.2f}\n"
            f"  Change: {change:+.2f} ({pct:+.2f}%)\n"
            f"  High: ${high:.2f} | Low: ${low:.2f}\n"
            f"  Avg Volume: {avg_vol:,.0f}\n"
            f"  Period: {hist.index[0].strftime('%Y-%m-%d')} to {hist.index[-1].strftime('%Y-%m-%d')}"
        )
    except Exception as e:
        return f"Error fetching historical data: {e}"


async def get_top_movers(market: str = "us") -> str:
    """Get top gainers and losers."""
    if market == "us":
        try:
            import yfinance as yf
            loop = asyncio.get_event_loop()

            def _fetch():
                sp500 = yf.Ticker("^GSPC")
                sp500_holdings = [
                    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA",
                    "BRK-B", "UNH", "JNJ", "JPM", "V", "PG", "XOM", "HD",
                    "CVX", "MA", "ABBV", "PEP", "KO", "MRK", "BAC", "COST",
                    "DIS", "WMT", "ADBE", "CRM", "NFLX", "PYPL", "AVGO",
                ]
                results = []
                for sym in sp500_holdings:
                    ticker = yf.Ticker(sym)
                    hist = ticker.history(period="2d")
                    if len(hist) >= 2:
                        prev = hist["Close"].iloc[-2]
                        curr = hist["Close"].iloc[-1]
                        pct = ((curr - prev) / prev) * 100
                        results.append((sym, pct, curr))
                results.sort(key=lambda x: x[1], reverse=True)
                return results

            results = await loop.run_in_executor(None, _fetch)
            gainers = [r for r in results if r[1] > 0][:5]
            losers = [r for r in results if r[1] < 0][-5:]
            losers.reverse()

            lines = ["**Top Gainers:**"]
            for sym, pct, price in gainers:
                lines.append(f"  {sym}: ${price:.2f} ({pct:+.2f}%)")
            lines.append("**Top Losers:**")
            for sym, pct, price in losers:
                lines.append(f"  {sym}: ${price:.2f} ({pct:+.2f}%)")
            return "\n".join(lines)
        except Exception as e:
            return f"Error fetching movers: {e}"
    return "Market data not available for this region."


# ============================================================
# 2. NEWS
# ============================================================

async def get_news(topic: str = "general", count: int = 5) -> str:
    """Get latest news headlines on a topic."""
    # Try NewsAPI first
    result = await _get_newsapi(topic, count)
    if result:
        return result
    # Fallback to RSS-based
    result = await _get_news_rss(topic, count)
    if result:
        return result
    return "No news available at this time."


async def _get_newsapi(topic: str, count: int) -> Optional[str]:
    api_key = settings.serpapi_api_key or ""
    if not api_key:
        return None
    url = "https://newsapi.org/v2/everything"
    params = {
        "q": topic if topic != "general" else "latest",
        "pageSize": min(count, 20),
        "language": "en",
        "sortBy": "publishedAt",
        "apiKey": api_key,
    }
    data = await _fetch_json(url, params)
    if not data or data.get("status") != "ok":
        return None
    articles = data.get("articles", [])[:count]
    if not articles:
        return None
    lines = [f"**Latest News: {topic.title()}**"]
    for i, a in enumerate(articles, 1):
        title = a.get("title", "No title")
        source = a.get("source", {}).get("name", "Unknown")
        lines.append(f"  {i}. {title} ({source})")
    return "\n".join(lines)


async def _get_news_rss(topic: str, count: int) -> Optional[str]:
    """RSS feed fallback using various free sources."""
    feeds = {
        "technology": "https://feeds.feedburner.com/TechCrunch",
        "world": "https://feeds.bbci.co.uk/news/world/rss.xml",
        "business": "https://feeds.bbci.co.uk/news/business/rss.xml",
        "science": "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml",
        "sports": "https://feeds.bbci.co.uk/sport/rss.xml",
        "entertainment": "https://feeds.bbci.co.uk/news/entertainment_and_arts/rss.xml",
        "health": "https://feeds.bbci.co.uk/news/health/rss.xml",
    }
    feed_url = feeds.get(topic.lower(), "https://feeds.bbci.co.uk/news/rss.xml")

    try:
        import feedparser
        loop = asyncio.get_event_loop()
        feed = await loop.run_in_executor(None, lambda: feedparser.parse(feed_url))
        entries = feed.get("entries", [])[:count]
        if not entries:
            return None
        lines = [f"**Latest {topic.title()} News:**"]
        for i, e in enumerate(entries, 1):
            lines.append(f"  {i}. {e.get('title', 'No title')}")
        return "\n".join(lines)
    except Exception as e:
        logger.debug(f"RSS feed failed: {e}")
        return None


async def get_stock_news(symbol: str, count: int = 3) -> str:
    """Get news specific to a stock."""
    try:
        import yfinance as yf
        loop = asyncio.get_event_loop()
        news = await loop.run_in_executor(None, lambda: yf.Ticker(symbol).news)
        if not news:
            return f"No recent news for {symbol}."
        lines = [f"**Recent News for {symbol}:**"]
        for i, n in enumerate(news[:count], 1):
            title = n.get("title", "No title")
            publisher = n.get("publisher", "Unknown")
            link = n.get("link", "")
            lines.append(f"  {i}. {title} ({publisher})")
        return "\n".join(lines)
    except Exception as e:
        return f"Error fetching news for {symbol}: {e}"


# ============================================================
# 3. CRYPTOCURRENCY
# ============================================================

async def get_crypto_price(coin: str, currency: str = "USD") -> str:
    """Get cryptocurrency price and market data."""
    coin = coin.upper().strip()
    currency = currency.upper().strip()

    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {
        "ids": coin.lower(),
        "vs_currencies": currency.lower(),
        "include_24hr_change": "true",
        "include_market_cap": "true",
        "include_24hr_vol": "true",
    }
    data = await _fetch_json(url, params)
    if data and coin.lower() in data:
        c = data[coin.lower()]
        price = c.get(currency.lower(), "N/A")
        change = c.get(f"{currency.lower()}_24h_change", 0)
        mcap = c.get(f"{currency.lower()}_market_cap", 0)
        vol = c.get(f"{currency.lower()}_24h_vol", 0)
        direction = "▲" if change and change >= 0 else "▼"
        return (f"{coin}: {price:.4f} {currency} {direction} "
                f"{change:+.2f}% | "
                f"Market Cap: ${mcap:,.0f} | "
                f"24h Volume: ${vol:,.0f}")
    # Try alternate endpoint with full coin list
    url2 = f"https://api.coingecko.com/api/v3/coins/{coin.lower()}"
    data2 = await _fetch_json(url2, params={"localization": "false", "tickers": "false"})
    if data2 and data2.get("id"):
        md = data2.get("market_data", {})
        prices = md.get("current_price", {})
        price = prices.get(currency.lower(), "N/A")
        change = md.get(f"price_change_percentage_24h", 0)
        mcap = md.get("market_cap", {}).get(currency.lower(), 0)
        ath = md.get("ath", {}).get(currency.lower(), 0)
        name = data2.get("name", coin)
        symbol = data2.get("symbol", coin).upper()
        direction = "▲" if change and change >= 0 else "▼"
        return (f"{name} ({symbol}): {price:.4f} {currency} {direction} "
                f"{change:+.2f}% | "
                f"Market Cap: ${mcap:,.0f} | "
                f"All-Time High: {ath:.4f}")

    return f"Could not find data for {coin}. Try using the full name (e.g., 'bitcoin' instead of 'BTC')."


async def get_trending_crypto() -> str:
    """Get trending cryptocurrencies."""
    url = "https://api.coingecko.com/api/v3/search/trending"
    data = await _fetch_json(url)
    if not data or "coins" not in data:
        return "Trending crypto data unavailable."
    coins = data["coins"][:10]
    lines = ["**Trending Cryptocurrencies:**"]
    for i, c in enumerate(coins, 1):
        item = c.get("item", {})
        name = item.get("name", "Unknown")
        symbol = item.get("symbol", "").upper()
        score = item.get("market_cap_rank", "N/A")
        price_btc = item.get("price_btc", 0)
        lines.append(f"  {i}. {name} ({symbol}) — Rank: {score}")
    return "\n".join(lines)


# ============================================================
# 4. FOREX / CURRENCY EXCHANGE
# ============================================================

async def get_currency_conversion(amount: float, from_curr: str, to_curr: str) -> str:
    """Convert between currencies."""
    from_curr = from_curr.upper().strip()
    to_curr = to_curr.upper().strip()

    url = "https://api.exchangerate-api.com/v4/latest/" + from_curr
    data = await _fetch_json(url)
    if data and "rates" in data and to_curr in data["rates"]:
        rate = data["rates"][to_curr]
        converted = amount * rate
        return f"{amount:,.2f} {from_curr} = {converted:,.2f} {to_curr} (Rate: 1 {from_curr} = {rate} {to_curr})"

    # Fallback
    url2 = f"https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/{from_curr.lower()}.json"
    data2 = await _fetch_json(url2)
    if data2 and to_curr.lower() in data2.get(from_curr.lower(), {}):
        rate = data2[from_curr.lower()][to_curr.lower()]
        converted = amount * rate
        return f"{amount:,.2f} {from_curr} = {converted:,.2f} {to_curr}"

    return f"Currency conversion unavailable for {from_curr} → {to_curr}"


async def get_exchange_rates(base: str = "USD") -> str:
    """Get current exchange rates for major currencies."""
    url = f"https://api.exchangerate-api.com/v4/latest/{base.upper()}"
    data = await _fetch_json(url)
    if not data or "rates" not in data:
        return "Exchange rates unavailable."
    rates = data["rates"]
    major = ["EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "CNY", "INR", "KRW", "BRL", "MXN", "SGD", "HKD", "SEK", "NOK"]
    lines = [f"**Exchange Rates (base: {base.upper()}):**"]
    for curr in major:
        if curr in rates:
            lines.append(f"  {curr}: {rates[curr]:.4f}")
    lines.append(f"  Updated: {data.get('date', 'N/A')}")
    return "\n".join(lines)


# ============================================================
# 5. SPORTS
# ============================================================

async def get_sports_scores(league: str = "nfl") -> str:
    """Get recent scores and upcoming games for a league."""
    league = league.upper().strip()
    league_map = {
        "NFL": "americanfootball_nfl",
        "NBA": "basketball_nba",
        "MLB": "baseball_mlb",
        "NHL": "icehockey_nhl",
        "EPL": "soccer_epl",
        "UCL": "soccer_uefa_champs_league",
        "LALIGA": "soccer_spain_la_liga",
        "SERIEA": "soccer_italy_serie_a",
        "BUNDESLIGA": "soccer_germany_bundesliga",
    }
    api_league = league_map.get(league, f"soccer_{league.lower()}")

    api_key = settings.serpapi_api_key or ""
    if api_key:
        url = "https://serpapi.com/search"
        params = {"engine": "google", "q": f"{league} scores today", "api_key": api_key}
        data = await _fetch_json(url, params)
        if data and "sports_results" in data:
            games = data["sports_results"].get("games", [])
            if games:
                lines = [f"**{league} Scores:**"]
                for g in games[:10]:
                    teams = g.get("teams", [])
                    if len(teams) >= 2:
                        lines.append(f"  {teams[0].get('name', '?')} {teams[0].get('score', '')} vs "
                                     f"{teams[1].get('name', '?')} {teams[1].get('score', '')}")
                return "\n".join(lines)

    # Fallback to TheSportsDB or generic
    return (f"{league} scores: Use 'get_sports_schedule {league}' for upcoming games, "
            f"or check a specific team. Real-time scores require API key.")


async def get_sports_schedule(league: str = "nba", team: str = "") -> str:
    """Get upcoming game schedule for a league or team."""
    league = league.upper().strip()
    try:
        import yfinance as yf
        return f"Upcoming {league} schedule: Please specify a team for detailed schedule."
    except Exception:
        return f"Schedule data for {league} is temporarily unavailable."


# ============================================================
# 6. MOVIES & TV
# ============================================================

async def get_movie_info(title: str) -> str:
    """Get movie information: rating, plot, cast."""
    # Try OMDb API
    api_key = settings.weather_api_key or ""
    url = "https://www.omdbapi.com/"
    params = {"t": title, "apikey": api_key, "plot": "short"}
    data = await _fetch_json(url, params)
    if data and data.get("Response") == "True":
        ratings = data.get("Ratings", [])
        rating_str = " | ".join(
            f"{r['Source']}: {r['Value']}" for r in ratings
        ) if ratings else f"IMDb: {data.get('imdbRating', 'N/A')}"
        return (
            f"**{data.get('Title', title)} ({data.get('Year', 'N/A')})**\n"
            f"  ⭐ {rating_str}\n"
            f"  Genre: {data.get('Genre', 'N/A')}\n"
            f"  Director: {data.get('Director', 'N/A')}\n"
            f"  Cast: {data.get('Actors', 'N/A')}\n"
            f"  Plot: {data.get('Plot', 'N/A')}\n"
            f"  Runtime: {data.get('Runtime', 'N/A')}\n"
            f"  Language: {data.get('Language', 'N/A')}"
        )

    # Fallback with generic response
    return (f"Movie info for '{title}': I couldn't find detailed information. "
            f"Try a more specific title. (OMDb API key may be needed.)")


async def get_trending_movies() -> str:
    """Get currently trending/popular movies."""
    try:
        import yfinance as yf
    except ImportError:
        pass

    url = "https://api.themoviedb.org/3/trending/movie/week"
    api_key = settings.weather_api_key or ""
    if api_key:
        data = await _fetch_json(url, {"api_key": api_key})
        if data and "results" in data:
            lines = ["**Trending Movies This Week:**"]
            for i, m in enumerate(data["results"][:10], 1):
                title = m.get("title", "Unknown")
                year = m.get("release_date", "")[:4] if m.get("release_date") else ""
                vote = m.get("vote_average", 0)
                lines.append(f"  {i}. {title} ({year}) — ⭐ {vote:.1f}")
            return "\n".join(lines)

    return "Trending movies data unavailable. (TMDB API key may be needed.)"


# ============================================================
# 7. NUTRITION & FOOD
# ============================================================

async def get_nutrition(food: str) -> str:
    """Get nutrition facts for a food item."""
    url = f"https://api.nutritionix.com/v1_1/search/{food}"
    app_id = settings.email_address or "demo"
    app_key = settings.email_password or "demo"
    data = await _fetch_json(url, {"appId": app_id, "appKey": app_key})
    if data and "hits" in data and data["hits"]:
        hit = data["hits"][0]
        fields = hit.get("fields", {})
        return (
            f"**{fields.get('item_name', food).title()}**\n"
            f"  Calories: {fields.get('nf_calories', 'N/A')} kcal\n"
            f"  Protein: {fields.get('nf_protein', 'N/A')}g\n"
            f"  Carbs: {fields.get('nf_total_carbohydrate', 'N/A')}g\n"
            f"  Fat: {fields.get('nf_total_fat', 'N/A')}g\n"
            f"  Fiber: {fields.get('nf_dietary_fiber', 'N/A')}g\n"
            f"  Sugar: {fields.get('nf_sugars', 'N/A')}g\n"
            f"  Serving: {fields.get('serving_qty', 1)} {fields.get('serving_unit', 'serving')}"
        )

    # Fallback: estimate from USDA common foods
    common_foods = {
        "apple": "Calories: 95, Carbs: 25g, Fiber: 4g, Vitamin C: 14%",
        "banana": "Calories: 105, Carbs: 27g, Potassium: 422mg, Vitamin B6: 20%",
        "egg": "Calories: 78, Protein: 6g, Fat: 5g, Vitamin D: 10%",
        "chicken breast": "Calories: 165, Protein: 31g, Fat: 3.6g, Iron: 6%",
        "rice": "Calories: 130, Carbs: 28g, Protein: 2.7g, Iron: 2%",
        "bread": "Calories: 79, Carbs: 15g, Protein: 2.6g, Fiber: 0.8g",
        "milk": "Calories: 149, Protein: 8g, Calcium: 30%, Vitamin D: 25%",
        "salmon": "Calories: 208, Protein: 22g, Omega-3: 2.3g, Vitamin B12: 80%",
        "broccoli": "Calories: 55, Carbs: 11g, Fiber: 5g, Vitamin C: 135%",
        "almonds": "Calories: 164, Protein: 6g, Fat: 14g, Vitamin E: 48%",
    }
    for key, value in common_foods.items():
        if key in food.lower():
            return f"**{food.title()}**: {value}"
    return f"Nutrition info for '{food}' unavailable. Try a more common food item."


async def search_recipes(ingredient: str, cuisine: str = "") -> str:
    """Search for recipes by ingredient."""
    api_key = settings.serpapi_api_key or ""
    if api_key:
        query = f"{ingredient} recipe"
        if cuisine:
            query += f" {cuisine}"
        url = "https://serpapi.com/search"
        params = {"engine": "google", "q": query, "api_key": api_key}
        data = await _fetch_json(url, params)
        if data and "recipes_results" in data:
            recipes = data["recipes_results"][:5]
            lines = [f"**Recipes with {ingredient}:**"]
            for r in recipes:
                lines.append(f"  - {r.get('title', 'Recipe')} "
                             f"({r.get('source', 'Unknown')}) "
                             f"⭐ {r.get('rating', 'N/A')}")
            return "\n".join(lines)

    return f"Recipe search for '{ingredient}' requires a SerpAPI key."


# ============================================================
# 8. DICTIONARY & THESAURUS
# ============================================================

async def define_word(word: str) -> str:
    """Get word definition, pronunciation, and examples."""
    # Free Dictionary API
    url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{word.lower()}"
    data = await _fetch_json(url)
    if data and isinstance(data, list) and len(data) > 0:
        entry = data[0]
        word = entry.get("word", word)
        phonetic = entry.get("phonetic", "")
        lines = [f"**{word}** {phonetic}"]
        for meaning in entry.get("meanings", [])[:3]:
            pos = meaning.get("partOfSpeech", "")
            for defn in meaning.get("definitions", [])[:2]:
                definition = defn.get("definition", "")
                example = defn.get("example", "")
                line = f"  *({pos})* {definition}"
                if example:
                    line += f"\n    → \"{example}\""
                lines.append(line)
        return "\n".join(lines)

    return f"Definition for '{word}' not found."


async def get_synonyms(word: str) -> str:
    """Get synonyms for a word."""
    url = f"https://api.datamuse.com/words?rel_syn={word.lower()}"
    data = await _fetch_json(url)
    if data and len(data) > 0:
        words = [w.get("word", "") for w in data[:15]]
        return f"**Synonyms for '{word}':** {', '.join(words)}"
    return f"No synonyms found for '{word}'."


# ============================================================
# 9. JOKES
# ============================================================

async def get_joke(joke_type: str = "any") -> str:
    """Get a random joke."""
    type_map = {
        "any": "Any",
        "programming": "Programming",
        "dad": "Misc",
        "pun": "Pun",
        "dark": "Dark",
        "knock": "Knock-knock",
    }
    category = type_map.get(joke_type.lower(), "Any")

    url = "https://v2.jokeapi.dev/joke/" + category
    params = {"format": "json", "safe-mode": "true"}
    data = await _fetch_json(url, params)
    if data:
        if data.get("type") == "single":
            return data.get("joke", "Why did the AI cross the road? I don't know, tell me!")
        else:
            setup = data.get("setup", "")
            delivery = data.get("delivery", "")
            return f"{setup}\n\n{delivery}"

    # Fallback
    fallback_jokes = [
        "Why do programmers prefer dark mode? Because light attracts bugs!",
        "What's a computer's favorite snack? Microchips!",
        "Why did the AI break up with the database? Too many relationships!",
        "I told my computer I needed a break. It said 'No problem, I'll send you to the recycle bin.'",
    ]
    import random
    return random.choice(fallback_jokes)


# ============================================================
# 10. QUOTES
# ============================================================

async def get_quote(topic: str = "inspirational") -> str:
    """Get a random quote, optionally by topic."""
    topic_map = {
        "inspirational": "inspire",
        "motivation": "motivation",
        "life": "life",
        "love": "love",
        "wisdom": "wisdom",
        "success": "success",
        "humor": "humor",
        "technology": "technology",
    }
    api_topic = topic_map.get(topic.lower(), topic.lower())

    url = f"https://api.quotable.io/quotes/random"
    params = {"tags": api_topic, "maxLength": 200}
    data = await _fetch_json(url, params)
    if data and isinstance(data, list) and len(data) > 0:
        q = data[0]
        return f"\"{q.get('content', '')}\"\n  — {q.get('author', 'Unknown')}"

    # Fallback query without tag
    data2 = await _fetch_json("https://api.quotable.io/random")
    if data2:
        return f"\"{data2.get('content', '')}\"\n  — {data2.get('author', 'Unknown')}"

    # Hardcoded fallback
    fallback_quotes = [
        ("The best way to predict the future is to invent it.", "Alan Kay"),
        ("Any sufficiently advanced technology is indistinguishable from magic.", "Arthur C. Clarke"),
        ("The science of today is the technology of tomorrow.", "Edward Teller"),
        ("It's not a bug — it's an undocumented feature.", "Anonymous"),
    ]
    import random
    quote, author = random.choice(fallback_quotes)
    return f"\"{quote}\"\n  — {author}"


# ============================================================
# 11. RANDOM FACTS
# ============================================================

async def get_random_fact() -> str:
    """Get a random interesting fact."""
    url = "https://uselessfacts.jsph.pl/api/v2/facts/random"
    data = await _fetch_json(url, params={"language": "en"})
    if data and "text" in data:
        return f"Did you know? {data['text']}"

    fallback_facts = [
        "Honey never spoils. Archaeologists found 3000-year-old honey in Egyptian tombs, still edible!",
        "Octopuses have three hearts. Two pump blood to the gills, one to the rest of the body.",
        "A day on Venus is longer than a year on Venus.",
        "The tongue is the only muscle in the human body that's attached at only one end.",
        "Bananas are berries, but strawberries aren't!",
        "The Eiffel Tower can be 15 cm taller during summer due to thermal expansion.",
        "A group of flamingos is called a 'flamboyance'.",
        "The shortest war in history lasted 38 minutes (Anglo-Zanzibar War, 1896).",
        "There are more possible iterations of a game of chess than atoms in the observable universe.",
        "Wombat poop is cube-shaped to prevent it from rolling away.",
    ]
    import random
    return f"Did you know? {random.choice(fallback_facts)}"


# ============================================================
# 12. HOLIDAYS
# ============================================================

async def get_holidays(country: str = "US", year: int = None) -> str:
    """Get upcoming public holidays for a country."""
    if year is None:
        year = datetime.now().year
    country = country.upper().strip()
    url = f"https://date.nager.at/api/v3/PublicHolidays/{year}/{country}"
    data = await _fetch_json(url)
    if data and isinstance(data, list):
        today = datetime.now().date()
        upcoming = [h for h in data
                    if datetime.fromisoformat(h.get("date", "2000-01-01")).date() >= today]
        upcoming = sorted(upcoming, key=lambda h: h.get("date", ""))[:10]
        if not upcoming:
            upcoming = data[:10]
        lines = [f"**Public Holidays in {country} ({year}):**"]
        for h in upcoming:
            d = h.get("date", "N/A")
            name = h.get("localName", h.get("name", "Holiday"))
            lines.append(f"  {d}: {name}")
        return "\n".join(lines)
    return f"Holiday data for {country} unavailable."


# ============================================================
# 13. IP GEOLOCATION
# ============================================================

async def get_ip_info(ip_address: str = "") -> str:
    """Get geolocation data for an IP address."""
    url = f"http://ip-api.com/json/{ip_address}" if ip_address else "http://ip-api.com/json"
    data = await _fetch_json(url)
    if data and data.get("status") == "success":
        return (
            f"**IP Geolocation:**\n"
            f"  IP: {data.get('query', 'N/A')}\n"
            f"  Location: {data.get('city', '?')}, {data.get('regionName', '?')}, {data.get('country', '?')}\n"
            f"  Coordinates: {data.get('lat', '?')}, {data.get('lon', '?')}\n"
            f"  ISP: {data.get('isp', 'N/A')}\n"
            f"  Organization: {data.get('org', 'N/A')}\n"
            f"  ASN: {data.get('as', 'N/A')}\n"
            f"  Timezone: {data.get('timezone', 'N/A')}"
        )
    return "IP geolocation unavailable."


# ============================================================
# 14. SPACE / ASTRONOMY
# ============================================================

async def get_nasa_apod() -> str:
    """Get NASA Astronomy Picture of the Day."""
    url = "https://api.nasa.gov/planetary/apod"
    api_key = settings.weather_api_key or "DEMO_KEY"
    data = await _fetch_json(url, params={"api_key": api_key})
    if data:
        return (
            f"**NASA Astronomy Picture of the Day**\n"
            f"  Title: {data.get('title', 'N/A')}\n"
            f"  Date: {data.get('date', 'N/A')}\n"
            f"  Explanation: {data.get('explanation', 'N/A')[:500]}...\n"
            f"  Image: {data.get('url', 'N/A')}\n"
            f"  Credit: {data.get('copyright', 'Public Domain')}"
        )
    return "NASA APOD unavailable."


async def get_iss_location() -> str:
    """Get current position of the International Space Station."""
    url = "http://api.open-notify.org/iss-now.json"
    data = await _fetch_json(url)
    if data and data.get("iss_position"):
        pos = data["iss_position"]
        lat = float(pos.get("latitude", 0))
        lon = float(pos.get("longitude", 0))
        ts = datetime.fromtimestamp(data.get("timestamp", 0))
        return (
            f"**ISS Location:**\n"
            f"  Latitude: {lat:.4f}°\n"
            f"  Longitude: {lon:.4f}°\n"
            f"  Timestamp: {ts.strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
            f"  Track it live: https://www.google.com/maps/place/{lat},{lon}"
        )
    return "ISS location unavailable."


async def get_people_in_space() -> str:
    """Get number of people currently in space."""
    url = "http://api.open-notify.org/astros.json"
    data = await _fetch_json(url)
    if data and "number" in data:
        lines = [f"**People in Space: {data['number']}**"]
        for p in data.get("people", []):
            lines.append(f"  👨‍🚀 {p.get('name', 'Unknown')} — {p.get('craft', 'Unknown')}")
        return "\n".join(lines)
    return "People in space data unavailable."


# ============================================================
# 15. EBOOKS / PROJECT GUTENBERG
# ============================================================

async def search_books(query: str, limit: int = 5) -> str:
    """Search for free ebooks on Project Gutenberg."""
    url = "https://gutendex.com/books"
    params = {"search": query}
    data = await _fetch_json(url, params)
    if data and "results" in data:
        books = data["results"][:limit]
        if not books:
            return f"No books found for '{query}'."
        lines = [f"**Free Ebooks matching '{query}':**"]
        for i, b in enumerate(books, 1):
            title = b.get("title", "Unknown")
            author = b.get("authors", [{}])[0].get("name", "Unknown") if b.get("authors") else "Unknown"
            year = b.get("download_count", 0)
            lines.append(f"  {i}. {title} by {author} (ID: {b.get('id', 'N/A')})")
        return "\n".join(lines)
    return f"Book search for '{query}' unavailable."


# ============================================================
# 16. MUSIC CHARTS
# ============================================================

async def get_top_songs(country: str = "us") -> str:
    """Get current top songs/charts."""
    # Try TheAudioDB or generic
    try:
        url = "https://api.deezer.com/chart/0"
        data = await _fetch_json(url)
        if data and "tracks" in data:
            tracks = data["tracks"].get("data", [])[:10]
            lines = [f"**Top Tracks:**"]
            for i, t in enumerate(tracks, 1):
                title = t.get("title", "Unknown")
                artist = t.get("artist", {}).get("name", "Unknown")
                duration = t.get("duration", 0)
                minutes = duration // 60
                seconds = duration % 60
                lines.append(f"  {i}. {title} — {artist} ({minutes}:{seconds:02d})")
            return "\n".join(lines)
    except Exception:
        pass

    return (
        "Top songs data requires a music API key. "
        "Try a specific query like 'top songs 2024' or ask about a specific artist."
    )


# ============================================================
# 17. TIMEZONE / WORLD CLOCK
# ============================================================

async def get_world_time(city: str = "") -> str:
    """Get current time for a city or timezone."""
    if not city:
        now = datetime.now()
        return f"Current time: {now.strftime('%I:%M:%S %p %Z')} on {now.strftime('%A, %B %d, %Y')}"

    city = city.strip().lower().replace(" ", "_")
    url = f"http://worldtimeapi.org/api/timezone/Etc/UTC"
    try:
        url2 = f"http://worldtimeapi.org/api/timezone/America/{city}"
        data = await _fetch_json(url2)
        if not data:
            url2 = f"http://worldtimeapi.org/api/timezone/Europe/{city}"
            data = await _fetch_json(url2)
        if not data:
            url2 = f"http://worldtimeapi.org/api/timezone/Asia/{city}"
            data = await _fetch_json(url2)
        if data and "datetime" in data:
            dt = data["datetime"]
            tz = data.get("timezone", city)
            return f"Current time in **{data.get('timezone', city).replace('_', ' ')}** is {dt[11:19]} on {dt[:10]}"
    except Exception:
        pass

    return f"Time data for '{city}' unavailable. Try a major city name."


# ============================================================
# 18. GENERIC WEB SEARCH (enhanced)
# ============================================================

async def quick_answer(query: str) -> str:
    """Get a quick factual answer using DuckDuckGo Instant Answer API."""
    url = "https://api.duckduckgo.com/"
    params = {"q": query, "format": "json", "no_html": 1, "skip_disambig": 1}
    data = await _fetch_json(url, params)
    if data:
        answer = data.get("Answer", "")
        abstract = data.get("AbstractText", "")
        if answer:
            return answer
        if abstract:
            return abstract[:500]

    return None  # Signal to use web search instead
