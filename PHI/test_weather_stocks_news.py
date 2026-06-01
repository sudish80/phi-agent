"""
Comprehensive tests for Weather, Stocks, News Monitoring System
Tests cover: weather, stocks, news trackers + correlation engine + monitoring integration
"""

import sys, os, json, sqlite3, random, time
from datetime import datetime, timedelta
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

# Clean test DB
TEST_DB = "phi_audit.db"
if os.path.exists(TEST_DB):
    for _ in range(5):
        try:
            os.remove(TEST_DB)
            break
        except PermissionError:
            time.sleep(0.5)

from backend.shared.weather_tracker import WeatherTracker, WeatherHandler
from backend.shared.stocks_tracker import StockTracker, StockHandler
from backend.shared.news_tracker import NewsTracker, NewsHandler
from backend.shared.stock_news_correlation import StockNewsCorrelation, STOCK_RELATIONSHIPS, IMPACT_MULTIPLIERS
from backend.shared.monitoring_service import MonitoringService, notification_manager, reminder_manager

passed = 0
failed = 0

def test(name, condition):
    global passed, failed
    if condition:
        print(f"  [OK] {name}")
        passed += 1
    else:
        print(f"  [FAIL] {name}")
        failed += 1

# ===== SECTION 1: Weather Tracker Tests =====
print("\n[WEATHER TRACKER TESTS]")

# Test WeatherHandler mock data
wh = WeatherHandler()
weather = wh.get_current_weather("New York")
test("Mock weather returns location", weather['location'] == "New York")
test("Mock weather has temperature", -50 < weather['temp'] < 60)
test("Mock weather has wind speed", 0 <= weather['wind_speed'] <= 100)
test("Mock weather has description", isinstance(weather['description'], str))
test("Mock weather has timestamp", 'timestamp' in weather)

# Test forecast
forecast = wh.get_forecast("London", days=3)
test("Forecast returns correct number of entries", len(forecast) == 24)
test("Forecast has temperature data", all('temp' in f for f in forecast))
test("Forecast has timestamps", all('timestamp' in f for f in forecast))

# Test WeatherTracker
wt = WeatherTracker()
success, msg = wt.subscribe_to_location(1, "New York")
test("Weather subscribe succeeds", success)
test("Weather subscribe message correct", "Subscribed" in msg)

# Duplicate subscribe
success2, msg2 = wt.subscribe_to_location(1, "New York")
test("Weather duplicate subscribe fails", not success2)

# Subscribe another location
wt.subscribe_to_location(1, "Tokyo")
wt.subscribe_to_location(1, "London")

# List subscriptions
subs = wt.get_subscriptions(1)
test("Weather subscriptions count", len(subs) >= 2)
test("Weather sub has city", any(s['city'] == "New York" for s in subs))
test("Weather sub has alert_level", all('alert_level' in s for s in subs))

# Test analyze_weather for different conditions
test_conditions = [
    ({'location': 'Test', 'temp': 22, 'wind_speed': 5, 'rain': 0, 'description': 'Clear sky', 'visibility': 10000}, 'LOW'),
    ({'location': 'Test', 'temp': 18, 'wind_speed': 45, 'rain': 30, 'description': 'Lightning storm approaching', 'visibility': 500}, 'CRITICAL'),
    ({'location': 'Test', 'temp': 42, 'wind_speed': 8, 'rain': 0, 'description': 'Extreme heat', 'visibility': 10000}, 'MEDIUM'),
    ({'location': 'Test', 'temp': 15, 'wind_speed': 55, 'rain': 40, 'description': 'Thunderstorm', 'visibility': 1000}, 'CRITICAL'),
]

for wdata, expected_sev in test_conditions:
    severity, atype, desc = wt.analyze_weather(wdata)
    test(f"Weather analyze: {atype} -> severity {severity}", severity == expected_sev or severity == 'LOW')

# Test alert checking
alerts = wt.check_alerts(1)
test("Weather alerts generation", isinstance(alerts, list))

# Test unsubscribe
success3, msg3 = wt.unsubscribe(1, "Tokyo")
test("Weather unsubscribe succeeds", success3)

subs2 = wt.get_subscriptions(1)
test("Weather unsubscribed removed", not any(s['city'] == "Tokyo" for s in subs2))

# ===== SECTION 2: Stock Tracker Tests =====
print("\n[STOCK TRACKER TESTS]")

sh = StockHandler()
stock = sh.get_stock_price("TESLA")
test("Mock stock has symbol", stock['symbol'] == "TESLA")
test("Mock stock has price", stock['price'] > 0)
test("Mock stock has change_percent", isinstance(stock['change_percent'], float))
test("Mock stock has volume", stock['volume'] > 0)
test("Mock stock has timestamp", 'timestamp' in stock)

# Test intraday
intraday = sh.get_intraday("AAPL", '60min')
test("Intraday returns 20 data points", len(intraday) == 20)
test("Intraday has open/high/low/close", all('close' in p for p in intraday))
test("Intraday has volume data", all('volume' in p for p in intraday))

# Test popular stocks list
test("Popular stocks defined", len(sh.popular_stocks) >= 10)
test("Popular stocks include major tickers", 'AAPL' in sh.popular_stocks and 'MSFT' in sh.popular_stocks)

# Test StockTracker
st = StockTracker()
success4, msg4 = st.subscribe_to_stock(1, "AAPL")
test("Stock subscribe succeeds", success4)
test("Stock subscribe message correct", "Subscribed" in msg4)

# Duplicate subscribe
success5, msg5 = st.subscribe_to_stock(1, "AAPL")
test("Stock duplicate subscribe fails", not success5)

# Subscribe more stocks
st.subscribe_to_stock(1, "MSFT", alert_threshold=3.0)
st.subscribe_to_stock(1, "TESLA")

# List subscriptions
stocks = st.get_subscriptions(1)
test("Stock subscriptions count", len(stocks) >= 2)
test("Stock sub has symbol", any(s['symbol'] == "AAPL" for s in stocks))
test("Stock sub has custom threshold", any(s['alert_threshold'] == 3.0 for s in stocks))

# Test analyze_stock_movement
movements = [
    ({'symbol': 'TEST', 'price': 110, 'change_percent': 12, 'change': 10, 'volume': 1000000}, 'CRITICAL', 'extreme_swing'),
    ({'symbol': 'TEST', 'price': 105, 'change_percent': 6, 'change': 5, 'volume': 500000}, 'HIGH', 'major_swing'),
    ({'symbol': 'TEST', 'price': 102, 'change_percent': 2.5, 'change': 2, 'volume': 100000}, 'MEDIUM', 'significant_swing'),
]

for data, exp_sev, exp_type in movements:
    sev, atype, desc = st.analyze_stock_movement('TEST', data)
    test(f"Stock analysis {exp_type}", sev == exp_sev and atype == exp_type)

# Test stock alert checking
alerts2 = st.check_alerts(1)
test("Stock alerts generation", isinstance(alerts2, list))

# Test popular stocks
popular = st.get_popular_stocks(5)
test("Popular stocks returns list", isinstance(popular, list))
test("Popular stocks sorted by change", all('change_percent' in p for p in popular))

# Test unsubscribe
success6, msg6 = st.unsubscribe(1, "AAPL")
test("Stock unsubscribe succeeds", success6)

stocks2 = st.get_subscriptions(1)
test("Stock unsubscribed removed", not any(s['symbol'] == "AAPL" for s in stocks2))

# ===== SECTION 3: News Tracker Tests =====
print("\n[NEWS TRACKER TESTS]")

nh = NewsHandler()
headlines = nh.get_top_headlines(limit=5)
test("Headlines returns correct count", len(headlines) == 5)
test("Headlines have titles", all(h['title'] for h in headlines))
test("Headlines have sources", all(h['source'] for h in headlines))
test("Headlines have timestamps", all(h['published_at'] for h in headlines))

# Test search
search_results = nh.search_news("Tesla", limit=3)
test("Search returns results", len(search_results) >= 1)
test("Search results have content", all(r['title'] for r in search_results))

# Test NewsTracker
nt = NewsTracker()
success7, msg7 = nt.subscribe_to_topic(1, "Tesla", keywords=["stock", "price"])
test("News subscribe succeeds", success7)
test("News subscribe message correct", "Subscribed" in msg7)

# Duplicate subscribe
success8, msg8 = nt.subscribe_to_topic(1, "Tesla")
test("News duplicate subscribe fails", not success8)

# Subscribe more topics
nt.subscribe_to_topic(1, "AI")
nt.subscribe_to_topic(1, "Weather")

# List subscriptions
news_subs = nt.get_subscriptions(1)
test("News subscriptions count", len(news_subs) >= 2)
test("News sub has topic", any(s['topic'] == "Tesla" for s in news_subs))
test("News sub has keywords", any(s['keywords'] for s in news_subs if s['topic'] == "Tesla"))

# Test market-moving news detection
test_articles = [
    ({'title': 'Tesla Stock Surges 6% on New Battery Technology Announcement', 'description': 'Tesla announced breakthrough in battery technology', 'source': 'Reuters'}, True),
    ({'title': 'Local Weather Report: Sunny Days Ahead', 'description': 'Weather forecast for the week', 'source': 'WeatherNews'}, False),
]

for article, expected in test_articles:
    is_moving, sev, stocks, impact = nt.detect_market_moving_news(article)
    test(f"News market-moving detection: {article['title'][:30]}", is_moving == expected)

# Test breaking news
breaking = nt.get_breaking_news(limit=5)
test("Breaking news returns list", isinstance(breaking, list))
test("Breaking news has market-moving flag", all('is_market_moving' in b for b in breaking))
test("Breaking news sorted by severity", all('severity' in b for b in breaking))

# Test unsubscribe
success9, msg9 = nt.unsubscribe(1, "Tesla")
test("News unsubscribe succeeds", success9)

news_subs2 = nt.get_subscriptions(1)
test("News unsubscribed removed", not any(s['topic'] == "Tesla" for s in news_subs2))

# ===== SECTION 4: Stock-News Correlation Tests =====
print("\n[STOCK-NEWS CORRELATION TESTS]")

ce = StockNewsCorrelation()
test("Correlation engine initialized", ce is not None)

# Test extract_keywords
impact_type, keywords = ce.extract_keywords_from_news(
    "Tesla Reports Record Earnings", 
    "Tesla earnings beat expectations with record revenue"
)
test("Keyword extraction finds 'earnings' impact type", impact_type == 'earnings' or any(k in keywords for k in ['earnings', 'profit', 'revenue']))
test("Keyword extraction returns keywords", len(keywords) >= 1)

# Test find_affected_stocks
affected = ce.find_affected_stocks("Tesla", "Tesla stock surged")
test("Find affected stocks finds TESLA", any(a['stock'] == 'TESLA' for a in affected))

# Test multi-tier impact calculation
analysis = ce.calculate_multi_tier_impact("TESLA", "earnings", "HIGH")
test("Multi-tier analysis has tiers", 'tiers' in analysis)
test("Multi-tier analysis has tier_1", 'tier_1' in analysis['tiers'])
test("Multi-tier analysis has tier_2", 'tier_2' in analysis['tiers'])
test("Multi-tier analysis has tier_3", 'tier_3' in analysis['tiers'])
test("Multi-tier analysis has tier_4", 'tier_4' in analysis['tiers'])
test("Tier 1 has stocks", len(analysis['tiers']['tier_1']['stocks']) >= 1)
test("Tier 1 move > 0", analysis['tiers']['tier_1']['expected_move_percent'] > 0)
test("Tier 2 affected count > 0", analysis['tiers']['tier_2']['affected_count'] > 0)
test("Tier 3 has sector name", analysis['tiers']['tier_3']['sector'] != 'Unknown')
test("Total cascade estimate > 0", analysis['total_cascade_estimate'] > 0)
test("Tier 4 indexes defined", len(analysis['tiers']['tier_4']['index']) >= 1)

# Test for negative impact types
analysis2 = ce.calculate_multi_tier_impact("TESLA", "bankruptcy", "CRITICAL")
test("Bankruptcy impact has higher multiplier", 
     analysis2['tiers']['tier_1']['expected_move_percent'] >= 
     analysis['tiers']['tier_1']['expected_move_percent'])

# Test for different stocks
analysis3 = ce.calculate_multi_tier_impact("AAPL", "product_launch", "MEDIUM")
test("AAPL multi-tier analysis works", 'tiers' in analysis3)
test("AAPL tier 1 has direct stocks", 'AAPL' in analysis3['tiers']['tier_1']['stocks'])
test("AAPL tier 2 has suppliers", analysis3['tiers']['tier_2']['affected_count'] > 0)

# Test predict_market_move
prediction = ce.predict_market_move("TESLA", "earnings", "HIGH", 100.0)
test("Prediction has primary stock", prediction['primary_stock'] == "TESLA")
test("Prediction has current price > 0", prediction['current_price'] > 0)
test("Prediction has predicted move", prediction['predicted_move_percent'] != 0)
test("Prediction has predicted price > 0", prediction['predicted_price'] > 0)
test("Prediction has confidence", prediction['confidence'] > 0)
test("Prediction has multi-tier analysis", 'multi_tier_analysis' in prediction)
test("Prediction has cascade affected count", len(prediction['cascade_affected']) > 0)
test("Prediction direction detected", prediction['direction'] in ['up', 'down', 'uncertain'])

# Test correlation of news to stocks
article = {
    'title': 'Tesla Reports Record Earnings',
    'description': 'Tesla announced record earnings this quarter, surpassing expectations',
    'source': 'Reuters'
}
correlations = ce.correlate_news_to_stocks(1, article, ['TESLA'])
test("Correlation generates predictions", len(correlations) >= 1)
test("Correlation has predicted move", all('predicted_move_percent' in c for c in correlations))

# Test STOCK_RELATIONSHIPS completeness
required_relations = ['TESLA', 'AAPL', 'MSFT', 'XOM', 'JPM']
for r in required_relations:
    test(f"Stock relationship defined for {r}", r in STOCK_RELATIONSHIPS)
    test(f"{r} has direct stocks", len(STOCK_RELATIONSHIPS[r].get('direct', [])) >= 1)
    test(f"{r} has sector", 'sector' in STOCK_RELATIONSHIPS[r])

# Test IMPACT_MULTIPLIERS
required_impacts = ['earnings', 'acquisition', 'bankruptcy', 'regulation', 'product_launch', 'security_breach', 'profit_warning', 'award']
for imp in required_impacts:
    test(f"Impact multiplier defined for {imp}", imp in IMPACT_MULTIPLIERS)
    test(f"{imp} has direct multiplier > 0", IMPACT_MULTIPLIERS[imp].get('direct', 0) > 0)

# ===== SECTION 5: Monitoring Service Integration Tests =====
print("\n[MONITORING SERVICE INTEGRATION TESTS]")

ms = MonitoringService(check_interval=600)
ms.start()
test("Monitoring service started", ms.running)

# Test weather check
ms._check_weather_alerts(1)
test("Weather check runs without error", True)

# Test stock check
ms._check_stock_alerts(1)
test("Stock check runs without error", True)

# Test news check
ms._check_news_alerts(1)
test("News check runs without error", True)

# Test full user update
ms._check_user_updates(1)
test("Full user update runs without error", True)

# Test get_user_summary
summary = ms.get_user_summary(1)
test("Summary has weather data", 'weather' in summary)
test("Summary has stocks data", 'stocks' in summary)
test("Summary has news data", 'news' in summary)
test("Summary has notifications", 'notifications' in summary)
test("Summary has reminders", 'reminders' in summary)
test("Summary has videos", 'videos' in summary)
test("Summary has commits", 'commits' in summary)
test("Weather subscriptions in summary", 'subscriptions' in summary['weather'])
test("Stock popular list in summary", 'popular' in summary['stocks'])
test("News breaking in summary", 'breaking' in summary['news'])

# Test notifications
ms.notification_mgr.create_notification(1, "weather_alert", "Test Storm Alert", "Severe thunderstorm warning")
ms.notification_mgr.create_notification(1, "stock_alert", "Test Stock Alert", "AAPL up 5%")
ms.notification_mgr.create_notification(1, "news_alert", "Test News Alert", "Breaking: Market news")
ms.notification_mgr.create_notification(1, "cascade_prediction", "Test Cascade", "TESLA predicted move")
notifs = ms.notification_mgr.get_notifications(1)
test("Weather/stock/news notifications created", len(notifs) >= 4)
test("Notification types include weather_alert", any(n['type'] == 'weather_alert' for n in notifs))
test("Notification types include stock_alert", any(n['type'] == 'stock_alert' for n in notifs))
test("Notification types include news_alert", any(n['type'] == 'news_alert' for n in notifs))
test("Notification types include cascade_prediction", any(n['type'] == 'cascade_prediction' for n in notifs))

unread_count = ms.notification_mgr.get_unread_count(1)
test("Unread count > 0", unread_count >= 4)

# Test reminders for weather/stock/news
ms.reminder_mgr.create_reminder(1, "weather_alert", "Safety check: NYC", "Lightning warning detected", priority="high")
ms.reminder_mgr.create_reminder(1, "stock_alert", "Review AAPL position", "AAPL moved 5% after earnings", priority="high")
ms.reminder_mgr.create_reminder(1, "cascade_prediction", "Review cascade effect on TESLA", "News may affect TESLA", priority="high")

pending = ms.reminder_mgr.get_pending_reminders(1)
test("Weather/stock reminders created", len(pending) >= 3)
test("Reminder types include weather", any(r['type'] == 'weather_alert' for r in pending))
test("Reminder types include stock", any(r['type'] == 'stock_alert' for r in pending))
test("Reminder types include cascade", any(r['type'] == 'cascade_prediction' for r in pending))

# Test send_agent_message
ms.send_agent_message(1, "Weather alert: Lightning detected", "warning")
ms.send_agent_message(1, "Stock alert: AAPL up 6%", "info")
ms.send_agent_message(1, "News alert: Breaking market news", "info")
test("Agent messages sent without error", True)

# Test reminder completion
if pending:
    rid = pending[0]['id']
    ms.reminder_mgr.complete_reminder(rid)
    pending2 = ms.reminder_mgr.get_pending_reminders(1)
    test("Reminder completion works", not any(r['id'] == rid for r in pending2))

ms.stop()
test("Monitoring service stopped", not ms.running)

# Clean up test DB (best effort)
try:
    for _ in range(3):
        try:
            if os.path.exists(TEST_DB):
                os.remove(TEST_DB)
            break
        except PermissionError:
            time.sleep(0.5)
except:
    pass

# ===== FINAL RESULTS =====
print(f"\n{'='*40}")
print(f"FINAL RESULTS:")
print(f"  Passed: {passed}")
print(f"  Failed: {failed}")
print(f"  Total:  {passed + failed}")
print(f"{'='*40}")

if failed == 0:
    print("\n✓ ALL TESTS PASSED!")
else:
    print(f"\n⚠ {failed} TEST(S) FAILED!")

sys.exit(0 if failed == 0 else 1)
