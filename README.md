# Amendly

Collaborative amendment management platform.

Original text → Proposed amendments → Reactions → Consolidated text → Export

## License

[AGPL-3.0](LICENSE). Hosted version available at [amendly.eu](https://amendly.eu).

## Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI · Python 3.12 |
| Database | PostgreSQL 16 · SQLAlchemy (async) |
| Cache | Redis 7 |
| Frontend | React 18 · Vite 6 · Tailwind CSS 3 |
| Auth | JWT · magic link · Google OAuth |
| Payments | Stripe |
| Email | Resend |
| Bot protection | Cloudflare Turnstile |

## Requirements

- Python 3.12
- Node.js 20+
- PostgreSQL 16
- Redis 7

## Development

### Backend

```bash
cp .env.example .env
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Tests

```bash
cd backend && .venv/bin/pytest -q
cd frontend && npm test
```

## Configuration

Copy `.env.example` to `.env`. All required variables are listed there.

External services required: PostgreSQL, Redis, Resend (email), Stripe (billing),
Google OAuth (SSO), Cloudflare Turnstile (bot protection). Each requires a
configured account and credentials set in `.env`.
