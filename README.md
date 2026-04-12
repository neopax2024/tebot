# 🔲 Telegram Code Scanner & Generator Platform

A production-ready **SaaS-level Telegram bot + Mini App** for scanning, generating, customising, and analysing multiple code formats — all inside Telegram chat and a native Mini App.

---

## ✨ Features

| Category | Capabilities |
|---|---|
| **Scanning** | QR, EAN-8/13, UPC-A, Code 128/39, ITF, Data Matrix, Aztec — from images, PDFs, live camera |
| **Generation** | QR codes, Barcodes, Data Matrix — PNG, SVG, PDF export |
| **Customisation** | Colors, dot style, embedded logo, error correction level |
| **Smart Analysis** | URL safety check (VirusTotal), product lookup (Open Food Facts), Google/SerpAPI search |
| **Dynamic QR** | Editable destination URLs, expiry dates, full scan analytics |
| **Mini App** | Mobile-first UI with live camera scanner, color picker, logo upload |
| **Monetisation** | Free tier limits, Premium via Telegram Stars or Stripe |
| **Admin** | Usage dashboard, ban/unban users, set premium manually |

---

## 🗂 Project Structure

```
telegram-bot/
├── bot/                    # aiogram bot
│   ├── handlers/           # start, scan, generate, dynamic, history, account, admin
│   ├── keyboards/          # inline & reply keyboard layouts
│   ├── middlewares/        # auth + rate-limit
│   └── main.py             # polling / webhook entry point
├── api/                    # FastAPI backend
│   ├── routes/             # dynamic_qr, generate, admin
│   ├── models/             # Pydantic schemas
│   └── main.py
├── scanner/                # multi-format detector + smart analyser
├── generator/              # qr_generator, barcode_generator, datamatrix_generator
├── dynamic/                # dynamic QR manager + analytics tracker
├── webapp/                 # Telegram Mini App (HTML/CSS/JS)
├── database/               # SQLAlchemy models, async operations, Alembic migrations
├── config/                 # settings.py (env vars), logging
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

---

## 🚀 Quick Start (Local / Development)

### 1. Prerequisites

```bash
# System packages (Ubuntu/Debian)
sudo apt-get install -y libzbar0 libdmtx0b poppler-utils libgl1 libglib2.0-0
```

### 2. Clone & configure

```bash
cp .env.example .env
# Edit .env — at minimum set BOT_TOKEN and DATABASE_URL
```

### 3. Install Python dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 4. Start the database

```bash
docker run -d --name pg \
  -e POSTGRES_DB=telegram_bot \
  -e POSTGRES_PASSWORD=postgres \
  -p 5432:5432 postgres:16-alpine
```

### 5. Run the bot (polling mode)

```bash
python -m bot.main
```

### 6. Run the FastAPI server (optional — needed for dynamic QR + Mini App)

```bash
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

Open **http://localhost:8000/docs** for the Swagger UI.

---

## 🐳 Docker Compose (Recommended)

```bash
cp .env.example .env
# Fill in BOT_TOKEN, API_SECRET_KEY, etc.

docker-compose up --build -d
```

This starts:
- **db** — PostgreSQL 16
- **redis** — Redis 7
- **api** — FastAPI + static Mini App
- **bot** — aiogram bot (polling)

---

## ☁️ Deployment Guide

### Railway (easiest)

1. Push repo to GitHub.
2. Create a new Railway project → *Deploy from GitHub repo*.
3. Add a **PostgreSQL** plugin and a **Redis** plugin.
4. Set all env vars from `.env.example` in the Railway dashboard.
5. For webhook mode, set `WEBHOOK_URL=https://<your-railway-domain>`.
6. Railway auto-detects `Dockerfile` — deploy!

### Render

1. Create a **Web Service** from your GitHub repo.
2. Build command: `pip install -r requirements.txt`
3. Start command: `uvicorn api.main:app --host 0.0.0.0 --port $PORT`
4. Add a separate **Background Worker** for the bot: `python -m bot.main`
5. Add a Render **PostgreSQL** database.

### VPS (Docker)

```bash
# On your VPS
git clone <repo>
cd telegram-bot
cp .env.example .env && nano .env
docker-compose up -d

# Set up Nginx reverse proxy pointing to port 8000
# Configure SSL with certbot
```

### Telegram Mini App setup

1. In BotFather: `/newapp` → select your bot → enter the HTTPS URL of your deployed server + `/app`.
2. Set `WEBAPP_URL=https://your-domain.com/app` in `.env`.
3. The Mini App is served automatically as static files by FastAPI at `/app/`.

---

## 📡 API Documentation

Full Swagger UI available at `http://localhost:8000/docs`.

### Key endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/r/{short_code}` | Dynamic QR redirect |
| `POST` | `/api/generate/qr` | Generate QR code |
| `POST` | `/api/generate/barcode` | Generate barcode |
| `POST` | `/api/generate/datamatrix` | Generate Data Matrix |
| `POST` | `/api/scan` | Scan uploaded image |
| `POST` | `/api/dynamic` | Create dynamic QR |
| `PUT` | `/api/dynamic/{id}` | Update destination URL |
| `GET` | `/api/dynamic/{id}/stats` | Analytics |
| `GET` | `/api/admin/stats` | Admin stats (requires `X-Admin-Key` header) |
| `GET` | `/health` | Health check |

---

## 🗄 Database Migrations

```bash
# Create a new migration after model changes
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Downgrade one step
alembic downgrade -1
```

---

## 💰 Monetisation

### Free tier (default limits)
- 20 scans / day
- 10 code generations / day
- 3 active dynamic QR codes

### Premium (configurable via env vars)
- Unlimited scans & generations
- Unlimited dynamic QR codes
- Advanced scan analytics

### Payment options
- **Telegram Stars** — built-in, no external account needed
- **Stripe** — traditional credit card payments (requires `STRIPE_SECRET_KEY`)

---

## 📈 Scaling

| Concern | Solution |
|---|---|
| High traffic | Add more uvicorn workers (`--workers N`), or use Gunicorn |
| Bot updates | Switch to webhook mode (`WEBHOOK_URL`) |
| FSM storage | Replace `MemoryStorage` with Redis storage |
| DB connections | Increase `pool_size` in `database/engine.py` |
| File storage | Replace `/tmp/` dirs with S3 / Cloudflare R2 |
| Search rate limits | Add caching layer (Redis TTL per query) |
| Observability | Add Sentry (`sentry-sdk`) and Prometheus metrics |

---

## 🔐 Security Notes

- All admin API endpoints require the `X-Admin-Key` header matching `API_SECRET_KEY`.
- URL safety check uses VirusTotal (set `VIRUSTOTAL_API_KEY`).
- Banned users are silently dropped by the auth middleware.
- Never expose `.env` — all secrets are environment variables.

---

## 📝 License

MIT
