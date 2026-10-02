# BrandForge

AI content studio for brands and creators.

## Run locally

Backend (Python 3.11+):

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn main:app --reload --port 8000 --env-file .env
```

Frontend (Node 18+):

```powershell
cd frontend
npm install
Copy-Item .env.example .env.local
npm run dev
```

Open http://localhost:3000 and register an account. Passwords are stored as PBKDF2 hashes. Login uses an HttpOnly server-side session cookie. Campaigns, assets, and publishing demo history are scoped to the signed-in user. Existing anonymous records are not assigned to new accounts.

## Configuration

Set `CORS_ORIGINS` to the exact frontend origin(s), comma-separated. For a production frontend and backend on separate domains, set `SESSION_COOKIE_SECURE=true` and `SESSION_COOKIE_SAMESITE=none`; HTTPS is required. Local development uses `SESSION_COOKIE_SECURE=false` and `SESSION_COOKIE_SAMESITE=lax`.

AI provider keys are optional. Without them BrandForge runs its clearly labeled demo content engine. Provider OAuth variables in `backend/.env.example` are placeholders only; live social account connection and publishing are not implemented yet.

## Deployment

Deploy the Next.js frontend from `frontend` and set `NEXT_PUBLIC_API_URL` to the HTTPS backend URL. Deploy the FastAPI backend with a persistent disk mounted at `DATA_DIR`, set its `CORS_ORIGINS` to the deployed frontend origin, and configure secure cookie settings above. SQLite data and media must remain on persistent storage.
