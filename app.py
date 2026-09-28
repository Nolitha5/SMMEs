"""
Price Agent AI v3.0
E-commerce price tracker with Gemini 2.0 Flash AI, multi-store comparison,
budget tracker, wishlists, currency converter & smart deal analysis.
"""

from __future__ import annotations

import csv
import io
import json
import os
import re
import sqlite3
import statistics
import threading
import time
from datetime import datetime, timedelta

import requests
from bs4 import BeautifulSoup
from flask import (Flask, Response, jsonify, render_template,
                   request, redirect, url_for, session)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────

DATABASE     = os.environ.get('DATABASE_PATH', 'price_agent.db')
SECRET_KEY   = os.environ.get('SECRET_KEY', 'pa-dev-key-change-in-prod-!!!')
CHECK_HOURS  = int(os.environ.get('CHECK_INTERVAL_HOURS', '6'))
PORT         = int(os.environ.get('PORT', '5000'))
GEMINI_KEY   = os.environ.get('GEMINI_API_KEY', '').strip()
GEMINI_MODEL = os.environ.get('GEMINI_MODEL', 'gemini-3.8-flash').strip()
ENABLE_BACKGROUND_CHECKER = os.environ.get('ENABLE_BACKGROUND_CHECKER', 'true').lower() in ('1','true','yes','on')

app = Flask(__name__)
app.secret_key = SECRET_KEY

# ── Optional Firebase Admin SDK ───────────────────────────────
_firebase_admin_available = False
try:
    import firebase_admin
    from firebase_admin import credentials, auth as fb_auth
    _sa_path = os.environ.get('FIREBASE_SERVICE_ACCOUNT')
    if _sa_path and os.path.exists(_sa_path):
        cred = credentials.Certificate(_sa_path)
        firebase_admin.initialize_app(cred)
        _firebase_admin_available = True
        print('[auth] Firebase Admin SDK initialised.')
    else:
        print('[auth] Running in client-trust mode.')
except ImportError:
    print('[auth] firebase-admin not installed — client-trust mode.')


# ─────────────────────────────────────────────
# DATABASE
# ─────────────────────────────────────────────

def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    conn.execute('PRAGMA journal_mode = WAL')
    return conn


def init_db() -> None:
    conn = get_db()
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS products (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            name          TEXT    NOT NULL,
            url           TEXT,
            url2          TEXT    DEFAULT '',
            url3          TEXT    DEFAULT '',
            target_price  REAL,
            current_price REAL,
            currency      TEXT    DEFAULT 'ZAR',
            image_url     TEXT    DEFAULT '',
            category      TEXT    DEFAULT 'Other',
            priority      TEXT    DEFAULT 'medium',
            notes         TEXT    DEFAULT '',
            wishlist_id   INTEGER DEFAULT NULL,
            ai_insight    TEXT    DEFAULT '',
            ai_insight_at TIMESTAMP,
            created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_checked  TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS price_history (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id  INTEGER NOT NULL,
            price       REAL    NOT NULL,
            store       TEXT    DEFAULT 'main',
            source      TEXT    DEFAULT 'manual',
            note        TEXT    DEFAULT '',
            checked_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS alerts (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id  INTEGER NOT NULL,
            alert_type  TEXT,
            message     TEXT,
            price       REAL,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_read     INTEGER DEFAULT 0,
            FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS wishlists (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT NOT NULL,
            emoji      TEXT DEFAULT '📋',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS budgets (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            amount      REAL NOT NULL,
            spent       REAL DEFAULT 0,
            currency    TEXT DEFAULT 'ZAR',
            period      TEXT DEFAULT 'monthly',
            category    TEXT DEFAULT 'All',
            reset_day   INTEGER DEFAULT 1,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS store_prices (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id  INTEGER NOT NULL,
            store_name  TEXT NOT NULL,
            url         TEXT,
            price       REAL,
            last_checked TIMESTAMP,
            FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS chat_history (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            role       TEXT NOT NULL,
            message    TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    ''')

    # Safe migrations
    for ddl in [
        'ALTER TABLE products ADD COLUMN priority    TEXT DEFAULT "medium"',
        'ALTER TABLE products ADD COLUMN notes       TEXT DEFAULT ""',
        'ALTER TABLE products ADD COLUMN image_url   TEXT DEFAULT ""',
        'ALTER TABLE products ADD COLUMN url2        TEXT DEFAULT ""',
        'ALTER TABLE products ADD COLUMN url3        TEXT DEFAULT ""',
        'ALTER TABLE products ADD COLUMN wishlist_id INTEGER DEFAULT NULL',
        'ALTER TABLE products ADD COLUMN ai_insight  TEXT DEFAULT ""',
        'ALTER TABLE products ADD COLUMN ai_insight_at TIMESTAMP',
        'ALTER TABLE price_history ADD COLUMN note   TEXT DEFAULT ""',
        'ALTER TABLE price_history ADD COLUMN store  TEXT DEFAULT "main"',
    ]:
        try:
            conn.execute(ddl)
        except sqlite3.OperationalError:
            pass

    conn.commit()
    conn.close()


# ─────────────────────────────────────────────
# AUTH HELPERS
# ─────────────────────────────────────────────

def _is_authenticated() -> bool:
    return bool(session.get('uid'))

def _require_auth():
    if not _is_authenticated():
        return redirect(url_for('login'))
    return None


# ─────────────────────────────────────────────
# GEMINI AI
# ─────────────────────────────────────────────

GEMINI_URL = 'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent'

def call_gemini(prompt: str, system: str = '', max_tokens: int = 1024) -> str:
    """Call the configured Gemini REST API model and return clean text."""
    if not GEMINI_KEY:
        return '⚠️ Gemini is not configured. Add GEMINI_API_KEY to your .env file.'
    payload = {
        'contents': [{'role': 'user', 'parts': [{'text': prompt}]}],
        'generationConfig': {
            'temperature': 0.55,
            'maxOutputTokens': max_tokens,
            'topP': 0.9,
        },
    }
    if system:
        payload['systemInstruction'] = {'parts': [{'text': system}]}
    url = GEMINI_URL.format(model=GEMINI_MODEL)
    try:
        r = requests.post(url, headers={'x-goog-api-key': GEMINI_KEY, 'Content-Type': 'application/json'},
                           json=payload, timeout=45)
        if r.status_code == 429:
            return '⏳ Gemini rate limit reached. Please wait a moment and try again.'
        if r.status_code in (401, 403):
            return '❌ Gemini API key was rejected. Check GEMINI_API_KEY and the selected model.'
        if r.status_code == 404:
            return f'❌ Gemini model “{GEMINI_MODEL}” is unavailable. Set GEMINI_MODEL to a current model in .env.'
        r.raise_for_status()
        data = r.json()
        candidates = data.get('candidates') or []
        if not candidates:
            return '❌ Gemini returned no response candidates.'
        parts = (candidates[0].get('content') or {}).get('parts') or []
        text = ''.join(part.get('text', '') for part in parts).strip()
        return text or '❌ Gemini returned an empty response.'
    except requests.RequestException as e:
        return f'❌ Gemini API connection error: {e}'
    except (ValueError, KeyError, TypeError) as e:
        return f'❌ Invalid Gemini API response: {e}'


SYSTEM_PROMPT = """You are Price Agent AI — a smart shopping assistant embedded in a price tracking app.
You help users track prices, find deals, and make smart buying decisions.
Be concise, data-driven, and friendly. Use emojis sparingly.
Currency is ZAR (South African Rand) by default unless stated otherwise.
When asked about a product, give actionable advice: should they buy now, wait, or avoid?"""


# ─────────────────────────────────────────────
# CURRENCY CONVERTER (free API)
# ─────────────────────────────────────────────

_fx_cache: dict = {}
_fx_cache_time: float = 0

def get_fx_rates(base: str = 'ZAR') -> dict:
    """Fetch live FX rates from free Open Exchange Rates API."""
    global _fx_cache, _fx_cache_time
    if time.time() - _fx_cache_time < 3600 and _fx_cache.get('base') == base:
        return _fx_cache
    try:
        # Free tier: exchangerate-api.com (no key needed for basic)
        r = requests.get(f'https://api.exchangerate-api.com/v4/latest/{base}', timeout=10)
        r.raise_for_status()
        data = r.json()
        _fx_cache = data
        _fx_cache_time = time.time()
        return data
    except Exception:
        # Fallback hardcoded rates relative to ZAR (approximate)
        return {
            'base': 'ZAR',
            'rates': {'ZAR': 1, 'USD': 0.054, 'EUR': 0.050, 'GBP': 0.043, 'NGN': 88.5}
        }


# ─────────────────────────────────────────────
# VALIDATION / API HELPERS
# ─────────────────────────────────────────────

def _valid_http_url(value: str) -> bool:
    if not value:
        return True
    from urllib.parse import urlparse
    try:
        parsed = urlparse(value)
        return parsed.scheme in ('http', 'https') and bool(parsed.netloc)
    except Exception:
        return False

def _json_error(message: str, status: int = 400):
    return jsonify({'ok': False, 'error': message}), status

# ─────────────────────────────────────────────
# SCRAPER
# ─────────────────────────────────────────────

_USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
]
_ua_idx = 0

def _next_ua() -> str:
    global _ua_idx
    ua = _USER_AGENTS[_ua_idx % len(_USER_AGENTS)]
    _ua_idx += 1
    return ua

_PRICE_RES = [
    re.compile(r'R\s*([\d\s,]+(?:[.,]\d{1,2})?)'),
    re.compile(r'ZAR\s*([\d,]+(?:\.\d{1,2})?)', re.I),
    re.compile(r'\$\s*([\d,]+(?:\.\d{1,2})?)'),
    re.compile(r'€\s*([\d.,]+)'),
    re.compile(r'£\s*([\d.,]+)'),
    re.compile(r'([\d,]+(?:\.\d{2})?)\s*(?:USD|ZAR|EUR|GBP)', re.I),
]

def _parse_price(text: str) -> float | None:
    for rx in _PRICE_RES:
        m = rx.search(text)
        if m:
            raw = m.group(1).replace(',', '').replace(' ', '').replace('\xa0', '')
            try:
                val = float(raw)
                if 0.01 < val < 10_000_000:
                    return round(val, 2)
            except ValueError:
                pass
    return None

def _guess_category(url: str) -> str:
    url = url.lower()
    if any(k in url for k in ('phone','laptop','tv','camera','headphone','tablet','monitor','computer','electronics','tech','gadget')):
        return 'Electronics'
    if any(k in url for k in ('shoe','sneaker','clothing','fashion','apparel','dress','jacket','shirt','jean','trouser')):
        return 'Fashion'
    if any(k in url for k in ('kitchen','home','furniture','appliance','bedding','decor')):
        return 'Home'
    if any(k in url for k in ('sport','gym','fitness','outdoor','bike','running','soccer','cricket')):
        return 'Sports'
    if any(k in url for k in ('beauty','skincare','makeup','hair','fragrance','perfume')):
        return 'Beauty'
    if any(k in url for k in ('food','grocery','supermarket','pick n pay','checkers','woolworth')):
        return 'Groceries'
    return 'Other'

def _get_store_name(url: str) -> str:
    try:
        from urllib.parse import urlparse
        host = urlparse(url).netloc.lower().replace('www.', '')
        parts = host.split('.')
        return parts[0].title() if parts else host
    except Exception:
        return 'Store'

def scrape_price(url: str, retries: int = 2) -> tuple[float | None, str, str]:
    last_err = None
    for attempt in range(retries + 1):
        if attempt:
            time.sleep(2 ** attempt)
        try:
            headers = {
                'User-Agent': _next_ua(),
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
            }
            r = requests.get(url, headers=headers, timeout=18, allow_redirects=True)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, 'html.parser')
            name = ''
            img  = ''

            def walk_jsonld(value):
                if isinstance(value, dict):
                    yield value
                    for child in value.values():
                        yield from walk_jsonld(child)
                elif isinstance(value, list):
                    for child in value:
                        yield from walk_jsonld(child)

            for tag in soup.find_all('script', type='application/ld+json'):
                try:
                    data = json.loads(tag.string or tag.get_text() or '{}')
                    for item in walk_jsonld(data):
                        offers = item.get('offers') or {}
                        if isinstance(offers, list):
                            offers = next((x for x in offers if isinstance(x, dict)), {})
                        price_raw = offers.get('price') or offers.get('lowPrice') or item.get('price')
                        if price_raw is not None:
                            val = float(str(price_raw).replace(',', '').strip())
                            if 0.01 < val < 10_000_000:
                                name = str(item.get('name', ''))[:120]
                                img_raw = item.get('image', '')
                                img = img_raw[0] if isinstance(img_raw, list) and img_raw else (img_raw if isinstance(img_raw, str) else '')
                                return round(val, 2), name, img
                except Exception:
                    pass

            for attrs in [
                {'property': 'product:price:amount'}, {'name': 'twitter:data1'},
                {'itemprop': 'price'}, {'property': 'og:price:amount'},
            ]:
                tag = soup.find('meta', attrs)
                if tag:
                    val = _parse_price(tag.get('content', ''))
                    if val:
                        og_title = soup.find('meta', {'property': 'og:title'})
                        og_img   = soup.find('meta', {'property': 'og:image'})
                        name = og_title.get('content', '')[:120] if og_title else ''
                        img  = og_img.get('content', '') if og_img else ''
                        return val, name, img

            for el in soup.find_all(attrs={'data-price': True})[:10]:
                val = _parse_price(el['data-price'])
                if val:
                    title = soup.find('title')
                    name = title.get_text(strip=True)[:120] if title else ''
                    return val, name, ''

            selectors = [
                '#priceblock_ourprice','#priceblock_dealprice','#price_inside_buybox',
                '#corePrice_desktop','.price','.product-price','.current-price',
                '.sale-price','.offer-price','.buying-price',
                '[class*="price"][class*="current"]','[class*="price"][class*="sale"]',
                '[itemprop="price"]',
            ]
            for sel in selectors:
                for el in soup.select(sel)[:4]:
                    text = el.get_text(' ', strip=True)
                    val = _parse_price(text)
                    if val:
                        title  = soup.find('title')
                        og_img = soup.find('meta', {'property': 'og:image'})
                        name   = title.get_text(strip=True)[:120] if title else ''
                        img    = og_img.get('content', '') if og_img else ''
                        return val, name, img

        except Exception as e:
            last_err = e
            continue

    print(f'[scraper] Failed: {url}: {last_err}')
    return None, None, None


# ─────────────────────────────────────────────
# AI PRICE AGENT (Statistical)
# ─────────────────────────────────────────────

class PriceAgent:

    @staticmethod
    def _linreg(xs, ys):
        n = len(xs)
        if n < 2: return 0.0, ys[0] if ys else 0.0
        xm, ym = sum(xs)/n, sum(ys)/n
        num = sum((x-xm)*(y-ym) for x,y in zip(xs,ys))
        den = sum((x-xm)**2 for x in xs)
        slope = num/den if den else 0.0
        return slope, ym - slope*xm

    @staticmethod
    def _rsi(prices, period=14):
        if len(prices) < period+1: return 50.0
        changes = [prices[i]-prices[i-1] for i in range(1,len(prices))]
        recent  = changes[-period:]
        gains   = sum(c for c in recent if c > 0)
        losses  = sum(-c for c in recent if c < 0)
        ag = gains/period
        al = losses/period if losses else 1e-9
        return round(100 - 100/(1 + ag/al), 1)

    @staticmethod
    def _bollinger(prices, window=20):
        subset = prices[-window:] if len(prices) >= window else prices
        mid    = sum(subset)/len(subset)
        sd     = statistics.stdev(subset) if len(subset) > 1 else 0.0
        return mid-2*sd, mid, mid+2*sd

    @classmethod
    def analyze(cls, product_id):
        conn    = get_db()
        product = conn.execute('SELECT * FROM products WHERE id=?', (product_id,)).fetchone()
        rows    = conn.execute('SELECT price, checked_at FROM price_history WHERE product_id=? ORDER BY checked_at ASC', (product_id,)).fetchall()
        conn.close()

        if not product: return None
        prices  = [r['price'] for r in rows]
        current = product['current_price']
        target  = product['target_price']
        cur     = product['currency'] or 'ZAR'

        if len(prices) < 2 or not current:
            return {'status':'insufficient_data','message':'Add at least 2 price entries to unlock AI analysis.',
                    'recommendation':'WATCH','rec_color':'yellow','deal_score':0,'trend':'unknown'}

        n       = len(prices)
        min_p   = min(prices)
        max_p   = max(prices)
        avg_p   = sum(prices)/n
        p_range = max_p - min_p

        slope, intercept = cls._linreg(list(range(n)), prices)
        wk_chg = slope*7/avg_p*100 if avg_p else 0

        if abs(slope) < avg_p*0.0005:   trend, trend_label = 'stable',  '➡️ Stable'
        elif slope < 0:                  trend, trend_label = 'falling', f'📉 Falling {abs(wk_chg):.1f}%/wk'
        else:                            trend, trend_label = 'rising',  f'📈 Rising {wk_chg:.1f}%/wk'

        forecast = max(slope*(n+7)+intercept, min_p*0.65)

        try: vol = statistics.stdev(prices)/avg_p*100
        except: vol = 0.0

        rsi_val = cls._rsi(prices)
        boll_lo, _, boll_hi = cls._bollinger(prices)

        pos   = 1-(current-min_p)/p_range if p_range else 0.5
        score = pos*55
        if trend=='falling': score+=20
        elif trend=='rising': score-=10
        if rsi_val<30: score+=20
        elif rsi_val>70: score-=15
        if current<=boll_lo: score+=10
        score = int(max(0,min(100,score)))

        data_bonus  = min(n/30,1.0)*0.5
        vol_penalty = min(vol/20,0.3)
        confidence  = int(max(20,min(95,(0.5+data_bonus-vol_penalty)*100)))

        disc_avg = (avg_p-current)/avg_p*100
        disc_max = (max_p-current)/max_p*100

        if target and current<=target:
            rec,color,reason = 'BUY NOW 🎯','green',f'Price hit your target! {cur} {current:.2f} ≤ target {cur} {target:.2f}.'
        elif score>=75:
            rec,color,reason = 'BUY NOW 🔥','green','Excellent deal — price is near its historical low.'
        elif score>=55:
            rec,color,reason = 'GOOD DEAL 👍','blue',f'Price is {abs(disc_avg):.1f}% below average.'
        elif trend=='falling' and vol>4:
            rec,color,reason = 'WAIT ⏳','orange',f'Price is actively falling ({abs(wk_chg):.1f}%/wk).'
        elif score<25:
            rec,color,reason = 'AVOID ❌','red','Price is near its all-time high.'
        else:
            rec,color,reason = 'WATCH 👀','yellow','Price is around average. Set a target to get alerted.'

        return {
            'status':'ok','current_price':current,
            'min_price':round(min_p,2),'max_price':round(max_p,2),'avg_price':round(avg_p,2),
            'trend':trend,'trend_label':trend_label,'forecast_price':round(forecast,2),
            'volatility':round(vol,1),'rsi':rsi_val,'boll_lower':round(boll_lo,2),'boll_upper':round(boll_hi,2),
            'deal_score':score,'confidence':confidence,
            'disc_from_avg':round(disc_avg,1),'disc_from_max':round(disc_max,1),
            'recommendation':rec,'rec_color':color,'rec_reason':reason,
            'data_points':n,'currency':cur,
        }


# ─────────────────────────────────────────────
# BACKGROUND PRICE CHECKER
# ─────────────────────────────────────────────

def _check_one(p) -> None:
    price, _, _ = scrape_price(p['url'])
    if not price: return
    conn = get_db()
    conn.execute('UPDATE products SET current_price=?, last_checked=? WHERE id=?',
                 (price, datetime.now().isoformat(), p['id']))
    conn.execute('INSERT INTO price_history (product_id, price, source, store) VALUES (?,?,?,?)',
                 (p['id'], price, 'auto', 'main'))

    if p['target_price'] and price <= p['target_price']:
        recent = conn.execute("SELECT id FROM alerts WHERE product_id=? AND alert_type='target_reached' AND created_at > datetime('now','-2 hours')", (p['id'],)).fetchone()
        if not recent:
            conn.execute('INSERT INTO alerts (product_id, alert_type, message, price) VALUES(?,?,?,?)',
                (p['id'],'target_reached',f"🎯 {p['name']} hit your target! Now {p['currency']} {price:.2f}",price))

    if p['current_price'] and price < p['current_price']*0.9:
        recent = conn.execute("SELECT id FROM alerts WHERE product_id=? AND alert_type='price_drop' AND created_at > datetime('now','-24 hours')", (p['id'],)).fetchone()
        if not recent:
            drop = (p['current_price']-price)/p['current_price']*100
            conn.execute('INSERT INTO alerts (product_id, alert_type, message, price) VALUES(?,?,?,?)',
                (p['id'],'price_drop',f"📉 {p['name']} dropped {drop:.1f}%! {p['currency']} {p['current_price']:.2f} → {price:.2f}",price))

    conn.commit()
    conn.close()

    # Also check store comparison URLs
    for url_col in ('url2','url3'):
        extra_url = p[url_col] if url_col in p.keys() else ''
        if extra_url:
            ep, _, _ = scrape_price(extra_url)
            if ep:
                store = _get_store_name(extra_url)
                conn2 = get_db()
                conn2.execute('''INSERT INTO store_prices (product_id, store_name, url, price, last_checked)
                                 VALUES (?,?,?,?,?) ON CONFLICT DO NOTHING''',
                              (p['id'], store, extra_url, ep, datetime.now().isoformat()))
                try:
                    conn2.execute('''UPDATE store_prices SET price=?, last_checked=? WHERE product_id=? AND store_name=?''',
                                  (ep, datetime.now().isoformat(), p['id'], store))
                except Exception:
                    pass
                conn2.commit()
                conn2.close()
                time.sleep(2)


def _background_loop() -> None:
    time.sleep(15)
    while True:
        try:
            conn = get_db()
            products = conn.execute("SELECT * FROM products WHERE url IS NOT NULL AND url != ''").fetchall()
            conn.close()
            for p in products:
                try: _check_one(p)
                except Exception as e: print(f'[bg] product {p["id"]}: {e}')
                time.sleep(3)
        except Exception as e:
            print(f'[bg-loop] {e}')
        time.sleep(CHECK_HOURS*3600)


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def _product_row(p, conn) -> dict:
    d = dict(p)
    stats = conn.execute(
        '''SELECT COUNT(*) AS cnt, MIN(price) AS lo, MAX(price) AS hi,
                  (SELECT price FROM price_history WHERE product_id=? ORDER BY checked_at DESC LIMIT 1 OFFSET 1) AS prev
           FROM price_history WHERE product_id=?''',
        (p['id'], p['id'])
    ).fetchone()
    d['history_count'] = stats['cnt']
    d['min_price']     = stats['lo']
    d['max_price']     = stats['hi']
    d['prev_price']    = stats['prev']
    # Store comparison prices
    stores = conn.execute('SELECT store_name, price, last_checked FROM store_prices WHERE product_id=? ORDER BY price ASC', (p['id'],)).fetchall()
    d['store_prices'] = [dict(s) for s in stores]
    return d


# ─────────────────────────────────────────────
# AUTH ROUTES
# ─────────────────────────────────────────────

@app.route('/login')
def login():
    if _is_authenticated(): return redirect(url_for('index'))
    firebase_config = os.environ.get('FIREBASE_CONFIG_JSON', '').strip()
    if firebase_config:
        try: firebase_config = json.loads(firebase_config)
        except Exception: firebase_config = {}
    return render_template('login.html', firebase_config=firebase_config or {})

@app.route('/api/auth/session', methods=['POST'])
def api_auth_session():
    data     = request.json or {}
    id_token = data.get('idToken')
    if not id_token:
        return jsonify({'error': 'No token provided'}), 400

    if _firebase_admin_available:
        try:
            decoded = fb_auth.verify_id_token(id_token)
            session['uid']   = decoded['uid']
            session['email'] = decoded.get('email', '')
        except Exception as e:
            return jsonify({'error': f'Invalid token: {e}'}), 401
    else:
        import base64
        try:
            payload = id_token.split('.')[1] + '=='
            decoded = json.loads(base64.urlsafe_b64decode(payload))
            session['uid']   = decoded.get('sub') or decoded.get('user_id', 'user')
            session['email'] = decoded.get('email', '')
        except Exception:
            session['uid']   = 'firebase-user'
            session['email'] = ''

    session.permanent = True
    return jsonify({'ok': True})

@app.route('/api/auth/logout', methods=['POST'])
def api_auth_logout():
    session.clear()
    return jsonify({'ok': True})


# ─────────────────────────────────────────────
# MAIN ROUTES
# ─────────────────────────────────────────────

@app.route('/')
def index():
    guard = _require_auth()
    if guard: return guard
    return render_template('index.html')

@app.route('/api/dashboard')
def api_dashboard():
    if not _is_authenticated(): return jsonify({'error':'Unauthorized'}), 401
    conn = get_db()
    total    = conn.execute('SELECT COUNT(*) FROM products').fetchone()[0]
    unread   = conn.execute('SELECT COUNT(*) FROM alerts WHERE is_read=0').fetchone()[0]
    on_sale  = conn.execute('SELECT COUNT(*) FROM products WHERE target_price IS NOT NULL AND current_price IS NOT NULL AND current_price <= target_price*1.05').fetchone()[0]
    high_pri = conn.execute("SELECT COUNT(*) FROM products WHERE priority='high'").fetchone()[0]
    savings  = conn.execute('SELECT COALESCE(SUM(target_price-current_price),0) FROM products WHERE target_price IS NOT NULL AND current_price IS NOT NULL AND current_price <= target_price').fetchone()[0]
    budgets  = conn.execute('SELECT COUNT(*) FROM budgets').fetchone()[0]
    wishlists= conn.execute('SELECT COUNT(*) FROM wishlists').fetchone()[0]
    conn.close()
    return jsonify({'total_products':total,'unread_alerts':unread,'on_sale':on_sale,
                    'high_priority':high_pri,'total_savings':round(float(savings),2),
                    'budgets':budgets,'wishlists':wishlists,
                    'gemini_active': bool(GEMINI_KEY)})


# ── Products ──────────────────────────────────

@app.route('/api/products', methods=['GET'])
def api_products():
    if not _is_authenticated(): return jsonify({'error':'Unauthorized'}), 401
    search = (request.args.get('search') or '').strip().lower()
    sort   = request.args.get('sort','date_desc')
    cat    = request.args.get('cat','')
    pri    = request.args.get('priority','')
    wl     = request.args.get('wishlist','')

    conn   = get_db()
    rows   = conn.execute('SELECT * FROM products').fetchall()
    result = [_product_row(p,conn) for p in rows]
    conn.close()

    if search: result = [p for p in result if search in p['name'].lower() or search in (p.get('notes') or '').lower()]
    if cat:    result = [p for p in result if p['category'] == cat]
    if pri:    result = [p for p in result if p['priority'] == pri]
    if wl:     result = [p for p in result if str(p.get('wishlist_id') or '') == wl]

    PRIORITY_ORDER = {'high':0,'medium':1,'low':2}
    if   sort == 'priority':    result.sort(key=lambda p: PRIORITY_ORDER.get(p['priority'],1))
    elif sort == 'price_asc':   result.sort(key=lambda p: p['current_price'] or 0)
    elif sort == 'price_desc':  result.sort(key=lambda p: p['current_price'] or 0, reverse=True)
    elif sort == 'name':        result.sort(key=lambda p: p['name'].lower())
    elif sort == 'last_checked':result.sort(key=lambda p: p['last_checked'] or '', reverse=True)
    elif sort == 'deal_score':
        def _qs(p):
            if not p['min_price'] or not p['max_price'] or not p['current_price']: return -1
            r = p['max_price'] - p['min_price']
            return (1-(p['current_price']-p['min_price'])/r*100) if r else 50
        result.sort(key=_qs, reverse=True)
    else: result.sort(key=lambda p: p['created_at'], reverse=True)

    return jsonify(result)


@app.route('/api/products', methods=['POST'])
def api_add_product():
    if not _is_authenticated(): return jsonify({'error':'Unauthorized'}), 401
    data         = request.json or {}
    name         = (data.get('name') or '').strip()
    url          = (data.get('url') or '').strip()
    url2         = (data.get('url2') or '').strip()
    url3         = (data.get('url3') or '').strip()
    target_price = data.get('target_price')
    init_price   = data.get('initial_price')
    category     = data.get('category','Other')
    currency     = data.get('currency','ZAR')
    priority     = data.get('priority','medium')
    notes        = (data.get('notes') or '').strip()
    wishlist_id  = data.get('wishlist_id')

    if not name: return jsonify({'error':'Product name is required'}), 400
    if any(not _valid_http_url(u) for u in (url, url2, url3) if u):
        return _json_error('Store URLs must start with http:// or https://')

    scraped_price = img_url = None
    if url:
        scraped_price, scraped_name, img_url = scrape_price(url)
        if not name and scraped_name: name = scraped_name
        if not category or category == 'Other': category = _guess_category(url)

    try:
        current = float(init_price) if init_price not in (None, '') else scraped_price
        tp = float(target_price) if target_price not in (None, '') else None
        if current is not None and current <= 0: raise ValueError
        if tp is not None and tp <= 0: raise ValueError
    except (TypeError, ValueError):
        return _json_error('Prices must be positive numbers.')

    conn = get_db()
    cur  = conn.execute(
        'INSERT INTO products (name,url,url2,url3,target_price,current_price,currency,image_url,category,priority,notes,wishlist_id,last_checked) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',
        (name, url or None, url2 or '', url3 or '', tp, current, currency, img_url or '', category, priority, notes, wishlist_id, datetime.now().isoformat())
    )
    pid = cur.lastrowid
    if current:
        conn.execute('INSERT INTO price_history (product_id,price,source,store) VALUES (?,?,?,?)',
                     (pid, current, 'url' if scraped_price else 'manual', 'main'))

    # Scrape comparison stores
    for i, extra_url in enumerate([url2, url3], 1):
        if extra_url:
            ep, _, _ = scrape_price(extra_url)
            if ep:
                store = _get_store_name(extra_url)
                conn.execute('INSERT OR REPLACE INTO store_prices (product_id,store_name,url,price,last_checked) VALUES (?,?,?,?,?)',
                             (pid, store, extra_url, ep, datetime.now().isoformat()))

    conn.commit()
    conn.close()
    return jsonify({'id':pid,'scraped':scraped_price is not None,'price':current}), 201


@app.route('/api/products/<int:pid>', methods=['PUT'])
def api_update_product(pid):
    if not _is_authenticated(): return jsonify({'error':'Unauthorized'}), 401
    data = request.json or {}
    conn = get_db()
    p    = conn.execute('SELECT * FROM products WHERE id=?', (pid,)).fetchone()
    if not p: conn.close(); return jsonify({'error':'Not found'}), 404
    conn.execute('UPDATE products SET name=?,target_price=?,priority=?,notes=?,category=?,url2=?,url3=?,wishlist_id=? WHERE id=?',
                 ((data.get('name') or p['name']).strip(), data.get('target_price',p['target_price']),
                  data.get('priority',p['priority']), data.get('notes',p['notes'] or ''),
                  data.get('category',p['category']), data.get('url2',p['url2'] or ''),
                  data.get('url3',p['url3'] or ''), data.get('wishlist_id',p['wishlist_id']), pid))
    conn.commit(); conn.close()
    return jsonify({'ok':True})


@app.route('/api/products/<int:pid>', methods=['DELETE'])
def api_delete_product(pid):
    if not _is_authenticated(): return jsonify({'error':'Unauthorized'}), 401
    conn = get_db()
    conn.execute('DELETE FROM products WHERE id=?', (pid,))
    conn.commit(); conn.close()
    return jsonify({'ok':True})


@app.route('/api/products/<int:pid>/price', methods=['POST'])
def api_update_price(pid):
    if not _is_authenticated(): return jsonify({'error':'Unauthorized'}), 401
    data  = request.json or {}
    price = data.get('price')
    note  = (data.get('note') or '').strip()[:200]
    if not price or float(price) <= 0: return jsonify({'error':'Valid price required'}), 400
    price = round(float(price), 2)
    conn  = get_db()
    old   = conn.execute('SELECT * FROM products WHERE id=?', (pid,)).fetchone()
    if not old: conn.close(); return jsonify({'error':'Product not found'}), 404
    conn.execute('UPDATE products SET current_price=?,last_checked=? WHERE id=?',
                 (price, datetime.now().isoformat(), pid))
    conn.execute('INSERT INTO price_history (product_id,price,source,note,store) VALUES (?,?,?,?,?)',
                 (pid, price, 'manual', note, 'main'))
    triggered = []
    if old['target_price'] and price <= old['target_price']:
        conn.execute('INSERT INTO alerts (product_id,alert_type,message,price) VALUES(?,?,?,?)',
            (pid,'target_reached',f"🎯 {old['name']} hit target! {old['currency']} {price:.2f} ≤ target {old['target_price']:.2f}",price))
        triggered.append('target_reached')
    if old['current_price'] and price < old['current_price']*0.9:
        drop = (old['current_price']-price)/old['current_price']*100
        conn.execute('INSERT INTO alerts (product_id,alert_type,message,price) VALUES(?,?,?,?)',
            (pid,'price_drop',f"📉 {old['name']} dropped {drop:.1f}%! {old['currency']} {old['current_price']:.2f} → {price:.2f}",price))
        triggered.append('price_drop')
    conn.commit(); conn.close()
    return jsonify({'ok':True,'alerts':triggered})


@app.route('/api/products/<int:pid>/scrape', methods=['POST'])
def api_scrape(pid):
    if not _is_authenticated(): return jsonify({'error':'Unauthorized'}), 401
    conn = get_db()
    p    = conn.execute('SELECT * FROM products WHERE id=?', (pid,)).fetchone()
    conn.close()
    if not p or not p['url']: return jsonify({'error':'No URL set'}), 400
    price, _, _ = scrape_price(p['url'])
    if not price: return jsonify({'error':'Could not scrape price. Update manually.'}), 400
    conn = get_db()
    conn.execute('UPDATE products SET current_price=?,last_checked=? WHERE id=?',
                 (price, datetime.now().isoformat(), pid))
    conn.execute('INSERT INTO price_history (product_id,price,source,store) VALUES(?,?,?,?)',
                 (pid, price, 'auto', 'main'))
    conn.commit(); conn.close()
    return jsonify({'price': price})


@app.route('/api/products/<int:pid>/history')
def api_history(pid):
    if not _is_authenticated(): return jsonify({'error':'Unauthorized'}), 401
    conn = get_db()
    rows = conn.execute('SELECT price,source,note,store,checked_at FROM price_history WHERE product_id=? ORDER BY checked_at ASC', (pid,)).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route('/api/products/<int:pid>/analysis')
def api_analysis(pid):
    if not _is_authenticated(): return jsonify({'error':'Unauthorized'}), 401
    result = PriceAgent.analyze(pid)
    if result is None: return jsonify({'error':'Product not found'}), 404
    return jsonify(result)


@app.route('/api/products/<int:pid>/export')
def api_export_csv(pid):
    if not _is_authenticated(): return jsonify({'error':'Unauthorized'}), 401
    conn    = get_db()
    product = conn.execute('SELECT * FROM products WHERE id=?', (pid,)).fetchone()
    rows    = conn.execute('SELECT price,source,note,store,checked_at FROM price_history WHERE product_id=? ORDER BY checked_at ASC', (pid,)).fetchall()
    conn.close()
    if not product: return jsonify({'error':'Not found'}), 404
    buf = io.StringIO()
    w   = csv.writer(buf)
    w.writerow(['Date','Price','Currency','Store','Source','Note'])
    for r in rows:
        w.writerow([r['checked_at'],r['price'],product['currency'],r['store'],r['source'],r['note'] or ''])
    filename = re.sub(r'[^\w\-]','_',product['name']) + '_price_history.csv'
    return Response(buf.getvalue(), mimetype='text/csv',
                    headers={'Content-Disposition':f'attachment; filename="{filename}"'})


# ── Alerts ────────────────────────────────────

@app.route('/api/alerts')
def api_alerts():
    if not _is_authenticated(): return jsonify({'error':'Unauthorized'}), 401
    conn = get_db()
    rows = conn.execute('''SELECT a.*,p.name AS product_name FROM alerts a
                           JOIN products p ON a.product_id=p.id
                           ORDER BY a.created_at DESC LIMIT 100''').fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/alerts/<int:aid>/read', methods=['POST'])
def api_mark_read(aid):
    if not _is_authenticated(): return jsonify({'error':'Unauthorized'}), 401
    conn = get_db(); conn.execute('UPDATE alerts SET is_read=1 WHERE id=?',(aid,)); conn.commit(); conn.close()
    return jsonify({'ok':True})

@app.route('/api/alerts/read-all', methods=['POST'])
def api_read_all():
    if not _is_authenticated(): return jsonify({'error':'Unauthorized'}), 401
    conn = get_db(); conn.execute('UPDATE alerts SET is_read=1'); conn.commit(); conn.close()
    return jsonify({'ok':True})


# ── Wishlists ─────────────────────────────────

@app.route('/api/wishlists', methods=['GET'])
def api_wishlists():
    if not _is_authenticated(): return jsonify({'error':'Unauthorized'}), 401
    conn = get_db()
    rows = conn.execute('''SELECT w.*, COUNT(p.id) AS product_count
                           FROM wishlists w LEFT JOIN products p ON p.wishlist_id=w.id
                           GROUP BY w.id ORDER BY w.created_at DESC''').fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/wishlists', methods=['POST'])
def api_create_wishlist():
    if not _is_authenticated(): return jsonify({'error':'Unauthorized'}), 401
    data  = request.json or {}
    name  = (data.get('name') or '').strip()
    emoji = data.get('emoji','📋')
    if not name: return jsonify({'error':'Name required'}), 400
    conn  = get_db()
    cur   = conn.execute('INSERT INTO wishlists (name,emoji) VALUES (?,?)', (name,emoji))
    wid   = cur.lastrowid
    conn.commit(); conn.close()
    return jsonify({'id':wid}), 201

@app.route('/api/wishlists/<int:wid>', methods=['DELETE'])
def api_delete_wishlist(wid):
    if not _is_authenticated(): return jsonify({'error':'Unauthorized'}), 401
    conn = get_db()
    conn.execute('UPDATE products SET wishlist_id=NULL WHERE wishlist_id=?',(wid,))
    conn.execute('DELETE FROM wishlists WHERE id=?',(wid,))
    conn.commit(); conn.close()
    return jsonify({'ok':True})


# ── Budgets ───────────────────────────────────

@app.route('/api/budgets', methods=['GET'])
def api_budgets():
    if not _is_authenticated(): return jsonify({'error':'Unauthorized'}), 401
    conn = get_db()
    rows = conn.execute('SELECT * FROM budgets ORDER BY created_at DESC').fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/budgets', methods=['POST'])
def api_create_budget():
    if not _is_authenticated(): return jsonify({'error':'Unauthorized'}), 401
    data = request.json or {}
    name = (data.get('name') or '').strip()
    amt  = data.get('amount')
    try:
        amt = float(amt)
        if amt <= 0: raise ValueError
    except (TypeError, ValueError):
        return _json_error('Budget amount must be greater than zero.')
    if not name: return _json_error('Budget name is required.')
    conn = get_db()
    cur  = conn.execute('INSERT INTO budgets (name,amount,currency,period,category,reset_day) VALUES (?,?,?,?,?,?)',
                        (name, float(amt), data.get('currency','ZAR'), data.get('period','monthly'),
                         data.get('category','All'), data.get('reset_day',1)))
    bid  = cur.lastrowid
    conn.commit(); conn.close()
    return jsonify({'id':bid}), 201

@app.route('/api/budgets/<int:bid>/spend', methods=['POST'])
def api_budget_spend(bid):
    if not _is_authenticated(): return jsonify({'error':'Unauthorized'}), 401
    try:
        amount = float((request.json or {}).get('amount', 0))
        if amount <= 0: raise ValueError
    except (TypeError, ValueError):
        return _json_error('Spend amount must be greater than zero.')
    conn   = get_db()
    conn.execute('UPDATE budgets SET spent=spent+? WHERE id=?',(amount,bid))
    conn.commit(); conn.close()
    return jsonify({'ok':True})

@app.route('/api/budgets/<int:bid>/reset', methods=['POST'])
def api_budget_reset(bid):
    if not _is_authenticated(): return jsonify({'error':'Unauthorized'}), 401
    conn = get_db()
    conn.execute('UPDATE budgets SET spent=0 WHERE id=?',(bid,))
    conn.commit(); conn.close()
    return jsonify({'ok':True})

@app.route('/api/budgets/<int:bid>', methods=['DELETE'])
def api_delete_budget(bid):
    if not _is_authenticated(): return jsonify({'error':'Unauthorized'}), 401
    conn = get_db()
    conn.execute('DELETE FROM budgets WHERE id=?',(bid,))
    conn.commit(); conn.close()
    return jsonify({'ok':True})


# ── Currency ──────────────────────────────────

@app.route('/api/currency')
def api_currency():
    if not _is_authenticated(): return jsonify({'error':'Unauthorized'}), 401
    base = (request.args.get('base','ZAR') or 'ZAR').upper()
    if not re.fullmatch(r'[A-Z]{3}', base): return _json_error('Currency must be a 3-letter ISO code.')
    return jsonify(get_fx_rates(base))


# ── AI (Gemini) ───────────────────────────────

@app.route('/api/ai/chat', methods=['POST'])
def api_ai_chat():
    if not _is_authenticated(): return jsonify({'error':'Unauthorized'}), 401
    data    = request.json or {}
    message = (data.get('message') or '').strip()
    if not message: return jsonify({'error':'Message required'}), 400

    # Build context from user's products
    conn     = get_db()
    products = conn.execute('SELECT name,current_price,target_price,currency,category FROM products ORDER BY created_at DESC LIMIT 10').fetchall()
    conn.close()
    context  = '\n'.join([f"- {p['name']}: {p['currency']} {p['current_price'] or 'N/A'} (target: {p['target_price'] or 'N/A'})" for p in products])

    prompt = f"""User's tracked products:
{context or 'No products tracked yet.'}

User question: {message}

Answer helpfully and concisely. Give specific advice based on the products if relevant."""

    response = call_gemini(prompt, system=SYSTEM_PROMPT, max_tokens=512)

    # Save to chat history
    conn = get_db()
    conn.execute('INSERT INTO chat_history (role,message) VALUES (?,?)', ('user',message))
    conn.execute('INSERT INTO chat_history (role,message) VALUES (?,?)', ('assistant',response))
    conn.commit(); conn.close()

    return jsonify({'response': response})


@app.route('/api/ai/explain/<int:pid>', methods=['GET'])
def api_ai_explain(pid):
    """Get Gemini AI explanation for a product's deal score."""
    if not _is_authenticated(): return jsonify({'error':'Unauthorized'}), 401

    conn    = get_db()
    product = conn.execute('SELECT * FROM products WHERE id=?', (pid,)).fetchone()
    rows    = conn.execute('SELECT price,checked_at FROM price_history WHERE product_id=? ORDER BY checked_at DESC LIMIT 20', (pid,)).fetchall()
    conn.close()

    if not product: return jsonify({'error':'Not found'}), 404

    analysis = PriceAgent.analyze(pid)
    prices   = [r['price'] for r in rows]

    prompt = f"""Analyze this product for a South African shopper:

Product: {product['name']}
Category: {product['category']}
Current Price: {product['currency']} {product['current_price'] or 'N/A'}
Target Price: {product['currency']} {product['target_price'] or 'Not set'}
Price History (last 20): {prices}
Statistical Analysis:
- Deal Score: {analysis.get('deal_score', 'N/A')}/100
- Trend: {analysis.get('trend_label', 'N/A')}
- Min Ever: {product['currency']} {analysis.get('min_price', 'N/A')}
- Max Ever: {product['currency']} {analysis.get('max_price', 'N/A')}
- Avg Price: {product['currency']} {analysis.get('avg_price', 'N/A')}
- RSI: {analysis.get('rsi', 'N/A')}
- Volatility: {analysis.get('volatility', 'N/A')}%
- Recommendation: {analysis.get('recommendation', 'N/A')}

Write a 3-4 sentence natural language explanation of whether this is a good time to buy.
Be specific about the numbers. Mention if the buyer should wait, buy now, or watch.
Keep it conversational and actionable."""

    response = call_gemini(prompt, system=SYSTEM_PROMPT, max_tokens=256)

    # Cache the insight
    conn = get_db()
    conn.execute('UPDATE products SET ai_insight=?, ai_insight_at=? WHERE id=?',
                 (response, datetime.now().isoformat(), pid))
    conn.commit(); conn.close()

    return jsonify({'insight': response, 'analysis': analysis})


@app.route('/api/ai/compare', methods=['POST'])
def api_ai_compare():
    """Ask Gemini to compare two products."""
    if not _is_authenticated(): return jsonify({'error':'Unauthorized'}), 401
    data = request.json or {}
    ids  = data.get('ids', [])
    if len(ids) < 2: return jsonify({'error':'Need at least 2 product IDs'}), 400

    conn     = get_db()
    products = [conn.execute('SELECT * FROM products WHERE id=?', (pid,)).fetchone() for pid in ids[:4]]
    conn.close()
    products = [p for p in products if p]
    if len(products) < 2: return _json_error('Select at least 2 valid products.')

    lines = [f"{i+1}. {p['name']} — {p['currency']} {p['current_price'] or 'N/A'} (target: {p['target_price'] or 'N/A'}, category: {p['category']})"
             for i, p in enumerate(products)]
    prompt = f"""Compare these products for a shopper and recommend which to buy first:

{chr(10).join(lines)}

Give a 3-5 sentence comparison. Which offers the best value right now? Which should they prioritize?"""

    response = call_gemini(prompt, system=SYSTEM_PROMPT, max_tokens=300)
    return jsonify({'comparison': response})


@app.route('/api/ai/summary', methods=['GET'])
def api_ai_summary():
    """Daily AI summary of the user's portfolio."""
    if not _is_authenticated(): return jsonify({'error':'Unauthorized'}), 401

    conn     = get_db()
    products = conn.execute('SELECT * FROM products ORDER BY priority DESC LIMIT 20').fetchall()
    alerts   = conn.execute("SELECT COUNT(*) FROM alerts WHERE is_read=0").fetchone()[0]
    on_sale  = conn.execute('SELECT COUNT(*) FROM products WHERE target_price IS NOT NULL AND current_price IS NOT NULL AND current_price <= target_price').fetchone()[0]
    budgets  = conn.execute('SELECT * FROM budgets').fetchall()
    conn.close()

    prod_lines = [f"- {p['name']}: {p['currency']} {p['current_price'] or 'N/A'} (priority: {p['priority']})" for p in products]
    budget_lines = [f"- {b['name']}: spent {b['currency']} {b['spent']:.2f} of {b['amount']:.2f}" for b in budgets]

    prompt = f"""Give a quick daily briefing for this shopper's price tracker:

Tracked products ({len(products)}):
{chr(10).join(prod_lines) or 'None yet.'}

Budgets:
{chr(10).join(budget_lines) or 'No budgets set.'}

Stats: {on_sale} products at or below target price, {alerts} unread alerts.

Write a friendly 3-4 sentence morning briefing. Highlight any urgent deals and budget status. Be encouraging."""

    response = call_gemini(prompt, system=SYSTEM_PROMPT, max_tokens=300)
    return jsonify({'summary': response})


# ── Health ────────────────────────────────────

@app.route('/health')
def health():
    return jsonify({'status':'ok','version':'3.1.0','gemini':bool(GEMINI_KEY),'gemini_model':GEMINI_MODEL,'background_checker':ENABLE_BACKGROUND_CHECKER})


# ─────────────────────────────────────────────
# STARTUP — works for both python app.py AND gunicorn
# ─────────────────────────────────────────────

init_db()
if ENABLE_BACKGROUND_CHECKER:
    threading.Thread(target=_background_loop, daemon=True, name='price-checker').start()

if __name__ == '__main__':
    print(f'\n🤖  Price Agent AI v3.0  →  http://localhost:{PORT}')
    print(f'✨  Gemini AI: {"✅ Active" if GEMINI_KEY else "❌ Add GEMINI_API_KEY to .env"}\n')
    app.run(host='0.0.0.0', port=PORT, debug=False)
