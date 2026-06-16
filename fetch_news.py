import time
import os
import feedparser
import requests
import urllib3

# Disable insecure request warnings for sites with bad SSL certificates
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

DB_FILE = "sent_articles.txt"
WEATHER_DB_FILE = "weather_sent.txt"

# Feed configurations utilizing environment variables for webhooks
FEEDS_CONFIG = {
    "Sport24": {
        "rss": "https://news.google.com/rss/search?q=site:sport24.gr&hl=el&gl=GR&ceid=GR:el",
        "webhook": os.environ.get("SPORT24_WEBHOOK")
    },
    "News247": {
        "rss": "https://news.google.com/rss/search?q=site:news247.gr&hl=el&gl=GR&ceid=GR:el",
        "webhook": os.environ.get("NEWS247_WEBHOOK")
    },
    "PaokToday": {
        "rss": "https://www.paoktoday.gr/rss",
        "webhook": os.environ.get("PAOKTODAY_WEBHOOK")
    },
    "Reuters": {
        "rss": "https://news.google.com/rss/search?q=reuters&hl=en-US&gl=US&ceid=US:en",
        "webhook": os.environ.get("REUTERS_WEBHOOK")
    }
}

# Weather setup for Copenhagen (Lat: 55.6761, Lon: 12.5683)
WEATHER_CONFIG = {
    "webhook": os.environ.get("WEATHER_WEBHOOK"),
    "lat": "55.6761",
    "lon": "12.5683"
}

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

def get_weather_emoji(code):
    mapping = {0: "☀️ Clear Sky", 1: "🌤️ Mainly Clear", 2: "⛅ Partly Cloudy", 3: "☁️ Overcast", 
               45: "🌫️ Fog", 51: "🌦️ Drizzle", 61: "🌧️ Rain", 71: "❄️ Snowfall", 80: "🌧️ Rain Showers", 95: "⚡ Thunderstorm"}
    return mapping.get(code, "🌡️")

def check_and_send_weather():
    today = time.strftime("%Y-%m-%d")
    
    # Avoid duplicate daily weather reports
    if os.path.exists(WEATHER_DB_FILE):
        with open(WEATHER_DB_FILE, "r") as f:
            if today in f.read():
                return

    print("🌤️ Fetching weather for Copenhagen...")
    webhook_url = WEATHER_CONFIG["webhook"]
    if not webhook_url:
        print("❌ Weather webhook missing from environment variables.")
        return

    url = f"https://api.open-meteo.com/v1/forecast?latitude={WEATHER_CONFIG['lat']}&longitude={WEATHER_CONFIG['lon']}&current=temperature_2m,apparent_temperature,weather_code,wind_speed_10m&timezone=Europe/Berlin"
    
    try:
        res = requests.get(url, timeout=10).json()
        current = res["current"]
        embed = {
            "title": f"📊 Daily Weather Report | Copenhagen ({time.strftime('%d/%m/%Y')})",
            "description": f"**Condition:** {get_weather_emoji(current['weather_code'])}\n**Temperature:** {current['temperature_2m']}°C\n**Feels Like:** {current['apparent_temperature']}°C\n**Wind Speed:** {current['wind_speed_10m']} km/h",
            "color": 5814783,
            "footer": {"text": "Powered by Open-Meteo"}
        }
        requests.post(webhook_url, json={"embeds": [embed]})
        with open(WEATHER_DB_FILE, "w") as f:
            f.write(today)
        print("✅ Weather report sent successfully!")
    except Exception as e:
        print(f"❌ Failed to fetch/send weather: {e}")

def load_sent_urls():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return set(line.strip() for line in f if line.strip())
    return set()

def save_sent_url(url):
    with open(DB_FILE, "a", encoding="utf-8") as f:
        f.write(url + "\n")

def send_to_discord(title, link, description, source_name, webhook_url):
    if not webhook_url:
        print(f"❌ Webhook missing for {source_name}. Skipping entry.")
        return
        
    desc = description[:300] + "..." if len(description) > 300 else description
    embed = {
        "title": title[:256],
        "url": link,
        "description": desc,
        "color": 3447003,
        "footer": {"text": f"Source: {source_name}"}
    }
    try:
        requests.post(webhook_url, json={"embeds": [embed]})
        print(f"✅ [{source_name}] Sent: {title}")
    except Exception as e:
        print(f"❌ Failed to send to {source_name} channel: {e}")

def check_feeds():
    print("\n🔄 Checking RSS feeds...")
    sent_urls = load_sent_urls()
    
    for source_name, config in FEEDS_CONFIG.items():
        try:
            response = requests.get(config["rss"], headers=HEADERS, verify=False, timeout=15)
            if response.status_code != 200: 
                print(f"⚠️ {source_name} returned status code {response.status_code}")
                continue
            
            feed = feedparser.parse(response.content)
            for entry in feed.entries[:5]:
                link = entry.get("link")
                if link and link not in sent_urls:
                    send_to_discord(entry.get("title"), link, entry.get("summary", ""), source_name, config["webhook"])
                    save_sent_url(link)
                    sent_urls.add(link)
                    time.sleep(1.5)
        except Exception as e:
            print(f"❌ Error processing feed for {source_name}: {e}")

if __name__ == "__main__":
    check_and_send_weather()
    check_feeds()
    print("🏁 Execution finished successfully!")