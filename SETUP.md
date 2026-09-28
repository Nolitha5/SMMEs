# Price Agent AI v3.1

A Flask-based price tracker with Gemini AI, multi-store comparison, alerts, wishlists, budgets, currency conversion and CSV export.

## 1. Local setup

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env   # Windows
# cp .env.example .env   # macOS/Linux
python app.py
```

Open `http://localhost:5000`.

## 2. Gemini API

Create a Gemini API key in Google AI Studio and set:

```env
GEMINI_API_KEY=your-key
GEMINI_MODEL=gemini-3.8-flash
```

The API key stays on the Flask server; the browser never receives it.

## 3. Firebase login

Set `FIREBASE_CONFIG_JSON` to your Firebase web configuration as a single JSON object. For production, also set `FIREBASE_SERVICE_ACCOUNT` to a server-side Firebase Admin service-account JSON path so Flask verifies Firebase ID tokens instead of using the development fallback.

## 4. API endpoints

- `GET /health` — deployment health and API status
- `GET /api/dashboard` — dashboard KPIs
- `GET/POST /api/products` — list/create products
- `PUT/DELETE /api/products/<id>` — edit/delete products
- `POST /api/products/<id>/price` — add a manual price point
- `POST /api/products/<id>/scrape` — refresh the primary store price
- `GET /api/products/<id>/history` — price history
- `GET /api/products/<id>/analysis` — statistical deal analysis
- `GET /api/products/<id>/export` — CSV history export
- `GET/POST /api/wishlists` — wishlists
- `GET/POST /api/budgets` — budgets
- `GET /api/currency?base=ZAR` — live FX rates
- `POST /api/ai/chat` — Gemini shopping assistant
- `GET /api/ai/explain/<id>` — AI product explanation
- `POST /api/ai/compare` — AI comparison
- `GET /api/ai/summary` — AI portfolio summary

## 5. Deployment

Render reads `render.yaml`. Add `GEMINI_API_KEY`, `FIREBASE_CONFIG_JSON`, and (for production authentication) `FIREBASE_SERVICE_ACCOUNT` in the Render environment.

The app uses one Gunicorn worker because the built-in background price checker is a process-local thread. This prevents duplicate price checks.

## Notes on price scraping

Many ecommerce stores render prices in JavaScript or block automated requests. The agent first checks structured product data (`JSON-LD`, OpenGraph/meta and common price selectors), then falls back to manual price entry. A failed scrape does not overwrite an existing price.
